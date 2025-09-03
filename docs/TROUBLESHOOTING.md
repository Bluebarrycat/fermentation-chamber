# TROUBLESHOOTING

## Quick checks
- **Power**: Peltier + fans draw current; unstable 5 V will cause erratic behavior.
- **Cables**: Reseat I²C and 1-Wire connections.

## LCD not showing
- Run `i2cdetect -y 1` → expect `0x27`. If missing, check wiring and enable I²C in `raspi-config`.
- Confirm package: `sudo apt install python3-smbus i2c-tools`.

## Buttons unresponsive
- Buttons are configured with internal pull-ups; they must short to **GND** when pressed.
- If wired to 3.3 V, change code to `Button(pin, pull_up=False)`.

## Sensors missing / bad values
- List sensors: `ls /sys/bus/w1/devices/` and compare to IDs in HARDWARE_MAP.
- CRC/NO or parse errors will appear in debug logs under `ferment.sensor`.
- Check 1-Wire is enabled in `/boot/config.txt`:
  ```
  dtoverlay=w1-gpio
  dtoverlay=w1-therm
  ```

## Motor / fans
- Ensure direction pin and PWM wiring match HARDWARE_MAP.
- Fans run-on for 10 seconds after motor stops; see logs `ferment.fan`.

## Service will not start
- Status: `systemctl status ferment.service`
- Logs: `journalctl -u ferment.service -f`
- Restart: `sudo systemctl restart ferment.service`
- Disable for manual testing: `sudo systemctl stop ferment.service && sudo systemctl disable ferment.service`

## Logs location
- CSV logs: `/home/rpizero/Ferment/logs/`
- Debug logs: `/home/rpizero/Ferment/logs/debug/`
- Windows access: `\\rpizero\ferment-logs`
