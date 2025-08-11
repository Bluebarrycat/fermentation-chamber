#!/usr/bin/env python3
import os
from gpiozero import Button, PWMOutputDevice, DigitalOutputDevice
from RPLCD.i2c import CharLCD
from config import PINS, LCD, FAN_SPEED

class HW:
    """
    Hardware interface: LCD, buttons, motor, fans.
    Provides simple helper methods so higher-level code stays clean.
    """
    def __init__(self):
        # Ensure 1-Wire modules are available
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')

        # LCD
        self.lcd = CharLCD(
            i2c_expander=LCD["i2c_expander"],
            address=LCD["address"],
            port=LCD["port"],
            cols=LCD["cols"],
            rows=LCD["rows"],
        )

        # Buttons
        self.btn_up = Button(PINS["BUTTON_UP"])
        self.btn_down = Button(PINS["BUTTON_DOWN"])
        self.btn_left = Button(PINS["BUTTON_LEFT"])
        self.btn_right = Button(PINS["BUTTON_RIGHT"])
        self.btn_ok = Button(PINS["BUTTON_CONFIRM"])

        # Motor & fans
        self.motor_pwm = PWMOutputDevice(PINS["MOTOR_PWM"])
        self.motor_dir = DigitalOutputDevice(PINS["MOTOR_DIR"])
        self.fan1 = PWMOutputDevice(PINS["FAN1"])
        self.fan2 = PWMOutputDevice(PINS["FAN2"])

        # Safe defaults
        self.motor_pwm.value = 0.0
        self.motor_dir.value = False  # Mode A per wiring
        self.fan1.value = 0.0
        self.fan2.value = 0.0

    # LCD helpers (always clear + set cursor)
    def lcd_two_line(self, a: str, b: str = ""):
        self.lcd.clear()
        self.lcd.write_string(a[:16])
        self.lcd.cursor_pos = (1, 0)
        self.lcd.write_string(b[:16])

    # Buttons (polling)
    def buttons_poll(self):
        if self.btn_up.is_pressed: return "UP"
        if self.btn_down.is_pressed: return "DOWN"
        if self.btn_left.is_pressed: return "LEFT"
        if self.btn_right.is_pressed: return "RIGHT"
        if self.btn_ok.is_pressed: return "CONFIRM"
        return None

    # Fans
    def fans_on(self):
        self.fan1.value = FAN_SPEED
        self.fan2.value = FAN_SPEED

    def fans_off(self):
        self.fan1.value = 0.0
        self.fan2.value = 0.0

    # Motor
    def motor_set_dir(self, mode_a: bool):
        """
        Mode A corresponds to motor_dir.value == False per wiring.
        'mode_a=True' sets value False; 'mode_a=False' sets True.
        """
        self.motor_dir.value = (False if mode_a else True)

    def motor_on_mode_a(self):
        self.motor_set_dir(True)
        self.motor_pwm.value = 1.0

    def motor_reverse_on(self):
        # flip polarity from current state
        self.motor_dir.value = (not self.motor_dir.value)
        self.motor_pwm.value = 1.0

    def motor_off(self):
        self.motor_pwm.value = 0.0

    def safe_stop(self):
        self.motor_off()
        self.fans_off()
