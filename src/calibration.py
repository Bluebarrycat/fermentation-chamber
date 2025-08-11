#!/usr/bin/env python3
import time
from collections import deque
from statistics import mean
from threading import Timer
import sensors
from config import SENSORS
from ui import show_two_line, pause_menu
from logger import log_data, 
from config import RECOMMENDED_BAND_WIDTH

def run_calibration(hw, mode_name, low, high, loop_sec, window_min, target_c):
    """
    Runs chamber with air setpoints (low/high).
    Uses last window_min of data to compute AIR-SAMPLE offset and suggest Low/High for air.
    Sample is used ONLY for recommendation, not for control.
    """
    reversing = False
    motor_on = False
    fan_timer = None

    def schedule_fans_off(delay):
        nonlocal fan_timer
        if fan_timer:
            fan_timer.cancel()
            fan_timer = None
        fan_timer = Timer(delay, hw.fans_off)
        fan_timer.start()

    # buffers sized by cadence
    maxlen = max(1, int((window_min * 60) / loop_sec))
    air_buf = deque(maxlen=maxlen)
    sample_buf = deque(maxlen=maxlen)

    hw.motor_off()
    hw.motor_set_dir(True)  # Mode A
    hw.fans_off()
    show_two_line(hw, f"Cal {mode_name}"[:16], "Confirm=Finish")

    while True:
        t1 = sensors.read_temp(SENSORS["Sensor1"])
        t2 = sensors.read_temp(SENSORS["Sensor2"])
        t_sample = sensors.read_temp(SENSORS["Sample"])

        air_vals = [t for t in (t1, t2) if t is not None]
        air = None if not air_vals else mean(air_vals)

        # Brief UI
        if air is not None and t_sample is not None:
            show_two_line(hw, f"Cal {mode_name}"[:16], f"A:{air:.1f} S:{t_sample:.1f}")
        else:
            show_two_line(hw, f"Cal {mode_name}"[:16], "Waiting temps")

        # Log as normal
        dir_mode_a = (hw.motor_dir.value == False)
        fans_on_state = (hw.fan1.value > 0 or hw.fan2.value > 0)
        log_data(f"CAL-{mode_name}", t1, t2, t_sample, motor_on, dir_mode_a, fans_on_state, reversing)

        # Control uses AIR only
        if air is not None:
            if not reversing and air >= high + 5:
                reversing = True
                hw.motor_reverse_on()
                hw.fans_on()
            if reversing and air <= high - 1:
                reversing = False
                hw.motor_off()
                schedule_fans_off(10)
                motor_on = False
                hw.motor_set_dir(True)

            if not reversing:
                if motor_on and air > high:
                    hw.motor_off()
                    motor_on = False
                    hw.fans_on()
                    schedule_fans_off(10)
                if (not motor_on) and air <= low:
                    hw.motor_set_dir(True)
                    hw.motor_on_mode_a()
                    motor_on = True
                    hw.fans_on()

        # add to buffers
        if air is not None: air_buf.append(air)
        if t_sample is not None: sample_buf.append(t_sample)

        # finish on Confirm
        if hw.btn_ok.is_pressed:
            time.sleep(0.2)
            break

        # responsive pause
        for _ in range(max(1, int(loop_sec / 0.1))):
            btn = hw.buttons_poll()
            if btn == "LEFT":
                choice = pause_menu(hw)
                if choice == "resume":
                    break
                if choice == "change":
                    if fan_timer: fan_timer.cancel()
                    hw.safe_stop()
                    return "change"
                if choice == "shutdown":
                    return "shutdown"
            time.sleep(0.1)

    # compute recommendation
    if len(air_buf) == 0 or len(sample_buf) == 0:
        show_two_line(hw, "Cal failed", "No data"); time.sleep(2); return "change"

    air_avg = mean(air_buf)
    sample_avg = mean(sample_buf)
    offset = air_avg - sample_avg
    center = target_c + offset
    half = RECOMMENDED_BAND_WIDTH / 2.0
    rec_low, rec_high = center - half, center + half

    # Save report
    from datetime import datetime
    import os
    from config import LOG_DIR
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(LOG_DIR, f"calibration_{mode_name}_{ts}.txt")
    with open(path, "w") as f:
        f.write(f"Calibration Report - {mode_name}\n")
        f.write(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(f"Target SAMPLE temperature: {target_c:.2f} °C\n")
        f.write(f"Window length: {window_min} minutes\n\n")
        f.write(f"Average AIR (mean of Sensor1 & Sensor2): {air_avg:.2f} °C\n")
        f.write(f"Average SAMPLE: {sample_avg:.2f} °C\n")
        f.write(f"Computed offset (AIR - SAMPLE): {offset:.2f} °C\n\n")
        f.write(f"Recommended AIR setpoints:\n")
        f.write(f"  Low:  {rec_low:.2f} °C\n")
        f.write(f"  High: {rec_high:.2f} °C\n")

    show_two_line(hw, "Cal done", f"L:{rec_low:.1f} H:{rec_high:.1f}")
    time.sleep(4)
    return "change"
