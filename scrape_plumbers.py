"""
Quick plumber lead scrape — runs headless, saves to output/plumbers.csv
"""
import sys
import csv
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "scraper_node"))
sys.path.insert(0, str(Path(__file__).parent))

import gmaps_scraper

LOCATION = "Las Vegas, NV"
QUERIES = [
    "plumber",
    "plumbing company",
    "plumbing repair",
    "emergency plumber",
    "drain cleaning service",
]
DEPTH = 8       # scroll passes per query (~15–20 results each)
HEADLESS = True

OUTPUT = Path(__file__).parent / "output" / "plumbers.csv"
OUTPUT.parent.mkdir(exist_ok=True)

FIELDS = [
    "title", "category", "phone", "address", "website",
    "review_rating", "review_count", "url", "scraped_at",
]


def main():
    print(f"[{datetime.now():%H:%M:%S}] Scraping plumbers in {LOCATION}...")
    print(f"  Queries: {QUERIES}")
    print(f"  Depth: {DEPTH} scrolls per query")
    print()

    results = gmaps_scraper.scrape(
        queries=QUERIES,
        location=LOCATION,
        depth=DEPTH,
        headless=HEADLESS,
        log=lambda m: print(f"  {m}"),
    )

    if not results:
        print("\nNo results returned.")
        return

    # Dedupe by phone + title
    seen = set()
    unique = []
    for r in results:
        key = (r.get("phone", ""), r.get("title", "").lower())
        if key not in seen:
            seen.add(key)
            r["scraped_at"] = datetime.now().isoformat()
            unique.append(r)

    all_keys = FIELDS + [k for k in unique[0].keys() if k not in FIELDS]

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(unique)

    print(f"\n{'='*50}")
    print(f"DONE — {len(unique)} unique leads saved to:")
    print(f"  {OUTPUT}")
    print(f"{'='*50}\n")

    # Print a preview table
    print(f"{'NAME':<35} {'PHONE':<16} {'RATING':<7} {'REVIEWS'}")
    print("-" * 75)
    for r in unique[:25]:
        print(
            f"{r.get('title','')[:34]:<35} "
            f"{r.get('phone','')[:15]:<16} "
            f"{r.get('review_rating',''):<7} "
            f"{r.get('review_count','')}"
        )
    if len(unique) > 25:
        print(f"  ... and {len(unique) - 25} more in the CSV")


if __name__ == "__main__":
    main()
