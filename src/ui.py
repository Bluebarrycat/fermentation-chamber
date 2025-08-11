#!/usr/bin/env python3
import time

def show_two_line(hw, a, b=""):
    hw.lcd_two_line(a, b)

def show_menu(hw, options, index):
    cur = f"> {options[index][:14]}"
    nxt = options[(index+1) % len(options)]
    show_two_line(hw, cur, f"  {nxt[:14]}")

def wait_for_button_any(hw):
    while True:
        btn = hw.buttons_poll()
        if btn:
            time.sleep(0.2)  # debounce
            return btn
        time.sleep(0.05)

def select_from_menu(hw, options, initial_index=0, cancel_with_left=False):
    idx = initial_index
    show_menu(hw, options, idx)
    while True:
        btn = wait_for_button_any(hw)
        if btn == "UP":
            idx = (idx - 1) % len(options); show_menu(hw, options, idx)
        elif btn == "DOWN":
            idx = (idx + 1) % len(options); show_menu(hw, options, idx)
        elif btn == "CONFIRM":
            return idx
        elif cancel_with_left and btn == "LEFT":
            return None

def status_display(hw, mode, tmax, high):
    show_two_line(hw, mode[:16], f"{tmax:.1f}C/{high:.0f}C")

def pause_menu(hw):
    options = ["Resume", "Change Mode", "Shutdown"]
    sel = select_from_menu(hw, options, initial_index=0, cancel_with_left=True)
    if sel is None or sel == 0: return "resume"
    if sel == 1: return "change"
    return "shutdown"

def shutting_down(hw):
    show_two_line(hw, "Shutting down", "")
