# SYNC_WORKFLOW

## Typical flow (develop on Windows, run on Pi)
1. Edit files in your Windows workspace (VS Code).
2. Commit and push to GitHub (HTTPS on Windows).
3. On the Pi, pull changes (SSH on Pi).
4. Restart the service or run manually to test.

## Commands
- Windows push:
  ```
  git add .
  git commit -m "Update docs and code"
  git push origin dev
  ```
- Pi pull and restart:
  ```
  cd ~/Ferment
  git pull origin dev
  sudo systemctl restart ferment.service
  ```

## Branching
- Use `dev` for active work, `main` for stable. Merge as needed.
