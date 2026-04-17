---
name: deploy-cheatkey
description: Build and deploy the CheatKey Electron app to /Applications. Use when the user asks to build, deploy, ship, or install the app, or says "билди", "положи в applications", "задеплой".
---

# Deploy CheatKey

Project root: `/Users/Igor.Slinko/projects/hermione`
Electron app: `electron-app/`

## Deployment workflow

### 1. Bump version in `electron-app/package.json`

Increment the patch version (e.g. `1.0.25` → `1.0.26`).

### 2. Build the DMG

```bash
cd /Users/Igor.Slinko/projects/hermione/electron-app && npm run build
```

Output: `dist/mac-arm64/CheatKey.app`

### 3. Kill running CheatKey (if any)

```bash
pgrep -x "CheatKey" && pkill -x "CheatKey" && sleep 1 || true
```

### 4. Copy to /Applications

```bash
cp -r /Users/Igor.Slinko/projects/hermione/electron-app/dist/mac-arm64/CheatKey.app /Applications/CheatKey.app
```

### 5. Ask user to confirm commit

After deploying, ask the user: **"Можно закоммитить изменения?"**

If yes — commit `electron-app/package.json` (and any other changed files) with a message like:
```
Bump version to 1.0.X and <short description of changes>
```
