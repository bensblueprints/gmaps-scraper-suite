"""
Lead Scraper Pro — desktop scraper + CRM application.
"""
import re
import sys
import json
import smtplib
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parent.parent))
    sys.path.insert(0, str(Path(__file__).parent))

try:
    import customtkinter as ctk
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from engine import ScraperEngine
from industries import INDUSTRIES
from shared import lead_db
from shared.machine_id import get_machine_id
from shared.cities import get_cities, CITY_COUNTS

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

import logging
import traceback

PRODUCT_NAME  = "Lead Scraper Pro"
PRODUCT_COLOR = "#4FC3F7"
LEADS_FOLDER  = "LeadScraperPro Leads"
APP_DATA_DIR  = Path.home() / "AppData" / "Local" / "LeadScraperPro"
LICENSE_FILE  = APP_DATA_DIR / "license.txt"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE      = APP_DATA_DIR / "debug.log"
MACHINE_ID    = get_machine_id()

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

ALL_INDUSTRY_NAMES = list(INDUSTRIES.keys())

DEFAULT_PIPELINE = ["New Lead", "Contacted", "Interested", "Proposal Sent", "Won", "Lost"]

TABLE_COLS = [
    ("Name",      "name",           220),
    ("Phone",     "phone",          120),
    ("Ph.Type",   "phone_type",      72),
    ("Email",     "email",          180),
    ("Platform",  "platform",       110),
    ("Rating",    "rating",          55),
    ("Reviews",   "review_count",    65),
    ("City",      "city",           110),
    ("State",     "state",           50),
    ("Industry",  "industry",       130),
    ("Website",   "website",        180),
    # ── Social media ──────────────────────────────
    ("Facebook",  "facebook",       180),
    ("FB Fans",   "fb_followers",    75),
    ("Instagram", "instagram",      180),
    ("IG Fans",   "ig_followers",    75),
    ("Twitter",   "twitter",        180),
    ("TW Fans",   "tw_followers",    75),
    ("LinkedIn",  "linkedin",       200),
    ("LI Fans",   "li_followers",    75),
    ("TikTok",    "tiktok",         180),
    ("TT Fans",   "tt_followers",    75),
    ("YouTube",   "youtube",        200),
    ("YT Subs",   "yt_subscribers",  75),
    ("Pinterest", "pinterest",      180),
    ("PIN Fans",  "pin_followers",   75),
]


# ── Settings helpers ──────────────────────────────────────────────────────────

def load_settings() -> dict:
    defaults = {
        "twilio": {"account_sid": "", "auth_token": "", "from_number": "", "your_number": ""},
        "smtp": {"host": "", "port": "587", "username": "", "password": "",
                 "from_name": "", "from_email": "", "use_tls": True},
        "pipeline_stages": DEFAULT_PIPELINE[:],
    }
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text())
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        pass
    return defaults


def save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))


def _apply_treeview_style():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Treeview",
        background="#1A1A2E", foreground="#C9D1D9",
        fieldbackground="#1A1A2E", rowheight=24,
        font=("Segoe UI", 10))
    s.configure("Treeview.Heading",
        background="#252540", foreground="#78909C",
        relief="flat", font=("Segoe UI", 10, "bold"))
    s.map("Treeview",
        background=[("selected", "#2D4A6E")],
        foreground=[("selected", "#FFFFFF")])


# ── CRM actions ───────────────────────────────────────────────────────────────

def crm_call(lead: dict, settings: dict):
    tw = settings.get("twilio", {})
    missing = [k for k in ("account_sid", "auth_token", "from_number", "your_number") if not tw.get(k)]
    if missing:
        messagebox.showerror("Twilio Not Configured",
                             "Go to the Settings tab and fill in your Twilio credentials.")
        return
    phone = lead.get("phone", "")
    if not phone:
        messagebox.showwarning("No Phone", f"{lead.get('name','Lead')} has no phone number.")
        return
    def _do():
        try:
            from twilio.rest import Client
            client = Client(tw["account_sid"], tw["auth_token"])
            twiml = f'<Response><Say>Connecting your call.</Say><Dial>{phone}</Dial></Response>'
            call = client.calls.create(to=tw["your_number"], from_=tw["from_number"], twiml=twiml)
            lead_db.log_conversation(
                lead_id=lead.get("id", 0), lead_name=lead.get("name", ""),
                lead_phone=phone, conv_type="call",
                subject=f"Call to {lead.get('name','')}",
                body=f"SID: {call.sid}", status="initiated",
            )
            messagebox.showinfo("Calling",
                f"Your phone ({tw['your_number']}) will ring.\n"
                f"Answer to be connected to:\n{lead.get('name','')} — {phone}")
        except Exception as e:
            messagebox.showerror("Call Failed", str(e))
    threading.Thread(target=_do, daemon=True).start()


def crm_email_dialog(lead: dict, settings: dict, parent):
    smtp = settings.get("smtp", {})
    win = tk.Toplevel(parent)
    win.title(f"Email — {lead.get('name','')}")
    win.configure(bg="#0D0D1A")
    win.geometry("560x420")
    win.grab_set()

    def lbl(t): return ctk.CTkLabel(win, text=t, font=ctk.CTkFont(size=11), text_color="#9E9E9E")

    lbl("To:").pack(anchor="w", padx=16, pady=(12,0))
    to_var = tk.StringVar(value=lead.get("email", ""))
    ctk.CTkEntry(win, textvariable=to_var, height=28).pack(fill="x", padx=16)

    lbl("Subject:").pack(anchor="w", padx=16, pady=(6,0))
    subj_var = tk.StringVar(value=f"Following up — {lead.get('name','')}")
    ctk.CTkEntry(win, textvariable=subj_var, height=28).pack(fill="x", padx=16)

    lbl("Message:").pack(anchor="w", padx=16, pady=(6,0))
    body_box = ctk.CTkTextbox(win, font=ctk.CTkFont(size=11), height=200, fg_color="#1A1A2E")
    body_box.pack(fill="both", padx=16, expand=True)

    def _send():
        to_addr = to_var.get().strip()
        subj    = subj_var.get().strip()
        body    = body_box.get("1.0", "end").strip()
        if not to_addr:
            messagebox.showwarning("No Email", "Enter a recipient email.", parent=win)
            return
        missing = [k for k in ("host", "username", "password", "from_email") if not smtp.get(k)]
        if missing:
            messagebox.showerror("SMTP Not Configured",
                                 "Go to Settings tab and fill in SMTP credentials.", parent=win)
            return
        def _do():
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subj
                msg["From"] = f"{smtp.get('from_name','')} <{smtp['from_email']}>"
                msg["To"] = to_addr
                msg.attach(MIMEText(body, "plain"))
                port = int(smtp.get("port", 587))
                if smtp.get("use_tls", True):
                    srv = smtplib.SMTP(smtp["host"], port, timeout=15)
                    srv.starttls()
                else:
                    srv = smtplib.SMTP_SSL(smtp["host"], port, timeout=15)
                srv.login(smtp["username"], smtp["password"])
                srv.sendmail(smtp["from_email"], to_addr, msg.as_string())
                srv.quit()
                lead_db.log_conversation(
                    lead_id=lead.get("id", 0), lead_name=lead.get("name", ""),
                    lead_phone=lead.get("phone", ""), conv_type="email",
                    subject=subj, body=body, status="sent",
                )
                win.after(0, lambda: [messagebox.showinfo("Sent", "Email sent!", parent=win), win.destroy()])
            except Exception as e:
                win.after(0, lambda: messagebox.showerror("Failed", str(e), parent=win))
        threading.Thread(target=_do, daemon=True).start()

    bf = ctk.CTkFrame(win, fg_color="transparent")
    bf.pack(fill="x", padx=16, pady=8)
    ctk.CTkButton(bf, text="Send", fg_color="#27AE60", hover_color="#1E8449",
                  command=_send).pack(side="right", padx=(4,0))
    ctk.CTkButton(bf, text="Cancel", fg_color="transparent", border_width=1,
                  command=win.destroy).pack(side="right")


# ─────────────────────────────────────────────────────────────────────────────
# License bar
# ─────────────────────────────────────────────────────────────────────────────

# ── License validation ────────────────────────────────────────────────────────

_LICENSE_HASHES: frozenset = None


def _load_license_hashes() -> frozenset:
    global _LICENSE_HASHES
    if _LICENSE_HASHES is not None:
        return _LICENSE_HASHES
    try:
        from license_hashes import VALID_HASHES
        _LICENSE_HASHES = VALID_HASHES
    except ImportError:
        _LICENSE_HASHES = frozenset()
    return _LICENSE_HASHES


def _is_whop_key(key: str) -> bool:
    import re
    return bool(re.match(r'^W-[A-Z0-9]{6}-[A-Z0-9]{8}-[A-Z0-9]{7}W$', key.upper().strip()))


def _validate_license_key(key: str) -> bool:
    normalized = key.upper().strip()
    if _is_whop_key(normalized):
        # Online Whop validation via backend
        try:
            from shared import whop_license
        except Exception:
            import whop_license  # frozen: shared dir is on sys.path
        whop_license.configure(APP_DATA_DIR.name, APP_DATA_DIR)
        result = whop_license.activate(normalized)
        if result.get("ok"):
            return True
        if result.get("error") == "network_error":
            # Network down — fall back to cached hash
            import hashlib
            h = hashlib.sha256(f"{APP_DATA_DIR.name}:{normalized}".encode()).hexdigest()
            return h in _load_license_hashes()
        return False
    # Local hash key (non-Whop products)
    import hashlib
    h = hashlib.sha256(f"{APP_DATA_DIR.name}:{normalized}".encode()).hexdigest()
    return h in _load_license_hashes()


