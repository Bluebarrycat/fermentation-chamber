#!/usr/bin/env python3
import time
from threading import Timer
import sensors
from config import SENSORS
from ui import status_display, pause_menu
from logger import log_data

def run_mode(hw, mode_name, low, high, loop_sec, fan_after_off_sec):
    """
    Production control loop. Uses AIR (Sensor1/2) only for control.
    Sample is read & logged but not used for decisions.
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

    # init
    hw.motor_off()
    hw.motor_set_dir(True)  # Mode A
    hw.fans_off()
    status_display(hw, mode_name, 0.0, high)

    while True:
        # Read temps
        t1 = sensors.read_temp(SENSORS["Sensor1"])
        t2 = sensors.read_temp(SENSORS["Sensor2"])
        t_sample = sensors.read_temp(SENSORS["Sample"])

        air_list = [t for t in (t1, t2) if t is not None]
        if air_list:
            tmax = max(air_list)
            status_display(hw, mode_name, tmax, high)
        else:
            tmax = 0.0
            status_display(hw, mode_name, 0.0, high)

        # Log each cycle
        dir_mode_a = (hw.motor_dir.value == False)  # False wire-level = Mode A
        fans_on_state = (hw.fan1.value > 0 or hw.fan2.value > 0)
        log_data(mode_name, t1, t2, t_sample, motor_on, dir_mode_a, fans_on_state, reversing)

        # Control logic (AIR only)
        if air_list:
            if not reversing and tmax >= high + 5:
                reversing = True
                hw.motor_reverse_on()
                hw.fans_on()

            if reversing and tmax <= high - 1:
                reversing = False
                hw.motor_off()
                schedule_fans_off(fan_after_off_sec)
                motor_on = False
                hw.motor_set_dir(True)  # back to Mode A

            if not reversing:
                if motor_on and tmax > high:
                    hw.motor_off()
                    motor_on = False
                    hw.fans_on()
                    schedule_fans_off(fan_after_off_sec)

                if (not motor_on) and tmax <= low:
                    hw.motor_set_dir(True)
                    hw.motor_on_mode_a()
                    motor_on = True
                    hw.fans_on()

        # Wait with responsive pause
        steps = max(1, int(loop_sec / 0.1))
        for _ in range(steps):
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
