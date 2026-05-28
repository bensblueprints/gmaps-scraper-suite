import sys
import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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

from data_manager import DataManager, DISPLAY_COLS
from shared.config import OUTPUT_DIR

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PAGE_SIZE = 200
REFRESH_INTERVAL_MS = 30_000  # 30 seconds


class StatCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str, color: str = "#4FC3F7", **kwargs):
        super().__init__(parent, fg_color="#1E2736", corner_radius=10, **kwargs)
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=11), text_color="#78909C").pack(
            anchor="w", padx=14, pady=(10, 2)
        )
        self.value_lbl = ctk.CTkLabel(
            self, text=value, font=ctk.CTkFont(size=26, weight="bold"), text_color=color
        )
        self.value_lbl.pack(anchor="w", padx=14, pady=(0, 10))

    def set_value(self, value: str):
        self.value_lbl.configure(text=value)


class MonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Google Maps Monitor Dashboard")
        self.geometry("1300x760")
        self.minsize(1000, 600)

        self.dm = DataManager()
        self._current_file: Path | None = None
        self._current_offset = 0
        self._total_rows = 0
        self._refresh_job = None

        self._build_ui()
        self._load_all()
        self._schedule_refresh()

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._build_header()
        self._build_stats_bar()
        self._build_sidebar()
        self._build_main_area()
        self._build_footer()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color="#0F1923")
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)

        ctk.CTkLabel(
            hdr, text="  Google Maps Monitor Dashboard",
            font=ctk.CTkFont(size=18, weight="bold"), text_color="#4FC3F7"
        ).pack(side="left", padx=10, pady=10)

        self.last_refresh_lbl = ctk.CTkLabel(
            hdr, text="", font=ctk.CTkFont(size=11), text_color="#546E7A"
        )
        self.last_refresh_lbl.pack(side="right", padx=15)

        ctk.CTkButton(
            hdr, text="Refresh Now", width=100, height=28,
            command=self._load_all
        ).pack(side="right", padx=8, pady=10)

    def _build_stats_bar(self):
        bar = ctk.CTkFrame(self, height=90, corner_radius=0, fg_color="#151F2E")
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_total = StatCard(bar, "TOTAL LEADS", "—", color="#4FC3F7")
        self.card_total.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.card_industries = StatCard(bar, "INDUSTRIES", "—", color="#A29BFE")
        self.card_industries.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

        self.card_today = StatCard(bar, "SCRAPED TODAY", "—", color="#27AE60")
        self.card_today.grid(row=0, column=2, sticky="nsew", padx=8, pady=8)

        self.card_current = StatCard(bar, "CURRENT VIEW", "—", color="#F39C12")
        self.card_current.grid(row=0, column=3, sticky="nsew", padx=8, pady=8)

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#111827")
        sidebar.grid(row=2, column=0, sticky="nsew", rowspan=2)
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sidebar, text="INDUSTRIES",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#78909C"
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self.ind_list_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.ind_list_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self.ind_list_frame.grid_columnconfigure(0, weight=1)

    def _build_main_area(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="#0D1117")
        main.grid(row=2, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(main, fg_color="#161B22", height=48)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(1, weight=1)

        self.industry_title_lbl = ctk.CTkLabel(
            toolbar, text="All Industries",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.industry_title_lbl.grid(row=0, column=0, padx=14, pady=8)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        search_entry = ctk.CTkEntry(
            toolbar, textvariable=self.search_var,
            placeholder_text="Search name, address, phone, email...",
            width=320, height=30
        )
        search_entry.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkButton(
            toolbar, text="Export CSV", width=100, height=30,
            command=self._export_csv,
            fg_color="#27AE60", hover_color="#1E8449"
        ).grid(row=0, column=2, padx=6, pady=8)

        ctk.CTkButton(
            toolbar, text="Open Folder", width=100, height=30,
            command=self._open_output_folder,
            fg_color="transparent", border_width=1
        ).grid(row=0, column=3, padx=(0, 10), pady=8)

        # Table
        table_frame = ctk.CTkFrame(main, fg_color="#0D1117")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.Treeview",
            background="#0D1117",
            foreground="#C9D1D9",
            fieldbackground="#0D1117",
            rowheight=26,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#161B22",
            foreground="#78909C",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", "#1F6FEB")],
            foreground=[("selected", "white")],
        )

        cols = [c[0] for c in DISPLAY_COLS]
        self.tree = ttk.Treeview(
            table_frame,
            columns=cols,
            show="headings",
            style="Custom.Treeview",
            selectmode="browse",
        )

        for col_id, col_label, col_width in DISPLAY_COLS:
            self.tree.heading(col_id, text=col_label, command=lambda c=col_id: self._sort_by(c))
            self.tree.column(col_id, width=col_width, minwidth=50, anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<Double-1>", self._on_row_double_click)

    def _build_footer(self):
        footer = ctk.CTkFrame(self, height=36, corner_radius=0, fg_color="#0F1923")
        footer.grid(row=3, column=1, sticky="ew")
        footer.grid_propagate(False)
        footer.grid_columnconfigure(1, weight=1)

        self.pagination_lbl = ctk.CTkLabel(
            footer, text="", font=ctk.CTkFont(size=11), text_color="#546E7A"
        )
        self.pagination_lbl.grid(row=0, column=0, padx=14)

        nav_frame = ctk.CTkFrame(footer, fg_color="transparent")
        nav_frame.grid(row=0, column=2, padx=10)

        self.prev_btn = ctk.CTkButton(
            nav_frame, text="< Prev", width=70, height=26,
            command=self._prev_page,
            fg_color="transparent", border_width=1
        )
        self.prev_btn.pack(side="left", padx=3)

        self.next_btn = ctk.CTkButton(
            nav_frame, text="Next >", width=70, height=26,
            command=self._next_page,
            fg_color="transparent", border_width=1
        )
        self.next_btn.pack(side="left", padx=3)

    # ── Data Loading ───────────────────────────────────────────────────────────

    def _load_all(self):
        def _run():
            industries = self.dm.get_industries()
            total = self.dm.get_total_count()
            today_count = self._count_today(industries)
            self.after(0, lambda: self._update_sidebar(industries))
            self.after(0, lambda: self._update_stats(total, len(industries), today_count))
            self.after(0, self._reload_table)
            now = datetime.now().strftime("%H:%M:%S")
            self.after(0, lambda: self.last_refresh_lbl.configure(text=f"Last refresh: {now}"))
        threading.Thread(target=_run, daemon=True).start()

    def _count_today(self, industries) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for ind in industries:
            try:
                with open(ind.file, "r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("scraped_at", "").startswith(today):
                            count += 1
            except Exception:
                pass
        return count

    def _update_stats(self, total: int, ind_count: int, today: int):
        self.card_total.set_value(f"{total:,}")
        self.card_industries.set_value(str(ind_count))
        self.card_today.set_value(f"{today:,}")

    def _update_sidebar(self, industries):
        for w in self.ind_list_frame.winfo_children():
            w.destroy()

        all_btn = ctk.CTkButton(
            self.ind_list_frame,
            text="  All Industries",
            anchor="w",
            fg_color="#1F6FEB",
            hover_color="#1558B0",
            font=ctk.CTkFont(size=12),
            command=self._show_all,
        )
        all_btn.pack(fill="x", pady=2)

        for ind in industries:
            label = f"  {ind.name}"
            count_str = f"{ind.count:,}"

            row_frame = ctk.CTkFrame(self.ind_list_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=1)
            row_frame.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                row_frame,
                text=label,
                anchor="w",
                fg_color="transparent",
                hover_color="#1C2433",
                font=ctk.CTkFont(size=12),
                command=lambda f=ind.file, n=ind.name: self._show_industry(f, n),
            )
            btn.grid(row=0, column=0, sticky="ew")

            ctk.CTkLabel(
                row_frame,
                text=count_str,
                font=ctk.CTkFont(size=11),
                text_color="#546E7A",
                width=50,
                anchor="e",
            ).grid(row=0, column=1, padx=(0, 4))

    def _show_all(self):
        self._current_file = None
        self._current_offset = 0
        self.industry_title_lbl.configure(text="All Industries")
        self._reload_table()

    def _show_industry(self, file: Path, name: str):
        self._current_file = file
        self._current_offset = 0
        self.industry_title_lbl.configure(text=name)
        self._reload_table()

    def _reload_table(self):
        search = self.search_var.get().strip()
        rows, total = self.dm.get_rows(
            industry_file=self._current_file,
            search=search,
            limit=PAGE_SIZE,
            offset=self._current_offset,
        )
        self._total_rows = total
        self._populate_table(rows)
        self._update_pagination()

    def _populate_table(self, rows: list[dict]):
        self.tree.delete(*self.tree.get_children())
        col_ids = [c[0] for c in DISPLAY_COLS]
        for i, row in enumerate(rows):
            vals = [row.get(c, "") for c in col_ids]
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", values=vals, tags=(tag,))
        self.tree.tag_configure("even", background="#0D1117")
        self.tree.tag_configure("odd", background="#111820")
        self.card_current.set_value(f"{len(rows):,}")

    def _update_pagination(self):
        start = self._current_offset + 1
        end = min(self._current_offset + PAGE_SIZE, self._total_rows)
        self.pagination_lbl.configure(
            text=f"Showing {start:,}–{end:,} of {self._total_rows:,} results"
        )
        self.prev_btn.configure(state="normal" if self._current_offset > 0 else "disabled")
        self.next_btn.configure(
            state="normal" if end < self._total_rows else "disabled"
        )

    def _prev_page(self):
        self._current_offset = max(0, self._current_offset - PAGE_SIZE)
        self._reload_table()

    def _next_page(self):
        self._current_offset += PAGE_SIZE
        self._reload_table()

    def _on_search_change(self, *_):
        self._current_offset = 0
        self.after(300, self._reload_table)

    def _sort_by(self, col: str):
        rows = [(self.tree.set(child, col), child) for child in self.tree.get_children("")]
        try:
            rows.sort(key=lambda x: float(x[0]) if x[0] else 0, reverse=True)
        except ValueError:
            rows.sort(key=lambda x: x[0].lower())
        for idx, (_, child) in enumerate(rows):
            self.tree.move(child, "", idx)

    def _on_row_double_click(self, event):
        item = self.tree.focus()
        if not item:
            return
        vals = self.tree.item(item, "values")
        cols = [c[0] for c in DISPLAY_COLS]
        detail = "\n".join(f"{c[1]}: {v}" for c, v in zip(DISPLAY_COLS, vals) if v)
        messagebox.showinfo("Lead Details", detail)

    # ── Export ─────────────────────────────────────────────────────────────────

    def _export_csv(self):
        ind_name = self.industry_title_lbl.cget("text").replace(" ", "_").lower()
        default = f"export_{ind_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default,
        )
        if not path:
            return

        search = self.search_var.get().strip()
        rows, _ = self.dm.get_rows(
            industry_file=self._current_file,
            search=search,
            limit=100_000,
            offset=0,
        )
        if not rows:
            messagebox.showinfo("Export", "No data to export.")
            return

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        messagebox.showinfo("Export Complete", f"Exported {len(rows):,} rows to:\n{path}")

    def _open_output_folder(self):
        import subprocess
        subprocess.Popen(f'explorer "{OUTPUT_DIR}"')

    # ── Auto-refresh ───────────────────────────────────────────────────────────

    def _schedule_refresh(self):
        self._refresh_job = self.after(REFRESH_INTERVAL_MS, self._auto_refresh)

    def _auto_refresh(self):
        self._load_all()
        self._schedule_refresh()

    def destroy(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        super().destroy()


def main():
    app = MonitorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
