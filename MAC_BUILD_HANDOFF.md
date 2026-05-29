# Mac Build Handoff — Build DMGs for All 6 Products

## What you are building
6 white-label Google Maps scraper desktop apps as macOS DMGs — one for Apple Silicon (arm64) and one for Intel (x86_64) per product = 12 DMG files total.

The Windows EXEs are already built and live. You are doing the macOS side only.

---

## Step 1 — Get the source code onto the Mac

```bash
cd ~
git clone "https://YOUR_GITHUB_PAT_HERE@github.com/bensblueprints/gmaps-scraper-suite.git" scraper
cd scraper
```

If that repo doesn't have the full source (it may just have a README), the actual source is on the Windows machine. In that case, ask Ben to copy the folder to the Mac via AirDrop or a USB drive. The folder is at:
`C:\Users\ADMIN\Desktop\gmaps-scraper-suite\`

The critical files/folders you need:
```
scraper_node/       ← LeadScraperPro source
discovery1/         ← Discovery1 source  
atomicscraper/      ← AtomicScraper source
prospecthunter/     ← ProspectHunter source
leadsbaby/          ← LeadsBaby source
leadripper/         ← LeadRipper source
shared/             ← shared modules (engine, lead_db, phone_lookup, etc.)
api/                ← FastAPI server
keys/               ← license key txt files (needed to run generate_keys.py)
generate_keys.py    ← generates license_hashes.py per product
*.spec files        ← PyInstaller specs (Windows paths — will need editing)
```

---

## Step 2 — Install dependencies

```bash
# Install Python 3.11 via Homebrew if not already there
brew install python@3.11
export PATH="/opt/homebrew/bin:$PATH"

# Install pip packages
pip3.11 install pyinstaller customtkinter playwright phonenumbers fastapi uvicorn twilio anyio starlette

# Install Chromium for Playwright
python3.11 -m playwright install chromium

# Install create-dmg for packaging
brew install create-dmg
```

---

## Step 3 — Generate license hashes

```bash
cd ~/scraper   # wherever the source landed
python3.11 generate_keys.py
```

This creates `license_hashes.py` inside each product folder (scraper_node/, discovery1/, etc.). Each file contains a `VALID_HASHES = frozenset({...})` with 10,000 SHA-256 hashes compiled into the EXE/app at build time.

---

## Step 4 — Build each product

For each product, run PyInstaller twice — once for arm64 (native Apple Silicon) and once for x86_64 (Intel, runs via Rosetta). Then wrap each .app in a DMG.

### The 6 products:

| Product Name   | Entry point              | App name       |
|----------------|--------------------------|----------------|
| LeadScraperPro | scraper_node/app.py      | LeadScraperPro |
| Discovery1     | discovery1/app.py        | Discovery1     |
| AtomicScraper  | atomicscraper/app.py     | AtomicScraper  |
| ProspectHunter | prospecthunter/app.py    | ProspectHunter |
| LeadsBaby      | leadsbaby/app.py         | LeadsBaby      |
| LeadRipper     | leadripper/app.py        | LeadRipper     |

### Build script — save as `build_mac.sh` and run it:

```bash
#!/bin/bash
set -e
cd ~/scraper   # adjust path if different

PRODUCTS=(
  "LeadScraperPro:scraper_node/app.py:scraper_node"
  "Discovery1:discovery1/app.py:discovery1"
  "AtomicScraper:atomicscraper/app.py:atomicscraper"
  "ProspectHunter:prospecthunter/app.py:prospecthunter"
  "LeadsBaby:leadsbaby/app.py:leadsbaby"
  "LeadRipper:leadripper/app.py:leadripper"
)

mkdir -p dmg_output