class LicenseBar(ctk.CTkFrame):
    def __init__(self, parent, on_activate, **kw):
        super().__init__(parent, height=46, fg_color="#0A0A18", corner_radius=0, **kw)
        self.grid_propagate(False)
        self.on_activate = on_activate

        ctk.CTkLabel(self, text=PRODUCT_NAME,
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=PRODUCT_COLOR).pack(side="left", padx=14)

        self.status_lbl = ctk.CTkLabel(self, text="Enter license key to unlock",
                                       font=ctk.CTkFont(size=11), text_color="#616161")
        self.status_lbl.pack(side="left", padx=4)

        self.activate_btn = ctk.CTkButton(
            self, text="Activate", width=80, height=28,
            font=ctk.CTkFont(size=11), command=self._do_activate)
        self.activate_btn.pack(side="right", padx=4)

        self.key_entry = ctk.CTkEntry(
            self, placeholder_text="XXXX-XXXX-XXXX-XXXX", width=220, height=28,
            font=ctk.CTkFont(size=11, family="Courier New"))
        self.key_entry.pack(side="right", padx=4)
        self.key_entry.bind("<Return>", lambda e: self._do_activate())

        # On startup: check cached license (fast, uses saved token)
        if LICENSE_FILE.exists():
            saved = LICENSE_FILE.read_text().strip()
            if saved:
                self.key_entry.insert(0, saved)
                self.after(100, self._check_saved)

    def _mark_licensed(self, offline: bool = False):
        label = "  Licensed (offline)" if offline else "  Licensed"
        self.status_lbl.configure(text=label, text_color="#27AE60")
        self.activate_btn.configure(text="Active", fg_color="#27AE60",
                                    hover_color="#1E8449", state="disabled")
        self.key_entry.configure(state="disabled")
        self.on_activate(True)

    def _check_saved(self):
        saved = LICENSE_FILE.read_text().strip() if LICENSE_FILE.exists() else ""
        if not saved:
            return
        if _is_whop_key(saved):
            # Whop key: use cached token check (fast, offline-capable)
            try:
                from shared import whop_license
            except Exception:
                import whop_license
            whop_license.configure(APP_DATA_DIR.name, APP_DATA_DIR)
            result = whop_license.check()
            if result.get("ok"):
                self._mark_licensed(offline=result.get("offline", False))
                return
            # Token invalid / revoked — clear cached license
            try:
                whop_license.clear()
                LICENSE_FILE.unlink()
            except Exception:
                pass
            self.key_entry.configure(state="normal")
            self.key_entry.delete(0, "end")
            self.status_lbl.configure(text="License expired — re-enter key", text_color="#E74C3C")
            self.on_activate(False)
        else:
            # Local hash key: validate instantly (no network needed)
            if _validate_license_key(saved):
                self._mark_licensed()
            else:
                try:
                    LICENSE_FILE.unlink()
                except Exception:
                    pass
                self.key_entry.configure(state="normal")
                self.key_entry.delete(0, "end")
                self.on_activate(False)

    def _do_activate(self):
        key = self.key_entry.get().strip()
        if not key:
            return
        if _validate_license_key(key):
            LICENSE_FILE.write_text(key)
            self._mark_licensed()
        else:
            self.status_lbl.configure(text="  Invalid key", text_color="#E74C3C")
            self.on_activate(False)


# ─────────────────────────────────────────────────────────────────────────────
# Left panel (scraper controls)
# ─────────────────────────────────────────────────────────────────────────────

