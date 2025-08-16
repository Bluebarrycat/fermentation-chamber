# Raspberry Pi Zero – GitHub Update Cheat Sheet (with Remote URL Fix)

This guide assumes your Raspberry Pi Zero is linked to your GitHub repo via **SSH**.

## 1. Navigate to your repository
```bash
cd ~/Ferment
```

## 2. Check and fix remote URL (if GitHub shows 'repository moved')
To avoid warnings like:
```
remote: This repository moved. Please use the new location:
```
Update your remote to the correct URL:
```bash
git remote set-url origin git@github.com:Bluebarrycat/fermentation-chamber.git
```
Verify:
```bash
git remote -v
```

## 3. Pull latest changes from GitHub
Use this when you want to update your Pi Zero with the latest code from GitHub:
```bash
git pull origin main
```
If working on a different branch (e.g., dev):
```bash
git pull origin dev
```

## 4. Commit changes made on the Pi
If you edit files directly on the Pi, commit them to Git:
```bash
git add .
git commit -m "Describe your change here"
```

## 5. Push changes back to GitHub
Push your commits to GitHub so your repo is up to date:
```bash
git push origin main
```
Or for dev branch:
```bash
git push origin dev
```

## 6. Check repository status
See which files have been changed:
```bash
git status
```

## 7. Switch branches
```bash
git checkout main
git checkout dev
```

## 8. Creating a new branch
```bash
git checkout -b branch-name
git push -u origin branch-name
```

## Notes:
- Always **pull before pushing** to avoid conflicts:
  ```bash
  git pull origin main
  ```
- Replace `main` with your current branch name if not working on main.
- Keep your SSH key added to GitHub to avoid login prompts.
