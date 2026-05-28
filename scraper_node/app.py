"""
Lead Scraper Pro — desktop application
Scrapes Google Maps, detects website platform, extracts emails.
"""
import re
import sys
import os
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

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

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# License server — local fleet or production
LICENSE_SERVER = os.environ.get("LICENSE_SERVER", "http://localhost:3001")
ADMIN_TOKEN    = os.environ.get("ADMIN_TOKEN", "2TQmwZePcT5k-PBcpY8k4YwPEG3dtNzP")

# License key stored locally
LICENSE_FILE = Path.home() / "AppData" / "Local" / "LeadScraperPro" / "license.txt"
LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Machine fingerprint
MACHINE_ID = get_machine_id()

TABLE_COLS = [
    ("Name",     "name",         220),
    ("Phone",    "phone",        120),
    ("Email",    "email",        200),
    ("Platform", "platform",      90),
    ("Rating",   "rating",        60),
    ("Reviews",  "review_count",  70),
    ("City",     "city",         110),
    ("Website",  "website",      180),
]

STATUS_COLORS = {
    "Pending": "#F39C12",
    "Running": "#3498DB",
    "Done":    "#27AE60",
    "Error":   "#E74C3C",
    "Stopped": "#7F8C8D",
}


def _validate_license(key: str) -> tuple:
    """Returns (ok: bool, message: str)."""
    try:
        import requests
        r = requests.post(
            f"{LICENSE_SERVER}/api/customer/verify",
            json={"license_key": key, "product": "lead-scraper-pro", "machine_id": MACHINE_ID},
            timeout=5,
            headers={"x-license-key": key},
        )
        if r.status_code == 200:
            data = r.json()
            return True, f"License active — {data.get('plan','pro').title()} plan"
        return False, "Invalid license key."
    except Exception:
        # Fleet server not reachable — allow offline mode for dev
        if key and len(key) >= 10:
            return True, "Offline mode (server unreachable)"
        return False, "Could not reach license server."


def _apply_treeview_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview",
        background="#1E1E2E", foreground="#C9D1D9",
        fieldbackground="#1E1E2E", rowheight=26,
        font=("Consolas", 10))
    style.configure("Treeview.Heading",
        background="#252535", foreground="#78909C",
        relief="flat", font=("Consolas", 10, "bold"))
    style.map("Treeview",
        background=[("selected", "#2D4A6E")],
        foreground=[("selected", "#FFFFFF")])
    style.map("Treeview.Heading",
        background=[("active", "#2D3748")])


