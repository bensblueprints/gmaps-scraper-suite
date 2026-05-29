#!/bin/bash
# Build the remaining 5 products (LeadScraperPro already built).
# Cleans each heavy .app + build scratch after its DMG to respect tight disk.
set -e
cd ~/scraper

PRODUCTS=(
  "Discovery1:discovery1/app.py:discovery1"
  "AtomicScraper:atomicscraper/app.py:atomicscraper"
  "ProspectHunter:prospecthunter/app.py:prospecthunter"
  "LeadsBaby:leadsbaby/app.py:leadsbaby"
  "LeadRipper:leadripper/app.py:leadripper"
)

for entry in "${PRODUCTS[@]}"; do
  IFS=':' read -r name ep dir <<< "$entry"
  echo "################ $name ################"
  ./build_one_arm64.sh "$name" "$ep" "$dir"
  rm -rf "dist/${name}_arm64.app" "build/$name"
  echo "[cleanup] dropped dist/${name}_arm64.app + build/$name"
  echo "[disk] $(df -h /System/Volumes/Data | tail -1 | awk '{print $4" free"}')"
done

echo "ALL REMAINING BUILDS DONE"
ls -lh dmg_output/
