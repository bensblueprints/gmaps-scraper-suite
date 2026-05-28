"""Quick test — scrape 3 plumbers and show rating + review_count."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "scraper_node"))

import gmaps_scraper

results = gmaps_scraper.scrape(
    queries=["plumber"],
    location="Las Vegas, NV",
    depth=1,
    headless=True,
    log=print,
)

print(f"\n--- {len(results)} results ---")
for r in results[:5]:
    print(f"  {r.get('title','?')[:35]:35} | rating={r.get('review_rating','?'):>5} | reviews={r.get('review_count','?')}")
