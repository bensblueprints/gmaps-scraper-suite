import csv
import sys
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
from shared.website_enricher import enrich_social
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
        license_validator: Callable = None,
    ) -> list:
        """Scrape one industry/city. Saves raw leads to DB immediately.
        Returns the list of raw leads for the caller to enrich later."""
        if license_validator is not None and not license_validator():
            self.log("ERROR: No valid license key. Scraping blocked.")
            return []

        if not self.is_browser_installed():
            self.log("ERROR: Chromium not installed.")
            return []

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
                stop_event=self._stop_event,
            )

            if self._stop_event.is_set():
                self.log("Stopped by user.")
                return []

            if not results:
                self.log("No results found.")
                return []

            # Dedupe by phone+name
            seen = set()
            unique = []
            for r in results:
                key = (r.get('phone', ''), r.get('title', '').lower())
                if key not in seen:
                    seen.add(key)
                    r['industry']     = industry_name
                    r['scraped_city'] = location
                    r['city']         = location
                    r['scraped_at']   = datetime.now().isoformat()
                    unique.append(r)

            # Save raw leads to DB immediately + notify UI
            saved = 0
            for lead in unique:
                if lead_db.insert_raw(lead):
                    saved += 1
                if on_lead:
                    on_lead(lead)

            self.log(f"Scraped {len(unique)} leads ({saved} new) — ready to enrich.")
            return unique

        except Exception as e:
            self.log(f"Scraper error: {e}")
            return []

    def enrich_batch(
        self,
        leads: list,
        extract_email: bool = True,
        enrich_workers: int = 8,
        on_progress: Callable = None,
    ) -> None:
        """Enrich a list of leads (already in DB). Updates DB in-place."""
        if not leads:
            return

        total = len(leads)
        self.log(f"Enriching {total} leads with {enrich_workers} threads...")

        def _process(i_lead):
            i, lead = i_lead
            if self._stop_event.is_set():
                return

            website = lead.get('website', '') or lead.get('website', '')
            name = lead.get('title') or lead.get('name', '')

            if extract_email and website:
                try:
                    info = website_enricher.enrich(website)
                    lead['platform']    = info.get('platform', '')
                    lead['emails']      = info.get('emails', [])
                    lead['email']       = info['emails'][0] if info.get('emails') else ''
                    lead['contact_url'] = info.get('contact_url', '')

                    status    = lead.get('platform') or 'unknown platform'
                    email_str = lead.get('email') or 'no email'
                    self.log(f"  [{i+1}/{total}] {name[:30]} → {status}, {email_str}")
                except Exception as e:
                    self.log(f"  [{i+1}/{total}] enrich error: {e}")
            else:
                self.log(f"  [{i+1}/{total}] {name[:40]} (no website)")

            # Phone type classification
            phone = lead.get('phone', '')
            if phone and not lead.get('phone_type'):
                try:
                    ph = phone_lookup.classify_phone(phone)
                    lead['phone_type'] = ph['type']
                    lead['carrier']    = ph['carrier']
                except Exception:
                    lead['phone_type'] = ''
                    lead['carrier']    = ''

            lead_db.update_enrichment(lead)

            if on_progress:
                on_progress(i + 1, total)

        with concurrent.futures.ThreadPoolExecutor(max_workers=enrich_workers) as pool:
            futures = {pool.submit(_process, (i, lead)): lead for i, lead in enumerate(leads)}
            for future in concurrent.futures.as_completed(futures):
                if self._stop_event.is_set():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    future.result()
                except Exception:
                    pass

        self.log("Enrichment complete.")

    def enrich_unenriched(
        self,
        extract_email: bool = True,
        enrich_workers: int = 8,
        on_progress: Callable = None,
        limit: int = 2000,
    ) -> None:
        """Enrich all leads in the DB that have a website but haven't been enriched yet."""
        leads = lead_db.get_unenriched(limit=limit)
        if not leads:
            self.log("No unenriched leads found.")
            return
        self.log(f"Found {len(leads)} unenriched leads.")
        self._stop_event.clear()
        self.enrich_batch(leads, extract_email=extract_email,
                          enrich_workers=enrich_workers, on_progress=on_progress)

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

    def social_enrich_batch(
        self,
        leads: list,
        workers: int = 8,
        on_progress: Callable = None,
    ) -> None:
        """Scan each lead's website for social media profile links."""
        if not leads:
            return

        total = len(leads)
        self.log(f"Social enrichment: {total} leads with {workers} threads…")

        def _process(i_lead):
            i, lead = i_lead
            if self._stop_event.is_set():
                return

            website = lead.get('website', '')
            name    = lead.get('title') or lead.get('name', '')

            if website:
                try:
                    info = enrich_social(website)
                    lead.update(info)
                    found = info.get('socials', '') or 'none found'
                    self.log(f"  [{i+1}/{total}] {name[:35]} → {found}")
                except Exception as e:
                    self.log(f"  [{i+1}/{total}] social error: {e}")
            else:
                self.log(f"  [{i+1}/{total}] {name[:40]} (no website)")

            lead_db.update_social(lead)

            if on_progress:
                on_progress(i + 1, total)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process, (i, lead)): lead for i, lead in enumerate(leads)}
            for future in concurrent.futures.as_completed(futures):
                if self._stop_event.is_set():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    future.result()
                except Exception:
                    pass

        self.log("Social enrichment complete.")

    def social_enrich_unenriched(
        self,
        workers: int = 8,
        on_progress: Callable = None,
        limit: int = 2000,
    ) -> None:
        """Social-enrich all leads that have a website but haven't been social-enriched yet."""
        leads = lead_db.get_social_unenriched(limit=limit)
        if not leads:
            self.log("No leads pending social enrichment.")
            return
        self.log(f"Found {len(leads)} leads for social enrichment.")
        self._stop_event.clear()
        self.social_enrich_batch(leads, workers=workers, on_progress=on_progress)

    def stop(self):
        self._stop_event.set()
