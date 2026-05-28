"""
Live dashboard for the USA scrape job queue.
Run: python jobs/status.py
     python jobs/status.py --watch      # refresh every 30s
     python jobs/status.py --top 20     # top 20 cities by leads
"""
import sys
import time
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jobs import job_db


def show(args):
    s = job_db.stats()
    total   = sum(v["count"] for v in s.values())
    done    = s.get("done",    {}).get("count", 0)
    pending = s.get("pending", {}).get("count", 0)
    running = s.get("running", {}).get("count", 0)
    failed  = s.get("failed",  {}).get("count", 0)
    leads   = sum(v["leads"] for v in s.values())
    pct     = done / total * 100 if total else 0

    print(f"\n{'='*55}")
    print(f"  USA LANDSCAPING SCRAPE — STATUS")
    print(f"{'='*55}")
    print(f"  Total cities  : {total:>7,}")
    print(f"  Done          : {done:>7,}  ({pct:.2f}%)")
    print(f"  Pending       : {pending:>7,}")
    print(f"  Running now   : {running:>7}")
    print(f"  Failed        : {failed:>7,}")
    print(f"  Total leads   : {leads:>7,}")
    print(f"{'='*55}")

    recent = job_db.recent_done(args.top)
    if recent:
        print(f"\n  Last {args.top} completed:")
        for r in recent:
            print(f"    {r['city']:<22} {r['state_abbr']}  {r['leads_found']:>4} leads  {r['completed_at'][:16]}")

    top = job_db.top_cities_by_leads(args.top)
    if top:
        print(f"\n  Top {args.top} cities by leads:")
        for i, r in enumerate(top, 1):
            print(f"    {i:>2}. {r['city']:<22} {r['state_abbr']}  {r['leads_found']:>4} leads")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Refresh every 30s")
    parser.add_argument("--top",   type=int, default=10, help="Lines in top/recent tables")
    args = parser.parse_args()

    if args.watch:
        while True:
            print("\033[2J\033[H", end="")  # clear screen
            show(args)
            print("  [Ctrl+C to stop watching]")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                break
    else:
        show(args)


if __name__ == "__main__":
    main()
