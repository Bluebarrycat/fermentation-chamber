# Fermentation Chamber Controller — Next Feature Roadmap

This document outlines proposed features and improvements for the Raspberry Pi Zero fermentation chamber controller. The roadmap builds on the current state (single `main.py`, LCD + buttons, calibration, logging, and systemd service) and is prioritized by accuracy, usability, maintainability, and flexibility.

---

## P1 — Accuracy & Safety First

1. **Adaptive Offset-Tracking (AIR→SAMPLE learning)**  
   - Continuously adjust AIR band center if SAMPLE drifts from target over long periods.  
   - Helps extend calibration accuracy between full recalibrations.

2. **Sensor Voting & Outlier Rejection**  
   - Ignore faulty AIR probes if deviation >1.5–2.0 °C persists.  
   - Logs flagged sensors and warns on LCD.

3. **Safety Thresholds & Watchdogs**  
   - Add SAMPLE-based hard cutout.  
   - Integrate systemd watchdog for process liveness.

4. **Dynamic Fan Speed Control**  
   - Scale fan duty cycle based on distance from band center (40–100%).

---

## P1 — Usability Wins (LCD, Menus, Calibration)

5. **Quick Cal Early Finish + Stability Gate**  
   - End calibration automatically when SAMPLE is within ±0.2–0.3 °C for 25–30 minutes.  
   - Adds safety to manual early-finish option.

6. **Status & Diagnostics Menu**  
   - Display live sensors, min/max values, motor/fan state, recent events, and Samba status.

7. **Guided Calibration Wizard**  
   - Step-through LCD flow: select product → confirm target → run → summary report.

---

## P2 — Maintainability & Cleaner Design

8. **Externalized Config (YAML/JSON)**  
   - Move constants (fan speed, bands, thresholds) out of code.  
   - Validate config at startup; log and warn on LCD if invalid.

9. **Pluggable Control Strategies**  
   - Abstract control logic to allow easy experimentation with PID vs. Boost/Hold.

10. **Simulation Mode (No GPIO)**  
   - Run on a dev machine using mock sensors and CSV playback.  
   - Keeps logging and state machine intact.

11. **Structured Event Logging**  
   - Add `session_id`.  
   - Log events for mode changes, pauses, Boost/Reverse transitions, calibration saves.

---

## P2 — Flexibility & Integrations

12. **Lightweight Web Dashboard**  
   - Flask-based read-only status page: live temps, charts, CSV downloads.

13. **Metrics Exporters**  
   - Optional push of AIR/SAMPLE/fan/motor states to Prometheus/Influx for Grafana.

---

## P3 — Quality of Life & Robustness

14. **Smarter Pause Menu Actions**  
   - Add “Fan purge 60s”, “Motor jog 10s”, “Restart service” options.

15. **Startup Self-Check**  
   - On boot, verify each DS18B20 responds.  
   - Show ERR/OK per sensor and log failures.

16. **Dynamic Menu Shortcuts**  
   - Remember last used production mode; add “Recent” list.

17. **Auto-Archive Calibration Assets**  
   - Bundle calibration report, CSV segment, and JSON setpoints into a timestamped folder.

---

## Priority Rationale
- **Accuracy:** Items 1–4 harden control and safety.  
- **Usability:** Items 5–7 make calibration and daily operation smoother.  
- **Maintainability:** Items 8–11 improve code clarity and debug workflow.  
- **Flexibility:** Items 12–13 expand visibility and monitoring options.  
- **Quality of Life:** Items 14–17 improve resilience and operator experience.

---

## Suggested First Implementations
- **Outlier rejection (#2)** — protects against sensor failures.  
- **Quick Cal (#5)** — saves time while ensuring stability.  
- **Structured event logging (#11)** — improves analysis without altering control behavior.
