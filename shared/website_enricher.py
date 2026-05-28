"""
Website enricher — visits a business website and returns:
  - platform: detected CMS/builder name
  - emails:   list of unique email addresses found
  - contact_url: which page the email was found on
Uses requests (fast, no JS required for most sites).
"""
import re
import time
import socket
from urllib.parse import urljoin, urlparse
from typing import Callable

try:
    import requests
    from requests.exceptions import RequestException
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ── Platform signatures ────────────────────────────────────────────────────────
# Each entry: (name, [regex patterns to search in full HTML + response headers])
PLATFORM_SIGS = [
    ("WordPress",    [r'wp-content/', r'/wp-json/', r'<meta[^>]+generator[^>]+WordPress',
                      r'wp-includes/', r'wp-emoji']),
    ("Shopify",      [r'cdn\.shopify\.com', r'\.myshopify\.com', r'Shopify\.theme',
                      r'"myshopify"', r'shopify\.com/s/files']),
    ("Wix",          [r'wixstatic\.com', r'static\.parastorage\.com', r'wix\.com/lpviral',
                      r'"wixCode"', r'X-Wix-Published-Version']),
    ("Squarespace",  [r'squarespace\.com', r'squarespace-cdn\.com', r'sqsp\.net',
                      r'"squarespace"', r'static1\.squarespace\.com']),
    ("Webflow",      [r'webflow\.io', r'assets\.website-files\.com', r'data-wf-site',
                      r'webflow\.com/collections', r'js\.webflow\.com']),
    ("Weebly",       [r'weebly\.com', r'editmysite\.com', r'weebly\.net',
                      r'weeblycloud\.com']),
    ("GoDaddy",      [r'secureserver\.net', r'myftpupload\.com', r'godaddy\.com/websites',
                      r'p3nwvpsxx\.shr\.prod\.iad1', r'website-builder\.godaddy']),
    ("Duda",         [r'dudaone\.com', r'multiscreensite\.com',
                      r'irp-cdn\.multiscreensite', r'duda\.co']),
    ("BigCommerce",  [r'bigcommerce\.com', r'cdn\d+\.bigcommerce', r'bigcommerceapp']),
    ("Magento",      [r'Mage\.Cookies', r'var Mage\s*=', r'/skin/frontend/', r'magento']),
    ("Drupal",       [r'/sites/default/files/', r'Drupal\.settings', r'drupal\.js',
                      r'<meta[^>]+generator[^>]+Drupal']),
    ("Joomla",       [r'/components/com_', r'Joomla!', r'/media/jui/',
                      r'<meta[^>]+generator[^>]+Joomla']),
    ("HubSpot",      [r'hs-scripts\.com', r'hubspot\.net', r'hbspt\.']),
    ("Ghost",        [r'ghost\.io', r'content\.ghost\.org', r'"ghost-url"']),
    ("Elementor",    [r'elementor\.com', r'elementor-frontend', r'elementor-pro']),
]

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

# Domains to skip — these show up in page source but aren't business emails
SKIP_DOMAINS = {
    'example.com', 'sentry.io', 'w3.org', 'schema.org', 'openssl.org',
    'yourdomain.com', 'youremail.com', 'email.com', 'domain.com', 'googleapis.com',
    'wixpress.com', 'squarespace.com', 'shopify.com', 'wordpress.org',
    'php.net', 'jquery.com', 'bootstrapcdn.com', 'cloudflare.com',
    'facebook.com', 'google.com', 'twitter.com', 'instagram.com',
    'yelp.com', 'bbb.org', 'angi.com', 'homeadvisor.com',
    'angieslist.com', 'fonts.com', 'latofonts.com', 'typekit.net',
    'fonts.googleapis.com', 'fontawesome.com', 'gravatar.com',
    'amazonaws.com', 'akamai.net', 'fastly.net', 'jsdelivr.net',
    'unpkg.com', 'cdnjs.cloudflare.com', 'adobe.com', 'vimeo.com',
    'youtube.com', 'youtu.be', 'maps.google.com', 'goo.gl',
    'bit.ly', 'tinyurl.com', 'sba.gov', 'irs.gov',
}