class LeftPanel(ctk.CTkFrame):
    def __init__(self, parent, on_start, on_stop, on_reenrich=None, on_social_enrich=None, **kw):
        super().__init__(parent, width=300, corner_radius=0, fg_color="#12121E", **kw)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._on_start         = on_start
        self._on_stop          = on_stop
        self._on_reenrich      = on_reenrich
        self._on_social_enrich = on_social_enrich
        self._filtered         = ALL_INDUSTRY_NAMES[:]

        self._build_industry_header()
        self._build_industry_list()
        self._build_config()
        self._build_buttons()

    def _build_industry_header(self):
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=0, column=0, sticky="ew", padx=8, pady=(10, 2))
        box.columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(box, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="INDUSTRIES",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#78909C").pack(side="left")
        ctk.CTkButton(hdr, text="None", width=44, height=22, font=ctk.CTkFont(size=10),
                      command=lambda: self._lb.select_clear(0, tk.END)
                      ).pack(side="right", padx=(2, 0))
        ctk.CTkButton(hdr, text="All", width=36, height=22, font=ctk.CTkFont(size=10),
                      command=lambda: self._lb.select_set(0, tk.END)
                      ).pack(side="right")

        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._filter())
        ctk.CTkEntry(box, textvariable=self._filter_var,
                     placeholder_text="Search 4,000+ industries...",
                     height=28, font=ctk.CTkFont(size=11)
                     ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _build_industry_list(self):
        outer = tk.Frame(self, bg="#1E1E32")
        outer.grid(row=1, column=0, sticky="nsew", padx=8, pady=(2, 0))
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        self._lb_var = tk.StringVar(value=ALL_INDUSTRY_NAMES)
        self._lb = tk.Listbox(
            outer, listvariable=self._lb_var, selectmode=tk.EXTENDED,
            bg="#1E1E32", fg="#C9D1D9",
            selectbackground="#2D4A6E", selectforeground="#FFFFFF",
            activestyle="none", font=("Segoe UI", 10),
            borderwidth=0, highlightthickness=0, relief="flat",
        )
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._lb.yview)
        self._lb.configure(yscrollcommand=vsb.set)
        self._lb.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

    def _filter(self):
        q = self._filter_var.get().lower().strip()
        self._filtered = [n for n in ALL_INDUSTRY_NAMES if not q or q in n.lower()]
        self._lb_var.set(self._filtered)

    def get_selected_industries(self) -> list:
        return [self._filtered[i] for i in self._lb.curselection()]

    def _build_config(self):
        cfg = ctk.CTkFrame(self, fg_color="#1E1E32", corner_radius=8)
        cfg.grid(row=2, column=0, sticky="ew", padx=8, pady=6)
        cfg.columnconfigure(0, weight=1)

        ctk.CTkLabel(cfg, text="CUSTOM SEARCH (optional)",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#616161").pack(anchor="w", padx=10, pady=(8, 2))
        self.custom_var = tk.StringVar()
        ctk.CTkEntry(cfg, textvariable=self.custom_var,
                     placeholder_text="e.g. yoga studios, dog groomers",
                     height=28).pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkLabel(cfg, text="LOCATION",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#616161").pack(anchor="w", padx=10, pady=(2, 2))

        self.city_mode_var = tk.StringVar(value="Custom city")
        ctk.CTkComboBox(
            cfg,
            values=["Custom city", "Top 10 US cities", "Top 100 US cities",
                    "Top 1000 US cities", "Top 5000 US cities", "All US cities"],
            variable=self.city_mode_var,
            command=self._on_city_mode,
            height=28, state="readonly",
        ).pack(fill="x", padx=8, pady=(0, 4))

        self._custom_loc = ctk.CTkFrame(cfg, fg_color="transparent")
        self._custom_loc.pack(fill="x", padx=8)
        self.location_var = tk.StringVar(value="Las Vegas, NV")
        ctk.CTkEntry(self._custom_loc, textvariable=self.location_var,
                     placeholder_text="City, State", height=28).pack(fill="x")

        self._city_lbl = ctk.CTkLabel(cfg, text="",
                                      font=ctk.CTkFont(size=9), text_color="#424242")
        self._city_lbl.pack(anchor="w", padx=10)

        # Row 1: Max leads + Browser tabs
        row1 = ctk.CTkFrame(cfg, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=(6, 2))
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        lf = ctk.CTkFrame(row1, fg_color="transparent")
        lf.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkLabel(lf, text="Max leads/city",
                     font=ctk.CTkFont(size=10), text_color="#9E9E9E").pack(anchor="w")
        self.max_leads_var = tk.StringVar(value="500")
        ctk.CTkEntry(lf, textvariable=self.max_leads_var, height=26).pack(fill="x")

        rf = ctk.CTkFrame(row1, fg_color="transparent")
        rf.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        ctk.CTkLabel(rf, text="Browser tabs",
                     font=ctk.CTkFont(size=10), text_color="#9E9E9E").pack(anchor="w")
        self.browsers_var = tk.StringVar(value="4")
        ctk.CTkEntry(rf, textvariable=self.browsers_var, height=26).pack(fill="x")

        # Row 2: Enrich threads
        row2 = ctk.CTkFrame(cfg, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(2, 2))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        ef = ctk.CTkFrame(row2, fg_color="transparent")
        ef.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkLabel(ef, text="Enrich threads",
                     font=ctk.CTkFont(size=10), text_color="#9E9E9E").pack(anchor="w")
        self.workers_var = tk.StringVar(value="8")
        ctk.CTkEntry(ef, textvariable=self.workers_var, height=26).pack(fill="x")

        ef2 = ctk.CTkFrame(row2, fg_color="transparent")
        ef2.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        ctk.CTkLabel(ef2, text="(20 cores = 8-16)",
                     font=ctk.CTkFont(size=9), text_color="#424242").pack(anchor="w", pady=(10, 0))

        self.email_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(cfg, text="Extract emails from websites",
                        variable=self.email_var,
                        font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=(6, 8))

    def _on_city_mode(self, val=None):
        mode = self.city_mode_var.get()
        if mode == "Custom city":
            self._custom_loc.pack(fill="x", padx=8)
            self._city_lbl.configure(text="")
        else:
            self._custom_loc.pack_forget()
            counts = {
                "Top 10 US cities":   CITY_COUNTS["Top 10"],
                "Top 100 US cities":  CITY_COUNTS["Top 100"],
                "Top 1000 US cities": CITY_COUNTS["Top 1000"],
                "Top 5000 US cities": CITY_COUNTS["Top 5000"],
                "All US cities":      CITY_COUNTS["All US"],
            }
            n = counts.get(mode, "")
            self._city_lbl.configure(text=f"Will scrape {n:,} cities one by one")

    def _build_buttons(self):
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 10))

        self.start_btn = ctk.CTkButton(
            bf, text="▶  START SCRAPE", command=self._on_start,
            fg_color="#27AE60", hover_color="#1E8449",
            height=40, font=ctk.CTkFont(size=13, weight="bold"))
        self.start_btn.pack(fill="x", pady=(0, 4))

        self.stop_btn = ctk.CTkButton(
            bf, text="■  STOP", command=self._on_stop,
            fg_color="#E74C3C", hover_color="#C0392B",
            height=32, state="disabled")
        self.stop_btn.pack(fill="x", pady=(0, 4))

        if self._on_reenrich:
            self.reenrich_btn = ctk.CTkButton(
                bf, text="↻  RE-ENRICH LEADS", command=self._on_reenrich,
                fg_color="#5C6BC0", hover_color="#3949AB",
                height=30, font=ctk.CTkFont(size=11))
            self.reenrich_btn.pack(fill="x", pady=(0, 4))

        if self._on_social_enrich:
            self.social_btn = ctk.CTkButton(
                bf, text="🔗  SOCIAL ENRICH", command=self._on_social_enrich,
                fg_color="#B7950B", hover_color="#9A7D0A",
                height=30, font=ctk.CTkFont(size=11, weight="bold"))
            self.social_btn.pack(fill="x")

    def set_running(self, running: bool):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")

    @property
    def config(self) -> dict:
        industries = self.get_selected_industries()
        custom = self.custom_var.get().strip()
        if custom:
            industries.append(custom)

        mode_map = {
            "Custom city": "Custom", "Top 10 US cities": "Top 10",
            "Top 100 US cities": "Top 100", "Top 1000 US cities": "Top 1000",
            "Top 5000 US cities": "Top 5000", "All US cities": "All US",
        }
        mode   = mode_map.get(self.city_mode_var.get(), "Custom")
        cities = get_cities(mode, self.location_var.get().strip())

        try:    max_leads = int(self.max_leads_var.get() or 500)
        except: max_leads = 500
        try:    page_workers = int(self.browsers_var.get() or 4)
        except: page_workers = 4
        try:    enrich_workers = int(self.workers_var.get() or 8)
        except: enrich_workers = 8

        return {
            "industries":     industries,
            "cities":         cities,
            "max_leads":      max(10, min(max_leads, 2000)),
            "page_workers":   max(1, min(page_workers, 20)),
            "enrich_workers": max(1, min(enrich_workers, 32)),
            "extract_email":  self.email_var.get(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Leads tab (with filters + export)
# ─────────────────────────────────────────────────────────────────────────────

class LeadsTab(ctk.CTkFrame):
    def __init__(self, parent, settings_getter, crm_parent, **kw):
        super().__init__(parent, fg_color="#0D0D1A", corner_radius=0, **kw)
        self.settings_getter = settings_getter
        self.crm_parent = crm_parent
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_filter_bar()
        self._build_action_bar()
        self._build_table()

    def _build_filter_bar(self):
        bar = ctk.CTkFrame(self, fg_color="#12121E", height=40, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        ctk.CTkLabel(bar, text="Filter:",
                     font=ctk.CTkFont(size=11), text_color="#78909C").pack(side="left", padx=(10,4), pady=6)

        self.industry_filter = tk.StringVar(value="All Industries")
        self._ind_cb = ctk.CTkComboBox(bar, variable=self.industry_filter,
                                        values=["All Industries"],
                                        width=180, height=26, state="readonly",
                                        command=lambda _: self.refresh())
        self._ind_cb.pack(side="left", padx=4, pady=6)

        self.city_filter = tk.StringVar(value="All Cities")
        self._city_cb = ctk.CTkComboBox(bar, variable=self.city_filter,
                                         values=["All Cities"],
                                         width=140, height=26, state="readonly",
                                         command=lambda _: self.refresh())
        self._city_cb.pack(side="left", padx=4, pady=6)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.after(300, self.refresh))
        ctk.CTkEntry(bar, textvariable=self.search_var,
                     placeholder_text="Search...", width=180, height=26
                     ).pack(side="left", padx=4, pady=6)

        ctk.CTkButton(bar, text="⟳ Refresh", width=80, height=26,
                      fg_color="transparent", border_width=1,
                      font=ctk.CTkFont(size=10),
                      command=self._reload_filters).pack(side="left", padx=4, pady=6)

    def _build_action_bar(self):
        bar = ctk.CTkFrame(self, fg_color="#0A0A18", height=36, corner_radius=0)
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_propagate(False)

        self.count_lbl = ctk.CTkLabel(bar, text="0 leads",
                                       font=ctk.CTkFont(size=11, weight="bold"),
                                       text_color=PRODUCT_COLOR)
        self.count_lbl.pack(side="left", padx=12, pady=6)

        # Select-all checkbox
        self._sel_all_var = tk.BooleanVar(value=False)
        self._sel_all_cb = ctk.CTkCheckBox(
            bar, text="Select All", variable=self._sel_all_var,
            font=ctk.CTkFont(size=10), width=90,
            command=self._toggle_select_all,
        )
        self._sel_all_cb.pack(side="left", padx=8, pady=6)

        self._sel_lbl = ctk.CTkLabel(bar, text="",
                                      font=ctk.CTkFont(size=10),
                                      text_color="#9E9E9E")
        self._sel_lbl.pack(side="left", padx=4, pady=6)

        ctk.CTkButton(bar, text="📤 Export CSV", width=110, height=26,
                      fg_color="#27AE60", hover_color="#1E8449",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._export).pack(side="right", padx=8, pady=5)

        ctk.CTkButton(bar, text="📞 Call", width=70, height=26,
                      font=ctk.CTkFont(size=10),
                      command=self._call_selected).pack(side="right", padx=2, pady=5)

        ctk.CTkButton(bar, text="✉️ Email", width=70, height=26,
                      font=ctk.CTkFont(size=10),
                      command=self._email_selected).pack(side="right", padx=2, pady=5)

        ctk.CTkButton(bar, text="🎯 Add to Pipeline", width=130, height=26,
                      fg_color=PRODUCT_COLOR, text_color="#000",
                      font=ctk.CTkFont(size=10, weight="bold"),
                      command=self._pipeline_selected).pack(side="right", padx=2, pady=5)

    def _build_table(self):
        tree_wrap = tk.Frame(self, bg="#1A1A2E")
        tree_wrap.grid(row=2, column=0, sticky="nsew")
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        _apply_treeview_style()
        self.tree = ttk.Treeview(tree_wrap,
                                  columns=[c[0] for c in TABLE_COLS],
                                  show="headings", selectmode="extended")
        for lbl, _, w in TABLE_COLS:
            self.tree.heading(lbl, text=lbl)
            self.tree.column(lbl, width=w, minwidth=40, stretch=False)

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        self._rows = []  # cache of current row dicts

    def _reload_filters(self):
        industries = ["All Industries"] + lead_db.get_distinct_industries()
        cities     = ["All Cities"]     + lead_db.get_distinct_cities()
        self._ind_cb.configure(values=industries)
        self._city_cb.configure(values=cities)
        self.refresh()

    def add_lead(self, lead: dict):
        self.after(0, lambda: self._insert(lead))

    def _insert(self, lead: dict):
        vals = tuple(str(lead.get(k, "") or "") for _, k, _ in TABLE_COLS)
        self.tree.insert("", 0, values=vals)
        self.count_lbl.configure(text=f"{lead_db.count():,} leads")

    def refresh(self):
        ind  = self.industry_filter.get()
        city = self.city_filter.get()
        srch = self.search_var.get().strip()
        ind_arg  = "" if ind  == "All Industries" else ind
        city_arg = "" if city == "All Cities"     else city

        rows = lead_db.get_all(search=srch, industry=ind_arg, city=city_arg, limit=3000)
        self._rows = rows
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            vals = tuple(str(r.get(k, "") or "") for _, k, _ in TABLE_COLS)
            self.tree.insert("", "end", values=vals)
        self.count_lbl.configure(text=f"{len(rows):,} leads shown  |  {lead_db.count():,} total")

    def _toggle_select_all(self):
        if self._sel_all_var.get():
            self.tree.selection_set(self.tree.get_children())
        else:
            self.tree.selection_remove(self.tree.get_children())

    def _on_tree_select(self, _event=None):
        n_sel   = len(self.tree.selection())
        n_total = len(self.tree.get_children())
        if n_sel == 0:
            self._sel_lbl.configure(text="")
            self._sel_all_var.set(False)
        elif n_sel == n_total:
            self._sel_lbl.configure(text=f"{n_sel} selected")
            self._sel_all_var.set(True)
        else:
            self._sel_lbl.configure(text=f"{n_sel} selected")
            self._sel_all_var.set(False)

    def _on_tree_double_click(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx >= len(self._rows):
            return
        lead = self._rows[idx]
        self._show_lead_detail(lead)

    def _show_lead_detail(self, lead: dict):
        win = tk.Toplevel(self.crm_parent)
        win.title(lead.get('name', 'Lead Detail'))
        win.configure(bg="#0D0D1A")
        win.geometry("520x500")
        win.grab_set()

        # Tab bar
        tab_frame = ctk.CTkFrame(win, fg_color="#12121E", corner_radius=0)
        tab_frame.pack(fill="x")
        content = ctk.CTkFrame(win, fg_color="#0D0D1A", corner_radius=0)
        content.pack(fill="both", expand=True)

        frames = {}
        tab_btns = {}

        def _show_tab(name):
            for n, f in frames.items():
                f.pack_forget()
            frames[name].pack(fill="both", expand=True, padx=14, pady=10)
            for n, b in tab_btns.items():
                b.configure(fg_color=PRODUCT_COLOR if n == name else "transparent",
                            text_color="#000" if n == name else "#AAA")

        def _make_tab(key, label):
            btn = ctk.CTkButton(tab_frame, text=label, width=110, height=30,
                                fg_color="transparent", text_color="#AAA",
                                hover_color="#1E1E2E", corner_radius=0,
                                font=ctk.CTkFont(size=11, weight="bold"),
                                command=lambda k=key: _show_tab(k))
            btn.pack(side="left", padx=2, pady=4)
            tab_btns[key] = btn
            frames[key] = ctk.CTkScrollableFrame(content, fg_color="transparent")

        _make_tab("info", "📋  Info")
        _make_tab("social", "🔗  Social Media")

        # ── Info tab ──────────────────────────────────────────────────────
        info_f = frames["info"]
        fields = [
            ("Name",      lead.get('name', '')),
            ("Phone",     lead.get('phone', '')),
            ("Email",     lead.get('email', '')),
            ("Platform",  lead.get('platform', '')),
            ("Website",   lead.get('website', '')),
            ("Address",   lead.get('address', '')),
            ("City",      lead.get('city', '')),
            ("State",     lead.get('state', '')),
            ("Category",  lead.get('category', '')),
            ("Rating",    lead.get('rating', '')),
            ("Reviews",   lead.get('review_count', '')),
            ("Industry",  lead.get('industry', '')),
            ("Scraped",   lead.get('scraped_at', '')[:19] if lead.get('scraped_at') else ''),
        ]
        for label, val in fields:
            if not val:
                continue
            row = ctk.CTkFrame(info_f, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{label}:", width=80, anchor="w",
                         font=ctk.CTkFont(size=11), text_color="#78909C").pack(side="left")
            ctk.CTkLabel(row, text=str(val), anchor="w", wraplength=340,
                         font=ctk.CTkFont(size=11), text_color="#E0E0E0").pack(side="left", padx=6)

        # ── Social tab ────────────────────────────────────────────────────
        soc_f = frames["social"]
        social_fields = [
            ("Facebook",  lead.get('facebook',  ''), lead.get('fb_followers',   '')),
            ("Instagram", lead.get('instagram', ''), lead.get('ig_followers',   '')),
            ("Twitter/X", lead.get('twitter',   ''), lead.get('tw_followers',   '')),
            ("LinkedIn",  lead.get('linkedin',  ''), lead.get('li_followers',   '')),
            ("TikTok",    lead.get('tiktok',    ''), lead.get('tt_followers',   '')),
            ("YouTube",   lead.get('youtube',   ''), lead.get('yt_subscribers', '')),
            ("Pinterest", lead.get('pinterest', ''), lead.get('pin_followers',  '')),
        ]
        has_any = any(url for _, url, _ in social_fields)
        if not has_any:
            ctk.CTkLabel(soc_f,
                         text="No social media links found yet.\nRun Social Enrich to detect them.",
                         text_color="#616161", font=ctk.CTkFont(size=12)).pack(pady=30)
        else:
            for label, url, followers in social_fields:
                if not url:
                    continue
                row = ctk.CTkFrame(soc_f, fg_color="#1A1A2E", corner_radius=6)
                row.pack(fill="x", pady=3)
                ctk.CTkLabel(row, text=label, width=90, anchor="w",
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color="#B7950B").pack(side="left", padx=10, pady=6)
                ctk.CTkLabel(row, text=url, anchor="w", wraplength=280,
                             font=ctk.CTkFont(size=10),
                             text_color="#90CAF9").pack(side="left", padx=4)
                if followers:
                    ctk.CTkLabel(row, text=f"  {followers} followers",
                                 font=ctk.CTkFont(size=10, weight="bold"),
                                 text_color="#2ECC71").pack(side="left", padx=6)

        _show_tab("info")

        ctk.CTkButton(win, text="Close", width=100, height=30,
                      command=win.destroy).pack(pady=(0, 10))

    def _get_selected_leads(self, require_one=False) -> list:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Nothing Selected",
                                   "Select at least one lead row first.\n"
                                   "Use Ctrl+A or 'Select All' to select all.")
            return []
        leads = []
        for item in selected:
            idx = self.tree.index(item)
            if idx < len(self._rows):
                leads.append(self._rows[idx])
        if require_one and len(leads) > 1:
            messagebox.showinfo("Select One", "Please select a single lead for this action.")
            return []
        return leads

    def _call_selected(self):
        leads = self._get_selected_leads(require_one=True)
        if leads:
            crm_call(leads[0], self.settings_getter())

    def _email_selected(self):
        leads = self._get_selected_leads(require_one=True)
        if leads:
            crm_email_dialog(leads[0], self.settings_getter(), self.crm_parent)

    def _pipeline_selected(self):
        leads = self._get_selected_leads()
        if not leads:
            return
        # Filter to only leads that have a DB id
        valid = [l for l in leads if l.get("id")]
        if not valid:
            messagebox.showinfo("Info", "These leads aren't in the database yet.\n"
                                        "They appear after a scrape completes.")
            return

        settings = load_settings()
        stages   = settings.get("pipeline_stages", DEFAULT_PIPELINE)
        n        = len(valid)

        win = tk.Toplevel(self.crm_parent)
        win.title("Add to Pipeline")
        win.configure(bg="#0D0D1A")
        win.geometry("320x210")
        win.grab_set()

        lbl_text = (f"Move {n} lead{'s' if n != 1 else ''} to stage:"
                    if n > 1 else f"Move '{valid[0].get('name','')[:28]}' to:")
        ctk.CTkLabel(win, text=lbl_text,
                     font=ctk.CTkFont(size=12)).pack(pady=(18, 8))
        stage_var = tk.StringVar(value=stages[0])
        ctk.CTkComboBox(win, values=stages, variable=stage_var,
                        state="readonly", width=240).pack(pady=4)

        def _apply():
            stage = stage_var.get()
            for lead in valid:
                lead_db.set_lead_stage(lead["id"], stage)
            win.destroy()
            messagebox.showinfo("Done",
                                f"{n} lead{'s' if n != 1 else ''} moved to '{stage}'.")
        ctk.CTkButton(win, text=f"Move {n} Lead{'s' if n != 1 else ''}",
                      fg_color="#27AE60", hover_color="#1E8449",
                      width=200, height=34,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=_apply).pack(pady=14)

    def _export(self):
        ind  = self.industry_filter.get()
        city = self.city_filter.get()
        ind_arg  = "" if ind  == "All Industries" else ind
        city_arg = "" if city == "All Cities"     else city

        fname = f"leads_{ind_arg or 'all'}_{city_arg or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
        fname = re.sub(r"[^\w._-]", "_", fname)

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=fname,
        )
        if not path:
            return
        n = lead_db.export_csv(path, industry=ind_arg, city=city_arg)
        messagebox.showinfo("Exported", f"{n:,} leads exported to:\n{path}")


# ─────────────────────────────────────────────────────────────────────────────
# Kanban / Pipeline board
# ─────────────────────────────────────────────────────────────────────────────

class KanbanBoard(ctk.CTkFrame):
    def __init__(self, parent, settings_getter, crm_parent, **kw):
        super().__init__(parent, fg_color="#0D0D1A", corner_radius=0, **kw)
        self.settings_getter = settings_getter
        self.crm_parent = crm_parent
        self._columns = {}   # stage → {"frame", "cards_area", "count_lbl"}
        self._stages  = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top bar
        bar = ctk.CTkFrame(self, fg_color="#12121E", height=38, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(bar, text="🎯  PIPELINE",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=PRODUCT_COLOR).pack(side="left", padx=12, pady=8)
        ctk.CTkButton(bar, text="⟳ Refresh", width=80, height=26,
                      fg_color="transparent", border_width=1,
                      font=ctk.CTkFont(size=10),
                      command=self.refresh).pack(side="right", padx=8, pady=6)

        # Horizontal scrollable board using CTkScrollableFrame
        self._board = ctk.CTkScrollableFrame(
            self, orientation="horizontal",
            fg_color="#0D0D1A", corner_radius=0,
        )
        self._board.grid(row=1, column=0, sticky="nsew")

    def build_columns(self, stages: list):
        for w in self._board.winfo_children():
            w.destroy()
        self._columns = {}
        self._stages  = stages

        for stage in stages:
            # Column outer frame — fixed width, full height
            col_outer = ctk.CTkFrame(self._board, width=230, fg_color="#12121E",
                                     corner_radius=8)
            col_outer.pack(side="left", fill="y", padx=6, pady=8)
            col_outer.pack_propagate(False)

            # Column header
            hdr = ctk.CTkFrame(col_outer, fg_color="#1E1E32", corner_radius=8, height=38)
            hdr.pack(fill="x", padx=0, pady=(0, 4))
            hdr.pack_propagate(False)
            ctk.CTkLabel(hdr, text=stage,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=PRODUCT_COLOR).pack(side="left", padx=10, pady=8)
            count_lbl = ctk.CTkLabel(hdr, text="0",
                                     font=ctk.CTkFont(size=10),
                                     text_color="#616161")
            count_lbl.pack(side="right", padx=8)

            # Scrollable card area
            cards_area = ctk.CTkScrollableFrame(col_outer, fg_color="#12121E",
                                                corner_radius=0)
            cards_area.pack(fill="both", expand=True, padx=2, pady=2)

            self._columns[stage] = {
                "frame": col_outer, "cards_area": cards_area, "count_lbl": count_lbl
            }

    def refresh(self):
        if not self._stages:
            settings = load_settings()
            self._stages = settings.get("pipeline_stages", DEFAULT_PIPELINE)
            self.build_columns(self._stages)

        counts = lead_db.get_stage_counts(self._stages)

        for stage in self._stages:
            col = self._columns.get(stage)
            if not col:
                continue
            for w in col["cards_area"].winfo_children():
                w.destroy()
            col["count_lbl"].configure(text=str(counts.get(stage, 0)))

            leads = lead_db.get_leads_by_stage(stage, limit=50)
            for lead in leads:
                self._make_card(col["cards_area"], lead, stage)

    def _make_card(self, parent, lead: dict, current_stage: str):
        card = ctk.CTkFrame(parent, fg_color="#1E1E32", corner_radius=6)
        card.pack(fill="x", padx=4, pady=4)

        name = (lead.get("name") or "")[:28]
        ctk.CTkLabel(card, text=name,
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#FFFFFF",
                     anchor="w", wraplength=190).pack(anchor="w", padx=8, pady=(8, 2))

        rating = lead.get("rating") or ""
        reviews = lead.get("review_count") or ""
        if rating:
            ctk.CTkLabel(card, text=f"⭐ {rating}  ({reviews} reviews)",
                         font=ctk.CTkFont(size=9),
                         text_color="#F39C12",
                         anchor="w").pack(anchor="w", padx=8)

        phone = lead.get("phone") or ""
        email = lead.get("email") or ""
        if phone:
            ctk.CTkLabel(card, text=f"📞 {phone}",
                         font=ctk.CTkFont(size=9),
                         text_color="#9E9E9E",
                         anchor="w").pack(anchor="w", padx=8)
        if email:
            ctk.CTkLabel(card, text=f"✉  {email[:28]}",
                         font=ctk.CTkFont(size=9),
                         text_color="#9E9E9E",
                         anchor="w").pack(anchor="w", padx=8)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=6, pady=(4, 8))

        def _call(l=lead): crm_call(l, self.settings_getter())
        def _email(l=lead): crm_email_dialog(l, self.settings_getter(), self.crm_parent)

        ctk.CTkButton(btn_row, text="📞", width=34, height=24,
                      fg_color="#2D4A6E", hover_color="#1E3A5F",
                      font=ctk.CTkFont(size=11), command=_call).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="✉", width=34, height=24,
                      fg_color="#2D4A6E", hover_color="#1E3A5F",
                      font=ctk.CTkFont(size=11), command=_email).pack(side="left", padx=2)

        # Stage move buttons
        stages = self._stages
        idx = stages.index(current_stage) if current_stage in stages else 0

        def _move(new_stage, l=lead):
            lead_db.set_lead_stage(l["id"], new_stage)
            self.refresh()

        if idx > 0:
            prev_s = stages[idx - 1]
            ctk.CTkButton(btn_row, text="←", width=28, height=24,
                          fg_color="#252540", hover_color="#353560",
                          text_color="#9E9E9E", font=ctk.CTkFont(size=11),
                          command=lambda s=prev_s: _move(s)).pack(side="left", padx=2)
        if idx < len(stages) - 1:
            next_s = stages[idx + 1]
            ctk.CTkButton(btn_row, text="→", width=28, height=24,
                          fg_color="#252540", hover_color="#353560",
                          text_color="#9E9E9E", font=ctk.CTkFont(size=11),
                          command=lambda s=next_s: _move(s)).pack(side="right", padx=2)

        ctk.CTkFrame(card, fg_color="#252540", height=1,
                     corner_radius=0).pack(fill="x", padx=0, pady=0)


