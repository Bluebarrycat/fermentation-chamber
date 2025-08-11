#!/usr/bin/env python3
import time
import subprocess
from config import (MENU, RANGES, SENSORS, LOG_DIR, LOOP_INTERVAL_SEC,
                    FAN_AFTER_OFF_SEC, CAL_WINDOW_MIN, CAL_TARGET_C)
from io_hw import HW
import sensors
import ui
import logger
from control import run_mode
from calibration import run_calibration

def main():
    logger.init_log()
    hw = HW()

    def main_menu():
        idx = 0
        ui.show_menu(hw, MENU, idx)
        while True:
            btn = ui.wait_for_button_any(hw)
            if btn == "UP":
                idx = (idx - 1) % len(MENU); ui.show_menu(hw, MENU, idx)
            elif btn == "DOWN":
                idx = (idx + 1) % len(MENU); ui.show_menu(hw, MENU, idx)
            elif btn == "CONFIRM":
                choice = MENU[idx]
                if choice == "Shutdown":
                    logger.log_shutdown()
                    ui.shutting_down(hw)
                    hw.safe_stop()
                    time.sleep(1)
                    subprocess.call(["sudo","shutdown","now"])
                    return ("shutdown",)
                elif choice.startswith("Cal "):
                    base = choice.replace("Cal ", "")
                    low, high = RANGES[base]
                    return ("cal", base, low, high)
                else:
                    low, high = RANGES[choice]
                    return ("mode", choice, low, high)

    while True:
        sel = main_menu()
        if sel[0] == "shutdown":
            return
        if sel[0] == "mode":
            _, name, low, high = sel
            res = run_mode(hw, name, low, high, LOOP_INTERVAL_SEC, FAN_AFTER_OFF_SEC)
            if res == "shutdown":
                logger.log_shutdown()
                ui.shutting_down(hw)
                hw.safe_stop()
                return
        elif sel[0] == "cal":
            _, name, low, high = sel
            res = run_calibration(hw, name, low, high,
                                  LOOP_INTERVAL_SEC, CAL_WINDOW_MIN,
                                  CAL_TARGET_C.get(name, 25.0))
            if res == "shutdown":
                logger.log_shutdown()
                ui.shutting_down(hw)
                hw.safe_stop()
                return

if __name__ == "__main__":
    main()
