"""Wire all 6 apps to Whop licensing on macOS (offline hashes remain for Windows).
Replaces _validate_license_key in each app.py. Aborts if the exact block isn't found once.
"""
from pathlib import Path
import sys

APPS = ["scraper_node", "discovery1", "atomicscraper",
        "prospecthunter", "leadsbaby", "leadripper"]

OLD = '''def _validate_license_key(key: str) -> bool:
    import hashlib
    normalized = key.upper().strip()
    h = hashlib.sha256(f"{APP_DATA_DIR.name}:{normalized}".encode()).hexdigest()
    return h in _load_license_hashes()'''

NEW = '''def _validate_license_key(key: str) -> bool:
    # macOS builds validate online via Whop; the embedded-hash path is Windows-only here.
    if sys.platform == "darwin":
        try:
            from shared import whop_license
        except Exception:
            import whop_license  # frozen: shared dir is on sys.path
        whop_license.configure(APP_DATA_DIR.name, APP_DATA_DIR)
        return bool(whop_license.activate(key).get("ok"))
    import hashlib
    normalized = key.upper().strip()
    h = hashlib.sha256(f"{APP_DATA_DIR.name}:{normalized}".encode()).hexdigest()
    return h in _load_license_hashes()'''

ROOT = Path(__file__).parent
errors = []
for app in APPS:
    fp = ROOT / app / "app.py"
    text = fp.read_text(encoding="utf-8")
    if "import sys" not in text:
        errors.append(f"{app}: 'import sys' not found at top of app.py")
        continue
    if text.count(OLD) != 1:
        errors.append(f"{app}: target block found {text.count(OLD)}x (expected 1)")
        continue
    fp.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print(f"  wired {app}/app.py -> Whop on macOS")

if errors:
    print("\nABORTED:")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("\nAll 6 wired.")
