"""MAC -> vendor lookup. Drop the IEEE list (https://standards-oui.ieee.org/oui/oui.csv) at landar/data/oui.csv to enable it."""
import csv
from functools import lru_cache
from pathlib import Path

OUI_FILE = Path(__file__).resolve().parent.parent / "data" / "oui.csv"

@lru_cache(maxsize=1)
def _table() -> dict:
    if not OUI_FILE.exists(): return {}
    with open(OUI_FILE, newline="", encoding="utf-8", errors="replace") as f:
        return {r[1].strip().upper(): r[2].strip() for r in csv.reader(f) if len(r) >= 3 and len(r[1].strip()) == 6}

def lookup(mac: str) -> str | None:
    return _table().get(mac.replace(":", "").upper()[:6])
