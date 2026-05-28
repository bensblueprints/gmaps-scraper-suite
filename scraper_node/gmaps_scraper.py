"""
Google Maps scraper using Playwright + Chromium.
"""
import re
import os
import sys
import time
import random
import subprocess
from pathlib import Path
from typing import Callable


# ── Browser management ─────────────────────────────────────────────────────────

def is_chromium_installed() -> bool:
    """Fast filesystem check — no browser launch needed."""
    profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    ms_pw = Path(profile) / "AppData" / "Local" / "ms-playwright"
    return (
        any(ms_pw.glob("chromium-*/chrome-win64/chrome.exe")) or
        any(ms_pw.glob("chromium-*/chrome-win/chrome.exe"))
    )


def install_chromium(log: Callable = print) -> bool:
    log("Installing Chromium browser (one-time, ~130 MB)...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
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


# ── Main entry point ───────────────────────────────────────────────────────────

def scrape(
    queries: list,
    location: str,
    depth: int = 5,
    headless: bool = True,
    log: Callable = print,
) -> list[dict]:
    from playwright.sync_api import sync_playwright

    all_results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for query in queries:
            full_query = f"{query} in {location}"
            log(f"Searching: {full_query}")

            try:
                urls = _collect_listing_urls(page, full_query, depth, log)
                log(f"  Found {len(urls)} listings - extracting details...")

                for i, url in enumerate(urls):
                    try:
                        data = _extract_place(page, url)
                        if data.get("title"):
                            all_results.append(data)
                            log(
                                f"  [{i+1}/{len(urls)}] {data['title']} | "
                                f"{data.get('phone', 'no phone')} | "
                                f"{data.get('review_rating', '')} stars"
                            )
                        else:
                            log(f"  [{i+1}/{len(urls)}] Skipped (no title)")
                    except Exception as e:
                        log(f"  [{i+1}/{len(urls)}] Error: {e}")
                    time.sleep(random.uniform(0.5, 1.2))

            except Exception as e:
                log(f"Query error: {e}")

            time.sleep(random.uniform(2.0, 3.5))

        browser.close()

    return all_results


# ── Collect listing URLs ───────────────────────────────────────────────────────

def _collect_listing_urls(page, query: str, depth: int, log: Callable) -> list:
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

    for i in range(depth):
        hrefs = page.eval_on_selector_all(
            'a[href*="/maps/place/"]',
            "els => els.map(el => el.href)",
        )
        for h in hrefs:
            seen.add(h.split("?")[0])

        log(f"  Scroll {i + 1}: {len(seen)} listings")

        # End of list?
        try:
            if page.locator("text=You've reached the end").count() > 0:
                log("  End of results.")
                break
        except Exception:
            pass

        # Scroll the feed
        try:
            feed = page.locator('div[role="feed"]')
            if feed.count() > 0:
                feed.evaluate("el => el.scrollBy(0, 3000)")
            else:
                page.mouse.wheel(0, 3000)
        except Exception:
            break

        page.wait_for_timeout(2500)

    return list(seen)


# ── Extract a single place ─────────────────────────────────────────────────────

def _extract_place(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    data: dict = {}

    # Title
    try:
        data["title"] = page.locator("h1").first.inner_text(timeout=3000).strip()
    except Exception:
        data["title"] = ""

    # Category
    try:
        data["category"] = page.locator("button.DkEaL").first.inner_text(timeout=2000).strip()
    except Exception:
        data["category"] = ""

    # Rating and review count — from div.F7nice innerHTML
    # Structure: span.ceNzKf aria-label="4.9 stars" + span[role=img] aria-label="456 reviews"
    try:
        f7_html = page.locator("div.F7nice").first.inner_html(timeout=2000)
        m = re.search(r'aria-label="([\d.]+)\s+stars?\s*"', f7_html)
        data["review_rating"] = m.group(1) if m else ""
        m2 = re.search(r'aria-label="([\d,]+)\s+reviews?"', f7_html)
        data["review_count"] = m2.group(1).replace(",", "") if m2 else ""
    except Exception:
        data["review_rating"] = ""
        data["review_count"] = ""

    # Info rows via data-item-id — the reliable approach
    data["address"] = _get_item(page, "address")
    data["phone"] = _get_item(page, "phone")
    data["website"] = _get_item(page, "authority")
    data["plus_code"] = _get_item(page, "oloc")

    # Hours / status
    try:
        hours_btn = page.locator('[data-item-id="oh"] button, [aria-label*="hours"]').first
        data["open_hours"] = hours_btn.inner_text(timeout=2000).strip()
    except Exception:
        data["open_hours"] = ""

    # Open/closed status
    try:
        data["status"] = page.locator("span.ZDu9vd span, .dHjBfd span").first.inner_text(timeout=2000).strip()
    except Exception:
        data["status"] = ""

    # Price range
    try:
        content = page.content()
        m = re.search(r'aria-label="Price: ([^"]+)"', content)
        data["price_range"] = m.group(1) if m else ""
    except Exception:
        data["price_range"] = ""

    # Coordinates and link from URL
    current_url = page.url
    data["link"] = current_url
    coord = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", current_url)
    if coord:
        data["latitude"] = coord.group(1)
        data["longitude"] = coord.group(2)
    else:
        data["latitude"] = ""
        data["longitude"] = ""

    return data


def _get_item(page, item_id: str) -> str:
    """Extract text from a [data-item-id] info row via its aria-label."""
    try:
        # Try exact match first
        el = page.locator(f'[data-item-id="{item_id}"]').first
        label = el.get_attribute("aria-label", timeout=2000) or ""
        if label:
            # Strip prefix like "Address: " / "Phone: " / "Website: "
            for prefix in ("Address:", "Phone:", "Website:", "Plus code:"):
                if label.startswith(prefix):
                    return label[len(prefix):].strip()
            return label.strip()
    except Exception:
        pass

    # Fallback: partial match (e.g. phone:tel:+1...)
    try:
        el = page.locator(f'[data-item-id^="{item_id}"]').first
        label = el.get_attribute("aria-label", timeout=2000) or ""
        for prefix in ("Address:", "Phone:", "Website:", "Plus code:"):
            if label.startswith(prefix):
                return label[len(prefix):].strip()
        return label.strip()
    except Exception:
        return ""
