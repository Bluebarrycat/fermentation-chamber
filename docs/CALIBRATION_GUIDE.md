# CALIBRATION_GUIDE.md


---
### Update: Early Calibration Completion (refined) & Set-and-Forget
- Calibration now **ends early** once the **Sample ≥ target** (no longer at 26.5 °C edge).
- Optional stability time via `CAL_EARLY_END_STABLE_MIN` (minutes); default 0 for immediate.
- When calibration starts, prior `calibration_*.txt` files are **deleted** to keep reports clean.
- When calibration completes, the controller **automatically starts normal mode** with the new setpoints.


> Note: When calibration starts, only reports matching the active product are removed
(e.g., starting **Kombucha** deletes `calibration_kombucha*.txt` only; starting **Sourdough**
deletes `calibration_sourdough*.txt` only). Other product reports are preserved.
