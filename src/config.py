#!/usr/bin/env python3
"""
Global configuration for the Fermentation Chamber controller.
Edit values here (or create a config_local.py to override per-machine).
"""

# Paths
LOG_DIR = "/home/rpizero/Ferment/logs"

# Timing & behavior
FAN_SPEED = 0.75
LOOP_INTERVAL_SEC = 15
FAN_AFTER_OFF_SEC = 10
CAL_WINDOW_MIN = 120
RECOMMENDED_BAND_WIDTH = 1.0  # °C total band for recommended Low/High

# Targets for calibration (sample temp)
CAL_TARGET_C = {
    "Sourdough": 25.0,
    "Kombucha": 25.0,
    "Water Kefir": 25.0,
}

# GPIO pins (BCM numbering)
PINS = {
    "BUTTON_UP": 17,
    "BUTTON_DOWN": 27,
    "BUTTON_LEFT": 23,
    "BUTTON_RIGHT": 22,
    "BUTTON_CONFIRM": 26,
    "MOTOR_PWM": 20,
    "MOTOR_DIR": 21,
    "FAN1": 12,
    "FAN2": 13,
}

# LCD (I2C) settings
LCD = {
    "i2c_expander": "PCF8574",
    "address": 0x27,
    "port": 1,
    "cols": 16,
    "rows": 2,
}

# DS18B20 sensors
SENSORS = {
    "Sensor1": "28-7db6d445e7a7",   # air
    "Sensor2": "28-37e5d44570c3",   # air
    "Sample":  "28-3ce1e3800798",   # jar/liquid — logged always, used only in calibration math
}

# Menus & ranges (AIR control)
MENU = [
    "Sourdough", "Kombucha", "Water Kefir",
    "Cal Sourdough", "Cal Kombucha", "Cal Water Kefir",
    "Shutdown",
]

RANGES = {
    "Sourdough": (24.0, 28.0),
    "Kombucha":  (24.0, 26.0),
    "Water Kefir": (20.0, 25.0),
}
