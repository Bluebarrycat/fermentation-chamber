# CALIBRATION_GUIDE

## What calibration does
Calibration computes the AIR control band that will produce a desired SAMPLE temperature for each mode (Sourdough, Kombucha, Water Kefir). It runs the chamber, records AIR and SAMPLE, and saves recommended AIR setpoints based on the observed offset.

- Default window: **200 minutes**.
- **Early finish**: ends as soon as SAMPLE is within target band (±0.5 °C). You can require stability time in minutes with `CAL_EARLY_END_STABLE_MIN` in `main.py` (0 means immediate).

## Targets (SAMPLE temperature)
- **Sourdough**: 27.0 °C
- **Kombucha**: 25.0 °C
- **Water Kefir**: 25.0 °C

## How to run calibration
1. From the main menu on the LCD, choose one of:
   - `Cal Sourdough`, `Cal Kombucha`, or `Cal Water Kefir`.
2. Stages:
   - **Startup**: heats aggressively until SAMPLE reaches its target; AIR is capped by a ceiling to reduce overshoot.
   - **Cooldown**: fans only until AIR is back to a safe threshold.
   - **Hold**: normal AIR band control.
3. You may press **Confirm** at any time to end early. Otherwise, calibration ends automatically when the window expires or early-finish conditions are met.

## What gets saved
- **File**: `calibration_setpoints.json` (persisted in `/home/rpizero/Ferment/`).
- **Values**: Low/High AIR setpoints for the chosen mode.
- **Application**: The saved setpoints are automatically loaded on startup and applied to the mode ranges.

## Reports and logs
- A text report is written to `/home/rpizero/Ferment/logs/calibration_<mode>_<timestamp>.txt` with:
  - Target SAMPLE temperature
  - Window length
  - Average AIR and SAMPLE
  - Computed offset (AIR − SAMPLE)
  - Recommended AIR setpoints (Low/High)
- Operational logs are appended to the daily **comma-separated values** file in `/home/rpizero/Ferment/logs/YYYY-MM-DD.csv`.
- Debug logs (if enabled) are written to `/home/rpizero/Ferment/logs/debug/`.

## Tips
- Place SAMPLE probe in the mass you care about (dough or jar). AIR probes should be near, but not touching, heat sources.
- If SAMPLE comes up very slowly, check fan direction and make sure the motor polarity is correct.
- You can rerun calibration any time. The newest setpoints will replace older ones.
