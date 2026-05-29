"""Add hash file data entries to all 6 spec files."""
from pathlib import Path

ROOT = Path(__file__).parent
KEYS_DIR = ROOT / "keys"

SPECS = {
    "LeadScraperPro.spec": "LeadScraperPro",
    "Discovery1.spec":     "Discovery1",
    "AtomicScraper.spec":  "AtomicScraper",
    "ProspectHunter.spec": "ProspectHunter",
    "LeadsBaby.spec":      "LeadsBaby",
    "LeadRipper.spec":     "LeadRipper",
}

for spec_name, product in SPECS.items():
    path = ROOT / spec_name
    txt  = path.read_text(encoding="utf-8")

    hash_entry = f"('{KEYS_DIR / (product + '_hashes.txt')}', 'keys')".replace("\\", "\\\\")

    if "_hashes.txt" in txt:
        print(f"  SKIP (already patched): {spec_name}")
        continue

    # Insert before the closing bracket of datas list
    # datas ends with ...('...cities.py', 'shared')]
    txt = txt.replace(
        "('C:\\\\Users\\\\ADMIN\\\\Desktop\\\\gmaps-scraper-suite\\\\shared\\\\cities.py', 'shared')]",
        f"('C:\\\\Users\\\\ADMIN\\\\Desktop\\\\gmaps-scraper-suite\\\\shared\\\\cities.py', 'shared'), {hash_entry}]"
    )

    path.write_text(txt, encoding="utf-8")
    print(f"  Patched: {spec_name}")

print("Done.")
