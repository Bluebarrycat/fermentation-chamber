# Fermentation Chamber Controller (Raspberry Pi Zero)

Controls a fermentation chamber using a Raspberry Pi Zero. The controller drives a Peltier module through a motor driver, runs two PWM fans, reads two **AIR** DS18B20 sensors for control, and uses one **Sample** DS18B20 sensor **only for calibration**. It provides an LCD user interface, physical buttons, CSV (comma‑separated values) logging, and a `systemd` service for automatic startup.

## What this repository is for
- **Version control** (Git): track changes, make checkpoints, revert if needed.
- **Backup and collaboration** (GitHub): store the repo online, open issues, review changes.
- **Deployment**: clone on the Raspberry Pi and run or install as a service.

## Hardware Summary
- **LCD 16x2** over I²C (inter‑integrated circuit) at address `0x27`  
  - SDA (data) = GPIO 2, SCL (clock) = GPIO 3
- **Buttons**  
  - Up: GPIO 17, Down: GPIO 27, Left: GPIO 23, Right: GPIO 22, Confirm: GPIO 26
- **Motor driver for Peltier**  
  - PWM (pulse‑width modulation) = GPIO 20, Direction = GPIO 21
- **Fans** (target duty ≈ 75%)  
  - Fan1 PWM = GPIO 12, Fan2 PWM = GPIO 13
- **DS18B20 sensors** on GPIO 4  
  - AIR #1: `28-7db6d445e7a7`  
  - AIR #2: `28-37e5d44570c3`  
  - Sample (Calibration only): `28-3ce1e3800798`

## Repository Layout
```
Ferment/
├─ src/
│  ├─ main.py
│  ├─ config.py
│  ├─ io_hw.py
│  ├─ sensors.py
│  ├─ ui.py
│  ├─ logger.py
│  ├─ control.py
│  └─ calibration.py
├─ logs/                 # runtime logs (gitignored)
├─ ferment.service       # systemd unit example
├─ requirements.txt
└─ README.md
```

> Note: If you prefer `python3 main.py`, we can add a small launcher script. The current layout assumes module style (`python3 -m src.main`).

## Quick Start (Raspberry Pi)
1. **Enable I²C and 1‑Wire** in `raspi-config`.
2. **Install packages and Python dependencies:**
   ```bash
   sudo apt update
   sudo apt install -y python3-pip python3-gpiozero python3-smbus i2c-tools
   pip3 install RPLCD
   # If your code uses additional libs, install them or: pip3 install -r requirements.txt
   ```
3. **Clone and run:**
   ```bash
   git clone https://github.com/<YOUR-USER>/fermentation-chamber.git Ferment
   cd Ferment
   python3 -m src.main
   ```
4. **(Optional) Install as a systemd service:**
   ```bash
   sudo cp ferment.service /etc/systemd/system/ferment.service
   sudo systemctl enable ferment.service
   sudo systemctl start ferment.service
   # Logs:
   journalctl -u ferment.service -f
   ```

## Calibration
- Calibration window: **120 minutes**.  
- AIR sensors control the chamber. The Sample probe is used only to inform calibration adjustments.  
- See `docs/CALIBRATION_GUIDE.md` (or your project docs folder) for steps and interpretation.

## Logging
- CSV logs are written under `logs/` (this folder is ignored by Git).  
- Network path for logs via Samba (Windows file sharing): `\\rpizero\ferment-logs`.

## Contribution Workflow
- `main` branch remains stable.  
- Create a feature branch for any change, commit locally, push, then open a Pull Request (PR).  
- After code changes, update your project `CHANGELOG.md` (kept in your ChatGPT documents; you may mirror it into `/docs`).

## License
Choose a license for your repository (MIT, Apache‑2.0, etc.). You can add `LICENSE` later via GitHub’s “Add file” → “Create new file” with the License template.
