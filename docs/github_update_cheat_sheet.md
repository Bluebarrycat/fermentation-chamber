# GitHub Update Cheat Sheet (Windows + Pi Zero)

This guide assumes:
- **Windows (VS Code)** uses HTTPS + Git Credential Manager.
- **Raspberry Pi Zero** uses SSH for GitHub.

---

## Windows (Visual Studio Code) - HTTPS workflow

### Check / Fix Remote URL
```bash
git remote set-url origin https://github.com/Bluebarrycat/fermentation-chamber.git
git config --global credential.helper manager-core
git remote -v
```

### Update Local Repo
```bash
git pull origin dev
git pull origin main
```

### Commit & Push Changes
```bash
git add .
git commit -m "Your message here"
git push origin dev
```

---

## Raspberry Pi Zero - SSH workflow

### Check / Fix Remote URL
```bash
git remote set-url origin git@github.com:Bluebarrycat/fermentation-chamber.git
git remote -v
```

### Update Local Repo
```bash
cd ~/Ferment
git pull origin main
git pull origin dev
```

### Commit & Push Changes (if editing on Pi)
```bash
git add .
git commit -m "Your message here"
git push origin dev
```

---

## Branch Merging

### Merge `main` into `dev` (bring stable changes into dev for further work)
```bash
git checkout dev
git pull origin dev
git merge main
git push origin dev
```

### Merge `dev` into `main` (promote tested changes to stable)
```bash
git checkout main
git pull origin main
git merge dev
git push origin main
```

---

## Notes
- Always **pull before pushing** to avoid conflicts:
  ```bash
  git pull origin dev
  ```
- Use `main` for stable tested code, `dev` for active work.
- If GitHub warns "repository moved", fix with:
  ```bash
  git remote set-url origin <correct-url>
  ```
- On Windows: use HTTPS (with token).
- On Pi: use SSH (with key).
