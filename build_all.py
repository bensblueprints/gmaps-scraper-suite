"""Build all 6 EXEs using their spec files, copy to Desktop/Scraper Downloads."""
import subprocess, sys, os, shutil
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
DOWNLOADS = Path.home() / "Desktop" / "Scraper Downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT)

specs = [
    "LeadScraperPro.spec",
    "Discovery1.spec",
    "AtomicScraper.spec",
    "ProspectHunter.spec",
    "LeadsBaby.spec",
    "LeadRipper.spec",
]

for spec in specs:
    name = spec.replace(".spec", "")
    print(f"Building {name}...")
    subprocess.run(["taskkill", "/F", "/IM", f"{name}.exe"], capture_output=True)
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", spec],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    for line in (r.stdout + r.stderr).splitlines():
        if "INFO: Build complete" in line or "WARNING" in line[:60] or "ERROR" in line or "error" in line.lower():
            print(f"  {line.strip()}")
    if r.returncode != 0:
        print(f"  FAILED (exit {r.returncode})")
        print(r.stderr[-2000:])
    else:
        src = DIST / f"{name}.exe"
        dst = DOWNLOADS / f"{name}.exe"
        if src.exists():
            shutil.copy2(src, dst)
            mb = dst.stat().st_size / 1_048_576
            print(f"  OK -> Scraper Downloads/{name}.exe  ({mb:.0f} MB)")
        else:
            print(f"  OK (dist/{name}.exe not found — check dist/)")

print(f"\nALL DONE  —  Files in: {DOWNLOADS}")