class LicenseBar(ctk.CTkFrame):
    def __init__(self, parent, on_activate: callable, **kw):
        super().__init__(parent, height=44, fg_color="#0F0F1A", corner_radius=0, **kw)
        self.grid_propagate(False)
        self.on_activate = on_activate
        self._licensed = False

        ctk.CTkLabel(self, text="LEAD SCRAPER PRO",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      text_color="#4FC3F7").pack(side="left", padx=12)

        self.status_lbl = ctk.CTkLabel(self, text="",
                                        font=ctk.CTkFont(size=11),
                                        text_color="#78909C")
        self.status_lbl.pack(side="left", padx=4)

        # Node ID label
        self.node_lbl = ctk.CTkLabel(
            self, text=f"Node: {MACHINE_ID[:8]}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#78909C")
        self.node_lbl.pack(side="left", padx=8)

        self.export_btn = ctk.CTkButton(
            self, text="Export CSV", width=100, height=28,
            fg_color="#27AE60", hover_color="#1E8449",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._export)
        self.export_btn.pack(side="right", padx=8)

        self.key_entry = ctk.CTkEntry(
            self, placeholder_text="License key (e.g. LR-XXXX-XXXX)",
            width=230, height=28, font=ctk.CTkFont(size=11))
        self.key_entry.pack(side="right", padx=4)

        self.activate_btn = ctk.CTkButton(
            self, text="Activate", width=80, height=28,
            font=ctk.CTkFont(size=11), command=self._activate)
        self.activate_btn.pack(side="right", padx=4)

        # Load saved key
        if LICENSE_FILE.exists():
            saved = LICENSE_FILE.read_text().strip()
            if saved:
                self.key_entry.insert(0, saved)
                threading.Thread(target=self._activate, daemon=True).start()

    def _activate(self):
        key = self.key_entry.get().strip()
        if not key:
            return
        self.activate_btn.configure(state="disabled", text="Checking...")
        ok, msg = _validate_license(key)
        self._licensed = ok
        if ok:
            LICENSE_FILE.write_text(key)
            self.status_lbl.configure(text=f"✓ {msg}", text_color="#27AE60")
            self.activate_btn.configure(text="Active", fg_color="#27AE60",
                                         hover_color="#1E8449")
        else:
            self.status_lbl.configure(text=f"✗ {msg}", text_color="#E74C3C")
            self.activate_btn.configure(state="normal", text="Activate")
        self.on_activate(ok)

    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            title="Export Leads to CSV",
        )
        if not path:
            return
        try:
            count = lead_db.export_csv(path)
            messagebox.showinfo("Exported", f"{count} leads exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    @property
    def is_licensed(self):
        return self._licensed


class LeadsTable(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color="#121212", corner_radius=0, **kw)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Search bar
        search_bar = ctk.CTkFrame(self, fg_color="#1A1A2E", height=36, corner_radius=0)
        search_bar.grid(row=0, column=0, sticky="ew")
        search_bar.grid_propagate(False)

        self.lead_count_lbl = ctk.CTkLabel(
            search_bar, text="0 leads",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#4FC3F7")
        self.lead_count_lbl.pack(side="left", padx=12, pady=6)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._search_changed())
        search_entry = ctk.CTkEntry(
            search_bar, textvariable=self.search_var,
            placeholder_text="Search leads...",
            width=220, height=26, font=ctk.CTkFont(size=11))
        search_entry.pack(side="right", padx=8, pady=5)

        # Treeview in a frame so the scrollbar is inside the dark area
        tree_frame = tk.Frame(self, bg="#1E1E2E")
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        _apply_treeview_style()
        cols = [c[0] for c in TABLE_COLS]
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="extended")
        for label, key, width in TABLE_COLS:
            self.tree.heading(label, text=label,
                              command=lambda c=label: self._sort(c))
            self.tree.column(label, width=width, minwidth=50, stretch=False)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._sort_col = None
        self._sort_rev = False
        self._all_rows = []  # cached from DB

    def add_lead(self, lead: dict):
        """Called from scraper thread — schedule UI update on main thread."""
        self.after(0, lambda: self._insert_row(lead))

    def _insert_row(self, lead: dict):
        vals = tuple(
            str(lead.get(key, '') or '') for _, key, _ in TABLE_COLS
        )
        self.tree.insert("", 0, values=vals)
        total = int(self.tree.tag_has("") or 0)
        count = lead_db.count()
        self.lead_count_lbl.configure(text=f"{count:,} leads")

    def refresh_from_db(self):
        search = self.search_var.get().strip()
        rows = lead_db.get_all(search=search, limit=2000)
        self._all_rows = rows
        self._render(rows)

    def _render(self, rows):
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            vals = tuple(str(r.get(key, '') or '') for _, key, _ in TABLE_COLS)
            self.tree.insert("", "end", values=vals)
        self.lead_count_lbl.configure(text=f"{lead_db.count():,} leads")

    def _search_changed(self):
        self.after(300, self.refresh_from_db)

    def _sort(self, col):
        rev = (self._sort_col == col and not self._sort_rev)
        self._sort_col = col
        self._sort_rev = rev
        rows = self._all_rows[:]
        key_idx = next(i for i, (l, _, _) in enumerate(TABLE_COLS) if l == col)
        db_key = TABLE_COLS[key_idx][1]
        rows.sort(key=lambda r: (r.get(db_key) or '').lower(), reverse=rev)
        self._render(rows)