# ─────────────────────────────────────────────────────────────────────────────
# Conversations tab
# ─────────────────────────────────────────────────────────────────────────────

class ConversationsTab(ctk.CTkFrame):
    def __init__(self, parent, settings_getter, crm_parent, **kw):
        super().__init__(parent, fg_color="#0D1117", corner_radius=0, **kw)
        self.settings_getter = settings_getter
        self.crm_parent = crm_parent
        self._selected_lead = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_left()
        self._build_right()

    def _build_left(self):
        left = ctk.CTkFrame(self, fg_color="#12121E", width=220, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="CONTACTS",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#78909C").grid(row=0, column=0, sticky="w", padx=10, pady=(10,4))

        self._lead_search = tk.StringVar()
        self._lead_search.trace_add("write", lambda *_: self._load_lead_list())
        ctk.CTkEntry(left, textvariable=self._lead_search,
                     placeholder_text="Search contacts...",
                     height=26).grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))

        self._lead_lb = tk.Listbox(
            left, bg="#12121E", fg="#C9D1D9",
            selectbackground="#2D4A6E", activestyle="none",
            font=("Segoe UI", 10), borderwidth=0,
            highlightthickness=0, relief="flat",
        )
        self._lead_lb.grid(row=2, column=0, sticky="nsew", padx=0)
        self._lead_lb.bind("<<ListboxSelect>>", self._on_lead_select)

        ctk.CTkButton(left, text="+ New Conversation", height=28,
                      font=ctk.CTkFont(size=10),
                      command=self._new_conv).grid(row=3, column=0, sticky="ew",
                                                    padx=6, pady=6)

    def _build_right(self):
        right = ctk.CTkFrame(self, fg_color="#0D1117", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Header
        self._conv_hdr = ctk.CTkLabel(right, text="Select a contact",
                                       font=ctk.CTkFont(size=12, weight="bold"),
                                       text_color="#78909C")
        self._conv_hdr.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        # Conversation log
        self._log_box = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#0D1117", text_color="#C9D1D9",
            wrap="word", state="disabled")
        self._log_box.grid(row=1, column=0, sticky="nsew", padx=8)

        # Type filter
        filter_bar = ctk.CTkFrame(right, fg_color="transparent")
        filter_bar.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 0))
        self._type_filter = tk.StringVar(value="All")
        for t in ("All", "Calls", "Emails"):
            ctk.CTkRadioButton(filter_bar, text=t, variable=self._type_filter,
                               value=t, command=self._show_conversations,
                               font=ctk.CTkFont(size=11)).pack(side="left", padx=8)

        # Compose area
        compose = ctk.CTkFrame(right, fg_color="#12121E", corner_radius=8)
        compose.grid(row=3, column=0, sticky="ew", padx=8, pady=8)
        compose.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(compose, text="Quick note / reply:",
                     font=ctk.CTkFont(size=10), text_color="#616161"
                     ).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))
        self._compose_box = ctk.CTkTextbox(compose, height=60,
                                            font=ctk.CTkFont(size=11),
                                            fg_color="#1A1A2E")
        self._compose_box.grid(row=1, column=0, sticky="ew", padx=8)

        btn_row = ctk.CTkFrame(compose, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="e", padx=8, pady=6)
        ctk.CTkButton(btn_row, text="📞 Call", width=70, height=26,
                      font=ctk.CTkFont(size=10),
                      command=self._call_current).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="✉ Email", width=70, height=26,
                      font=ctk.CTkFont(size=10),
                      command=self._email_current).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="💾 Save Note", width=90, height=26,
                      fg_color="#27AE60", hover_color="#1E8449",
                      font=ctk.CTkFont(size=10),
                      command=self._save_note).pack(side="left", padx=4)

        self._lead_data = []  # list of lead dicts from conversation_leads

    def refresh(self):
        self._load_lead_list()

    def _load_lead_list(self):
        q = self._lead_search.get().lower().strip()
        leads = lead_db.get_conversation_leads()
        self._lead_data = [l for l in leads if not q or q in (l.get("lead_name") or "").lower()]
        self._lead_lb.delete(0, tk.END)
        for l in self._lead_data:
            name = l.get("lead_name") or "Unknown"
            self._lead_lb.insert(tk.END, name)

    def _on_lead_select(self, event=None):
        sel = self._lead_lb.curselection()
        if not sel:
            return
        self._selected_lead = self._lead_data[sel[0]]
        name = self._selected_lead.get("lead_name") or "Unknown"
        self._conv_hdr.configure(text=f"💬  {name}")
        self._show_conversations()

    def _show_conversations(self):
        if not self._selected_lead:
            return
        lead_id = self._selected_lead.get("lead_id")
        convs = lead_db.get_conversations(lead_id=lead_id)
        filt = self._type_filter.get()

        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")

        for c in reversed(convs):
            if filt == "Calls" and c["type"] != "call":
                continue
            if filt == "Emails" and c["type"] != "email":
                continue

            icon = "📞" if c["type"] == "call" else "✉"
            ts = (c.get("created_at") or "")[:19].replace("T", " ")
            self._log_box.insert("end", f"{icon} {ts}  [{c.get('status','')}]\n")
            self._log_box.insert("end", f"   {c.get('subject','')}\n")
            if c.get("body"):
                body_preview = (c["body"] or "")[:120]
                self._log_box.insert("end", f"   {body_preview}\n")
            self._log_box.insert("end", "\n")

        self._log_box.configure(state="disabled")
        self._log_box.see("end")

    def _call_current(self):
        if not self._selected_lead:
            messagebox.showwarning("No Contact", "Select a contact first.")
            return
        lead = {
            "id": self._selected_lead.get("lead_id", 0),
            "name": self._selected_lead.get("lead_name", ""),
            "phone": self._selected_lead.get("lead_phone", ""),
        }
        crm_call(lead, self.settings_getter())

    def _email_current(self):
        if not self._selected_lead:
            messagebox.showwarning("No Contact", "Select a contact first.")
            return
        rows = lead_db.get_all(limit=1)  # get the lead's email from DB
        lead = {
            "id": self._selected_lead.get("lead_id", 0),
            "name": self._selected_lead.get("lead_name", ""),
            "phone": self._selected_lead.get("lead_phone", ""),
            "email": "",
        }
        crm_email_dialog(lead, self.settings_getter(), self.crm_parent)

    def _save_note(self):
        if not self._selected_lead:
            messagebox.showwarning("No Contact", "Select a contact first.")
            return
        note = self._compose_box.get("1.0", "end").strip()
        if not note:
            return
        lead_db.log_conversation(
            lead_id=self._selected_lead.get("lead_id", 0),
            lead_name=self._selected_lead.get("lead_name", ""),
            lead_phone=self._selected_lead.get("lead_phone", ""),
            conv_type="note", subject="Note", body=note, status="saved",
        )
        self._compose_box.delete("1.0", "end")
        self._show_conversations()

    def _new_conv(self):
        win = tk.Toplevel(self.crm_parent)
        win.title("Find Lead")
        win.configure(bg="#0D0D1A")
        win.geometry("360x300")
        win.grab_set()
        ctk.CTkLabel(win, text="Search lead name or phone:",
                     font=ctk.CTkFont(size=11)).pack(padx=16, pady=(12, 4))
        sv = tk.StringVar()
        ctk.CTkEntry(win, textvariable=sv, height=28).pack(fill="x", padx=16)

        lb = tk.Listbox(win, bg="#1E1E32", fg="#C9D1D9",
                        selectbackground="#2D4A6E", font=("Segoe UI", 10))
        lb.pack(fill="both", expand=True, padx=16, pady=6)
        _found = []

        def _search(*_):
            q = sv.get().strip()
            rows = lead_db.get_all(search=q, limit=20) if q else []
            _found.clear(); _found.extend(rows)
            lb.delete(0, tk.END)
            for r in rows:
                lb.insert(tk.END, f"{r.get('name','')}  {r.get('phone','')}")

        sv.trace_add("write", _search)

        def _pick():
            sel = lb.curselection()
            if not sel:
                return
            r = _found[sel[0]]
            lead_db.log_conversation(
                lead_id=r.get("id", 0), lead_name=r.get("name", ""),
                lead_phone=r.get("phone", ""), conv_type="note",
                subject="Started conversation", body="", status="open",
            )
            self.refresh()
            win.destroy()

        ctk.CTkButton(win, text="Start Conversation", fg_color="#27AE60",
                      command=_pick).pack(padx=16, pady=6)


