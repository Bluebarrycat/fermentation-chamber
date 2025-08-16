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

## 2025-08-16
- Add two-phase Boost→Hold control (AIR-based) in production and calibration
  - Boost enters when AIR is far below band center; exits near center
  - Safety cap during Boost: `BOOST_MAX_AIR_C` (default 31.0 °C)
  - Sample remains read-only for control; used only in calibration math
- Set calibration window default to **200 minutes** across modes
- Updated sourdough calibration target in `main.py`:
  - `CAL_TARGET_C['Sourdough']` changed from 25.0 °C → 27.0 °C
