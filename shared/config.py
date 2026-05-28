import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Running as PyInstaller .exe — put data dirs next to the exe
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.parent

OUTPUT_DIR = BASE_DIR / "output"
QUERIES_DIR = BASE_DIR / "queries"
BIN_DIR = BASE_DIR / "bin"

for _d in (OUTPUT_DIR, QUERIES_DIR, BIN_DIR):
    _d.mkdir(exist_ok=True)

SCRAPER_BINARY = BIN_DIR / "google-maps-scraper.exe"
BINARY_VERSION = "1.12.1"
BINARY_DOWNLOAD_URL = (
    f"https://github.com/gosom/google-maps-scraper/releases/download/"
    f"v{BINARY_VERSION}/google_maps_scraper-{BINARY_VERSION}-windows-amd64.exe"
)
