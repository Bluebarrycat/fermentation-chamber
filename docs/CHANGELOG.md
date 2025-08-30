# Change Log


## 2025-08-30
- Calibration report cleanup now matches files **case-insensitively** to avoid missed deletions.

- Calibration report cleanup is now **scoped per product** (e.g., only `calibration_sourdough*.txt`).

- Early calibration end refined to **Sample ≥ target** (not bottom of band).
- Deletes prior `calibration_*.txt` files at calibration start.
- Auto-starts **normal mode** after calibration completes (set-and-forget).

- LCD now shows **A:xx.x S:yy.y** during calibration (AIR vs Sample), with stage tag on the first line.
