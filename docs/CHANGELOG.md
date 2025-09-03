# Change Log

## 2025-08-10
- Sample sensor added
- Calibration window changed from 60 → 120 minutes
- Pause menu introduced
- Fan speed set to 75%
- Samba log path confirmed

## 2025-08-14
- Calibration auto-finishes at 120 minutes
- Confirm button made edge-triggered
- Calibration results auto-save setpoints

## 2025-08-15
- Calibration window extended to 180 minutes for all modes
- CALIBRATION_GUIDE.md updated accordingly

## 2025-08-16
- Add two-phase Boost→Hold control (AIR-based) in production and calibration
  - Boost enters when AIR is far below band center; exits near center
  - Safety cap during Boost: `BOOST_MAX_AIR_C` (default 31.0 °C)
  - Sample remains read-only for control; used only in calibration math
- Set calibration window default to **200 minutes** across modes

## 2025-08-17
- Add 3-stage warm-up with AIR ceiling 34 °C and fans-only cool-down.
- Calibration can now **end early** when Sample reaches target band (±0.5 °C), controlled by `CAL_EARLY_END_ENABLED` and `CAL_EARLY_END_STABLE_MIN`.

## 2025-09-02
- **Debug Mode** added (enabled by default). Toggle via single line in `main.py`:
  - `DEBUG = True` → verbose logs ON (console + daily file under `logs/debug/debug_YYYY-MM-DD.log`).
  - `DEBUG = False` → quiet (operational CSV logs only).
- Instrumented key events: button presses, stage transitions, motor/fan actions, emergency reverse, early-end triggers, file I/O errors.

## 2025-09-02
- Fix: initialize category loggers inside `_setup_logger()` to avoid `_NoopLogger.getChild` error.
- Docs overhaul: completed **HARDWARE_MAP.md**, expanded **DESIGN_DECISIONS.md** and **CALIBRATION_GUIDE.md**, updated **PROJECT_MAP.md**, refined **README.md**, added **TROUBLESHOOTING.md**, **SYNC_WORKFLOW.md**, **AI_COLLAB.md**, and **TEMPLATES.md**. 
