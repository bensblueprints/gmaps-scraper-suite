# /new-scraper-product

Guide the user through creating a brand new white-label scraper product in this monorepo. Follow every step below in order without skipping.

---

## Step 1 — Gather product details

Ask the user for all of the following. Collect all answers before doing any work:

1. **Product name** — e.g. `RoofingLeads Pro`
2. **Primary color** — hex code, e.g. `#E74C3C`
3. **Hover color** — slightly darker shade of the primary, e.g. `#C0392B`
4. **Target industries / niche** — comma-separated free text, e.g. `roofing, gutters, siding, skylights`
5. **Monthly price** — e.g. `49`
6. **Lifetime price** — e.g. `297`
7. **Extra node price** — e.g. `19`

Once you have all seven answers, derive the **slug**: lowercase the product name, strip everything that isn't a letter or digit, replace spaces with underscores. Examples:
- `RoofingLeads Pro` → `roofingleads_pro`
- `HVAC Lead Machine` → `hvac_lead_machine`

Confirm the slug with the user before continuing.

---

## Step 2 — Create `{slug}/__init__.py`

Create an empty Python init file at `{slug}/__init__.py` (relative to the repo root `C:\Users\ADMIN\Desktop\gmaps-scraper-suite`).

Content:
```python
```
(Empty file — just needs to exist so Python treats the folder as a package.)

---

## Step 3 — Create `{slug}/industries.py`

Build an `INDUSTRIES` dict from the user's niche list. Each key is the industry name (title-cased), and each value is a dict with a `color` key set to the user's primary color. Add as many entries as the user provided.

Template (fill in actual industries and color):

```python
"""
{ProductName} — industry definitions
"""

INDUSTRIES = {
    "IndustryOne": {"color": "{PRIMARY_COLOR}"},
    "IndustryTwo": {"color": "{PRIMARY_COLOR}"},
    # ... one entry per industry the user listed
}
```

Example for `roofing, gutters, siding` with color `#E74C3C`:

```python
"""
RoofingLeads Pro — industry definitions
"""

INDUSTRIES = {
    "Roofing": {"color": "#E74C3C"},
    "Gutters": {"color": "#E74C3C"},
    "Siding": {"color": "#E74C3C"},
}
```

---

## Step 4 — Create `{slug}/app.py`

Write the full desktop GUI application. Use the template below, substituting every placeholder:

| Placeholder | Value |
|---|---|
| `{ProductName}` | Product name exactly as entered, e.g. `RoofingLeads Pro` |
| `{slug}` | Derived slug, e.g. `roofingleads_pro` |
| `{PRIMARY_COLOR}` | Primary hex color |
| `{HOVER_COLOR}` | Hover hex color |