# ─────────────────────────────────────────────────────────────────────────────
# Live progress panel
# ─────────────────────────────────────────────────────────────────────────────

class ProgressPanel(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color="#0D1117", corner_radius=0, **kw)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self, fg_color="#12121E", height=34, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        ctk.CTkLabel(bar, text="⚡  LIVE SCRAPER OUTPUT",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#78909C").pack(side="left", padx=12, pady=6)
        ctk.CTkButton(bar, text="Clear", width=55, height=22,
                      fg_color="transparent", border_width=1,
                      font=ctk.CTkFont(size=10),
                      command=self.clear).pack(side="right", padx=8)

        self.box = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#0D1117", text_color="#C9D1D9",
            wrap="word", state="disabled")
        self.box.grid(row=1, column=0, sticky="nsew")

    def append(self, msg: str):
        self.after(0, lambda m=msg: self._write(m))

    def _write(self, msg: str):
        self.box.configure(state="normal")
        self.box.insert("end", msg + "\n")
        self.box.see("end")
        self.box.configure(state="disabled")

    def clear(self):
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.configure(state="disabled")


# ─────────────────────────────────────────────────────────────────────────────
# Settings panel
# ─────────────────────────────────────────────────────────────────────────────

class SettingsPanel(ctk.CTkFrame):
    def __init__(self, parent, on_save, **kw):
        super().__init__(parent, fg_color="#0D0D1A", corner_radius=0, **kw)
        self.on_save = on_save
        self._settings = load_settings()

        scroll = ctk.CTkScrollableFrame(self, fg_color="#0D0D1A")
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        self._build_twilio(scroll)
        self._build_smtp(scroll)
        self._build_pipeline(scroll)

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 4))
        ctk.CTkButton(btn_row, text="💾  Save Settings", height=36,
                      fg_color="#27AE60", hover_color="#1E8449",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(btn_row, text="🐛 View Debug Log", width=160, height=36,
                      fg_color="#424242", hover_color="#555555",
                      font=ctk.CTkFont(size=12),
                      command=self._view_log).pack(side="left")

        ctk.CTkLabel(scroll, text=f"Log: {LOG_FILE}",
                     font=ctk.CTkFont(size=9), text_color="#424242"
                     ).pack(anchor="w", padx=24, pady=(0, 24))

    def _section(self, parent, title):
        f = ctk.CTkFrame(parent, fg_color="#12121E", corner_radius=8)
        f.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(f, text=title,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=PRODUCT_COLOR).pack(anchor="w", padx=14, pady=(10, 4))
        return f

    def _row(self, parent, label, var, placeholder="", show=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=2)
        row.columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text=label, width=130, anchor="e",
                     font=ctk.CTkFont(size=11), text_color="#9E9E9E"
                     ).grid(row=0, column=0, padx=(0, 8))
        e = ctk.CTkEntry(row, textvariable=var, placeholder_text=placeholder,
                         height=28, show=show)
        e.grid(row=0, column=1, sticky="ew")

    def _build_twilio(self, parent):
        f = self._section(parent, "📞  Twilio (Click-to-Call)")
        tw = self._settings.get("twilio", {})
        self._tw_sid    = tk.StringVar(value=tw.get("account_sid", ""))
        self._tw_token  = tk.StringVar(value=tw.get("auth_token", ""))
        self._tw_from   = tk.StringVar(value=tw.get("from_number", ""))
        self._tw_yours  = tk.StringVar(value=tw.get("your_number", ""))
        self._row(f, "Account SID",   self._tw_sid,   "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self._row(f, "Auth Token",    self._tw_token,  "your auth token", show="*")
        self._row(f, "Twilio Number", self._tw_from,   "+15551234567")
        self._row(f, "Your Number",   self._tw_yours,  "+15559876543")
        ctk.CTkLabel(f, text="Twilio will call YOUR number first, then connect to the lead.",
                     font=ctk.CTkFont(size=9), text_color="#424242"
                     ).pack(anchor="w", padx=14, pady=(0, 10))

    def _build_smtp(self, parent):
        f = self._section(parent, "✉️  SMTP (Send Emails)")
        sm = self._settings.get("smtp", {})
        self._sm_host   = tk.StringVar(value=sm.get("host", ""))
        self._sm_port   = tk.StringVar(value=str(sm.get("port", "587")))
        self._sm_user   = tk.StringVar(value=sm.get("username", ""))
        self._sm_pass   = tk.StringVar(value=sm.get("password", ""))
        self._sm_fname  = tk.StringVar(value=sm.get("from_name", ""))
        self._sm_femail = tk.StringVar(value=sm.get("from_email", ""))
        self._sm_tls    = tk.BooleanVar(value=sm.get("use_tls", True))
        self._row(f, "SMTP Host",    self._sm_host,   "smtp.gmail.com")
        self._row(f, "Port",         self._sm_port,   "587")
        self._row(f, "Username",     self._sm_user,   "you@gmail.com")
        self._row(f, "Password",     self._sm_pass,   "app password", show="*")
        self._row(f, "From Name",    self._sm_fname,  "Your Name")
        self._row(f, "From Email",   self._sm_femail, "you@gmail.com")
        ctk.CTkCheckBox(f, text="Use STARTTLS (recommended)",
                        variable=self._sm_tls,
                        font=ctk.CTkFont(size=11)).pack(anchor="w", padx=14, pady=(4, 10))

        ctk.CTkButton(f, text="Send Test Email", width=140, height=28,
                      fg_color="transparent", border_width=1,
                      font=ctk.CTkFont(size=10),
                      command=self._test_smtp).pack(anchor="w", padx=14, pady=(0, 10))

    def _build_pipeline(self, parent):
        f = self._section(parent, "🎯  Pipeline Stages")
        ctk.CTkLabel(f, text="One stage per line. Order = left-to-right on the Kanban board.",
                     font=ctk.CTkFont(size=10), text_color="#616161"
                     ).pack(anchor="w", padx=14, pady=(0, 4))

        stages = self._settings.get("pipeline_stages", DEFAULT_PIPELINE)
        self._stages_box = ctk.CTkTextbox(f, height=120, font=ctk.CTkFont(size=11),
                                           fg_color="#1A1A2E")
        self._stages_box.pack(fill="x", padx=12, pady=(0, 12))
        self._stages_box.insert("1.0", "\n".join(stages))

    def _test_smtp(self):
        host  = self._sm_host.get().strip()
        port  = int(self._sm_port.get() or 587)
        user  = self._sm_user.get().strip()
        pwd   = self._sm_pass.get().strip()
        femail = self._sm_femail.get().strip()
        if not all([host, user, pwd, femail]):
            messagebox.showwarning("Incomplete", "Fill in all SMTP fields first.")
            return
        def _do():
            try:
                if self._sm_tls.get():
                    srv = smtplib.SMTP(host, port, timeout=10)
                    srv.starttls()
                else:
                    srv = smtplib.SMTP_SSL(host, port, timeout=10)
                srv.login(user, pwd)
                srv.quit()
                messagebox.showinfo("SMTP OK", "Connection successful!")
            except Exception as e:
                messagebox.showerror("SMTP Failed", str(e))
        threading.Thread(target=_do, daemon=True).start()

    def _view_log(self):
        win = tk.Toplevel()
        win.title("Debug Log")
        win.configure(bg="#0D0D1A")
        win.geometry("800x500")
        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=10),
                              fg_color="#0D1117", text_color="#C9D1D9", wrap="none")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        try:
            content = LOG_FILE.read_text(encoding="utf-8") if LOG_FILE.exists() else "No log file yet."
        except Exception as e:
            content = str(e)
        box.insert("1.0", content)
        box.see("end")
        box.configure(state="disabled")
        ctk.CTkButton(win, text="Refresh", command=lambda: [
            box.configure(state="normal"),
            box.delete("1.0", "end"),
            box.insert("1.0", LOG_FILE.read_text(encoding="utf-8") if LOG_FILE.exists() else ""),
            box.see("end"),
            box.configure(state="disabled"),
        ]).pack(pady=4)

    def _save(self):
        stages_raw = self._stages_box.get("1.0", "end").strip()
        stages = [s.strip() for s in stages_raw.split("\n") if s.strip()]

        self._settings["twilio"] = {
            "account_sid": self._tw_sid.get().strip(),
            "auth_token":  self._tw_token.get().strip(),
            "from_number": self._tw_from.get().strip(),
            "your_number": self._tw_yours.get().strip(),
        }
        self._settings["smtp"] = {
            "host":       self._sm_host.get().strip(),
            "port":       self._sm_port.get().strip(),
            "username":   self._sm_user.get().strip(),
            "password":   self._sm_pass.get().strip(),
            "from_name":  self._sm_fname.get().strip(),
            "from_email": self._sm_femail.get().strip(),
            "use_tls":    self._sm_tls.get(),
        }
        self._settings["pipeline_stages"] = stages if stages else DEFAULT_PIPELINE[:]

        save_settings(self._settings)
        self.on_save(self._settings)
        messagebox.showinfo("Saved", "Settings saved successfully.")


