# HARDWARE_MAP

This is the authoritative wiring and device reference for the Fermentation Chamber (Pi Zero).

## LCD
- Type: 16×2 I²C character LCD (PCF8574 expander)
- Address: `0x27` (verify with `i2cdetect -y 1`)
- I²C pins: SDA=GPIO2, SCL=GPIO3 (Pi header pins 3 and 5)

## Buttons (wired to GND; pull-ups enabled in software)
- Up: GPIO17
- Down: GPIO27
- Left: GPIO23
- Right: GPIO22
- Confirm: GPIO26

## Motor / Peltier Driver
- PWM: GPIO20
- Direction: GPIO21
- Default direction in code: **A = False**, **B = True**
- Safety: Emergency reverse logic is enabled in software for over-temperature conditions.

## Fans
- Fan 1 PWM: GPIO12
- Fan 2 PWM: GPIO13
- Default duty cycle: 0.75 (0.0–1.0 scale)

## DS18B20 Temperature Sensors (1-Wire)
- Bus path: `/sys/bus/w1/devices/`
- AIR Sensor 1: `28-7db6d445e7a7`
- AIR Sensor 2: `28-37e5d44570c3`
- SAMPLE Sensor: `28-3ce1e3800798`
- Note: AIR sensors are used for control; SAMPLE is used for calibration math.

## Power Notes
- Ensure stable 5 V supply with adequate current for Peltier + fans.
- Observe polarity and driver limits per your H-bridge/module.

## Quick Checks
- LCD: `i2cdetect -y 1` should show `0x27`.
- 1-Wire: `ls /sys/bus/w1/devices/` should list the sensor IDs above.
- Buttons: verify they short to GND when pressed (since software uses internal pull-ups).