```python
"""
{ProductName} — desktop application
"""
import sys
import os
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

# Allow imports from the monorepo root and scraper_node when running from source
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parent.parent))
    sys.path.insert(0, str(Path(__file__).parent.parent / "scraper_node"))

try:
    import customtkinter as ctk
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

from engine import ScraperEngine
from {slug}.industries import INDUSTRIES
from shared import lead_db

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PRIMARY_COLOR = "{PRIMARY_COLOR}"
HOVER_COLOR   = "{HOVER_COLOR}"

# ── License config ───────────────────────────────────────────────────────────
LICENSE_SERVER = os.environ.get("LICENSE_SERVER", "http://localhost:3001")
LICENSE_FILE   = Path.home() / "AppData" / "Local" / "{ProductName}" / "license.txt"
LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
PRODUCT_SLUG   = "{slug}"


# ── License helpers ──────────────────────────────────────────────────────────
def get_machine_id() -> str:
    return socket.gethostname()


def validate_license(key: str) -> tuple[bool, str]:
    """POST the license key to the license server and return (ok, message)."""
    try:
        resp = requests.post(
            f"{LICENSE_SERVER}/api/validate",
            json={"key": key, "product": PRODUCT_SLUG, "machine": get_machine_id()},
            timeout=10,
        )
        data = resp.json()
        return data.get("valid", False), data.get("message", "Unknown error")
    except requests.RequestException as exc:
        return False, f"Could not reach license server: {exc}"


def load_saved_license() -> str | None:
    if LICENSE_FILE.exists():
        return LICENSE_FILE.read_text(encoding="utf-8").strip() or None
    return None


def save_license(key: str) -> None:
    LICENSE_FILE.write_text(key.strip(), encoding="utf-8")


# ── License gate screen ───────────────────────────────────────────────────────
class LicenseScreen(ctk.CTkFrame):
    def __init__(self, master, on_unlock, **kwargs):
        super().__init__(master, **kwargs)
        self._on_unlock = on_unlock

        ctk.CTkLabel(
            self, text="{ProductName}", font=("Segoe UI", 28, "bold"), text_color=PRIMARY_COLOR
        ).pack(pady=(60, 8))
        ctk.CTkLabel(self, text="Enter your license key to continue").pack(pady=(0, 24))

        self._key_var = tk.StringVar()
        ctk.CTkEntry(self, textvariable=self._key_var, width=340, placeholder_text="XXXX-XXXX-XXXX-XXXX").pack()

        ctk.CTkButton(
            self,
            text="Activate",
            fg_color=PRIMARY_COLOR,
            hover_color=HOVER_COLOR,
            command=self._activate,
        ).pack(pady=16)

        self._status = ctk.CTkLabel(self, text="")
        self._status.pack()

    def _activate(self):
        key = self._key_var.get().strip()
        if not key:
            self._status.configure(text="Please enter a key.", text_color="orange")
            return
        self._status.configure(text="Validating…", text_color="gray")
        self.update()
        ok, msg = validate_license(key)
        if ok:
            save_license(key)
            self._on_unlock()
        else:
            self._status.configure(text=f"Invalid: {msg}", text_color="red")


# ── Main application window ───────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("{ProductName}")
        self.geometry("1100x700")
        self.resizable(True, True)

        self._engine: ScraperEngine | None = None
        self._running = False

        saved_key = load_saved_license()
        if saved_key:
            ok, _ = validate_license(saved_key)
            if ok:
                self._build_main_ui()
                return
        self._build_license_gate()

    # ── License gate ─────────────────────────────────────────────────────────
    def _build_license_gate(self):
        self._gate = LicenseScreen(self, on_unlock=self._on_licensed)
        self._gate.pack(fill="both", expand=True)

    def _on_licensed(self):
        self._gate.destroy()
        self._build_main_ui()

    # ── Main UI ───────────────────────────────────────────────────────────────
    def _build_main_ui(self):
        # Sidebar
        self._sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(
            self._sidebar,
            text="{ProductName}",
            font=("Segoe UI", 16, "bold"),
            text_color=PRIMARY_COLOR,
            wraplength=180,
        ).pack(pady=(20, 4), padx=12)
        ctk.CTkLabel(self._sidebar, text="Lead Scraper", font=("Segoe UI", 11), text_color="gray").pack(pady=(0, 20))

        self._industry_var = tk.StringVar(value=list(INDUSTRIES.keys())[0])
        ctk.CTkLabel(self._sidebar, text="Industry").pack(anchor="w", padx=16)
        self._industry_menu = ctk.CTkOptionMenu(
            self._sidebar,
            values=list(INDUSTRIES.keys()),
            variable=self._industry_var,
            fg_color=PRIMARY_COLOR,
            button_color=HOVER_COLOR,
            button_hover_color=HOVER_COLOR,
        )
        self._industry_menu.pack(padx=16, pady=(4, 16), fill="x")

        ctk.CTkLabel(self._sidebar, text="Location").pack(anchor="w", padx=16)
        self._location_var = tk.StringVar()
        ctk.CTkEntry(self._sidebar, textvariable=self._location_var, placeholder_text="City, State").pack(
            padx=16, pady=(4, 16), fill="x"
        )

        ctk.CTkLabel(self._sidebar, text="Max results").pack(anchor="w", padx=16)
        self._max_var = tk.StringVar(value="50")
        ctk.CTkEntry(self._sidebar, textvariable=self._max_var).pack(padx=16, pady=(4, 24), fill="x")

        self._run_btn = ctk.CTkButton(
            self._sidebar,
            text="▶  Start Scrape",
            fg_color=PRIMARY_COLOR,
            hover_color=HOVER_COLOR,
            command=self._start_scrape,
        )
        self._run_btn.pack(padx=16, fill="x")

        self._stop_btn = ctk.CTkButton(
            self._sidebar,
            text="■  Stop",
            fg_color="#555",
            hover_color="#444",
            command=self._stop_scrape,
            state="disabled",
        )
        self._stop_btn.pack(padx=16, pady=8, fill="x")

        ctk.CTkButton(
            self._sidebar,
            text="Export CSV",
            fg_color="#2C3E50",
            hover_color="#1A252F",
            command=self._export_csv,
        ).pack(padx=16, fill="x")

        # Main panel
        main = ctk.CTkFrame(self)
        main.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self._status_label = ctk.CTkLabel(main, text="Ready.", anchor="w")
        self._status_label.pack(fill="x", padx=8, pady=(4, 0))

        cols = ("Name", "Address", "Phone", "Rating", "Reviews", "Website", "Category")
        self._tree = ttk.Treeview(main, columns=cols, show="headings", selectmode="extended")
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=130, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=8, pady=8)

        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self._log = ctk.CTkTextbox(main, height=120, state="disabled")
        self._log.pack(fill="x", padx=8, pady=(0, 8))

    # ── Scraping ──────────────────────────────────────────────────────────────
    def _start_scrape(self):
        location = self._location_var.get().strip()
        if not location:
            messagebox.showwarning("{ProductName}", "Please enter a location.")
            return
        try:
            max_results = int(self._max_var.get())
        except ValueError:
            max_results = 50

        industry = self._industry_var.get()
        self._running = True
        self._run_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._set_status(f"Scraping {industry} in {location}…")

        thread = threading.Thread(target=self._run_scrape, args=(industry, location, max_results), daemon=True)
        thread.start()

    def _run_scrape(self, industry: str, location: str, max_results: int):
        try:
            engine = ScraperEngine()
            self._engine = engine
            results = engine.scrape(query=f"{industry} in {location}", max_results=max_results)
            self.after(0, self._populate_results, results)
        except Exception as exc:
            self.after(0, self._log_message, f"Error: {exc}")
        finally:
            self.after(0, self._scrape_done)

    def _stop_scrape(self):
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
        self._running = False
        self._scrape_done()

    def _scrape_done(self):
        self._running = False
        self._run_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._set_status("Done.")

    def _populate_results(self, results):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for r in results:
            self._tree.insert(
                "",
                "end",
                values=(
                    r.get("name", ""),
                    r.get("address", ""),
                    r.get("phone", ""),
                    r.get("rating", ""),
                    r.get("reviews", ""),
                    r.get("website", ""),
                    r.get("category", ""),
                ),
            )
        lead_db.save_many(results)
        self._log_message(f"Scraped {len(results)} leads.")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"leads_{datetime.now():%Y%m%d_%H%M%S}.csv",
        )
        if not path:
            return
        rows = [self._tree.item(i)["values"] for i in self._tree.get_children()]
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Address", "Phone", "Rating", "Reviews", "Website", "Category"])
            writer.writerows(rows)
        self._log_message(f"Exported {len(rows)} rows → {path}")

    def _set_status(self, msg: str):
        self._status_label.configure(text=msg)

    def _log_message(self, msg: str):
        self._log.configure(state="normal")
        self._log.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
        self._log.see("end")
        self._log.configure(state="disabled")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
```

