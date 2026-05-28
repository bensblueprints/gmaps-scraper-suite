"""
USA Landscaping Job Runner
Processes one city at a time from the job queue.

Usage:
  python jobs/runner.py                  # Run with defaults
  python jobs/runner.py --depth 4        # Fewer scrolls (faster)
  python jobs/runner.py --state TX       # Only Texas cities
  python jobs/runner.py --retry-failed   # Retry failed jobs first
  python jobs/runner.py --status        # Show queue stats and exit

Ctrl+C for graceful shutdown after current city completes.
"""
import sys
import signal
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scraper_node"))

from jobs import job_db
from scraper_node.engine import ScraperEngine

INDUSTRY = "Landscaping"
QUERIES = [
    "landscaping companies",
    "lawn care services",
    "lawn mowing",
]

_stop_requested = False


def _handle_sigint(sig, frame):
    global _stop_requested
    print("\n[RUNNER] Ctrl+C received — finishing current city then stopping...")
    _stop_requested = True


def print_stats(s: dict, elapsed_sec: float = 0, cities_this_session: int = 0):
    total   = sum(v["count"] for v in s.values())
    done    = s.get("done",    {}).get("count", 0)
    pending = s.get("pending", {}).get("count", 0)
    running = s.get("running", {}).get("count", 0)
    failed  = s.get("failed",  {}).get("count", 0)
    leads   = sum(v["leads"] for v in s.values())

    pct = done / total * 100 if total else 0

    eta_str = ""
    if cities_this_session > 0 and elapsed_sec > 0 and pending > 0:
        rate = cities_this_session / elapsed_sec          # cities/sec
        remaining_sec = pending / rate
        eta = datetime.now() + timedelta(seconds=remaining_sec)
        days = int(remaining_sec // 86400)
        hours = int((remaining_sec % 86400) // 3600)
        eta_str = f"  ETA ~{days}d {hours}h (at {rate * 3600:.1f} cities/hr)"

    print(f"\n{'='*60}")
    print(f"  Total jobs   : {total:>7}")
    print(f"  Done         : {done:>7}  ({pct:.1f}%)")
    print(f"  Pending      : {pending:>7}")
    print(f"  Running      : {running:>7}")
    print(f"  Failed       : {failed:>7}")
    print(f"  Total leads  : {leads:>7}")
    if eta_str:
        print(eta_str)
    print(f"{'='*60}\n")


def run(args):
    global _stop_requested

    signal.signal(signal.SIGINT, _handle_sigint)

    # Reset any stuck running jobs from a previous crash
    stuck = job_db.reset_running()
    if stuck:
        print(f"[RUNNER] Reset {stuck} stuck jobs back to pending")

    if args.retry_failed:
        n = job_db.retry_failed()
        print(f"[RUNNER] Reset {n} failed jobs to pending")

    if args.status:
        print_stats(job_db.stats())
        recent = job_db.recent_done(10)
        if recent:
            print("Recent completions:")
            for r in recent:
                print(f"  {r['city']}, {r['state_abbr']}  ({r['leads_found']} leads)  {r['completed_at'][:16]}")
        top = job_db.top_cities_by_leads(10)
        if top:
            print("\nTop cities by leads:")
            for r in top:
                print(f"  {r['city']}, {r['state_abbr']}  {r['leads_found']} leads")
        return

    engine = ScraperEngine(log_callback=_log)

    if not engine.is_browser_installed():
        print("[RUNNER] Chromium not installed — run: python -m playwright install chromium")
        sys.exit(1)

    session_start = time.time()
    cities_this_session = 0
    leads_this_session = 0

    print(f"[RUNNER] Starting USA Landscaping scrape")
    print(f"[RUNNER] depth={args.depth}  state_filter={args.state or 'ALL'}")
    print_stats(job_db.stats())

    while not _stop_requested:
        job = job_db.claim_next()

        if job is None:
            print("[RUNNER] No more pending jobs. Queue is empty!")
            break

        # State filter
        if args.state and job["state_abbr"].upper() != args.state.upper():
            job_db.mark_done(job["id"], leads_found=0)
            continue

        city_label = f"{job['city']}, {job['state_abbr']}"
        print(f"\n[RUNNER] [{job['id']}] Starting: {city_label}")

        leads_before = _count_leads()

        try:
            engine._stop_event.clear()
            ok = engine.run_industry(
                industry_name=INDUSTRY,
                queries=QUERIES,
                location=city_label,
                depth=args.depth,
                extract_email=True,
                on_lead=None,
            )
            leads_after = _count_leads()
            new_leads = leads_after - leads_before

            job_db.mark_done(job["id"], leads_found=new_leads)
            cities_this_session += 1
            leads_this_session += new_leads

            elapsed = time.time() - session_start
            rate = cities_this_session / (elapsed / 3600) if elapsed > 0 else 0
            print(f"[RUNNER] Done: {city_label}  +{new_leads} leads  "
                  f"({cities_this_session} cities this session, {rate:.1f}/hr)")

            # Print full stats every 25 cities
            if cities_this_session % 25 == 0:
                print_stats(job_db.stats(), time.time() - session_start, cities_this_session)
                top = job_db.top_cities_by_leads(5)
                if top:
                    print("Top cities so far:")
                    for r in top:
                        print(f"  {r['city']}, {r['state_abbr']}  {r['leads_found']} leads")

        except KeyboardInterrupt:
            _stop_requested = True
            job_db.mark_failed(job["id"], "interrupted")
            break
        except Exception as e:
            print(f"[RUNNER] ERROR on {city_label}: {e}")
            job_db.mark_failed(job["id"], str(e))

    elapsed = time.time() - session_start
    print(f"\n[RUNNER] Session ended.")
    print(f"  Cities processed: {cities_this_session}")
    print(f"  Leads found:      {leads_this_session}")
    print(f"  Time elapsed:     {elapsed/3600:.2f}h")
    print_stats(job_db.stats(), elapsed, cities_this_session)


def _log(msg: str):
    print(msg)


def _count_leads() -> int:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from shared import lead_db
        return lead_db.count()
    except Exception:
        return 0


def main():
    parser = argparse.ArgumentParser(description="USA Landscaping Job Runner")
    parser.add_argument("--depth",        type=int, default=5,
                        help="Scroll depth per query (default 5)")
    parser.add_argument("--state",        type=str, default="",
                        help="Only run cities in this state (e.g. TX)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Reset failed jobs to pending before starting")
    parser.add_argument("--status",       action="store_true",
                        help="Print queue status and exit")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
