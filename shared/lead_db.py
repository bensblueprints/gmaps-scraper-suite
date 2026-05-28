"""
Local SQLite database for persistent lead storage.
Stored at ~/AppData/Local/LeadScraperPro/leads.db on Windows.
"""
import csv
import sqlite3
import threading
from pathlib import Path
from datetime import datetime

_DB_DIR = Path.home() / 'AppData' / 'Local' / 'LeadScraperPro'
_DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = _DB_DIR / 'leads.db'

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    phone       TEXT,
    email       TEXT,
    platform    TEXT,
    address     TEXT,
    city        TEXT,
    state       TEXT,
    website     TEXT,
    category    TEXT,
    rating      TEXT,
    review_count TEXT,
    latitude    TEXT,
    longitude   TEXT,
    contact_url TEXT,
    industry    TEXT,
    scraped_at  TEXT,
    UNIQUE(name, phone)
);
CREATE INDEX IF NOT EXISTS idx_leads_name  ON leads(name);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_city  ON leads(city);
"""

EXPORT_FIELDS = [
    'name', 'phone', 'email', 'platform', 'address', 'city', 'state',
    'website', 'category', 'rating', 'review_count', 'contact_url',
    'industry', 'scraped_at',
]


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock:
        c = _conn()
        c.executescript(SCHEMA)
        c.commit()
        c.close()


def _city_state(address: str) -> tuple:
    """Parse 'Street, City, ST ZIP, Country' → (city, state)."""
    if not address:
        return '', ''
    parts = [p.strip() for p in address.split(',')]
    if len(parts) >= 3:
        city = parts[-3] if len(parts) >= 3 else ''
        state_zip = parts[-2].strip().split()
        state = state_zip[0] if state_zip else ''
        return city, state
    return '', ''


def upsert(lead: dict) -> bool:
    """Insert or ignore duplicate (name+phone). Returns True if new."""
    city, state = _city_state(lead.get('address', ''))
    emails = lead.get('emails', [])
    email = emails[0] if emails else lead.get('email', '')

    row = {
        'name':         lead.get('title') or lead.get('name', ''),
        'phone':        lead.get('phone', ''),
        'email':        email,
        'platform':     lead.get('platform', ''),
        'address':      lead.get('address', ''),
        'city':         city,
        'state':        state,
        'website':      lead.get('website', ''),
        'category':     lead.get('category', ''),
        'rating':       lead.get('review_rating', ''),
        'review_count': lead.get('review_count', ''),
        'latitude':     lead.get('latitude', ''),
        'longitude':    lead.get('longitude', ''),
        'contact_url':  lead.get('contact_url', ''),
        'industry':     lead.get('industry', ''),
        'scraped_at':   lead.get('scraped_at') or datetime.now().isoformat(),
    }

    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                """INSERT OR IGNORE INTO leads
                   (name,phone,email,platform,address,city,state,website,
                    category,rating,review_count,latitude,longitude,
                    contact_url,industry,scraped_at)
                   VALUES
                   (:name,:phone,:email,:platform,:address,:city,:state,:website,
                    :category,:rating,:review_count,:latitude,:longitude,
                    :contact_url,:industry,:scraped_at)""",
                row
            )
            inserted = cur.rowcount > 0
            c.commit()
            return inserted
        finally:
            c.close()


def count() -> int:
    with _lock:
        c = _conn()
        try:
            return c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        finally:
            c.close()


def get_all(search: str = '', limit: int = 5000) -> list:
    """Return leads as list of dicts, optionally filtered by search term."""
    with _lock:
        c = _conn()
        try:
            if search:
                q = f'%{search}%'
                rows = c.execute(
                    """SELECT * FROM leads
                       WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
                          OR city LIKE ? OR platform LIKE ?
                       ORDER BY id DESC LIMIT ?""",
                    (q, q, q, q, q, limit)
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def export_csv(path: str) -> int:
    """Write all leads to a CSV file. Returns row count."""
    rows = get_all(limit=1_000_000)
    if not rows:
        return 0
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# Auto-init on import
init()
