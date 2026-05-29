"""
Patch all 6 spec files:
  - Add 'license_hashes' to hiddenimports
  - Add product dir to pathex so license_hashes.py is importable at build time
"""
from pathlib import Path

ROOT = Path(__file__).parent

SPECS = {
    "LeadScraperPro.spec": "scraper_node",
    "Discovery1.spec":     "discovery1",
    "AtomicScraper.spec":  "atomicscraper",
    "ProspectHunter.spec": "prospecthunter",
    "LeadsBaby.spec":      "leadsbaby",
    "LeadRipper.spec":     "leadripper",
}

for spec_name, prod_dir in SPECS.items():
    path = ROOT / spec_name
    txt = path.read_text(encoding="utf-8")
    changed = False

    # 1. Add license_hashes to hiddenimports if not already there
    if "'license_hashes'" not in txt:
        txt = txt.replace(
            "hiddenimports = [",
            "hiddenimports = ['license_hashes', "
        )
        changed = True

    # 2. Add product dir to pathex if not already there
    prod_dir_entry = f"'{prod_dir}'"
    if prod_dir_entry not in txt.split("pathex=")[1].split("]")[0]:
        txt = txt.replace(
            "pathex=['.', 'scraper_node', 'api']",
            f"pathex=['.', 'scraper_node', '{prod_dir}', 'api']"
        )
        changed = True

    if changed:
        path.write_text(txt, encoding="utf-8")
        print(f"  Patched: {spec_name}")
    else:
        print(f"  SKIP (already patched): {spec_name}")

print("Done.")