for entry in "${PRODUCTS[@]}"; do
  IFS=':' read -r name entrypoint proddir <<< "$entry"
  echo ""
  echo "========================================"
  echo "Building $name"
  echo "========================================"

  for arch in arm64 x86_64; do
    echo "--- $name $arch ---"

    python3.11 -m PyInstaller \
      --noconfirm \
      --onefile \
      --windowed \
      --name "$name" \
      --target-arch "$arch" \
      --add-data "shared/industries_data.json:shared" \
      --add-data "shared/cities.py:shared" \
      --hidden-import license_hashes \
      --hidden-import shared \
      --hidden-import shared.config \
      --hidden-import shared.machine_id \
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

    # Rename the .app so arm64 and x86_64 don't overwrite each other
    mv "dist/$name.app" "dist/${name}_${arch}.app"

    # Wrap in DMG
    create-dmg \
      --volname "$name" \
      --window-size 600 400 \
      --icon-size 128 \
      --app-drop-link 450 185 \
      "dmg_output/${name}_${arch}.dmg" \
      "dist/${name}_${arch}.app"

    echo "  Done: dmg_output/${name}_${arch}.dmg"
  done
done

echo ""
echo "ALL DONE — DMGs are in ~/scraper/dmg_output/"
ls -lh dmg_output/
```

```bash
chmod +x build_mac.sh
./build_mac.sh
```

---

## Step 5 — Upload DMGs to GitHub releases

Each product has an existing GitHub release (v1.0.0) that already has the Windows EXE. Upload the 2 DMGs per product to the same release.

**GitHub PAT:** `YOUR_GITHUB_PAT_HERE`
**GitHub owner:** `bensblueprints`

### Repo names and release IDs:

| Product        | Repo name        | Release ID |
|----------------|------------------|------------|
| LeadScraperPro | leadscraper-pro  | 331237846  |
| Discovery1     | discovery1-leads | 331238674  |
| AtomicScraper  | atomic-scraper   | 331238723  |
| ProspectHunter | prospect-hunter  | 331238771  |
| LeadsBaby      | leads-baby       | 331238834  |
| LeadRipper     | lead-ripper      | 331238871  |

### Upload script — save as `upload_dmgs.sh`:

```bash
#!/bin/bash
PAT="YOUR_GITHUB_PAT_HERE"
OWNER="bensblueprints"

declare -A REPOS
REPOS["LeadScraperPro"]="leadscraper-pro:331237846"
REPOS["Discovery1"]="discovery1-leads:331238674"
REPOS["AtomicScraper"]="atomic-scraper:331238723"
REPOS["ProspectHunter"]="prospect-hunter:331238771"
REPOS["LeadsBaby"]="leads-baby:331238834"
REPOS["LeadRipper"]="lead-ripper:331238871"

cd ~/scraper/dmg_output

for name in "${!REPOS[@]}"; do
  IFS=':' read -r repo release_id <<< "${REPOS[$name]}"

  for arch in arm64 x86_64; do
    dmg="${name}_${arch}.dmg"
    if [ ! -f "$dmg" ]; then
      echo "SKIP: $dmg not found"
      continue
    fi

    echo "Uploading $dmg..."
    curl -s -o /dev/null -w "%{http_code}" \
      -H "Authorization: token $PAT" \
      -H "Content-Type: application/octet-stream" \
      --data-binary @"$dmg" \
      "https://uploads.github.com/repos/$OWNER/$repo/releases/$release_id/assets?name=$dmg"
    echo " -> $dmg uploaded"
  done
done

echo "Done."
```

```bash
chmod +x upload_dmgs.sh
./upload_dmgs.sh
```

---

## Notes

- `--onefile` on macOS produces a `.app` bundle (not a single binary). This is normal.
- If PyInstaller complains about Tkinter on macOS, install a Tkinter-aware Python: `brew install python-tk@3.11`
- If `create-dmg` fails, fallback: `hdiutil create -volname "AppName" -srcfolder dist/AppName.app -ov -format UDZO dmg_output/AppName_arm64.dmg`
- The `--target-arch x86_64` build on Apple Silicon requires Rosetta 2. If not installed: `softwareupdate --install-rosetta`
- Playwright bundling is the heaviest part — each build takes 5–10 min

## Final download URLs (after upload)

Pattern: `https://github.com/bensblueprints/{repo}/releases/download/v1.0.0/{ProductName}_{arch}.dmg`

Example:
- `https://github.com/bensblueprints/leadscraper-pro/releases/download/v1.0.0/LeadScraperPro_arm64.dmg`
- `https://github.com/bensblueprints/leadscraper-pro/releases/download/v1.0.0/LeadScraperPro_x86_64.dmg`
