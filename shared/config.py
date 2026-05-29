import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Frozen app: write data to a user-writable dir. The bundle/install dir can be
    # read-only (a mounted .dmg, /Applications), so never create folders inside it.
    _app = Path(sys.executable).stem
    if sys.platform == "darwin":
        BASE_DIR = Path.home() / "Library" / "Application Support" / _app
    elif sys.platform == "win32":
        BASE_DIR = Path(sys.executable).parent  # preserve existing Windows behavior
    else:
        BASE_DIR = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / _app
else:
    BASE_DIR = Path(__file__).parent.parent

OUTPUT_DIR = BASE_DIR / "output"
QUERIES_DIR = BASE_DIR / "queries"
BIN_DIR = BASE_DIR / "bin"

for _d in (OUTPUT_DIR, QUERIES_DIR, BIN_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SCRAPER_BINARY = BIN_DIR / "google-maps-scraper.exe"
BINARY_VERSION = "1.12.1"
BINARY_DOWNLOAD_URL = (
    f"https://github.com/gosom/google-maps-scraper/releases/download/"
    f"v{BINARY_VERSION}/google_maps_scraper-{BINARY_VERSION}-windows-amd64.exe"
)
