"""
Google Maps scraper using Playwright + Chromium.
Parallel extraction uses one browser instance per worker thread (greenlet-safe).
"""
import re
import os
import sys
import time
import random
import threading
import subprocess
import concurrent.futures
from pathlib import Path
from typing import Callable

# When frozen by PyInstaller, Playwright can't find its bundled browsers.
# Point it to the system-wide ms-playwright installation instead.
if getattr(sys, "frozen", False):
    # Find the Chromium bundled inside the app. Check PyInstaller's _MEIPASS and
    # the .app's Resources/Frameworks dirs (browser is injected post-build), then
    # fall back to a system-wide ms-playwright install. First match wins.
    _cands = []
    _meipass = getattr(sys, "_MEIPASS", "")
    if _meipass:
        _cands.append(Path(_meipass) / "ms-playwright")
    _contents = Path(sys.executable).resolve().parent.parent  # <App>.app/Contents
    _cands += [
        _contents / "Resources" / "ms-playwright",
        _contents / "Frameworks" / "ms-playwright",
    ]
    _profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    _cands += [
        Path(_profile) / "AppData" / "Local" / "ms-playwright",
        Path(_profile) / "Library" / "Caches" / "ms-playwright",
    ]
    for _cand in _cands:
        try:
            if _cand.exists() and any(_cand.glob("chromium*")):
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_cand)
                break
        except Exception:
            pass


# ── Browser management ─────────────────────────────────────────────────────────

def is_chromium_installed() -> bool:
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if base:
        roots = [Path(base)]
    else:
        profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        roots = [
            Path(profile) / "Library" / "Caches" / "ms-playwright",
            Path(profile) / "AppData" / "Local" / "ms-playwright",
        ]
    patterns = (
        "chromium-*/chrome-mac*/*.app",
        "chromium-*/chrome-win64/chrome.exe",
        "chromium-*/chrome-win/chrome.exe",
        "chromium-*/chrome-linux*/chrome",
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell.exe",
    )
    for ms_pw in roots:
        if any(any(ms_pw.glob(p)) for p in patterns):
            return True
    return False


def install_chromium(log: Callable = print) -> bool:
    log("Installing Chromium browser (one-time, ~130 MB)...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log(line)
        proc.wait()
        ok = proc.returncode == 0
        log("Chromium installed." if ok else "Install failed.")
        return ok
    except Exception as e:
        log(f"Install error: {e}")
        return False


def _browser_args():
    return [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]


def _context_opts():
    return dict(
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
    )


# ── Main entry point ───────────────────────────────────────────────────────────

def scrape(
    queries: list,
    location: str,
    max_leads: int = 500,
    headless: bool = True,
    page_workers: int = 4,
    log: Callable = print,
    stop_event=None,
) -> list[dict]:
    """
    1. Collect listing URLs with one browser (sequential scroll — required by Google Maps).
    2. Split URLs across N worker threads, each running its OWN Playwright instance.
       This avoids greenlet cross-thread errors that occur when sharing a browser.
    """
    from playwright.sync_api import sync_playwright

    def _stopped():
        return stop_event is not None and stop_event.is_set()

    leads_per_query = max(10, max_leads // max(len(queries), 1))

    # ── Phase 1: URL collection ────────────────────────────────────────────────
    all_urls: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=_browser_args())
        context = browser.new_context(**_context_opts())
        page    = context.new_page()

        for query in queries:
            if _stopped():
                break
            full_query = f"{query} in {location}"
            log(f"Searching: {full_query} (target: up to {leads_per_query} leads)")
            try:
                urls = _collect_listing_urls(page, full_query, leads_per_query, log, stop_event)
                all_urls.extend(urls)
            except Exception as e:
                log(f"Query error: {e}")
            if not _stopped():
                time.sleep(random.uniform(1.5, 2.5))

        browser.close()

    if _stopped() or not all_urls:
        return []

    # Deduplicate across queries
    all_urls = list(dict.fromkeys(all_urls))[:max_leads]
    total = len(all_urls)
    n_workers = min(page_workers, total)
    log(f"Extracting {total} listings with {n_workers} parallel browser(s)...")

    # ── Phase 2: Parallel extraction — one Playwright instance per thread ─────
    counter      = [0]
    counter_lock = threading.Lock()
    results_lock = threading.Lock()
    all_results: list[dict] = []

    # Split URLs round-robin across workers
    chunks = [all_urls[i::n_workers] for i in range(n_workers)]

    def extract_worker(chunk: list) -> list:
        """Runs in its own thread with its own Playwright event loop."""
        from playwright.sync_api import sync_playwright
        worker_results = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=headless, args=_browser_args())
                context = browser.new_context(**_context_opts())
                page    = context.new_page()

                for url in chunk:
                    if _stopped():
                        break
                    try:
                        data = _extract_place(page, url)
                        if data.get("title"):
                            worker_results.append(data)
                            with counter_lock:
                                counter[0] += 1
                                n = counter[0]
                            log(
                                f"  [{n}/{total}] {data['title']} | "
                                f"{data.get('phone', 'no phone')} | "
                                f"{data.get('review_rating', '')} stars"
                            )
                        else:
                            with counter_lock:
                                counter[0] += 1
                    except Exception as e:
                        with counter_lock:
                            counter[0] += 1
                        log(f"  Error: {e}")
                    if not _stopped():
                        time.sleep(random.uniform(0.3, 0.8))

                browser.close()
        except Exception as e:
            log(f"  Worker error: {e}")
        return worker_results

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = [pool.submit(extract_worker, chunk) for chunk in chunks]
        for future in concurrent.futures.as_completed(futures):
            try:
                with results_lock:
                    all_results.extend(future.result())
            except Exception as e:
                log(f"  Worker failed: {e}")

    return all_results


