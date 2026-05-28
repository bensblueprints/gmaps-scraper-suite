"""
Download and cache the US cities list.
Source: kelvins/US-Cities-Database on GitHub (29,880 cities).
Cached locally at ~/AppData/Local/LeadScraperPro/us_cities.csv
"""
import csv
import io
import urllib.request
from pathlib import Path

CACHE_PATH = Path.home() / "AppData" / "Local" / "LeadScraperPro" / "us_cities.csv"
SOURCE_URL = (
    "https://raw.githubusercontent.com/kelvins/"
    "US-Cities-Database/main/csv/us_cities.csv"
)


def load(force_download: bool = False) -> list[dict]:
    """Return list of city dicts: {city, state_abbr, state_name, county, latitude, longitude}"""
    if not force_download and CACHE_PATH.exists() and CACHE_PATH.stat().st_size > 10_000:
        return _parse(CACHE_PATH.read_text(encoding="utf-8"))

    print("Downloading US cities list (~30k cities)...")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="replace")
    CACHE_PATH.write_text(raw, encoding="utf-8")
    print(f"Saved to {CACHE_PATH}")
    return _parse(raw)


def _parse(raw: str) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(raw)))
    cities = []
    for r in rows:
        city = r.get("CITY", "").strip()
        state_abbr = r.get("STATE_CODE", "").strip()
        state_name = r.get("STATE_NAME", "").strip()
        if not city or not state_abbr:
            continue
        cities.append({
            "city":       city,
            "state_abbr": state_abbr,
            "state_name": state_name,
            "county":     r.get("COUNTY", "").strip(),
            "latitude":   r.get("LATITUDE", "").strip(),
            "longitude":  r.get("LONGITUDE", "").strip(),
        })
    return cities


if __name__ == "__main__":
    cities = load()
    print(f"Total cities: {len(cities)}")
    # State breakdown
    from collections import Counter
    states = Counter(c["state_abbr"] for c in cities)
    for state, count in sorted(states.items()):
        print(f"  {state}: {count}")
