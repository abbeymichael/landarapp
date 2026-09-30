import json
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QFont

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_icons: dict = {}

def load_fonts(app) -> None:
    """Register bundled Inter / JetBrains Mono / Material Symbols so the UI looks identical on every machine."""
    for f in ASSETS.glob("*.ttf"): QFontDatabase.addApplicationFont(str(f))
    _icons.update(json.loads((ASSETS / "icons.json").read_text()))
    app.setFont(QFont("Inter", 10))

def icon_char(name: str) -> str: return chr(_icons.get(name, 0xE88E))   # fallback: info
