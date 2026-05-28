import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.config import OUTPUT_DIR

DISPLAY_COLS = [
    ("title", "Business Name", 200),
    ("category", "Category", 130),
    ("address", "Address", 200),
    ("phone", "Phone", 120),
    ("website", "Website", 160),
    ("review_rating", "Rating", 70),
    ("review_count", "Reviews", 70),
    ("status", "Status", 80),
    ("price_range", "Price", 60),
    ("emails", "Emails", 160),
    ("scraped_at", "Scraped", 130),
]


def _friendly_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


class IndustrySummary:
    def __init__(self, name: str, file: Path, count: int, last_update: Optional[str]):
        self.name = name
        self.file = file
        self.count = count
        self.last_update = last_update


class DataManager:
    def get_industries(self) -> list[IndustrySummary]:
        result = []
        for f in sorted(OUTPUT_DIR.glob("*.csv")):
            name = f.stem.replace("_", " ").title()
            rows = self._count_rows(f)
            last = self._last_scraped(f)
            result.append(IndustrySummary(name, f, rows, last))
        return result

    def get_total_count(self) -> int:
        total = 0
        for f in OUTPUT_DIR.glob("*.csv"):
            total += self._count_rows(f)
        return total

    def get_rows(
        self,
        industry_file: Optional[Path] = None,
        search: str = "",
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        files = [industry_file] if industry_file else list(OUTPUT_DIR.glob("*.csv"))
        all_rows = []
        for f in files:
            if not f.exists():
                continue
            try:
                with open(f, "r", encoding="utf-8", newline="") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        all_rows.append(row)
            except Exception:
                pass

        if search:
            s = search.lower()
            all_rows = [
                r for r in all_rows
                if any(s in str(v).lower() for v in r.values())
            ]

        total = len(all_rows)
        page_rows = all_rows[offset: offset + limit]
        return page_rows, total

    def _count_rows(self, f: Path) -> int:
        try:
            with open(f, "r", encoding="utf-8", newline="") as fh:
                reader = csv.reader(fh)
                next(reader, None)  # skip header
                return sum(1 for _ in reader)
        except Exception:
            return 0

    def _last_scraped(self, f: Path) -> Optional[str]:
        try:
            with open(f, "r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                last = None
                for row in reader:
                    ts = row.get("scraped_at", "")
                    if ts:
                        last = ts
                return _friendly_date(last) if last else None
        except Exception:
            return None