---

## Step 5 — Create `{slug}/build.bat`

Write the PyInstaller build script:

```bat
@echo off
pyinstaller --onefile --windowed --name "{ProductName}" ^
  --add-data "shared;shared" ^
  --add-data "scraper_node;scraper_node" ^
  --add-data "{slug};{slug}" ^
  {slug}/app.py
echo Done. Check dist/{ProductName}.exe
pause
```

Replace `{ProductName}` and `{slug}` with the actual values.

---

## Step 6 — Update `shared/products.py`

Open `shared/products.py` if it exists; otherwise create it. Add (or update) an entry for this product in the `PRODUCTS` registry dict.

The file must follow this structure:

```python
"""
Shared product registry — maps slug → product metadata.
Used by the license server and any shared tooling.
"""

PRODUCTS: dict[str, dict] = {
    # existing entries are preserved here ...
    "{slug}": {
        "name":              "{ProductName}",
        "price_monthly":     {MONTHLY_PRICE},
        "price_lifetime":    {LIFETIME_PRICE},
        "extra_node_price":  {EXTRA_NODE_PRICE},
        "color":             "{PRIMARY_COLOR}",
    },
}
```

If the file already has a `PRODUCTS` dict, merge the new entry in without removing existing ones.

---

## Step 7 — Confirm and summarize

After writing all files, print a confirmation message to the user with:

1. A list of every file created or modified, using their paths relative to the repo root.
2. How to run the app from source:
   ```
   cd C:\Users\ADMIN\Desktop\gmaps-scraper-suite
   python {slug}/app.py
   ```
3. How to build the `.exe`:
   ```
   cd C:\Users\ADMIN\Desktop\gmaps-scraper-suite
   {slug}\build.bat
   ```
4. Where the built executable will appear: `dist/{ProductName}.exe`
5. A reminder to add the product to the license server database so keys can be generated for it.
