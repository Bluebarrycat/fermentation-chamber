#!/usr/bin/env python3
import os

BASE_DIR = "/sys/bus/w1/devices/"

def read_temp(sensor_id: str):
    """
    Read a DS18B20 sensor by its ID. Returns temperature in °C (float) or None on failure.
    """
    path = os.path.join(BASE_DIR, sensor_id, "w1_slave")
    try:
        with open(path) as f:
            lines = f.readlines()
        if not lines or lines[0].strip()[-3:] != "YES":
            return None
        t_pos = lines[1].find("t=")
        if t_pos == -1:
            return None
        c = float(lines[1][t_pos + 2:]) / 1000.0
        return round(c, 2)
    except:
        return None
