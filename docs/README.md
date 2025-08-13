# Fermentation Chamber Controller (Monolithic `main.py`)

This repo starts clean with your **original single-file implementation** (`main.py`) and a minimal set of project files
so you can push to GitHub and run on a Raspberry Pi Zero without modularization.

## What’s Included
- `main.py` — your full controller
- `requirements.txt` — Python dependencies to `pip install`
- `.gitignore` — ignores logs, caches, virtualenvs
- `ferment.service` — systemd unit for auto-start (optional)

## Hardware (per `main.py`)
- LCD: 16x2 I²C, address `0x27`, expander `PCF8574`
- Buttons: Up=GPIO17, Down=GPIO27, Left=GPIO23, Right=GPIO22, Confirm=GPIO26
  - **Wiring**: Button default is `pull_up=True` in gpiozero. For standard wiring, connect buttons to **GND**.
- Motor: PWM=GPIO20, DIR=GPIO21 (Mode A=False, Mode B=True)
- Fans: PWM=GPIO12 and GPIO13 (default 75% duty in code)
- DS18B20 sensors on 1-Wire: 
  - Sensor1: 28-7db6d445e7a7
  - Sensor2: 28-37e5d44570c3
  - Sample : 28-3ce1e3800798

## Raspberry Pi Setup (once)
```bash
sudo apt update
sudo apt install -y python3-pip python3-gpiozero python3-smbus i2c-tools

# Enable I2C and 1-Wire (run menu and enable both):
sudo raspi-config
# Interfacing Options -> I2C -> Enable
# Interfacing Options -> 1-Wire -> Enable
```

Add to `/boot/config.txt` (if not already present):
```
dtoverlay=w1-gpio
dtoverlay=w1-therm
```

## Python Env
```bash
cd /home/rpizero/Ferment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Run Manually
```bash
cd /home/rpizero/Ferment
source venv/bin/activate
python3 main.py
```

## Install as a Service (optional)
```bash
sudo cp ferment.service /etc/systemd/system/ferment.service
sudo systemctl daemon-reload
sudo systemctl enable ferment.service
sudo systemctl start ferment.service
sudo journalctl -u ferment.service -f
```

## Logs
CSV logs are written to `/home/rpizero/Ferment/logs/YYYY-MM-DD.csv`.
Calibration reports save to: `/home/rpizero/Ferment/logs/calibration_<mode>_<timestamp>.txt`.

## GitHub Quick Start
```bash
cd /home/rpizero/Ferment
git init
git remote add origin YOUR_REPO_URL_HERE
git add .
git commit -m "Initial commit (monolithic main.py)"
git branch -M main
git push -u origin main
```

## Common Pitfalls
- **Buttons not responding**: Ensure they’re wired to **GND** (since `gpiozero.Button` defaults to pull-up). If wired to 3.3V, change your code to `Button(pin, pull_up=False)`.
- **DS18B20 not detected**: `ls /sys/bus/w1/devices/`; check sensor IDs match `SENSORS` in `main.py`.
- **LCD not showing**: `i2cdetect -y 1` to confirm address `0x27`.
