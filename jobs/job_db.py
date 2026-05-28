"""
Job queue for the USA-wide scrape.
Stored at ~/AppData/Local/LeadScraperPro/jobs.db
"""
import sqlite3
import threading
from pathlib import Path
from datetime import datetime

_DB_DIR = Path.home() / "AppData" / "Local" / "LeadScraperPro"
_DB_DIR.mkdir(parents=True, exist_ok=True)
JOB_DB_PATH = _DB_DIR / "jobs.db"

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    city          TEXT    NOT NULL,
    state_abbr    TEXT    NOT NULL,
    state_name    TEXT    NOT NULL,
    county        TEXT,
    latitude      TEXT,
    longitude     TEXT,
    status        TEXT    NOT NULL DEFAULT 'pending',
    leads_found   INTEGER DEFAULT 0,
    started_at    TEXT,
    completed_at  TEXT,
    error         TEXT,
    UNIQUE(city, state_abbr)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_state  ON jobs(state_abbr);
"""


def _conn():
    c = sqlite3.connect(JOB_DB_PATH, check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    with _lock:
        c = _conn()
        c.executescript(SCHEMA)
        c.commit()
        c.close()


def seed(cities: list[dict]) -> int:
    """Insert cities into job queue (skip duplicates). Returns count inserted."""
    inserted = 0
    with _lock:
        c = _conn()
        for city in cities:
            try:
                c.execute(
                    """INSERT OR IGNORE INTO jobs
                       (city, state_abbr, state_name, county, latitude, longitude)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (city["city"], city["state_abbr"], city["state_name"],
                     city.get("county", ""), city.get("latitude", ""),
                     city.get("longitude", ""))
                )
                if c.lastrowid:
                    inserted += 1
            except Exception:
                pass
        c.commit()
        c.close()
    return inserted


def claim_next(worker_id: str = "") -> dict | None:
    """Atomically claim the next pending job. Returns job dict or None."""
    with _lock:
        c = _conn()
        try:
            row = c.execute(
                "SELECT * FROM jobs WHERE status='pending' ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            c.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE id=?",
                (datetime.now().isoformat(), row["id"])
            )
            c.commit()
            return dict(row)
        finally:
            c.close()


def mark_done(job_id: int, leads_found: int = 0):
    with _lock:
        c = _conn()
        c.execute(
            "UPDATE jobs SET status='done', leads_found=?, completed_at=? WHERE id=?",
            (leads_found, datetime.now().isoformat(), job_id)
        )
        c.commit()
        c.close()


def mark_failed(job_id: int, error: str = ""):
    with _lock:
        c = _conn()
        c.execute(
            "UPDATE jobs SET status='failed', error=?, completed_at=? WHERE id=?",
            (str(error)[:500], datetime.now().isoformat(), job_id)
        )
        c.commit()
        c.close()


def reset_running():
    """Reset any jobs stuck in 'running' state (from a crash)."""
    with _lock:
        c = _conn()
        n = c.execute(
            "UPDATE jobs SET status='pending', started_at=NULL WHERE status='running'"
        ).rowcount
        c.commit()
        c.close()
    return n


def retry_failed():
    """Reset all failed jobs back to pending."""
    with _lock:
        c = _conn()
        n = c.execute(
            "UPDATE jobs SET status='pending', error=NULL WHERE status='failed'"
        ).rowcount
        c.commit()
        c.close()
    return n


def stats() -> dict:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT status, COUNT(*) as n, SUM(leads_found) as leads "
                "FROM jobs GROUP BY status"
            ).fetchall()
            result = {r["status"]: {"count": r["n"], "leads": r["leads"] or 0} for r in rows}
            return result
        finally:
            c.close()


def recent_done(limit: int = 10) -> list:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT city, state_abbr, leads_found, completed_at FROM jobs "
                "WHERE status='done' ORDER BY completed_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


def top_cities_by_leads(limit: int = 20) -> list:
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT city, state_abbr, leads_found FROM jobs "
                "WHERE status='done' ORDER BY leads_found DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()


init()
