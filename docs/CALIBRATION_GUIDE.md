# CALIBRATION_GUIDE.md

## Overview
This guide provides step-by-step instructions for running calibration for **Sourdough**, **Kombucha**, and **Water Kefir** in the fermentation control system.

The calibration process measures environmental and product-specific temperature offsets to ensure accurate readings during operation.

---

## Duration
- **Standard Duration**: 200 minutes (3 hours 20 minutes)  
- You may stop early if readings are stable and representative, but avoid stopping before 100 minutes unless necessary.

---

## Step-by-Step Calibration Process

### 1. Preparation
1. Ensure all sensors are connected and operational.
2. Place sensors in their designated positions according to the **HARDWARE_MAP.md**.
3. Make sure the fermentation chamber is closed to maintain stable conditions.

### 2. Starting Calibration
1. Enter calibration mode using the control interface (physical buttons or LCD menu).
2. Confirm the product type:
   - `Sourdough`
   - `Kombucha`
   - `Water Kefir`
3. The system will log temperatures every few seconds for the duration of the calibration window.

### 3. Monitoring Progress
- The LCD will display live sensor readings.
- Data will also be logged to the Samba share:
  ```
  \\rpizero\ferment-logs
  ```
- You can view progress in real time from a networked computer.

### 4. Stopping Calibration Early
- Press the confirm button to end calibration before the 200-minute mark.
- Only stop early if temperatures have stabilized for at least 25 minutes.

### 5. Interpreting Results
1. Review the logged CSV file after calibration ends.
2. Identify the stable temperature plateau for each sensor.
3. Calculate the offset between target and measured values.

### 6. Updating Configuration
1. Open the configuration file (e.g., `config.json` or relevant settings module).
2. Apply sensor offsets based on calibration results.
3. Save the file and restart the `ferment.service`:
   ```bash
   sudo systemctl restart ferment.service
   ```

---

## Tips & Best Practices
- Avoid opening the chamber during calibration.
- Ensure sensors are not in direct contact with cooling/heating elements.
- Perform calibration in a stable ambient environment.

---

## Related Documents
- **HARDWARE_MAP.md** — Sensor IDs and placement
- **TROUBLESHOOTING.md** — If calibration does not start or sensors are unresponsive
- **SERVICE_SETUP.md** — How to restart or stop the `ferment.service`
