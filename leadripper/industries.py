"""
Loads 4000+ GMB industries from shared/industries_data.json.
Falls back to a small built-in set if the JSON is missing.
"""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent
_DATA = _HERE.parent / "shared" / "industries_data.json"

# When frozen by PyInstaller, shared data is bundled at _MEIPASS/shared/
if getattr(sys, "frozen", False):
    _MEIPASS = Path(sys._MEIPASS)
    _DATA = _MEIPASS / "shared" / "industries_data.json"

try:
    with open(_DATA, encoding="utf-8") as f:
        INDUSTRIES = json.load(f)
except FileNotFoundError:
    INDUSTRIES = {
        "Restaurants":       {"queries": ["restaurants"],       "color": "#E74C3C"},
        "Plumbers":          {"queries": ["plumbers"],          "color": "#3498DB"},
        "Dentists":          {"queries": ["dentists"],          "color": "#2ECC71"},
        "Lawyers":           {"queries": ["lawyers"],           "color": "#9B59B6"},
        "Electricians":      {"queries": ["electricians"],      "color": "#F39C12"},
        "HVAC":              {"queries": ["HVAC companies"],    "color": "#1ABC9C"},
        "Auto Repair":       {"queries": ["auto repair shops"], "color": "#E67E22"},
        "Contractors":       {"queries": ["general contractors"],"color": "#7F8C8D"},
        "Cleaning Services": {"queries": ["cleaning services"], "color": "#D35400"},
        "Landscaping":       {"queries": ["landscaping"],       "color": "#27AE60"},
    }
