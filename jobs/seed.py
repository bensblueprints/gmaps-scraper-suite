"""
Seed the job queue with all US cities.
Run once: python jobs/seed.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jobs.us_cities import load
from jobs.job_db import seed, stats

def main():
    cities = load()
    print(f"Loaded {len(cities)} US cities")

    inserted = seed(cities)
    print(f"Inserted {inserted} new jobs into queue")

    s = stats()
    total = sum(v["count"] for v in s.values())
    print(f"Queue total: {total} jobs")
    for status, data in sorted(s.items()):
        print(f"  {status:<10} {data['count']:>6}  ({data['leads']} leads)")

if __name__ == "__main__":
    main()
