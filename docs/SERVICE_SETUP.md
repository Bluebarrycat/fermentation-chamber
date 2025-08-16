# ferment.service Setup

## Example Unit File
`/etc/systemd/system/ferment.service`:
```ini
[Unit]
Description=Ferment Controller
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/rpizero/Ferment/main.py
WorkingDirectory=/home/rpizero/Ferment
StandardOutput=inherit
StandardError=inherit
Restart=always
User=rpizero

[Install]
WantedBy=multi-user.target
```

---

## Commands

### Enable and Start at Boot
Enable the service so it runs every time the Pi boots:
```bash
sudo systemctl enable ferment.service
```

Start it immediately without rebooting:
```bash
sudo systemctl start ferment.service
```

### Stop and Disable
Stop the running service:
```bash
sudo systemctl stop ferment.service
```

Disable it from starting on boot:
```bash
sudo systemctl disable ferment.service
```

### Restart (after code or config changes)
```bash
sudo systemctl restart ferment.service
```

### Check Service Status
```bash
systemctl status ferment.service
```

### View Logs in Real-Time
```bash
journalctl -u ferment.service -f
```
