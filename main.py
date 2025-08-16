#!/usr/bin/env python3
import time
import os
import json
import subprocess
import csv
from datetime import datetime
from threading import Timer
from collections import deque
from statistics import mean
from gpiozero import Button, PWMOutputDevice, DigitalOutputDevice
from RPLCD.i2c import CharLCD

# =========================
# Configuration
# =========================
FAN_SPEED = 0.75
LOOP_INTERVAL_SEC = 15          # main control cadence
FAN_AFTER_OFF_SEC = 10          # fans run this long after motor turns off due to High
CAL_WINDOW_MIN = 200            # minutes of data used for final calibration window
CAL_TARGET_C = {                # target SAMPLE temperature per mode (adjust if needed)
    'Sourdough': 25.0,
    'Kombucha':  25.0,
    'Water Kefir': 25.0,
}
RECOMMENDED_BAND_WIDTH = 1.0    # °C total band for air setpoints during recommendation

# --- Two-Phase Boost Controls ---
# Phase 1 (Boost) → if AIR is far below band center, push hard to approach quickly.
# Phase 2 (Hold)  → normal band logic once near center.
BOOST_ENABLE = True
BOOST_DELTA_C = 3.0             # Enter Boost if AIR <= (band_center - BOOST_DELTA_C)
BOOST_EXIT_GAP_C = 1.5          # Exit Boost once AIR >= (band_center - BOOST_EXIT_GAP_C)
BOOST_MAX_AIR_C = 31.0          # Safety: do not allow AIR to exceed this while boosting

BASE_DIR_APP = "/home/rpizero/Ferment"
LOG_DIR = os.path.join(BASE_DIR_APP, "logs")
CAL_FILE = os.path.join(BASE_DIR_APP, "calibration_setpoints.json")
os.makedirs(LOG_DIR, exist_ok=True)

# =========================
# Hardware setup
# =========================
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2)

button_up = Button(17)
button_down = Button(27)
button_left = Button(23)
button_right = Button(22)
button_confirm = Button(26)

motor_pwm = PWMOutputDevice(20)
motor_dir = DigitalOutputDevice(21)
fan1 = PWMOutputDevice(12)
fan2 = PWMOutputDevice(13)

# Ensure off at start
motor_pwm.value = 0
fan1.value = 0
fan2.value = 0
motor_dir.value = False  # Mode A per wiring

# 1-Wire setup
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
BASE_DIR = '/sys/bus/w1/devices/'
SENSORS = {
    'Sensor1': '28-7db6d445e7a7',
    'Sensor2': '28-37e5d44570c3',
    'Sample':  '28-3ce1e3800798'
}

# =========================
# Menus & ranges (defaults)
# =========================
MENU = [
    'Sourdough', 'Kombucha', 'Water Kefir',
    'Cal Sourdough', 'Cal Kombucha', 'Cal Water Kefir',
    'Shutdown'
]
RANGES = {
    'Sourdough': (24.0, 28.0),
    'Kombucha':  (24.0, 26.0),
    'Water Kefir': (20.0, 25.0)
}

# =========================
# Global state
# =========================
motor_on = False
reversing = False
fan_off_timer = None
request_pause_menu = False

# Boost state (separate per loop instance)
def _boost_should_enter(air, low, high):
    if not BOOST_ENABLE or air is None:
        return False
    center = (low + high) / 2.0
    return air <= (center - BOOST_DELTA_C)

def _boost_should_exit(air, low, high):
    if air is None:
        return False
    center = (low + high) / 2.0
    # Exit when we're within a reasonable margin of the center
    return air >= (center - BOOST_EXIT_GAP_C)

# =========================
# Persistence (calibration setpoints)
# =========================
def load_calibration_setpoints():
    """Load saved setpoints from CAL_FILE and merge into RANGES (if present)."""
    if not os.path.exists(CAL_FILE):
        return
    try:
        with open(CAL_FILE, "r") as f:
            data = json.load(f)
        changed = False
        for mode, vals in data.items():
            if isinstance(vals, dict) and "low" in vals and "high" in vals:
                low = float(vals["low"]); high = float(vals["high"])
                if mode in RANGES and (low, high) != RANGES[mode]:
                    RANGES[mode] = (low, high)
                    changed = True
        if changed:
            show_two_line("Loaded saved", "cal setpoints")
            time.sleep(1.2)
    except Exception:
        show_two_line("Cal file error", "Using defaults")
        time.sleep(1.5)