# ── Collect listing URLs ───────────────────────────────────────────────────────

def _collect_listing_urls(page, query: str, max_leads: int, log: Callable, stop_event=None) -> list:
    search_url = "https://www.google.com/maps/search/" + query.replace(" ", "+")
    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    # Dismiss consent banners
    for sel in ['button[aria-label*="Accept"]', 'button[aria-label*="Agree"]',
                'form[action*="consent"] button']:
        try:
            page.click(sel, timeout=2000)
            page.wait_for_timeout(800)
            break
        except Exception:
            pass

    seen: set = set()
    scroll_num = 0
    last_count = 0
    stale_scrolls = 0
    MAX_STALE = 3    # stop after 3 consecutive scrolls with zero new results
    MAX_SCROLLS = 60 # absolute hard cap regardless of what Google shows

    while len(seen) < max_leads and scroll_num < MAX_SCROLLS:
        if stop_event is not None and stop_event.is_set():
            log("  Stopped by user.")
            break
        scroll_num += 1

        # Check for no-results page before scrolling
        try:
            for no_res_text in ["didn't find", "no results", "couldn't find"]:
                if page.get_by_text(no_res_text, exact=False).count() > 0:
                    log(f"  Google Maps: no results for this search.")
                    return []
        except Exception:
            pass

        hrefs = page.eval_on_selector_all(
            'a[href*="/maps/place/"]',
            "els => els.map(el => el.href)",
        )
        for h in hrefs:
            seen.add(h.split("?")[0])

        log(f"  Scroll {scroll_num}: {len(seen)} listings found (target {max_leads})")

        # Stale detection — no new listings this scroll
        if len(seen) == last_count:
            stale_scrolls += 1
            if stale_scrolls >= MAX_STALE:
                log(f"  No new listings after {MAX_STALE} scrolls — stopping.")
                break
        else:
            stale_scrolls = 0
            last_count = len(seen)

        try:
            if page.locator("text=You've reached the end").count() > 0:
                log("  Reached end of Google Maps results.")
                break
        except Exception:
            pass

        try:
            feed = page.locator('div[role="feed"]')
            if feed.count() > 0:
                feed.evaluate("el => el.scrollBy(0, 3000)")
            else:
                # No feed panel at all — likely a no-results or error page
                log("  No results feed found — stopping.")
                break
        except Exception:
            break

        # Interruptible 2s wait — checks stop every 200ms
        for _ in range(10):
            if stop_event is not None and stop_event.is_set():
                break
            page.wait_for_timeout(200)

    if scroll_num >= MAX_SCROLLS:
        log(f"  Hit max scroll limit ({MAX_SCROLLS}) — stopping.")

    urls = list(seen)[:max_leads]
    log(f"  Collected {len(urls)} listing URLs")
    return urls


# ── Extract a single place ─────────────────────────────────────────────────────

def _extract_place(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    data: dict = {}

    try:
        data["title"] = page.locator("h1").first.inner_text(timeout=3000).strip()
    except Exception:
        data["title"] = ""

    try:
        data["category"] = page.locator("button.DkEaL").first.inner_text(timeout=2000).strip()
    except Exception:
        data["category"] = ""

    try:
        f7_html = page.locator("div.F7nice").first.inner_html(timeout=2000)
        m = re.search(r'aria-label="([\d.]+)\s+stars?\s*"', f7_html)
        data["review_rating"] = m.group(1) if m else ""
        m2 = re.search(r'aria-label="([\d,]+)\s+reviews?"', f7_html)
        data["review_count"] = m2.group(1).replace(",", "") if m2 else ""
    except Exception:
        data["review_rating"] = ""
        data["review_count"] = ""

    data["address"]   = _get_item(page, "address")
    data["phone"]     = _get_item(page, "phone")
    data["website"]   = _get_item(page, "authority")
    data["plus_code"] = _get_item(page, "oloc")

    try:
        hours_btn = page.locator('[data-item-id="oh"] button, [aria-label*="hours"]').first
        data["open_hours"] = hours_btn.inner_text(timeout=2000).strip()
    except Exception:
        data["open_hours"] = ""

    try:
        data["status"] = page.locator("span.ZDu9vd span, .dHjBfd span").first.inner_text(timeout=2000).strip()
    except Exception:
        data["status"] = ""

    try:
        content = page.content()
        m = re.search(r'aria-label="Price: ([^"]+)"', content)
        data["price_range"] = m.group(1) if m else ""
    except Exception:
        data["price_range"] = ""

    current_url = page.url
    data["link"] = current_url
    coord = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", current_url)
    if coord:
        data["latitude"]  = coord.group(1)
        data["longitude"] = coord.group(2)
    else:
        data["latitude"]  = ""
        data["longitude"] = ""

    return data


def _get_item(page, item_id: str) -> str:
    try:
        el = page.locator(f'[data-item-id="{item_id}"]').first
        label = el.get_attribute("aria-label", timeout=2000) or ""
        if label:
            for prefix in ("Address:", "Phone:", "Website:", "Plus code:"):
                if label.startswith(prefix):
                    return label[len(prefix):].strip()
            return label.strip()
    except Exception:
        pass
    try:
        el = page.locator(f'[data-item-id^="{item_id}"]').first
        label = el.get_attribute("aria-label", timeout=2000) or ""
        for prefix in ("Address:", "Phone:", "Website:", "Plus code:"):
            if label.startswith(prefix):
                return label[len(prefix):].strip()
        return label.strip()
    except Exception:
        return ""
