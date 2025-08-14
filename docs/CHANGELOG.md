# Change Log


## 2025-08-14
- Calibration results are now persisted to `calibration_setpoints.json` in /home/rpizero/Ferment
- Saved setpoints are automatically loaded on startup and override defaults
- After calibration, recommended Low/High air setpoints are saved, applied immediately, and used for all future runs until overwritten
- Calibration mode now auto-finishes after 120 minutes if Confirm not pressed
- Confirm button in calibration is now edge-triggered for reliable stop detection
- Calibration now immediately computes and saves recommended Low/High air setpoints after finish

## 2025-08-10
- Added Sample sensor integration for calibration
- Increased calibration window from 60 min to 120 min
- Added pause menu (Left button during run)
- Fans set to 75% speed
- Samba logs path confirmed: `\\rpizero\ferment-logs`