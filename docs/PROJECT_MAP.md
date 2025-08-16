# PROJECT_MAP.md

## Overview
Raspberry Pi fermentation chamber controller implemented as a **single Python program** (`main.py`) with LCD UI, physical buttons, CSV logging, and a systemd service. Calibration computes AIR setpoints to achieve a **Sample** target (Sample is logged-only for control; used for calibration math).

- Logs available via Samba: `\\rpizero\ferment-logs`

---

## Repository Layout (Single-File)
```
Ferment/
│
├─ main.py                      # Entire application (menus, control, calibration, logging)
├─ calibration_setpoints.json   # Created/updated by calibration; per‑mode Low/High AIR setpoints
├─ logs/                        # Daily CSV logs + calibration reports
│   └─ YYYY-MM-DD.csv
├─ requirements.txt             # Python dependencies
└─ docs/                        # (optional mirror) project documents, if you keep them in-repo
    ├─ CALIBRATION_GUIDE.md
    ├─ HARDWARE_MAP.md
    ├─ TROUBLESHOOTING.md
    ├─ SERVICE_SETUP.md
    ├─ CHANGELOG.md
    ├─ PROJECT_MAP.md
    ├─ ENVIRONMENT_SETUP.md
    ├─ SYNC_WORKFLOW.md
    ├─ AI_COLLAB.md
    └─ TEMPLATES.md
```

---

## Sensors & Pins (see HARDWARE_MAP.md for full details)
- **LCD**: 16×2 I²C (`0x27`), SDA=GPIO 2, SCL=GPIO 3
- **Buttons**: Up=17, Down=27, Left=23, Right=22, Confirm=26
- **Motor (Peltier) Driver**: PWM=20, Direction=21
- **Fans**: Fan1 PWM=12, Fan2 PWM=13 (nominal 0.75 duty)
- **DS18B20 sensors (GPIO 4, 1‑Wire)**:
  - AIR #1: `28-7db6d445e7a7`
  - AIR #2: `28-37e5d44570c3`
  - SAMPLE (calibration only): `28-3ce1e3800798`

---

## Control Logic (Summary)
- **Production (normal)**: AIR-only control.
  - If `tmax > High` → motor OFF; fans continue for `FAN_AFTER_OFF_SEC`.
  - If `tmax ≥ High + 5` → emergency reverse until `≤ High − 1`.
  - If `tmax ≤ Low` → Mode A, motor ON; fans ON.
- **Calibration**: runs chamber on current Low/High (AIR-based). Uses **Sample** only to compute AIR↔Sample offset for recommended setpoints.

### Two-Phase Heating (Boost → Hold)
- **Boost phase** (AIR-based): engages when AIR ≤ (band_center − `BOOST_DELTA_C`, default 3.0 °C). Pushes hard in Mode A while capping AIR at `BOOST_MAX_AIR_C` (default **31.0 °C**). Exits when AIR ≥ (band_center − `BOOST_EXIT_GAP_C`, default 1.5 °C).
- **Hold phase**: returns to the standard AIR band logic using current Low/High.

---

## Calibration Details
- **Window**: **200 minutes** for all modes (Sourdough, Kombucha, Water Kefir).
- **Target Sample** (default per mode): 25.0 °C.
- **Computation**:
  - `offset = mean(AIR) − mean(Sample)` over the window buffer.
  - Desired AIR center = `target_sample + offset`.
  - Recommended band = `center ± (RECOMMENDED_BAND_WIDTH / 2)`.

---

## Known Good Defaults
- Fan speed: **0.75**
- Loop interval: **15 s**
- Fans after off: **10 s**
- Calibration window: **200 min**
- Recommended band width: **1.0 °C**
- Logs path: `\\rpizero\ferment-logs`

---

## Workflow
1. Code changes in `main.py` → test on Pi.
2. After any code change, update **CHANGELOG.md**.
3. Keep docs in ChatGPT project in sync with any mirrored `/docs` folder in the repo.
