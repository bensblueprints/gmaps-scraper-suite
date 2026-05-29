"""
FastAPI REST server — runs as a daemon thread inside the scraper app process.

Endpoints:
  GET  /health
  POST /api/scrape          → {job_id, status, poll_url}
  GET  /api/jobs/{job_id}   → {status, leads_found, log, result}
  GET  /api/leads           → [{...}]
  GET  /api/industries      → [{name, queries}]
  GET  /api/stats           → {total_leads, jobs_running}
"""
import os
import sys
import threading
import uuid
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scraper_node"))

_fastapi_app    = None
_uvicorn_server = None
_server_lock    = threading.Lock()
_jobs: dict     = {}
_jobs_lock      = threading.Lock()

# Injected by configure()
_validate_fn  = None
_lead_db_mod  = None
_engine_cls   = None
_industries   = None


def configure(validate_fn, lead_db_mod, engine_cls, industries_dict):
    """Call once from the app before start(). Injects dependencies."""
    global _validate_fn, _lead_db_mod, _engine_cls, _industries, _fastapi_app
    _validate_fn  = validate_fn
    _lead_db_mod  = lead_db_mod
    _engine_cls   = engine_cls
    _industries   = industries_dict
    _fastapi_app  = _build_app()


def is_running() -> bool:
    return _uvicorn_server is not None and not _uvicorn_server.should_exit


def get_port() -> int:
    return int(os.environ.get("SCRAPER_API_PORT", "7842"))


def start(port: Optional[int] = None):
    global _uvicorn_server
    port = port or get_port()
    try:
        import uvicorn
    except ImportError:
        return False, "uvicorn not installed — run: pip install fastapi uvicorn"
    if _fastapi_app is None:
        return False, "Call configure() before start()"
    with _server_lock:
        if is_running():
            return True, f"Already running on port {port}"
        cfg = uvicorn.Config(
            _fastapi_app, host="0.0.0.0", port=port,
            log_level="warning", access_log=False,
        )
        _uvicorn_server = uvicorn.Server(cfg)
        t = threading.Thread(target=_uvicorn_server.run, daemon=True)
        t.start()
    return True, f"API server started on http://localhost:{port}"


def stop():
    global _uvicorn_server
    with _server_lock:
        if _uvicorn_server:
            _uvicorn_server.should_exit = True
            _uvicorn_server = None
    return True, "API server stopped"


def _build_app():
    try:
        from fastapi import FastAPI, Header, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
    except ImportError:
        return None

    app = FastAPI(
        title="GMaps Scraper API", version="1.0.0",
        description="Scrape Google Maps leads via REST API",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    def _auth(key: str):
        if not _validate_fn(key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    class ScrapeRequest(BaseModel):
        industry: str
        location: str
        max_leads: int = 50
        page_workers: int = 2

    @app.get("/health")
    def health():
        return {
            "status":      "ok",
            "jobs_running": sum(1 for j in _jobs.values() if j["status"] == "running"),
        }

    @app.post("/api/scrape")
    def start_scrape(req: ScrapeRequest, x_api_key: str = Header(default="")):
        _auth(x_api_key)
        job_id = uuid.uuid4().hex[:8]
        with _jobs_lock:
            _jobs[job_id] = {"status": "running", "leads": 0, "log": [], "result": []}

        def _run():
            try:
                engine = _engine_cls()
                leads = []

                def _log(msg):
                    _jobs[job_id]["log"].append(msg)

                def _on_lead(lead):
                    leads.append(lead)
                    _jobs[job_id]["leads"] = len(leads)

                engine.log_callback = _log
                info    = _industries.get(req.industry, {})
                queries = (info.get("queries", [req.industry])
                           if isinstance(info, dict) else [req.industry])
                engine.run_industry(
                    industry_name=req.industry,
                    queries=queries,
                    location=req.location,
                    max_leads=req.max_leads,
                    page_workers=req.page_workers,
                    on_lead=_on_lead,
                )
                with _jobs_lock:
                    _jobs[job_id]["status"] = "done"
                    _jobs[job_id]["result"] = leads
            except Exception as e:
                with _jobs_lock:
                    _jobs[job_id]["status"] = "error"
                    _jobs[job_id]["log"].append(f"Error: {e}")

        threading.Thread(target=_run, daemon=True).start()
        return {"job_id": job_id, "status": "running",
                "poll_url": f"/api/jobs/{job_id}"}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, x_api_key: str = Header(default="")):
        _auth(x_api_key)
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id":      job_id,
            "status":      job["status"],
            "leads_found": job["leads"],
            "log":         job["log"][-20:],
            "result":      job.get("result", []),
        }

    @app.get("/api/leads")
    def get_leads(
        industry: str = "", city: str = "", limit: int = 100,
        x_api_key: str = Header(default=""),
    ):
        _auth(x_api_key)
        return _lead_db_mod.get_all(industry=industry, city=city, limit=limit)

    @app.get("/api/industries")
    def get_industries(q: str = "", x_api_key: str = Header(default="")):
        _auth(x_api_key)
        items = list(_industries.items())
        if q:
            ql = q.lower()
            items = [(n, v) for n, v in items if ql in n.lower()]
        return [
            {
                "name":    n,
                "queries": (v.get("queries", [n]) if isinstance(v, dict) else [n]),
            }
            for n, v in items[:100]
        ]

    @app.get("/api/stats")
    def get_stats(x_api_key: str = Header(default="")):
        _auth(x_api_key)
        return {
            "total_leads":  _lead_db_mod.count(),
            "jobs_running": sum(1 for j in _jobs.values() if j["status"] == "running"),
            "jobs_total":   len(_jobs),
        }

    return app
