"""API key generation, validation and management (stored in SQLite)."""
import hashlib
import secrets
import sqlite3
from pathlib import Path

_DB_PATH: Path = Path.home() / "AppData" / "Local" / "LeadScraperPro" / "api_keys.db"


def set_db_path(path: Path):
    global _DB_PATH
    _DB_PATH = path


def _conn():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                key_hash   TEXT    UNIQUE NOT NULL,
                key_prefix TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now')),
                last_used  TEXT,
                active     INTEGER DEFAULT 1
            )
        """)


def create_key(name: str) -> str:
    """Generate a new API key, store its hash, return the raw key (shown once)."""
    raw = "sk-" + secrets.token_urlsafe(32)
    h = hashlib.sha256(raw.encode()).hexdigest()
    with _conn() as c:
        c.execute(
            "INSERT INTO api_keys (name, key_hash, key_prefix) VALUES (?, ?, ?)",
            (name, h, raw[:12])
        )
    return raw


def validate_key(raw: str) -> bool:
    if not raw:
        return False
    h = hashlib.sha256(raw.encode()).hexdigest()
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM api_keys WHERE key_hash=? AND active=1", (h,)
        ).fetchone()
        if row:
            c.execute(
                "UPDATE api_keys SET last_used=datetime('now') WHERE key_hash=?", (h,)
            )
            return True
    return False


def list_keys() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, name, key_prefix, created_at, last_used, active "
            "FROM api_keys ORDER BY id DESC"
        )]


def revoke_key(key_id: int):
    with _conn() as c:
        c.execute("UPDATE api_keys SET active=0 WHERE id=?", (key_id,))


def delete_key(key_id: int):
    with _conn() as c:
        c.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