class LeftPanel(ctk.CTkFrame):
    def __init__(self, parent, on_start, on_stop, **kw):
        super().__init__(parent, width=270, corner_radius=0, fg_color="#1E1E2E", **kw)
        self.grid_propagate(False)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._on_start = on_start
        self._on_stop  = on_stop

        self._build_industry_section()
        self._build_config_section()
        self._build_buttons()

    def _build_industry_section(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(10, 0))

        top = ctk.CTkFrame(hdr, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text="INDUSTRIES",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color="#78909C").pack(side="left")
        ctk.CTkButton(top, text="All",  width=38, height=22,
                       command=lambda: self._select_all(True)).pack(side="right", padx=2)
        ctk.CTkButton(top, text="None", width=42, height=22,
                       command=lambda: self._select_all(False)).pack(side="right")

        self.industry_filter_var = tk.StringVar()
        self.industry_filter_var.trace_add("write", lambda *_: self._filter_industries())
        ctk.CTkEntry(hdr, textvariable=self.industry_filter_var,
                      placeholder_text="Filter industries...",
                      height=24, font=ctk.CTkFont(size=10)).pack(fill="x", pady=(4, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color="#252535", label_text="")
        scroll.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 0))

        self.industry_vars: dict[str, tk.BooleanVar] = {}
        self._industry_checkboxes: dict[str, ctk.CTkCheckBox] = {}
        for name, info in INDUSTRIES.items():
            var = tk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(scroll, text=name, variable=var,
                                  font=ctk.CTkFont(size=12),
                                  checkmark_color=info["color"],
                                  border_color=info["color"])
            cb.pack(anchor="w", padx=8, pady=2)
            self.industry_vars[name] = var
            self._industry_checkboxes[name] = cb

    def _select_all(self, val: bool):
        for v in self.industry_vars.values():
            v.set(val)

    def _filter_industries(self):
        q = self.industry_filter_var.get().lower().strip()
        for name, cb in self._industry_checkboxes.items():
            if not q or q in name.lower():
                cb.pack(anchor="w", padx=8, pady=2)
            else:
                cb.pack_forget()

    def _build_config_section(self):
        cfg = ctk.CTkFrame(self, fg_color="#252535")
        cfg.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        cfg.grid_columnconfigure(0, weight=1)

        def _row(parent, label, default, row):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(f, text=label, width=72, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(default))
            ctk.CTkEntry(f, textvariable=var, width=64).pack(side="right")
            return var

        ctk.CTkLabel(cfg, text="CUSTOM KEYWORD",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color="#78909C").pack(anchor="w", padx=10, pady=(10, 2))
        self.custom_var = tk.StringVar()
        ctk.CTkEntry(cfg, textvariable=self.custom_var,
                      placeholder_text="e.g. yoga studios, dog groomers",
                      height=30).pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkLabel(cfg, text="LOCATION",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color="#78909C").pack(anchor="w", padx=10, pady=(4, 2))
        self.location_var = tk.StringVar(value="Las Vegas, NV")
        ctk.CTkEntry(cfg, textvariable=self.location_var,
                      placeholder_text="City, State").pack(fill="x", padx=8, pady=(0,6))

        ctk.CTkLabel(cfg, text="OPTIONS",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color="#78909C").pack(anchor="w", padx=10, pady=(4,2))
        self.depth_var       = _row(cfg, "Depth:",   5, 0)
        self.workers_var     = _row(cfg, "Workers:", 4, 1)

        self.email_var    = tk.BooleanVar(value=True)
        self.platform_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(cfg, text="Extract Emails + Platform",
                         variable=self.email_var).pack(anchor="w", padx=10, pady=2)
        ctk.CTkCheckBox(cfg, text="Fast mode (~20 results/query)",
                         variable=self.platform_var).pack(anchor="w", padx=10, pady=(2,10))

    def _build_buttons(self):
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.grid(row=3, column=0, sticky="ew", padx=8, pady=(0,10))

        self.start_btn = ctk.CTkButton(
            bf, text="▶  START SCRAPE",
            command=self._on_start,
            fg_color="#27AE60", hover_color="#1E8449",
            height=36, font=ctk.CTkFont(size=13, weight="bold"))
        self.start_btn.pack(fill="x", pady=3)

        self.stop_btn = ctk.CTkButton(
            bf, text="■  STOP",
            command=self._on_stop,
            fg_color="#E74C3C", hover_color="#C0392B",
            height=32, state="disabled")
        self.stop_btn.pack(fill="x", pady=3)

    def set_running(self, running: bool):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")

    @property
    def config(self) -> dict:
        industries = [n for n, v in self.industry_vars.items() if v.get()]
        custom = self.custom_var.get().strip()
        if custom:
            industries = industries + [custom]
        return {
            "location":      self.location_var.get().strip(),
            "depth":         int(self.depth_var.get() or 5),
            "concurrency":   int(self.workers_var.get() or 4),
            "extract_email": self.email_var.get(),
            "fast":          self.platform_var.get(),
            "industries":    industries,
        }


