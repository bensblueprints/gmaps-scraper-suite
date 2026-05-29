import csv
import sys
import time
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import OUTPUT_DIR, QUERIES_DIR
from shared import website_enricher, lead_db
from shared import phone_lookup
import gmaps_scraper


class ScraperEngine:
    def __init__(self, log_callback: Callable = None):
        self.log_callback = log_callback or print
        self._stop_event = threading.Event()

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_callback(f"[{ts}] {msg}")

    def is_browser_installed(self) -> bool:
        return gmaps_scraper.is_chromium_installed()

    def install_browser(self, progress_callback: Callable = None) -> bool:
        return gmaps_scraper.install_chromium(log=self.log)

    def run_industry(
        self,
        industry_name: str,
        queries: list,
        location: str,
        max_leads: int = 500,
        page_workers: int = 4,
        enrich_workers: int = 8,
        extract_email: bool = True,
        headless: bool = True,
        on_lead: Callable = None,
    ) -> bool:
        if not self.is_browser_installed():
            self.log("ERROR: Chromium not installed.")
            return False

        self._stop_event.clear()
        self.log(f"Starting: {industry_name} in {location}")
        self.log(f"Settings: max_leads={max_leads}, browser_tabs={page_workers}, enrich_threads={enrich_workers}")

        try:
            results = gmaps_scraper.scrape(
                queries=queries,
                location=location,
                max_leads=max_leads,
                headless=headless,
                page_workers=page_workers,
                log=self.log,
            )

            if self._stop_event.is_set():
                self.log("Stopped by user.")
                return False

            if not results:
                self.log("No results found.")
                return True

            self.log(f"Scrape done: {len(results)} raw listings — enriching websites...")

            # Dedupe by phone+name before enriching
            seen = set()
            unique = []
            for r in results:
                key = (r.get('phone', ''), r.get('title', '').lower())
                if key not in seen:
                    seen.add(key)
                    r['industry']    = industry_name
                    r['scraped_city'] = location     # used as fallback city in DB
                    r['scraped_at']  = datetime.now().isoformat()
                    unique.append(r)

            enriched = self._enrich_batch(unique, extract_email=extract_email,
                                          enrich_workers=enrich_workers, on_lead=on_lead)

            count = self._save_to_csv(enriched, industry_name)
            self.log(f"Saved {count} leads to CSV.")

            return True

        except Exception as e:
            self.log(f"Scraper error: {e}")
            return False

    def _enrich_batch(self, leads: list, extract_email: bool,
                      enrich_workers: int = 8, on_lead: Callable = None) -> list:
        """Enrich leads with platform + email, respecting stop_event."""
        total = len(leads)

        def _process(i_lead):
            i, lead = i_lead
            if self._stop_event.is_set():
                return lead

            website = lead.get('website', '')
            if extract_email and website:
                try:
                    info = website_enricher.enrich(website)
                    lead['platform'] = info.get('platform', '')
                    lead['emails'] = info.get('emails', [])
                    lead['email'] = info['emails'][0] if info.get('emails') else ''
                    lead['contact_url'] = info.get('contact_url', '')

                    status = f"{lead.get('platform') or 'unknown platform'}"
                    email_str = lead.get('email') or 'no email'
                    self.log(f"  [{i+1}/{total}] {lead.get('title','')[:30]} -> {status}, {email_str}")
                except Exception as e:
                    self.log(f"  [{i+1}/{total}] enrich error: {e}")
            else:
                self.log(f"  [{i+1}/{total}] {lead.get('title','')[:40]} (no website)")

            # Phone type classification (free, no API needed)
            phone = lead.get('phone', '')
            if phone and not lead.get('phone_type'):
                try:
                    ph = phone_lookup.classify_phone(phone)
                    lead['phone_type'] = ph['type']
                    lead['carrier']    = ph['carrier']
                except Exception:
                    lead['phone_type'] = ''
                    lead['carrier']    = ''

            lead_db.upsert(lead)
            if on_lead:
                on_lead(lead)

            return lead

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=enrich_workers) as pool:
            futures = {pool.submit(_process, (i, lead)): lead for i, lead in enumerate(leads)}
            for future in concurrent.futures.as_completed(futures):
                if self._stop_event.is_set():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    results.append(future.result())
                except Exception:
                    results.append(futures[future])

        return results

    def _save_to_csv(self, rows: list, industry: str) -> int:
        slug = industry.lower().replace(" ", "_").replace("&", "and")
        out_file = OUTPUT_DIR / f"{slug}.csv"

        if not rows:
            return 0

        all_keys = list(rows[0].keys())
        priority = ['title', 'phone', 'email', 'platform', 'address',
                    'website', 'review_rating', 'review_count', 'category',
                    'industry', 'scraped_at']
        ordered = priority + [k for k in all_keys if k not in priority]

        file_exists = out_file.exists()
        with open(out_file, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerows(rows)

        return len(rows)

    def stop(self):
        self._stop_event.set()
