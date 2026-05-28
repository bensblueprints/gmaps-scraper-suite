"""
Debug phase 3 — dump HTML around div.F7nice and try a higher-review business.
"""
import re
from playwright.sync_api import sync_playwright

# Use a well-known high-review plumber
TEST_URLS = [
    "https://www.google.com/maps/search/plumber+in+Las+Vegas+NV",  # search page first
]

def scrape_one(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)

    # Grab first result
    hrefs = page.eval_on_selector_all(
        'a[href*="/maps/place/"]',
        "els => els.map(el => el.href).slice(0, 3)"
    )
    print(f"First 3 place URLs found:")
    for h in hrefs:
        print(f"  {h[:100]}")
    return hrefs[0] if hrefs else None


def analyze_place(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)

    title = ""
    try:
        title = page.locator("h1").first.inner_text(timeout=3000)
    except Exception:
        pass

    print(f"\n=== {title} ===")

    # Rating
    try:
        el = page.locator("span.ceNzKf").first
        label = el.get_attribute("aria-label", timeout=2000) or ""
        m = re.search(r"([\d.]+)\s+star", label)
        print(f"  Rating: {m.group(1) if m else 'n/a'} (from {label!r})")
    except Exception as e:
        print(f"  Rating: ERROR {e}")

    # Dump innerHTML of div.F7nice
    try:
        html = page.locator("div.F7nice").first.inner_html(timeout=2000)
        print(f"  div.F7nice innerHTML: {html!r}")
    except Exception as e:
        print(f"  div.F7nice: NOT FOUND ({e})")

    # Look for "(N)" pattern in text
    try:
        all_text = page.locator("div.fontBodyMedium").all_inner_texts()
        for t in all_text[:20]:
            t = t.strip()
            if t and re.search(r'\d', t) and len(t) < 30:
                print(f"  fontBodyMedium text: {t!r}")
    except Exception:
        pass

    # Regex on page content
    content = page.content()
    # Find (N) near star rating
    patterns = [
        r'ceNzKf[^>]*>[^<]*<.*?\((\d[\d,]*)\)',
        r'F7nice[^>]*>.*?(\d\.\d).*?\(([\d,]+)\)',
        r'aria-label="[\d.]+ stars.*?"\D{0,50}(\d+)',
    ]
    for pat in patterns:
        m = re.search(pat, content, re.DOTALL)
        if m:
            print(f"  Regex {pat[:40]}: {m.group(0)[:80]!r}")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 768}, locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()

        # Get real place URLs from search
        place_url = scrape_one(page, TEST_URLS[0])

        if place_url:
            analyze_place(page, place_url)

        browser.close()

if __name__ == "__main__":
    main()
