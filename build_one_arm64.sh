#!/bin/bash
# Build a single product as an arm64 .app + .dmg
# Usage: ./build_one_arm64.sh <AppName> <entrypoint.py> <proddir>
set -e
cd ~/scraper
PY=.venv/bin/python

name="$1"
entrypoint="$2"
proddir="$3"

# Browser bundled into each app: the headless shell is what chromium.launch(headless=True)
# uses in Playwright 1.49+. Apps always run headless, so the shell is sufficient (and smaller).
CHROMIUM_REV="chromium_headless_shell-1223"
CHROMIUM_SRC="$HOME/Library/Caches/ms-playwright/$CHROMIUM_REV"
if [ ! -d "$CHROMIUM_SRC" ]; then
  echo "FATAL: $CHROMIUM_SRC not found — run: .venv/bin/python -m playwright install chromium"
  exit 1
fi

mkdir -p dmg_output

echo "=== Building $name (arm64) ==="
rm -rf "dist/$name.app" "dist/${name}_arm64.app"

"$PY" -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "$name" \
  --add-data "shared/industries_data.json:shared" \
  --add-data "shared/cities.py:shared" \
  --hidden-import license_hashes \
  --hidden-import shared \
  --hidden-import shared.config \
  --hidden-import shared.machine_id \
  --hidden-import shared.whop_license \
  --hidden-import shared.api_key_db \
  --hidden-import shared.phone_lookup \
  --hidden-import api \
  --hidden-import api.server \
  --hidden-import engine \
  --hidden-import tkinter \
  --hidden-import tkinter.ttk \
  --hidden-import fastapi \
  --hidden-import uvicorn \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import starlette \
  --hidden-import anyio \
  --hidden-import phonenumbers \
  --hidden-import twilio \
  --hidden-import twilio.rest \
  --paths "." \
  --paths "$proddir" \
  --paths "api" \
  --collect-all playwright \
  --collect-all customtkinter \
  "$entrypoint"

# Inject Chromium AFTER PyInstaller (it can't process Chromium's signed binaries).
# Place it next to the other bundled data so PLAYWRIGHT_BROWSERS_PATH=_MEIPASS/ms-playwright resolves.
shared_dir="$(find "dist/$name.app" -type f -name industries_data.json -path '*/shared/*' | head -1)"
if [ -z "$shared_dir" ]; then echo "FATAL: could not locate bundled data root in dist/$name.app"; exit 1; fi
dataroot="$(dirname "$(dirname "$shared_dir")")"
echo "=== Injecting Chromium into $dataroot/ms-playwright/$CHROMIUM_REV ==="
mkdir -p "$dataroot/ms-playwright"
ditto "$CHROMIUM_SRC" "$dataroot/ms-playwright/$CHROMIUM_REV"

# Mirror ms-playwright into the sibling dir so PyInstaller's _MEIPASS resolves it too
# (datas land in Resources, but _MEIPASS points at Frameworks).
contents="$(dirname "$dataroot")"
if [ "$(basename "$dataroot")" = "Resources" ] && [ -d "$contents/Frameworks" ]; then
  ln -sfn ../Resources/ms-playwright "$contents/Frameworks/ms-playwright"
elif [ "$(basename "$dataroot")" = "Frameworks" ] && [ -d "$contents/Resources" ]; then
  ln -sfn ../Frameworks/ms-playwright "$contents/Resources/ms-playwright"
fi

mv "dist/$name.app" "dist/${name}_arm64.app"

echo "=== Packaging DMG for $name ==="
rm -f "dmg_output/${name}_arm64.dmg"
# hdiutil is used directly (create-dmg's AppleScript/Finder step can't run in a non-GUI shell).
hdiutil create -volname "$name" -srcfolder "dist/${name}_arm64.app" -ov -format UDZO "dmg_output/${name}_arm64.dmg"

echo "  Done: dmg_output/${name}_arm64.dmg"
ls -lh "dmg_output/${name}_arm64.dmg"
