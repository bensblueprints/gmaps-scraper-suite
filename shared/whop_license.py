"""
Whop online license client.

Talks to the license backend (Netlify Functions) which proxies Whop's
validate_license API, binds the device, ingests purchase webhooks, and owns the
DB. This replaces the offline embedded-hash check for Whop-enabled builds.

App usage:
    import whop_license
    whop_license.configure("AtomicScraper", APP_DATA_DIR)  # once at startup
    res = whop_license.check()          # on launch: {"ok": bool, "tier": "paid"|"free"}
    res = whop_license.activate(key)    # when user clicks Activate

Only stdlib is used (urllib) so nothing extra needs bundling.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

# Stable per-machine id (works whether imported as machine_id or shared.machine_id).
try:
    from machine_id import get_machine_id
except Exception:  # pragma: no cover
    try:
        from shared.machine_id import get_machine_id
    except Exception:
        import hashlib, platform, uuid
        def get_machine_id() -> str:
            raw = f"{platform.node()}|{uuid.getnode()}|{platform.machine()}"
            return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

# Public backend base URL. Override via env or configure(api_base=...).
# Filled in after the backend is deployed (Netlify site URL).
LICENSE_API_BASE = os.environ.get("LICENSE_API_BASE", "https://hub.atomicscraper.com").rstrip("/")

_TIMEOUT = 15
_PRODUCT = "Unknown"
_STORE = Path.home() / ".whop_license.json"


def configure(product: str, storage_dir, api_base: str = None) -> None:
    """Set the product id, where to cache the license, and (optionally) the API base."""
    global _PRODUCT, _STORE, LICENSE_API_BASE
    _PRODUCT = product
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    _STORE = storage_dir / "whop_license.json"
    if api_base:
        LICENSE_API_BASE = api_base.rstrip("/")


def normalize_key(key: str) -> str:
    """Normalize Whop key formats (W-XXXXXX-XXXXXXXX-XXXXXXXW and WT-...)."""
    cleaned = re.sub(r"[^A-Z0-9]", "", key.upper())
    if cleaned.startswith("WT") and len(cleaned) == 18:
        b = cleaned[2:]
        return f"WT-{b[0:4]}-{b[4:8]}-{b[8:12]}-{b[12:16]}"
    if cleaned.startswith("W") and cleaned.endswith("W") and len(cleaned) == 22:
        return f"W-{cleaned[1:7]}-{cleaned[7:15]}-{cleaned[15:22]}"
    return key.strip().upper()


def _post(path: str, payload: dict):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{LICENSE_API_BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": f"network_error: {e}"}


def _save(rec: dict) -> None:
    try:
        _STORE.write_text(json.dumps(rec), encoding="utf-8")
    except Exception:
        pass


def _load() -> dict:
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def activate(key: str) -> dict:
    """Activate a Whop key on this machine. Returns {"ok", "tier"} or {"ok": False, "error"}."""
    key = normalize_key(key)
    status, body = _post("/api/license/activate", {
        "key": key, "deviceId": get_machine_id(), "product": _PRODUCT,
    })
    if status in (200, 201) and body.get("ok"):
        _save({"key": key, "token": body.get("token", ""),
               "tier": body.get("tier", "paid"), "email": body.get("email", "")})
        return {"ok": True, "tier": body.get("tier", "paid")}
    return {"ok": False, "error": body.get("error", f"activation_failed_{status}")}


def check() -> dict:
    """Re-validate the cached license on launch."""
    rec = _load()
    if not rec.get("key"):
        return {"ok": False, "error": "no_license"}
    status, body = _post("/api/license/verify", {
        "key": rec["key"], "token": rec.get("token", ""),
        "deviceId": get_machine_id(), "product": _PRODUCT,
    })
    if status in (200, 201) and body.get("ok"):
        rec["tier"] = body.get("tier", rec.get("tier", "paid"))
        _save(rec)
        return {"ok": True, "tier": rec["tier"]}
    # Hard-invalid: refunded / wrong device / unknown key -> drop the cached license.
    hard = {"license_refunded", "device_mismatch", "invalid_key", "revoked"}
    if status in (401, 403, 404) or body.get("error") in hard:
        try:
            _STORE.unlink()
        except Exception:
            pass
        return {"ok": False, "error": body.get("error", "invalid")}
    # Backend unreachable -> offline grace using the last good token.
    return {"ok": bool(rec.get("token")), "tier": rec.get("tier", "paid"), "offline": True}


def clear() -> None:
    try:
        _STORE.unlink()
    except Exception:
        pass