def save_calibration_setpoints(mode_name, low, high):
    """Persist setpoints to CAL_FILE (per-mode)."""
    data = {}
    if os.path.exists(CAL_FILE):
        try:
            with open(CAL_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[mode_name] = {"low": round(low, 2), "high": round(high, 2)}
    tmp = CAL_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CAL_FILE)

# =========================
# Logging
# =========================
def get_log_file():
    date_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"{date_str}.csv")

def _write_header_if_needed(path):
    if not os.path.exists(path):
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                "Timestamp", "Mode", "Temp1_C", "Temp2_C", "Sample_C",
                "Motor", "Direction", "Fans", "Reversing"
            ])

def init_log():
    """
    Ensure today's CSV exists with header, then append a *** STARTUP *** marker row.
    """
    log_file = get_log_file()
    _write_header_if_needed(log_file)
    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         "*** STARTUP ***", "", "", "", "", "", "", ""])

def log_data(mode, t1, t2, t_sample, motor_on_state, dir_value, fans_on_state, reversing_state):
    log_file = get_log_file()
    _write_header_if_needed(log_file)
    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            mode if mode else "",
            f"{t1:.2f}" if t1 is not None else "ERR",
            f"{t2:.2f}" if t2 is not None else "ERR",
            f"{t_sample:.2f}" if t_sample is not None else "ERR",
            "ON" if motor_on_state else "OFF",
            "A" if not dir_value else "B",  # False = A
            "ON" if fans_on_state else "OFF",
            "YES" if reversing_state else "NO"
        ])

def write_calibration_report(mode, target, air_avg, sample_avg, offset, rec_low, rec_high):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(LOG_DIR, f"calibration_{mode}_{ts}.txt")
    with open(path, "w") as f:
        f.write(f"Calibration Report - {mode}\n")
        f.write(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(f"Target SAMPLE temperature: {target:.2f} °C\n")
        f.write(f"Window length: {CAL_WINDOW_MIN} minutes\n\n")
        f.write(f"Average AIR (mean of Sensor1 & Sensor2): {air_avg:.2f} °C\n")
        f.write(f"Average SAMPLE: {sample_avg:.2f} °C\n")
        f.write(f"Computed offset (AIR - SAMPLE): {offset:.2f} °C\n\n")
        f.write(f"Recommended AIR setpoints:\n")
        f.write(f"  Low:  {rec_low:.2f} °C\n")
        f.write(f"  High: {rec_high:.2f} °C\n")
        f.write("\nPersisted to: calibration_setpoints.json\n")
    return path

# =========================
# Helpers
# =========================
def read_temp(sensor_id):
    path = os.path.join(BASE_DIR, sensor_id, 'w1_slave')
    try:
        with open(path) as f:
            lines = f.readlines()
        if not lines or lines[0].strip()[-3:] != 'YES':
            return None
        t_pos = lines[1].find('t=')
        if t_pos == -1:
            return None
        c = float(lines[1][t_pos + 2:]) / 1000.0
        return round(c, 2)
    except:
        return None

def fans_on():
    fan1.value = FAN_SPEED
    fan2.value = FAN_SPEED

def fans_off():
    fan1.value = 0
    fan2.value = 0

def cancel_fan_timer():
    global fan_off_timer
    if fan_off_timer:
        fan_off_timer.cancel()
        fan_off_timer = None

def schedule_fan_off(delay=FAN_AFTER_OFF_SEC):
    global fan_off_timer
    cancel_fan_timer()
    fan_off_timer = Timer(delay, fans_off)
    fan_off_timer.start()

# LCD helpers (always clear before writing, no '\n')
def show_two_line(a, b):
    lcd.clear()
    lcd.write_string(a[:16])
    lcd.cursor_pos = (1, 0)
    lcd.write_string(b[:16])

def show_menu(options, index):
    current = f"> {options[index][:14]}"
    nxt = options[(index + 1) % len(options)]
    next_line = f"  {nxt[:14]}"
    show_two_line(current, next_line)

def status_display(mode, tval, high, prefix=""):
    # line2 shows current and high; prefix shows "Boost" when active
    tag = "Boost " if prefix == "boost" else ""
    line1 = (tag + mode)[:16]
    line2 = f"{tval:.1f}C/{high:.0f}C"
    show_two_line(line1, line2)

# Input polling
def wait_for_button_any():
    while True:
        if button_up.is_pressed:
            time.sleep(0.2); return "UP"
        if button_down.is_pressed:
            time.sleep(0.2); return "DOWN"
        if button_left.is_pressed:
            time.sleep(0.2); return "LEFT"
        if button_right.is_pressed:
            time.sleep(0.2); return "RIGHT"
        if button_confirm.is_pressed:
            time.sleep(0.2); return "CONFIRM"
        time.sleep(0.05)

def select_from_menu(options, initial_index=0, cancel_with_left=False):
    idx = initial_index
    show_menu(options, idx)
    while True:
        btn = wait_for_button_any()
        if btn == "UP":
            idx = (idx - 1) % len(options); show_menu(options, idx)
        elif btn == "DOWN":
            idx = (idx + 1) % len(options); show_menu(options, idx)
        elif btn == "CONFIRM":
            return idx
        elif cancel_with_left and btn == "LEFT":
            return None

def on_left_pressed():
    global request_pause_menu
    request_pause_menu = True

button_left.when_pressed = on_left_pressed

# =========================
# Control & Menus
# =========================
def safe_stop():
    global motor_on
    motor_pwm.value = 0.0
    motor_on = False
    cancel_fan_timer()
    fans_off()

def shutdown_now():
    # write shutdown marker then poweroff
    log_file = get_log_file()
    _write_header_if_needed(log_file)
    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         "*** SHUTDOWN ***", "", "", "", "", "", "", ""])
    safe_stop()
    show_two_line("Shutting down", "")
    time.sleep(1)
    subprocess.call(['sudo', 'shutdown', 'now'])

