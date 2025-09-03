# GitHub Update Cheat Sheet (Windows + Pi Zero)

## Windows (HTTPS + Credential Manager)
```
git remote set-url origin https://github.com/Bluebarrycat/fermentation-chamber.git
git config --global credential.helper manager-core
git pull origin main
git pull origin dev
git add .
git commit -m "Your message here"
git push origin dev
```

## Pi Zero (SSH)
```
git remote set-url origin git@github.com:Bluebarrycat/fermentation-chamber.git
git pull origin main
git pull origin dev
git add .
git commit -m "Your message here"
git push origin dev
```

## Merge flows
```
# bring main into dev
git checkout dev && git pull origin dev && git merge main && git push origin dev

# promote dev to main
git checkout main && git pull origin main && git merge dev && git push origin main
```
