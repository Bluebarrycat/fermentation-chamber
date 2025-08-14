# Environment Setup

## Raspberry Pi Zero Configuration
- **Enable I²C**: `sudo raspi-config` → Interfacing Options → I2C → Enable
- **Enable 1-Wire**: `sudo raspi-config` → Interfacing Options → 1-Wire → Enable

## Required Packages
Install Python dependencies:
```bash
sudo apt update
sudo apt install python3-pip python3-smbus i2c-tools python3-venv lgpio
pip3 install RPLCD gpiozero smbus2 lgpio
```

## 1-Wire Modules
Ensure modules are loaded at boot by adding to `/boot/config.txt`:
```
dtoverlay=w1-gpio
dtoverlay=w1-therm
```

## Samba Share Setup
Edit `/etc/samba/smb.conf` and add:
```
[ferment-logs]
   path = /home/rpizero/Ferment/logs
   writeable = yes
   browseable = yes
   create mask = 0775
   directory mask = 0775
   valid users = rpizero
```

Restart Samba:
```bash
sudo systemctl restart smbd
```

Access from Windows:
```
\\rpizero\ferment-logs
```

Note: `lgpio` is installed for gpiozero compatibility on newer Raspberry Pi OS versions.
