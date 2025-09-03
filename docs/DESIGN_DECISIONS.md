# DESIGN_DECISIONS

This document captures key choices and why we made them. It supersedes older notes that mentioned a **120-minute** calibration window. The current default is **200 minutes**.

## Control Strategy
- **AIR sensors for control**, SAMPLE for calibration math only.  
  Rationale: AIR reacts faster and represents environment around the loaf/jar; SAMPLE lags and is used to compute an offset that translates desired sample temperature to an AIR control band.
- **Recommended AIR band width**: ±0.5 °C around computed center (total width 1.0 °C).

## Warm-up & Stages
- **Startup (aggressive heat)** until SAMPLE reaches the per-mode target, while capping AIR via a ceiling to avoid overshoot.
- **Cooldown (fans only)** to bring AIR down to a safe threshold after SAMPLE entry.
- **Hold** (band control) using AIR max (tmax) vs. low/high hysteresis.

## Calibration
- Default window: **200 minutes** with **early-end** when SAMPLE is within target band (±0.5 °C). Optional stability time can be set in code.
- Results: AIR average, SAMPLE average, **offset = AIR − SAMPLE**.  
  AIR setpoints saved to `calibration_setpoints.json` and applied on next run.

## Safety
- **Emergency reverse** thresholds (AIR-based):  
  - Instant: 36.0 °C (immediate reverse)  
  - Sustain: 34.5 °C for 60 seconds (then reverse)  
- **Fan run-on** after motor stop: 10 seconds to purge residual heat.

## Logging
- **Operational CSV logs** (comma-separated values) rotate daily in `/home/rpizero/Ferment/logs/`.
- **Debug logs** (if enabled) with categories (`ferment.mode`, `ferment.sensor`, etc.) write to `/home/rpizero/Ferment/logs/debug/`.

## Rationale Summary
- Faster feedback and safer control with AIR; SAMPLE provides calibration linkage to true contents temperature.
- Three-stage sequence reduces overshoot and stabilizes faster.
- Early-end calibration saves time once SAMPLE is in the correct band.
