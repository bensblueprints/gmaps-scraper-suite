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
    phone_type  TEXT    DEFAULT '',
    carrier     TEXT    DEFAULT '',
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
    enriched         INTEGER DEFAULT 0,
    social_enriched  INTEGER DEFAULT 0,
    facebook    TEXT    DEFAULT '',
    instagram   TEXT    DEFAULT '',
    twitter     TEXT    DEFAULT '',
    linkedin    TEXT    DEFAULT '',
    tiktok      TEXT    DEFAULT '',
    youtube     TEXT    DEFAULT '',
    pinterest   TEXT    DEFAULT '',
    socials     TEXT    DEFAULT '',
    fb_followers  TEXT  DEFAULT '',
    ig_followers  TEXT  DEFAULT '',
    tw_followers  TEXT  DEFAULT '',
    li_followers  TEXT  DEFAULT '',
    tt_followers  TEXT  DEFAULT '',
    yt_subscribers TEXT DEFAULT '',
    pin_followers TEXT  DEFAULT '',
    UNIQUE(name, phone)
);
CREATE INDEX IF NOT EXISTS idx_leads_name     ON leads(name);
CREATE INDEX IF NOT EXISTS idx_leads_phone    ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_city     ON leads(city);
CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry);

CREATE TABLE IF NOT EXISTS lead_stages (
    lead_id    INTEGER PRIMARY KEY,
    stage      TEXT    DEFAULT 'New Lead',
    notes      TEXT    DEFAULT '',
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id    INTEGER,
    lead_name  TEXT,
    lead_phone TEXT,
    type       TEXT,
    subject    TEXT,
    body       TEXT,
    status     TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_conv_lead ON conversations(lead_id);
CREATE INDEX IF NOT EXISTS idx_conv_type ON conversations(type);
"""

EXPORT_FIELDS = [
    'name', 'phone', 'email', 'platform', 'address', 'city', 'state',
    'website', 'category', 'rating', 'review_count', 'contact_url',
    'industry', 'scraped_at',
    'facebook', 'instagram', 'twitter', 'linkedin', 'tiktok', 'youtube', 'pinterest',
    'fb_followers', 'ig_followers', 'tw_followers', 'li_followers',
    'tt_followers', 'yt_subscribers', 'pin_followers',
]


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock:
        c = _conn()
        c.executescript(SCHEMA)
        _migrations = [
            ("phone_type",      "TEXT",    "''"),
            ("carrier",         "TEXT",    "''"),
            ("enriched",        "INTEGER", "0"),
            ("social_enriched", "INTEGER", "0"),
            ("facebook",        "TEXT",    "''"),
            ("instagram",       "TEXT",    "''"),
            ("twitter",         "TEXT",    "''"),
            ("linkedin",        "TEXT",    "''"),
            ("tiktok",          "TEXT",    "''"),
            ("youtube",         "TEXT",    "''"),
            ("pinterest",       "TEXT",    "''"),
            ("socials",         "TEXT",    "''"),
            ("fb_followers",    "TEXT",    "''"),
            ("ig_followers",    "TEXT",    "''"),
            ("tw_followers",    "TEXT",    "''"),
            ("li_followers",    "TEXT",    "''"),
            ("tt_followers",    "TEXT",    "''"),
            ("yt_subscribers",  "TEXT",    "''"),
            ("pin_followers",   "TEXT",    "''"),
        ]
        for col, typ, defval in _migrations:
            try:
                c.execute(f"ALTER TABLE leads ADD COLUMN {col} {typ} DEFAULT {defval}")
            except Exception:
                pass
        c.commit()
        c.close()


def _city_state(address: str) -> tuple:
    if not address:
        return '', ''
    parts = [p.strip() for p in address.split(',')]
    if len(parts) >= 3:
        city = parts[-3] if len(parts) >= 3 else ''
        state_zip = parts[-2].strip().split()
        state = state_zip[0] if state_zip else ''
        return city, state
    return '', ''


def insert_raw(lead: dict) -> bool:
    """Insert a raw (pre-enrichment) lead. Skips if name+phone already exists."""
    city_parsed, state = _city_state(lead.get('address', ''))
    city = lead.get('scraped_city', '') or city_parsed
    row = {
        'name':         lead.get('title') or lead.get('name', ''),
        'phone':        lead.get('phone', ''),
        'address':      lead.get('address', ''),
        'city':         city,
        'state':        state,
        'website':      lead.get('website', ''),
        'category':     lead.get('category', ''),
        'rating':       lead.get('review_rating', ''),
        'review_count': lead.get('review_count', ''),
        'latitude':     lead.get('latitude', ''),
        'longitude':    lead.get('longitude', ''),
        'industry':     lead.get('industry', ''),
        'scraped_at':   lead.get('scraped_at') or datetime.now().isoformat(),
    }
    with _lock:
        c = _conn()
        try:
            cur = c.execute(
                """INSERT OR IGNORE INTO leads
                   (name,phone,address,city,state,website,category,rating,
                    review_count,latitude,longitude,industry,scraped_at,enriched)
                   VALUES
                   (:name,:phone,:address,:city,:state,:website,:category,:rating,
                    :review_count,:latitude,:longitude,:industry,:scraped_at,0)""",
                row
            )
            inserted = cur.rowcount > 0
            c.commit()
            return inserted
        finally:
            c.close()


def update_enrichment(lead: dict) -> None:
    """Update enrichment fields (email, platform, phone_type, etc.) for an existing lead."""
    name  = lead.get('title') or lead.get('name', '')
    phone = lead.get('phone', '')
    emails = lead.get('emails', [])
    email  = emails[0] if emails else lead.get('email', '')
    with _lock:
        c = _conn()
        try:
            c.execute(
                """UPDATE leads SET
                   email = CASE WHEN ? != '' THEN ? ELSE email END,
                   platform = CASE WHEN ? != '' THEN ? ELSE platform END,
                   phone_type = CASE WHEN ? != '' THEN ? ELSE phone_type END,
                   carrier = CASE WHEN ? != '' THEN ? ELSE carrier END,
                   contact_url = CASE WHEN ? != '' THEN ? ELSE contact_url END,
                   enriched = 1
                   WHERE name = ? AND phone = ?""",
                (
                    email, email,
                    lead.get('platform', ''), lead.get('platform', ''),
                    lead.get('phone_type', ''), lead.get('phone_type', ''),
                    lead.get('carrier', ''), lead.get('carrier', ''),
                    lead.get('contact_url', ''), lead.get('contact_url', ''),
                    name, phone,
                )
            )
            c.commit()
        finally:
            c.close()


def get_unenriched(limit: int = 2000) -> list:
    """Return leads that have a website but haven't been enriched yet."""
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                """SELECT * FROM leads
                   WHERE website != '' AND website IS NOT NULL AND enriched = 0
                   ORDER BY id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def count_unenriched() -> int:
    with _lock:
        c = _conn()
        try:
            return c.execute(
                "SELECT COUNT(*) FROM leads WHERE website != '' AND website IS NOT NULL AND enriched = 0"
            ).fetchone()[0]
        finally:
            c.close()


def get_social_unenriched(limit: int = 2000) -> list:
    """Return leads that have a website but haven't had social enrichment yet."""
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                """SELECT * FROM leads
                   WHERE website != '' AND website IS NOT NULL AND social_enriched = 0
                   ORDER BY id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def count_social_unenriched() -> int:
    with _lock:
        c = _conn()
        try:
            return c.execute(
                "SELECT COUNT(*) FROM leads WHERE website != '' AND website IS NOT NULL AND social_enriched = 0"
            ).fetchone()[0]
        finally:
            c.close()


def update_social(lead: dict) -> None:
    """Update social media fields and follower counts for an existing lead."""
    name  = lead.get('title') or lead.get('name', '')
    phone = lead.get('phone', '')
    with _lock:
        c = _conn()
        try:
            c.execute(
                """UPDATE leads SET
                   facebook     = CASE WHEN ? != '' THEN ? ELSE facebook     END,
                   instagram    = CASE WHEN ? != '' THEN ? ELSE instagram    END,
                   twitter      = CASE WHEN ? != '' THEN ? ELSE twitter      END,
                   linkedin     = CASE WHEN ? != '' THEN ? ELSE linkedin     END,
                   tiktok       = CASE WHEN ? != '' THEN ? ELSE tiktok       END,
                   youtube      = CASE WHEN ? != '' THEN ? ELSE youtube      END,
                   pinterest    = CASE WHEN ? != '' THEN ? ELSE pinterest    END,
                   socials      = ?,
                   fb_followers  = CASE WHEN ? != '' THEN ? ELSE fb_followers  END,
                   ig_followers  = CASE WHEN ? != '' THEN ? ELSE ig_followers  END,
                   tw_followers  = CASE WHEN ? != '' THEN ? ELSE tw_followers  END,
                   li_followers  = CASE WHEN ? != '' THEN ? ELSE li_followers  END,
                   tt_followers  = CASE WHEN ? != '' THEN ? ELSE tt_followers  END,
                   yt_subscribers = CASE WHEN ? != '' THEN ? ELSE yt_subscribers END,
                   pin_followers = CASE WHEN ? != '' THEN ? ELSE pin_followers END,
                   social_enriched = 1
                   WHERE name = ? AND phone = ?""",
                (
                    lead.get('facebook',  ''), lead.get('facebook',  ''),
                    lead.get('instagram', ''), lead.get('instagram', ''),
                    lead.get('twitter',   ''), lead.get('twitter',   ''),
                    lead.get('linkedin',  ''), lead.get('linkedin',  ''),
                    lead.get('tiktok',    ''), lead.get('tiktok',    ''),
                    lead.get('youtube',   ''), lead.get('youtube',   ''),
                    lead.get('pinterest', ''), lead.get('pinterest', ''),
                    lead.get('socials',   ''),
                    lead.get('fb_followers',   ''), lead.get('fb_followers',   ''),
                    lead.get('ig_followers',   ''), lead.get('ig_followers',   ''),
                    lead.get('tw_followers',   ''), lead.get('tw_followers',   ''),
                    lead.get('li_followers',   ''), lead.get('li_followers',   ''),
                    lead.get('tt_followers',   ''), lead.get('tt_followers',   ''),
                    lead.get('yt_subscribers', ''), lead.get('yt_subscribers', ''),
                    lead.get('pin_followers',  ''), lead.get('pin_followers',  ''),
                    name, phone,
                )
            )
            c.commit()
        finally:
            c.close()


def upsert(lead: dict) -> bool:
    city_parsed, state = _city_state(lead.get('address', ''))
    # Prefer the city the user searched for; fall back to address parsing
    city = lead.get('scraped_city', '') or city_parsed

    emails = lead.get('emails', [])
    email  = emails[0] if emails else lead.get('email', '')

    row = {
        'name':         lead.get('title') or lead.get('name', ''),
        'phone':        lead.get('phone', ''),
        'phone_type':   lead.get('phone_type', ''),
        'carrier':      lead.get('carrier', ''),
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
                   (name,phone,phone_type,carrier,email,platform,address,city,state,website,
                    category,rating,review_count,latitude,longitude,
                    contact_url,industry,scraped_at)
                   VALUES
                   (:name,:phone,:phone_type,:carrier,:email,:platform,:address,:city,:state,:website,
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


def get_all(search: str = '', industry: str = '', city: str = '', limit: int = 5000) -> list:
    with _lock:
        c = _conn()
        try:
            conditions = []
            params = []
            if search:
                q = f'%{search}%'
                conditions.append("(name LIKE ? OR phone LIKE ? OR email LIKE ? OR city LIKE ? OR platform LIKE ?)")
                params.extend([q, q, q, q, q])
            if industry:
                conditions.append("industry = ?")
                params.append(industry)
            if city:
                conditions.append("city LIKE ?")
                params.append(f'%{city}%')
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params.append(limit)
            rows = c.execute(
                f"SELECT * FROM leads {where} ORDER BY id DESC LIMIT ?", params
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def get_distinct_industries() -> list:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT DISTINCT industry FROM leads WHERE industry != '' ORDER BY industry"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            c.close()


def get_distinct_cities() -> list:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT DISTINCT city FROM leads WHERE city != '' ORDER BY city"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            c.close()


def export_csv(path: str, industry: str = '', city: str = '') -> int:
    rows = get_all(industry=industry, city=city, limit=1_000_000)
    if not rows:
        return 0
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def get_by_industry(industry: str) -> list:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT * FROM leads WHERE industry = ? ORDER BY id DESC", (industry,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def export_industry_csv(industry: str, path: str) -> int:
    with _lock:
        c = _conn()
        try:
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM leads WHERE industry = ? ORDER BY id DESC", (industry,)
            ).fetchall()]
        finally:
            c.close()
    if not rows:
        return 0
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ── Pipeline / Kanban ──────────────────────────────────────────────────────────

def get_lead_stage(lead_id: int) -> str:
    with _lock:
        c = _conn()
        try:
            row = c.execute("SELECT stage FROM lead_stages WHERE lead_id = ?", (lead_id,)).fetchone()
            return row[0] if row else "New Lead"
        finally:
            c.close()


def set_lead_stage(lead_id: int, stage: str, notes: str = ''):
    with _lock:
        c = _conn()
        try:
            c.execute(
                """INSERT INTO lead_stages (lead_id, stage, notes, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(lead_id) DO UPDATE SET stage=excluded.stage,
                   notes=excluded.notes, updated_at=excluded.updated_at""",
                (lead_id, stage, notes, datetime.now().isoformat())
            )
            c.commit()
        finally:
            c.close()


def get_leads_by_stage(stage: str, limit: int = 100) -> list:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                """SELECT l.*, COALESCE(s.stage, 'New Lead') as stage, COALESCE(s.notes,'') as notes
                   FROM leads l
                   LEFT JOIN lead_stages s ON s.lead_id = l.id
                   WHERE COALESCE(s.stage, 'New Lead') = ?
                   ORDER BY l.id DESC LIMIT ?""",
                (stage, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def get_stage_counts(stages: list) -> dict:
    with _lock:
        c = _conn()
        try:
            counts = {}
            for stage in stages:
                n = c.execute(
                    """SELECT COUNT(*) FROM leads l
                       LEFT JOIN lead_stages s ON s.lead_id = l.id
                       WHERE COALESCE(s.stage, 'New Lead') = ?""",
                    (stage,)
                ).fetchone()[0]
                counts[stage] = n
            return counts
        finally:
            c.close()


# ── Conversations ──────────────────────────────────────────────────────────────

def log_conversation(lead_id: int, lead_name: str, lead_phone: str,
                     conv_type: str, subject: str, body: str, status: str):
    with _lock:
        c = _conn()
        try:
            c.execute(
                """INSERT INTO conversations
                   (lead_id, lead_name, lead_phone, type, subject, body, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (lead_id, lead_name, lead_phone, conv_type,
                 subject, body, status, datetime.now().isoformat())
            )
            c.commit()
        finally:
            c.close()


def get_conversations(lead_id: int = None, limit: int = 500) -> list:
    with _lock:
        c = _conn()
        try:
            if lead_id:
                rows = c.execute(
                    "SELECT * FROM conversations WHERE lead_id=? ORDER BY created_at DESC LIMIT ?",
                    (lead_id, limit)
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def get_conversation_leads(limit: int = 200) -> list:
    """Distinct leads that have conversations, most recent first."""
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                """SELECT DISTINCT lead_id, lead_name, lead_phone,
                   MAX(created_at) as last_contact
                   FROM conversations
                   GROUP BY lead_id
                   ORDER BY last_contact DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


# Auto-init on import
init()
