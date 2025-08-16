# Ferment Project Map (Single‑File Layout)

Raspberry Pi fermentation chamber controller with **one** Python program (`main.py`), LCD UI, physical buttons, CSV logging, and a systemd service. Calibration computes AIR setpoints to achieve a Sample temperature target.

> Samba network path to logs (Windows/macOS): `\\rpizero\ferment-logs`

---

## Repository Layout

```
Ferment/
│
├─ main.py                 # The entire application (menus, control, calibration, logging)
├─ calibration_setpoints.json   # Created/updated by calibration; holds per‑mode Low/High AIR setpoints
├─ logs/                   # Daily CSV logs + calibration reports
│   └─ YYYY-MM-DD.csv
├─ docs/                   # Project docs stored in your ChatGPT project, mirrored here as needed
│   ├─ PROJECT_MAP.md
│   ├─ CALIBRATION_GUIDE.md
│   ├─ AI_COLLAB.md
│   ├─ SYNC_WORKFLOW.md
│   ├─ HARDWARE_MAP.md
│   ├─ TROUBLESHOOTING.md
│   └─ CHANGELOG.md
├─ requirements.txt        # Python dependencies
└─ README.md               # (optional) quick start
```

---

## What `main.py` Includes

- **Configuration constants** (fan speed, loop interval, fan run‑on, calibration window, targets).
  - Change calibration window here:  
    ```python
    CAL_WINDOW_MIN = 200  # minutes
    ```
- **Hardware setup** (GPIO pins, LCD address).
- **Menus**: Sourdough, Kombucha, Water Kefir, Cal <mode>, Shutdown.
- **Logging** to `logs/YYYY-MM-DD.csv` with `*** STARTUP ***` and `*** SHUTDOWN ***` markers.
- **Normal control loop**: **AIR‑only** decisions; Sample is read + logged.
- **Calibration loop**: runs using current AIR band; uses **Sample** to compute AIR/Sample offset and recommend AIR Low/High; persists to `calibration_setpoints.json` and applies in‑memory immediately.
- **Reports**: `logs/calibration_<mode>_<timestamp>.txt` after calibration.

---

## Sensors & Pins (from HARDWARE_MAP)

- **LCD**: 16×2 I²C (`0x27`), SDA=GPIO 2, SCL=GPIO 3
- **Buttons**: Up=17, Down=27, Left=23, Right=22, Confirm=26
- **Motor (Peltier) Driver**: PWM=20, Direction=21
- **Fans**: Fan1 PWM=12, Fan2 PWM=13 (normal at 0.75 duty)
- **DS18B20**: 
  - Sensor1 (AIR): `28-7db6d445e7a7`
  - Sensor2 (AIR): `28-37e5d44570c3`
  - Sample (CAL only): `28-3ce1e3800798`
  - All on GPIO 4 (1‑Wire)

---

## Runtime & Service

- **Systemd unit**: `ferment.service`
  - Example unit is in `docs/SERVICE_SETUP.md` (or your system at `/etc/systemd/system/ferment.service`).
- **Control**:
  - If `tmax > High` → motor OFF; fans continue for `FAN_AFTER_OFF_SEC`.
  - If `tmax ≥ High + 5` → **reverse** until `≤ High − 1`.
  - If `tmax ≤ Low` → Mode A, motor ON; fans ON.

---

## Calibration Details

- **Window**: **200 minutes** for all modes (Sourdough, Kombucha, Water Kefir).
- **Target Sample** (default): 25.0 °C per mode (editable in `CAL_TARGET_C`).
- **Computation**:
  - `offset = mean(AIR) − mean(Sample)` over the window buffer.
  - Desired AIR **center** = `target_sample + offset`.
  - Recommended band = `center ± (RECOMMENDED_BAND_WIDTH / 2)`.
- **Persistence**: Saved to `calibration_setpoints.json` and auto‑applied on next startup via `load_calibration_setpoints()`.

---

## Known Good Defaults (current)

- Fan speed: **0.75**
- Loop interval: **15 s**
- Fans after off: **10 s**
- Calibration window: **200 min**
- Recommended band width: **1.0 °C**
- Logs path (also via Samba): `\\rpizero\ferment-logs`

---

## Workflow & Collaboration

- Code lives in `main.py`. When changing behavior, specify:
  - **Exact constants** to change (e.g., `CAL_WINDOW_MIN`, `FAN_AFTER_OFF_SEC`).
  - **Acceptance criteria** (e.g., expected log evidence).
- After any code change, remember to update **CHANGELOG.md**.

Example change request:
```
Change request:

Files: main.py
Goal: Increase fan run-on to 12 seconds

Edits:
- Set FAN_AFTER_OFF_SEC = 12

Acceptance:
- Logs show fans turning OFF ~12 seconds after high-temp cut
- No change to CSV columns
```