# ─────────────────────────────────────────────────────────────────────────────
# API & MCP tab
# ─────────────────────────────────────────────────────────────────────────────

class APITab(ctk.CTkFrame):
    def __init__(self, parent, engine_cls, industries, lead_db_mod, app_data_dir, **kw):
        super().__init__(parent, fg_color="#0D0D1A", corner_radius=0, **kw)
        self._api_server = None
        self._key_db     = None

        # Lazy-import so missing fastapi/uvicorn doesn't crash the app
        try:
            from shared import api_key_db as _akdb
            _akdb.set_db_path(app_data_dir / "api_keys.db")
            _akdb.init()
            self._key_db = _akdb

            from api import server as _srv
            _srv.configure(
                validate_fn=_akdb.validate_key,
                lead_db_mod=lead_db_mod,
                engine_cls=engine_cls,
                industries_dict=industries,
            )
            self._api_server = _srv
        except Exception as e:
            self._init_error = str(e)
        else:
            self._init_error = None

        self._build_ui()

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="#0D0D1A")
        scroll.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(scroll, fg_color="#12121E", corner_radius=8)
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(hdr, text="🔌  REST API & MCP SERVER",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=PRODUCT_COLOR).pack(side="left", padx=14, pady=10)

        if self._init_error:
            ctk.CTkLabel(scroll,
                         text=f"⚠️  API module load error:\n{self._init_error}\n"
                              "Run: pip install fastapi uvicorn httpx",
                         font=ctk.CTkFont(size=11), text_color="#E74C3C",
                         justify="left").pack(padx=16, pady=8, anchor="w")
            return

        # ── Server controls ───────────────────────────────────────────────────
        srv = ctk.CTkFrame(scroll, fg_color="#12121E", corner_radius=8)
        srv.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(srv, text="API SERVER",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#78909C").pack(anchor="w", padx=14, pady=(10, 4))

        r1 = ctk.CTkFrame(srv, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(0, 4))

        self._status_lbl = ctk.CTkLabel(r1, text="● STOPPED",
                                         font=ctk.CTkFont(size=11, weight="bold"),
                                         text_color="#E74C3C")
        self._status_lbl.pack(side="left", padx=4)

        r2 = ctk.CTkFrame(srv, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(r2, text="Port:", font=ctk.CTkFont(size=11),
                     text_color="#9E9E9E").pack(side="left", padx=4)
        self._port_var = tk.StringVar(value="7842")
        ctk.CTkEntry(r2, textvariable=self._port_var, width=70,
                     height=28).pack(side="left", padx=4)
        self._toggle_btn = ctk.CTkButton(
            r2, text="▶ Start Server", width=130, height=28,
            fg_color="#27AE60", hover_color="#1E8449",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._toggle_server,
        )
        self._toggle_btn.pack(side="left", padx=10)

        self._url_lbl = ctk.CTkLabel(srv, text="",
                                      font=ctk.CTkFont(family="Courier New", size=10),
                                      text_color="#4FC3F7")
        self._url_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        # ── API Keys ──────────────────────────────────────────────────────────
        kf = ctk.CTkFrame(scroll, fg_color="#12121E", corner_radius=8)
        kf.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(kf, text="API KEYS",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#78909C").pack(anchor="w", padx=14, pady=(10, 4))

        gen_row = ctk.CTkFrame(kf, fg_color="transparent")
        gen_row.pack(fill="x", padx=12, pady=(0, 6))
        self._key_name_var = tk.StringVar(value="My Key")
        ctk.CTkEntry(gen_row, textvariable=self._key_name_var,
                     width=160, height=28, placeholder_text="Key name"
                     ).pack(side="left", padx=4)
        ctk.CTkButton(gen_row, text="+ Generate Key", width=130, height=28,
                      fg_color=PRODUCT_COLOR, text_color="#000",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._generate_key).pack(side="left", padx=4)

        self._last_raw_key = ""
        self._new_key_row = ctk.CTkFrame(kf, fg_color="transparent")
        self._new_key_row.pack(fill="x", padx=12, pady=(0, 4))
        self._new_key_lbl = ctk.CTkLabel(self._new_key_row, text="",
                                          font=ctk.CTkFont(family="Courier New", size=10),
                                          text_color="#2ECC71", wraplength=400,
                                          justify="left")
        self._new_key_lbl.pack(side="left", padx=(2, 8))
        self._copy_key_btn = ctk.CTkButton(
            self._new_key_row, text="📋 Copy Key", width=100, height=26,
            fg_color="#2ECC71", hover_color="#1E8449", text_color="#000",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._copy_new_key,
        )
        self._copy_key_btn.pack(side="left")
        self._copy_key_btn.pack_forget()  # hidden until a key is generated

        self._keys_frame = ctk.CTkFrame(kf, fg_color="transparent")
        self._keys_frame.pack(fill="x", padx=8, pady=(0, 10))

        # ── MCP Config ────────────────────────────────────────────────────────
        mf = ctk.CTkFrame(scroll, fg_color="#12121E", corner_radius=8)
        mf.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(mf, text="MCP CONFIG  (Claude Desktop / any MCP-compatible LLM)",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#78909C").pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(mf,
                     text="1.  pip install mcp httpx\n"
                          "2.  Paste the JSON below into your Claude Desktop config\n"
                          "3.  Replace the placeholder with a key generated above",
                     font=ctk.CTkFont(size=10), text_color="#9E9E9E",
                     justify="left").pack(anchor="w", padx=14, pady=(0, 6))

        mcp_path = str(Path(__file__).parent.parent / "mcp_server.py").replace("\\", "/")
        self._mcp_cfg = json.dumps({
            "mcpServers": {
                "gmaps-scraper": {
                    "command": "python",
                    "args": [mcp_path],
                    "env": {
                        "SCRAPER_API_KEY": "sk-PASTE_YOUR_KEY_HERE",
                        "SCRAPER_API_URL": "http://localhost:7842",
                    },
                }
            }
        }, indent=2)

        box = ctk.CTkTextbox(mf, height=180,
                              font=ctk.CTkFont(family="Courier New", size=10),
                              fg_color="#0D0D1A")
        box.pack(fill="x", padx=12, pady=(0, 4))
        box.insert("1.0", self._mcp_cfg)
        box.configure(state="disabled")

        ctk.CTkButton(mf, text="📋  Copy Config", width=130, height=26,
                      fg_color="transparent", border_width=1,
                      font=ctk.CTkFont(size=10),
                      command=self._copy_mcp).pack(anchor="w", padx=12, pady=(0, 10))

        self._refresh_keys()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toggle_server(self):
        if self._api_server is None:
            return
        if self._api_server.is_running():
            self._api_server.stop()
            self._status_lbl.configure(text="● STOPPED", text_color="#E74C3C")
            self._toggle_btn.configure(text="▶ Start Server",
                                        fg_color="#27AE60", hover_color="#1E8449")
            self._url_lbl.configure(text="")
        else:
            try:
                port = int(self._port_var.get())
            except ValueError:
                port = 7842
            ok, msg = self._api_server.start(port)
            if ok:
                self._status_lbl.configure(text="● RUNNING", text_color="#2ECC71")
                self._toggle_btn.configure(text="■  Stop Server",
                                            fg_color="#E74C3C", hover_color="#C0392B")
                self._url_lbl.configure(
                    text=f"http://localhost:{port}   |   Docs: http://localhost:{port}/docs"
                )
            else:
                messagebox.showerror("API Server", msg)

    def _generate_key(self):
        if self._key_db is None:
            return
        name = self._key_name_var.get().strip() or "Key"
        raw  = self._key_db.create_key(name)
        self._last_raw_key = raw
        self._new_key_lbl.configure(text=f"✓ Shown once:\n{raw}")
        self._copy_key_btn.pack(side="left")
        self._refresh_keys()

    def _copy_new_key(self):
        if self._last_raw_key:
            self.clipboard_clear()
            self.clipboard_append(self._last_raw_key)
            self._copy_key_btn.configure(text="✓ Copied!")

    def _refresh_keys(self):
        if self._key_db is None:
            return
        for w in self._keys_frame.winfo_children():
            w.destroy()
        keys = self._key_db.list_keys()
        if not keys:
            ctk.CTkLabel(self._keys_frame, text="No API keys yet.",
                         font=ctk.CTkFont(size=10), text_color="#616161"
                         ).pack(padx=10, pady=4)
            return
        for k in keys:
            row = ctk.CTkFrame(self._keys_frame, fg_color="#1E1E32", corner_radius=4)
            row.pack(fill="x", padx=4, pady=2)
            active = k["active"] == 1
            ctk.CTkLabel(row, text="●" if active else "○",
                         text_color="#2ECC71" if active else "#616161",
                         font=ctk.CTkFont(size=12), width=18
                         ).pack(side="left", padx=(8, 2), pady=4)
            ctk.CTkLabel(row, text=k["name"],
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#FFFFFF").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=k["key_prefix"] + "…",
                         font=ctk.CTkFont(family="Courier New", size=9),
                         text_color="#9E9E9E").pack(side="left", padx=6)
            created = (k["created_at"] or "")[:10]
            last    = (k["last_used"] or "never")[:10]
            ctk.CTkLabel(row, text=f"Created {created}  ·  Last used {last}",
                         font=ctk.CTkFont(size=9), text_color="#616161"
                         ).pack(side="left", padx=4)
            ctk.CTkButton(row, text="Delete", width=60, height=22,
                          fg_color="#424242", hover_color="#555555",
                          font=ctk.CTkFont(size=9),
                          command=lambda kid=k["id"]: self._delete_key(kid)
                          ).pack(side="right", padx=(2, 6), pady=3)
            if active:
                ctk.CTkButton(row, text="Revoke", width=60, height=22,
                              fg_color="#E74C3C", hover_color="#C0392B",
                              font=ctk.CTkFont(size=9),
                              command=lambda kid=k["id"]: self._revoke_key(kid)
                              ).pack(side="right", padx=2, pady=3)

    def _revoke_key(self, key_id: int):
        self._key_db.revoke_key(key_id)
        self._refresh_keys()

    def _delete_key(self, key_id: int):
        if messagebox.askyesno("Delete Key", "Permanently delete this API key?"):
            self._key_db.delete_key(key_id)
            self._refresh_keys()

    def _copy_mcp(self):
        self.clipboard_clear()
        self.clipboard_append(self._mcp_cfg)
        messagebox.showinfo("Copied", "MCP config copied to clipboard.")


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(PRODUCT_NAME)
        self.geometry("1500x900")
        self.minsize(1200, 720)

        self._settings   = load_settings()
        self.engine      = ScraperEngine(log_callback=self._log)
        self._thread     = None
        self._licensed   = False
        self._job_queue  = []  # queued cfgs waiting to run

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.license_bar = LicenseBar(self, on_activate=self._on_license)
        self.license_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.left = LeftPanel(self, on_start=self._start, on_stop=self._stop,
                              on_reenrich=self._start_reenrich,
                              on_social_enrich=self._start_social_enrich)
        self.left.grid(row=1, column=0, sticky="nsew")

        # Right panel with tabs
        right = ctk.CTkFrame(self, fg_color="#0D0D1A", corner_radius=0)
        right.grid(row=1, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Tab bar
        tab_bar = ctk.CTkFrame(right, fg_color="#0A0A18", height=38, corner_radius=0)
        tab_bar.grid(row=0, column=0, sticky="ew")
        tab_bar.grid_propagate(False)

        self._tab_btns = {}
        tabs = [
            ("leads",         "📋  Leads"),
            ("pipeline",      "🎯  Pipeline"),
            ("conversations", "💬  Conversations"),
            ("progress",      "⚡  Live Progress"),
            ("settings",      "⚙️  Settings"),
            ("api",           "🔌  API"),
        ]
        for key, label in tabs:
            btn = ctk.CTkButton(
                tab_bar, text=label, width=110, height=28,
                fg_color="#1E1E32", text_color="#9E9E9E",
                hover_color="#252540",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda k=key: self._show_tab(k))
            btn.pack(side="left", padx=(6 if key == "leads" else 2, 2), pady=5)
            self._tab_btns[key] = btn

        self.status_lbl = ctk.CTkLabel(
            tab_bar, text="● READY",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#2ECC71")
        self.status_lbl.pack(side="right", padx=14)

        # Content panels (stacked)
        self.leads_tab    = LeadsTab(right, settings_getter=lambda: self._settings, crm_parent=self)
        self.kanban_tab   = KanbanBoard(right, settings_getter=lambda: self._settings, crm_parent=self)
        self.conv_tab     = ConversationsTab(right, settings_getter=lambda: self._settings, crm_parent=self)
        self.progress_tab = ProgressPanel(right)
        self.settings_tab = SettingsPanel(right, on_save=self._on_settings_saved)
        self.api_tab      = APITab(
            right,
            engine_cls=ScraperEngine,
            industries=INDUSTRIES,
            lead_db_mod=lead_db,
            app_data_dir=APP_DATA_DIR,
        )

        for tab in (self.leads_tab, self.kanban_tab, self.conv_tab,
                    self.progress_tab, self.settings_tab, self.api_tab):
            tab.grid(row=1, column=0, sticky="nsew")

        self._show_tab("leads")
        self.after(500, self._init_tabs)

    def _init_tabs(self):
        self.leads_tab.refresh()
        self.leads_tab._reload_filters()
        stages = self._settings.get("pipeline_stages", DEFAULT_PIPELINE)
        self.kanban_tab.build_columns(stages)
        self.kanban_tab.refresh()
        self.conv_tab.refresh()

    def _show_tab(self, tab: str):
        for key, btn in self._tab_btns.items():
            if key == tab:
                btn.configure(fg_color=PRODUCT_COLOR, text_color="#000")
            else:
                btn.configure(fg_color="#1E1E32", text_color="#9E9E9E")
        tabs_map = {
            "leads":         self.leads_tab,
            "pipeline":      self.kanban_tab,
            "conversations": self.conv_tab,
            "progress":      self.progress_tab,
            "settings":      self.settings_tab,
            "api":           self.api_tab,
        }
        tabs_map[tab].lift()

    def _on_settings_saved(self, new_settings: dict):
        self._settings = new_settings
        stages = new_settings.get("pipeline_stages", DEFAULT_PIPELINE)
        self.kanban_tab.build_columns(stages)
        self.kanban_tab.refresh()

    def _on_license(self, ok: bool):
        self._licensed = ok

    def _log(self, msg: str):
        self.progress_tab.append(msg)

    def _on_new_lead(self, lead: dict):
        # Scraper uses 'title'/'review_rating'; DB stores 'name'/'rating'. Normalize for live display.
        if lead.get("title") and not lead.get("name"):
            lead["name"] = lead["title"]
        if lead.get("review_rating") and not lead.get("rating"):
            lead["rating"] = lead["review_rating"]
        self.leads_tab.add_lead(lead)

    # ── Start / stop ─────────────────────────────────────────────────────────

    def _start(self):
        if not self._licensed:
            messagebox.showerror(
                "License Required",
                "A valid license key is required to scrape.\n\n"
                "Enter your key in the field at the top of the window and click Activate."
            )
            return

        cfg = self.left.config

        if not cfg["industries"]:
            messagebox.showwarning(
                "No Industry Selected",
                "Click one or more industries (Ctrl+click for multiple),\n"
                "or type a Custom Search term above.")
            return
        if not cfg["cities"]:
            messagebox.showerror("No Location", "Choose a location mode.")
            return
        if not self.engine.is_browser_installed():
            messagebox.showerror(
                "Browser Missing",
                "Chromium is not installed.\nRun: playwright install chromium")
            return

        if self._thread and self._thread.is_alive():
            self._job_queue.append(cfg)
            q = len(self._job_queue)
            self.status_lbl.configure(
                text=f"● RUNNING  (+{q} queued)", text_color="#3498DB")
            messagebox.showinfo(
                "Job Queued",
                f"Job added to queue ({q} waiting).\n"
                "It will start automatically when the current scrape finishes.")
            return

        self._launch_job(cfg)

    def _launch_job(self, cfg: dict):
        self.engine._stop_event.clear()
        self.left.set_running(True)
        q = len(self._job_queue)
        status = f"● RUNNING  (+{q} queued)" if q else "● RUNNING"
        self.status_lbl.configure(text=status, text_color="#3498DB")
        self._show_tab("progress")
        self.progress_tab.clear()
        self._thread = threading.Thread(target=self._run_jobs, args=(cfg,), daemon=True)
        self._thread.start()

    def _stop(self):
        self._job_queue.clear()
        self.engine.stop()
        self.status_lbl.configure(text="● STOPPING…", text_color="#F39C12")

    # ── Sequential job runner ────────────────────────────────────────────────

    def _run_jobs(self, cfg: dict):
        leads_folder = Path.home() / "Documents" / LEADS_FOLDER
        leads_folder.mkdir(parents=True, exist_ok=True)

        industries     = cfg["industries"]
        cities         = cfg["cities"]
        max_leads      = cfg["max_leads"]
        page_workers   = cfg["page_workers"]
        enrich_workers = cfg["enrich_workers"]
        extract_email  = cfg["extract_email"]
        total_cities   = len(cities)
        total_jobs     = len(industries) * total_cities
        job_num        = 0
        all_scraped    = []  # collect raw leads for enrichment pass

        self._log(f"[START] {len(industries)} industr{'ies' if len(industries)!=1 else 'y'} × "
                  f"{total_cities} cit{'ies' if total_cities!=1 else 'y'} = {total_jobs} jobs")
        self._log(f"[START] {page_workers} browser tabs  |  {enrich_workers} enrich threads  |  "
                  f"max {max_leads} leads/city\n")

        # ── Phase 1: scrape (leads saved to DB immediately) ───────────────────
        for industry in industries:
            if self.engine._stop_event.is_set():
                break

            info    = INDUSTRIES.get(industry, {})
            queries = info.get("queries", [industry])

            for city in cities:
                if self.engine._stop_event.is_set():
                    break

                job_num += 1
                pct = int(100 * job_num / total_jobs)
                self._log(f"\n{'─'*60}")
                self._log(f"[JOB {job_num}/{total_jobs}] {industry} — {city}  ({pct}%)")
                self._log(f"{'─'*60}")

                self.after(0, lambda t=f"● {industry[:30]} — {city} ({pct}%)":
                           self.status_lbl.configure(text=t, text_color="#3498DB"))

                try:
                    raw = self.engine.run_industry(
                        industry_name=industry,
                        queries=queries,
                        location=city,
                        max_leads=max_leads,
                        page_workers=page_workers,
                        enrich_workers=enrich_workers,
                        extract_email=extract_email,
                        on_lead=self._on_new_lead,
                        license_validator=lambda: self._licensed,
                    )
                    all_scraped.extend(raw)
                except Exception as e:
                    self._log(f"[ERROR] {e}")

        if self.engine._stop_event.is_set():
            self.after(0, self._done)
            return

        # ── Phase 2: enrich (updates DB in-place) ────────────────────────────
        leads_with_site = [l for l in all_scraped if l.get('website')]
        if leads_with_site and extract_email:
            self._log(f"\n[ENRICH] Starting enrichment for {len(leads_with_site)} leads with websites...")
            self.after(0, lambda: self.status_lbl.configure(
                text=f"● Enriching {len(leads_with_site)} leads…", text_color="#9B59B6"))

            def _on_progress(done, total):
                if done % 10 == 0 or done == total:
                    self.after(0, lambda: self.status_lbl.configure(
                        text=f"● Enriching {done}/{total}…", text_color="#9B59B6"))

            try:
                self.engine.enrich_batch(
                    leads_with_site,
                    extract_email=extract_email,
                    enrich_workers=enrich_workers,
                    on_progress=_on_progress,
                )
            except Exception as e:
                self._log(f"[ENRICH ERROR] {e}")

        # ── Phase 3: social enrichment (links + follower counts) ─────────────
        if leads_with_site and not self.engine._stop_event.is_set():
            self._log(f"\n[SOCIAL] Social enriching {len(leads_with_site)} leads...")
            self.after(0, lambda: self.status_lbl.configure(
                text=f"● Social enriching {len(leads_with_site)} leads…", text_color="#B7950B"))

            def _on_social(done, total):
                if done % 10 == 0 or done == total:
                    self.after(0, lambda: self.status_lbl.configure(
                        text=f"● Social {done}/{total}…", text_color="#B7950B"))

            try:
                self.engine.social_enrich_batch(
                    leads_with_site,
                    workers=enrich_workers,
                    on_progress=_on_social,
                )
            except Exception as e:
                self._log(f"[SOCIAL ERROR] {e}")

        # Export CSVs
        for industry in industries:
            safe = re.sub(r"[^\w\s-]", "", industry).strip().replace(" ", "_")
            csv_path = leads_folder / f"{safe}_leads.csv"
            n = lead_db.export_industry_csv(industry, str(csv_path))
            if n:
                self._log(f"[CSV] {n} leads → {csv_path.name}")

        self.after(0, self._done)

    def _done(self):
        self.leads_tab.refresh()
        self.leads_tab._reload_filters()
        self._log("\n[DONE] All jobs finished.")

        # Auto-start next queued job if any
        if self._job_queue:
            next_cfg = self._job_queue.pop(0)
            q = len(self._job_queue)
            self._log(f"[QUEUE] Starting next job ({q} remaining after this)…")
            self.after(500, lambda: self._launch_job(next_cfg))
        else:
            self.left.set_running(False)
            self.status_lbl.configure(text="● DONE", text_color="#2ECC71")
            self.after(2000, lambda: self._show_tab("leads"))

    def _start_reenrich(self):
        n_enrich = lead_db.count_unenriched()
        n_social  = lead_db.count_social_unenriched()
        if n_enrich == 0 and n_social == 0:
            messagebox.showinfo("Re-Enrich", "Nothing to enrich — all leads are already fully enriched.")
            return
        if self._thread and self._thread.is_alive():
            messagebox.showwarning("Busy", "A scrape is already running. Wait for it to finish.")
            return
        self.engine._stop_event.clear()
        self.status_lbl.configure(text=f"● Enriching…", text_color="#9B59B6")
        self._show_tab("progress")

        def _run():
            # Phase 1: regular enrichment (email + platform)
            if n_enrich > 0:
                def _on_enrich(done, total):
                    if done % 10 == 0 or done == total:
                        self.after(0, lambda: self.status_lbl.configure(
                            text=f"● Enriching {done}/{total}…", text_color="#9B59B6"))
                self.engine.enrich_unenriched(on_progress=_on_enrich)

            # Phase 2: social enrichment (links + followers)
            if n_social > 0 and not self.engine._stop_event.is_set():
                self.after(0, lambda: self.status_lbl.configure(
                    text=f"● Social enriching {n_social} leads…", text_color="#B7950B"))
                def _on_social(done, total):
                    if done % 10 == 0 or done == total:
                        self.after(0, lambda: self.status_lbl.configure(
                            text=f"● Social {done}/{total}…", text_color="#B7950B"))
                self.engine.social_enrich_unenriched(on_progress=_on_social)

            self.after(0, lambda: (
                self.status_lbl.configure(text="● DONE", text_color="#2ECC71"),
                self.leads_tab.refresh(),
                self.leads_tab._reload_filters(),
            ))

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _start_social_enrich(self):
        n = lead_db.count_social_unenriched()
        if n == 0:
            messagebox.showinfo("Social Enrich", "No leads pending social enrichment.")
            return
        if self._thread and self._thread.is_alive():
            messagebox.showwarning("Busy", "A scrape or enrichment is already running.")
            return
        self.engine._stop_event.clear()
        self.status_lbl.configure(text=f"● Social enriching {n} leads…", text_color="#B7950B")
        self._show_tab("progress")

        def _run():
            def _on_progress(done, total):
                if done % 10 == 0 or done == total:
                    self.after(0, lambda: self.status_lbl.configure(
                        text=f"● Social {done}/{total}…", text_color="#B7950B"))
            self.engine.social_enrich_unenriched(on_progress=_on_progress)
            self.after(0, lambda: (
                self.status_lbl.configure(text="● DONE", text_color="#2ECC71"),
                self.leads_tab.refresh(),
                self.leads_tab._reload_filters(),
            ))

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()


def main():
    logging.info(f"Starting {PRODUCT_NAME}")
    try:
        app = App()
        app.mainloop()
    except Exception:
        err = traceback.format_exc()
        logging.error(f"Crash:\n{err}")
        try:
            messagebox.showerror(
                "Startup Error",
                f"{err[:600]}\n\nFull log: {LOG_FILE}"
            )
        except Exception:
            pass


if __name__ == "__main__":
    main()