def pause_menu():
    options = ['Resume', 'Change Mode', 'Shutdown']
    sel = select_from_menu(options, initial_index=0, cancel_with_left=True)
    if sel is None or sel == 0:
        return "resume"
    elif sel == 1:
        return "change"
    else:
        return "shutdown"

def _read_air_and_sample():
    t1 = read_temp(SENSORS['Sensor1'])
    t2 = read_temp(SENSORS['Sensor2'])
    t_sample = read_temp(SENSORS['Sample'])  # read + log only (never used for control)
    air_vals = [t for t in (t1, t2) if t is not None]
    air = None if not air_vals else (mean(air_vals))
    return t1, t2, t_sample, air

def _apply_emergency_reverse(tmax, high):
    global reversing, motor_on
    if not reversing and tmax is not None and tmax >= high + 5:
        reversing = True
        motor_dir.value = not motor_dir.value
        motor_pwm.value = 1.0
        cancel_fan_timer(); fans_on()

    if reversing and tmax is not None and tmax <= high - 1:
        reversing = False
        motor_pwm.value = 0.0
        schedule_fan_off()
        motor_on = False
        motor_dir.value = False  # back to Mode A

def run_mode(mode_name, low, high):
    """
    Normal production control loop for a selected mode.
    NOTE: Sample is always read & logged, but NOT used for any control.
    Two-phase behavior:
      - Boost: if AIR << center, push hard until near center (capped by BOOST_MAX_AIR_C).
      - Hold:  original band logic.
    """
    global motor_on, reversing, request_pause_menu

    motor_dir.value = False  # Mode A
    motor_on = False
    reversing = False
    cancel_fan_timer(); fans_off()
    status_display(mode_name, 0.0, high)

    boosting = False
    center = (low + high) / 2.0

    while True:
        t1, t2, t_sample, air = _read_air_and_sample()
        tmax = None
        if t1 is not None or t2 is not None:
            tmax = max([v for v in (t1, t2) if v is not None])

        # Display & log
        status_display(mode_name, (tmax if tmax is not None else 0.0), high, prefix=("boost" if boosting else ""))
        log_data(mode_name, t1, t2, t_sample, motor_on, motor_dir.value, fan1.value > 0 or fan2.value > 0, reversing)

        # Emergency Reverse guard (AIR only)
        if tmax is not None:
            _apply_emergency_reverse(tmax, high)

        if reversing:
            # let reverse branch above handle transitions; skip normal/boost control
            pass
        else:
            # --- Decide Boost vs Hold ---
            if BOOST_ENABLE:
                if not boosting and air is not None and _boost_should_enter(air, low, high):
                    boosting = True
                elif boosting and air is not None and _boost_should_exit(air, low, high):
                    boosting = False

            if boosting:
                # BOOST PHASE: push hard but don't exceed BOOST_MAX_AIR_C
                if air is not None and air >= min(BOOST_MAX_AIR_C, center + 1.0):
                    # close enough to center or hitting safety cap → stop pushing
                    motor_pwm.value = 0.0
                    motor_on = False
                    cancel_fan_timer(); fans_on()
                    schedule_fan_off()
                else:
                    motor_dir.value = False
                    motor_pwm.value = 1.0
                    motor_on = True
                    cancel_fan_timer(); fans_on()
            else:
                # HOLD PHASE: original band logic (AIR only)
                if tmax is not None:
                    if motor_on and tmax > high:
                        motor_pwm.value = 0.0
                        motor_on = False
                        cancel_fan_timer(); fans_on()
                        schedule_fan_off()
                    if not motor_on and tmax <= low:
                        motor_dir.value = False
                        motor_pwm.value = 1.0
                        motor_on = True
                        cancel_fan_timer(); fans_on()

        # 15-second interval with responsive pause
        for _ in range(int(LOOP_INTERVAL_SEC / 0.1)):
            if request_pause_menu:
                choice = pause_menu()
                if choice == "resume":
                    request_pause_menu = False; break
                elif choice == "change":
                    request_pause_menu = False; safe_stop(); return "change"
                elif choice == "shutdown":
                    shutdown_now(); return "shutdown"
            time.sleep(0.1)