class LogPanel(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color="#121212", corner_radius=0, **kw)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent", height=28)
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(4,0))
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="LIVE LOG",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      text_color="#78909C").pack(side="left")
        ctk.CTkButton(hdr, text="Clear", width=55, height=20,
                       fg_color="transparent", border_width=1,
                       command=self.clear).pack(side="right")

        self.box = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#0D1117", text_color="#C9D1D9",
            wrap="word", state="disabled")
        self.box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4,8))

    def append(self, msg: str):
        self.after(0, lambda: self._write(msg))

    def _write(self, msg: str):
        self.box.configure(state="normal")
        self.box.insert("end", msg + "\n")
        self.box.see("end")
        self.box.configure(state="disabled")

    def clear(self):
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.configure(state="disabled")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Lead Scraper Pro")
        self.geometry("1400x820")
        self.minsize(1100, 650)

        self.engine = ScraperEngine(log_callback=self._log)
        self._thread: threading.Thread = None
        self._licensed = False

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Header ──
        self.license_bar = LicenseBar(self, on_activate=self._on_license)
        self.license_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

        # ── Left panel ──
        self.left = LeftPanel(self, on_start=self._start, on_stop=self._stop)
        self.left.grid(row=1, column=0, sticky="nsew")

        # ── Right: table on top, log on bottom ──
        right = ctk.CTkFrame(self, fg_color="#121212", corner_radius=0)
        right.grid(row=1, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=3)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.table = LeadsTable(right)
        self.table.grid(row=0, column=0, sticky="nsew")

        sep = ctk.CTkFrame(right, height=1, fg_color="#2B2B2B")
        sep.grid(row=0, column=0, sticky="s", padx=0)

        self.log_panel = LogPanel(right)
        self.log_panel.grid(row=1, column=0, sticky="nsew")

        # Status bar
        status_frame = ctk.CTkFrame(self, fg_color="transparent", height=28)
        status_frame.grid(row=2, column=0, columnspan=2, pady=4)

        self.status_lbl = ctk.CTkLabel(status_frame, text="● READY",
                                         font=ctk.CTkFont(size=12, weight="bold"),
                                         text_color="#2ECC71")
        self.status_lbl.pack(side="left", padx=12)

        ctk.CTkLabel(status_frame,
                      text=f"Node: {MACHINE_ID[:8]}",
                      font=ctk.CTkFont(family="Consolas", size=10),
                      text_color="#78909C").pack(side="left", padx=8)

        # Load existing leads
        self.after(500, self._check_browser)
        self.after(800, lambda: self.table.refresh_from_db())

    def _on_license(self, ok: bool):
        self._licensed = ok

    def _check_browser(self):
        if not self.engine.is_browser_installed():
            self._log("[SYSTEM] Chromium not installed — click Install in the settings.")

    def _log(self, msg: str):
        self.log_panel.append(msg)

    def _start(self):
        cfg = self.left.config
        if not cfg["industries"]:
            messagebox.showwarning("No Industry", "Select at least one industry or enter a custom keyword.")
            return
        if not cfg["location"]:
            messagebox.showerror("Location Required", "Enter a city/state.")
            return
        if not self.engine.is_browser_installed():
            messagebox.showerror("No Browser", "Install Chromium first.")
            return

        self.left.set_running(True)
        self.status_lbl.configure(text="● RUNNING", text_color="#3498DB")

        self._thread = threading.Thread(
            target=self._run_jobs, args=(cfg,), daemon=True)
        self._thread.start()

    def _run_jobs(self, cfg: dict):
        leads_folder = Path.home() / "Documents" / "LeadScraperPro Leads"
        leads_folder.mkdir(parents=True, exist_ok=True)
        saved_key = LICENSE_FILE.read_text().strip() if LICENSE_FILE.exists() else ''
        for industry in cfg["industries"]:
            if self.engine._stop_event.is_set():
                break
            info = INDUSTRIES.get(industry, {})
            self.after(0, lambda n=industry: self.status_lbl.configure(
                text=f"● {n}", text_color="#3498DB"))
            self.engine.run_industry(
                industry_name=industry,
                queries=info.get("queries", [industry]),
                location=cfg["location"],
                depth=cfg["depth"],
                concurrency=cfg["concurrency"],
                extract_email=cfg["extract_email"],
                on_lead=self._on_new_lead,
            )
            safe = re.sub(r'[^\w\s-]', '', industry).strip().replace(' ', '_')
            csv_path = leads_folder / f"{safe}_leads.csv"
            n = lead_db.export_industry_csv(industry, str(csv_path))
            if n:
                self._log(f"[CSV] {n} leads → {csv_path}")
            if saved_key:
                try:
                    import requests as _req
                    rows = lead_db.get_by_industry(industry)
                    if rows:
                        r = _req.post(
                            "https://leadripper.com/api/portal/sync-leads",
                            json={"leads": rows},
                            headers={"x-license-key": saved_key},
                            timeout=20,
                        )
                        ins = r.json().get("inserted", 0) if r.ok else 0
                        self._log(f"[SYNC] {ins}/{len(rows)} leads synced to cloud")
                except Exception as _e:
                    self._log(f"[SYNC] Cloud sync skipped: {_e}")
        self.after(0, self._done)

    def _on_new_lead(self, lead: dict):
        self.table.add_lead(lead)

    def _done(self):
        self.left.set_running(False)
        self.status_lbl.configure(text="● READY", text_color="#2ECC71")
        self.table.refresh_from_db()
        self._log("[SYSTEM] All jobs finished.")

    def _stop(self):
        self.engine.stop()
        self.status_lbl.configure(text="● STOPPING...", text_color="#F39C12")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
