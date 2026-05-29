"""Patch all 6 products' gmaps_scraper.py for macOS bundled-Chromium support.

Two surgical replacements per file:
  1. frozen block  -> point PLAYWRIGHT_BROWSERS_PATH at the bundled browser
  2. is_chromium_installed() -> detect mac/win/linux + honor the env var
Aborts loudly if either pattern isn't found exactly once.
"""
from pathlib import Path
import sys

PRODUCTS = ["scraper_node", "discovery1", "atomicscraper",
            "prospecthunter", "leadsbaby", "leadripper"]

OLD_A = '''if getattr(sys, "frozen", False):
    _profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    _ms_pw   = Path(_profile) / "AppData" / "Local" / "ms-playwright"
    if _ms_pw.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_ms_pw)'''

NEW_A = '''if getattr(sys, "frozen", False):
    # Find the Chromium bundled inside the app. Check PyInstaller's _MEIPASS and
    # the .app's Resources/Frameworks dirs (browser is injected post-build), then
    # fall back to a system-wide ms-playwright install. First match wins.
    _cands = []
    _meipass = getattr(sys, "_MEIPASS", "")
    if _meipass:
        _cands.append(Path(_meipass) / "ms-playwright")
    _contents = Path(sys.executable).resolve().parent.parent  # <App>.app/Contents
    _cands += [
        _contents / "Resources" / "ms-playwright",
        _contents / "Frameworks" / "ms-playwright",
    ]
    _profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    _cands += [
        Path(_profile) / "AppData" / "Local" / "ms-playwright",
        Path(_profile) / "Library" / "Caches" / "ms-playwright",
    ]
    for _cand in _cands:
        try:
            if _cand.exists() and any(_cand.glob("chromium*")):
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_cand)
                break
        except Exception:
            pass'''

OLD_B = '''def is_chromium_installed() -> bool:
    profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    ms_pw = Path(profile) / "AppData" / "Local" / "ms-playwright"
    return (
        any(ms_pw.glob("chromium-*/chrome-win64/chrome.exe")) or
        any(ms_pw.glob("chromium-*/chrome-win/chrome.exe"))
    )'''

NEW_B = '''def is_chromium_installed() -> bool:
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if base:
        roots = [Path(base)]
    else:
        profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        roots = [
            Path(profile) / "Library" / "Caches" / "ms-playwright",
            Path(profile) / "AppData" / "Local" / "ms-playwright",
        ]
    patterns = (
        "chromium-*/chrome-mac*/*.app",
        "chromium-*/chrome-win64/chrome.exe",
        "chromium-*/chrome-win/chrome.exe",
        "chromium-*/chrome-linux*/chrome",
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell.exe",
    )
    for ms_pw in roots:
        if any(any(ms_pw.glob(p)) for p in patterns):
            return True
    return False'''

ROOT = Path(__file__).parent
errors = []
for prod in PRODUCTS:
    fp = ROOT / prod / "gmaps_scraper.py"
    text = fp.read_text(encoding="utf-8")
    if text.count(OLD_A) != 1:
        errors.append(f"{prod}: OLD_A found {text.count(OLD_A)} times (expected 1)")
        continue
    if text.count(OLD_B) != 1:
        errors.append(f"{prod}: OLD_B found {text.count(OLD_B)} times (expected 1)")
        continue
    text = text.replace(OLD_A, NEW_A).replace(OLD_B, NEW_B)
    fp.write_text(text, encoding="utf-8")
    print(f"  patched {prod}/gmaps_scraper.py")

if errors:
    print("\nABORTED — no files written for these:")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("\nAll 6 patched successfully.")