def run_calibration(mode_name, low, high):
    """
    Calibration mode:
    - Runs chamber with current air setpoints (low/high).
    - Ends when Confirm is pressed OR when CAL_WINDOW_MIN elapses.
    - Uses last CAL_WINDOW_MIN of data (or all available if shorter).
    - Sample is USED here to compute offset; still ignored for control itself.
    - On finish: computes recommendation, SAVES to disk, APPLIES in memory, returns to menu.

    Two-phase behavior mirrors run_mode: Boost based on AIR vs band center,
    then Hold with original band logic. Emergency reverse remains in place.
    """
    global motor_on, reversing, request_pause_menu

    # --- edge-triggered Confirm handler for reliable finish ---
    finish_requested = False
    def _on_confirm():
        nonlocal finish_requested
        finish_requested = True

    old_confirm_handler = button_confirm.when_pressed
    button_confirm.when_pressed = _on_confirm

    try:
        target = CAL_TARGET_C.get(mode_name, 25.0)
        motor_dir.value = False
        motor_on = False; reversing = False
        cancel_fan_timer(); fans_off()

        maxlen = max(1, int((CAL_WINDOW_MIN * 60) / LOOP_INTERVAL_SEC))
        air_buf = deque(maxlen=maxlen)     # mean of Sensor1 & Sensor2
        sample_buf = deque(maxlen=maxlen)

        start_ts = time.time()
        boosting = False
        center = (low + high) / 2.0

        # UI
        show_two_line(f"Cal {mode_name}"[:16], "Confirm=Finish")

        while True:
            t1, t2, t_sample, air = _read_air_and_sample()
            air_vals = [t for t in (t1, t2) if t is not None]
            tmax = None if not air_vals else max(air_vals)

            # Short status
            if air is not None and t_sample is not None:
                # show when boosting for operator awareness
                tag = "B" if boosting else ""
                show_two_line(f"Cal {mode_name}{tag}"[:16], f"A:{air:.1f} S:{t_sample:.1f}")
            else:
                show_two_line(f"Cal {mode_name}"[:16], "Waiting temps")

            # Log as normal
            log_data(f"CAL-{mode_name}", t1, t2, t_sample, motor_on, motor_dir.value, fan1.value > 0 or fan2.value > 0, reversing)

            # Emergency Reverse (AIR only)
            if tmax is not None:
                _apply_emergency_reverse(tmax, high)

            if not reversing:
                # --- Decide Boost vs Hold (AIR only) ---
                if BOOST_ENABLE and air is not None:
                    if not boosting and _boost_should_enter(air, low, high):
                        boosting = True
                    elif boosting and _boost_should_exit(air, low, high):
                        boosting = False

                if boosting:
                    # BOOST PHASE with safety cap
                    if air is not None and air >= min(BOOST_MAX_AIR_C, center + 1.0):
                        motor_pwm.value = 0.0
                        motor_on = False
                        cancel_fan_timer(); fans_on()
                        schedule_fan_off()
                    else:
                        motor_dir.value = False
                        motor_pwm.value = 1.0
                        motor_on = True
                        cancel_fan_timer(); fans_on()
                else:
                    # HOLD PHASE: original band logic
                    if air is not None:
                        if motor_on and air > high:
                            motor_pwm.value = 0.0
                            motor_on = False
                            cancel_fan_timer(); fans_on()
                            schedule_fan_off()
                        if not motor_on and air <= low:
                            motor_dir.value = False
                            motor_pwm.value = 1.0
                            motor_on = True
                            cancel_fan_timer(); fans_on()

            # Add to buffers (only if we have readings)
            if air is not None: air_buf.append(air)
            if t_sample is not None: sample_buf.append(t_sample)

            # --- Finish conditions ---
            elapsed = time.time() - start_ts
            if finish_requested or elapsed >= CAL_WINDOW_MIN * 60:
                break

            # Allow Pause menu with Left; also check finish flag frequently
            for _ in range(int(LOOP_INTERVAL_SEC / 0.1)):
                if finish_requested:
                    break
                if request_pause_menu:
                    choice = pause_menu()
                    if choice == "resume":
                        request_pause_menu = False; break
                    elif choice == "change":
                        request_pause_menu = False; safe_stop(); return "change"
                    elif choice == "shutdown":
                        shutdown_now(); return "shutdown"
                time.sleep(0.1)
            if finish_requested:
                break

        # Compute recommendation (Sample USED here)
        if len(air_buf) == 0 or len(sample_buf) == 0:
            show_two_line("Cal failed", "No data")
            time.sleep(2)
            return "change"

        air_avg = mean(air_buf)
        sample_avg = mean(sample_buf)
        offset = air_avg - sample_avg           # positive if air hotter than sample
        center_calc = target + offset           # desired air avg to hold target sample
        half = RECOMMENDED_BAND_WIDTH / 2.0
        rec_low, rec_high = center_calc - half, center_calc + half

        # Save & apply
        save_calibration_setpoints(mode_name, rec_low, rec_high)
        RANGES[mode_name] = (rec_low, rec_high)

        # Save report & show on LCD
        write_calibration_report(mode_name, target, air_avg, sample_avg, offset, rec_low, rec_high)
        show_two_line("Cal saved+applied", f"L:{rec_low:.1f} H:{rec_high:.1f}")
        time.sleep(4)
        return "change"

    finally:
        # restore previous handler to avoid side-effects outside calibration
        button_confirm.when_pressed = old_confirm_handler

