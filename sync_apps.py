"""Sync scraper_node/app.py → all product app.py files with product-specific substitutions."""
from pathlib import Path

ROOT = Path(__file__).parent

PRODUCTS = [
    {
        "dir":     "discovery1",
        "name":    "Discovery1",
        "color":   "#E67E22",
        "folder":  "Discovery1 Leads",
        "appdata": "Discovery1",
    },
    {
        "dir":     "atomicscraper",
        "name":    "AtomicScraper",
        "color":   "#00BCD4",
        "folder":  "AtomicScraper Leads",
        "appdata": "AtomicScraper",
    },
    {
        "dir":     "prospecthunter",
        "name":    "ProspectHunter",
        "color":   "#8E44AD",
        "folder":  "ProspectHunter Leads",
        "appdata": "ProspectHunter",
    },
    {
        "dir":     "leadsbaby",
        "name":    "Leads.Baby",
        "color":   "#FF6B9D",
        "folder":  "LeadsBaby Leads",
        "appdata": "LeadsBaby",
    },
    {
        "dir":     "leadripper",
        "name":    "LeadRipper",
        "color":   "#FF4500",
        "folder":  "LeadRipper Leads",
        "appdata": "LeadRipper",
    },
]

src = (ROOT / "scraper_node" / "app.py").read_text(encoding="utf-8")

for p in PRODUCTS:
    out = src
    out = out.replace('Lead Scraper Pro — desktop scraper + CRM application.',
                      f'{p["name"]} — desktop scraper + CRM application.')
    out = out.replace('PRODUCT_NAME  = "Lead Scraper Pro"',
                      f'PRODUCT_NAME  = "{p["name"]}"')
    out = out.replace('PRODUCT_COLOR = "#4FC3F7"',
                      f'PRODUCT_COLOR = "{p["color"]}"')
    out = out.replace('LEADS_FOLDER  = "LeadScraperPro Leads"',
                      f'LEADS_FOLDER  = "{p["folder"]}"')
    out = out.replace('/ "LeadScraperPro"',
                      f'/ "{p["appdata"]}"')

    dest = ROOT / p["dir"] / "app.py"
    dest.write_text(out, encoding="utf-8")
    print(f"  Written: {dest}")

print("Done.")
