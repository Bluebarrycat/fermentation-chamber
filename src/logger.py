#!/usr/bin/env python3
import os, csv
from datetime import datetime
from config import LOG_DIR

os.makedirs(LOG_DIR, exist_ok=True)

def _log_path():
    return os.path.join(LOG_DIR, datetime.now().strftime("%Y-%m-%d") + ".csv")

def _ensure_header(path):
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Timestamp","Mode","Temp1_C","Temp2_C","Sample_C","Motor","Direction","Fans","Reversing"])

def init_log():
    p = _log_path()
    _ensure_header(p)
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "*** STARTUP ***","","","","","","",""])

def log_shutdown():
    p = _log_path()
    _ensure_header(p)
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "*** SHUTDOWN ***","","","","","","",""])

def log_data(mode, t1, t2, t_sample, motor_on, dir_mode_a, fans_on, reversing):
    p = _log_path()
    _ensure_header(p)
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            mode or "",
            f"{t1:.2f}" if t1 is not None else "ERR",
            f"{t2:.2f}" if t2 is not None else "ERR",
            f"{t_sample:.2f}" if t_sample is not None else "ERR",
            "ON" if motor_on else "OFF",
            "A" if dir_mode_a else "B",
            "ON" if fans_on else "OFF",
            "YES" if reversing else "NO",
        ])