def main_menu():
    idx = 0
    show_menu(MENU, idx)
    while True:
        btn = wait_for_button_any()
        if btn == "UP":
            idx = (idx - 1) % len(MENU); show_menu(MENU, idx)
        elif btn == "DOWN":
            idx = (idx + 1) % len(MENU); show_menu(MENU, idx)
        elif btn == "CONFIRM":
            choice = MENU[idx]
            if choice == 'Shutdown':
                shutdown_now(); return ('shutdown',)
            elif choice.startswith('Cal '):
                base = choice.replace('Cal ', '')
                # Always use current (possibly loaded) setpoints:
                low, high = RANGES[base]
                return ('cal', base, low, high)
            else:
                low, high = RANGES[choice]
                return ('mode', choice, low, high)

def main():
    load_calibration_setpoints()  # merge any saved setpoints before anything else
    init_log()
    while True:
        sel = main_menu()
        if sel[0] == 'shutdown':
            return
        if sel[0] == 'mode':
            _, mode_name, low, high = sel
            result = run_mode(mode_name, low, high)
            if result == "shutdown":
                return
        elif sel[0] == 'cal':
            _, mode_name, low, high = sel
            result = run_calibration(mode_name, low, high)
            if result == "shutdown":
                return
        # if "change", loop back to main menu

if __name__ == '__main__':
    main()