# Ignore emails starting with these prefixes
SKIP_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'do-not-reply',
                 'unsubscribe', 'bounce', 'mailer-daemon', 'postmaster',
                 'webmaster', 'hostmaster', 'abuse', 'spam', 'info+',
                 'news@', 'newsletter@', 'support+'}

SESSION_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

CONTACT_PATHS = ['/contact', '/contact-us', '/contact-us/', '/about-us', '/about',
                 '/get-in-touch', '/reach-us', '/support', '/help']

TIMEOUT = 8  # seconds per request


def _make_session():
    if not REQUESTS_OK:
        return None
    s = requests.Session()
    s.headers.update(SESSION_HEADERS)
    s.max_redirects = 5
    return s


def _detect_platform(html: str, headers: dict) -> str:
    """Search HTML + response headers for platform signatures."""
    # Check response headers too (convert to string for regex)
    header_str = ' '.join(f'{k}: {v}' for k, v in headers.items())
    combined = html + '\n' + header_str

    for name, patterns in PLATFORM_SIGS:
        for pat in patterns:
            if re.search(pat, combined, re.IGNORECASE):
                return name
    return ''


def _extract_emails(html: str, base_domain: str) -> list:
    """Pull email addresses from HTML, filtering noise."""
    found = []
    seen = set()
    for m in EMAIL_RE.finditer(html):
        email = m.group(0).lower().strip('.,;:"\')>')
        domain = email.split('@')[-1]
        prefix = email.split('@')[0]

        # Skip non-email file extensions
        if any(domain.endswith(ext) for ext in ['.png', '.jpg', '.gif', '.webp', '.svg', '.css', '.js']):
            continue
        if domain in SKIP_DOMAINS:
            continue
        if any(prefix.startswith(p) for p in SKIP_PREFIXES):
            continue
        if email in seen:
            continue
        seen.add(email)
        found.append(email)

    # Sort: prefer emails matching the business domain
    found.sort(key=lambda e: (0 if base_domain and base_domain in e else 1, e))
    return found[:5]  # max 5 per page


def _fetch(session, url: str) -> tuple:
    """Returns (html, headers) or (None, {}) on failure."""
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True, verify=False)
        if r.status_code == 200 and 'text/html' in r.headers.get('Content-Type', ''):
            return r.text, dict(r.headers)
    except Exception:
        pass
    return None, {}


def enrich(url: str, log: Callable = None) -> dict:
    """
    Visit url and return:
      {platform, emails, contact_url, error}
    Safe to call from a thread — no shared state.
    """
    result = {'platform': '', 'emails': [], 'contact_url': '', 'error': ''}

    if not url or not REQUESTS_OK:
        return result

    # Normalise URL
    if not url.startswith('http'):
        url = 'https://' + url
    parsed = urlparse(url)
    base_domain = parsed.netloc.replace('www.', '')

    session = _make_session()

    # ── Step 1: fetch home page ───────────────────────────────────────────────
    html, headers = _fetch(session, url)
    if html is None:
        # Try http fallback
        http_url = url.replace('https://', 'http://')
        html, headers = _fetch(session, http_url)

    if html is None:
        result['error'] = 'unreachable'
        return result

    # ── Detect platform ───────────────────────────────────────────────────────
    result['platform'] = _detect_platform(html, headers)

    # ── Extract emails from home page ─────────────────────────────────────────
    emails = _extract_emails(html, base_domain)

    if emails:
        result['emails'] = emails
        result['contact_url'] = url
        return result

    # ── Step 2: try contact/about pages ──────────────────────────────────────
    for path in CONTACT_PATHS:
        contact_url = urljoin(url, path)
        chtml, _ = _fetch(session, contact_url)
        if not chtml:
            continue
        cemails = _extract_emails(chtml, base_domain)
        if cemails:
            result['emails'] = cemails
            result['contact_url'] = contact_url
            break
        time.sleep(0.3)

    return result


# Suppress InsecureRequestWarning globally
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass
