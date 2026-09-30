"""Small reusable building blocks that mirror the HTML design: caps labels, chips, KPI cards, section cards, icons."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from landar.ui.fonts import icon_char
from landar.ui.theme import C, MONO, SANS

def _style(w, color=None, size=13, bold=False, mono=False, weight=None):
    """Font props go in the widget stylesheet: they must beat the app-wide '* {font-size}' rule."""
    wt = weight or (700 if bold else 400)
    w.setStyleSheet(f"color:{color or C['on_surface']}; background:transparent; font-size:{size}px; font-weight:{wt}; "
                    f"font-family:'{MONO if mono else SANS}';")
    return w

def label(text="", color=None, size=13, bold=False, mono=False, weight=None):
    return _style(QLabel(text), color or C["on_surface"], size, bold, mono, weight)

def caps(text, color=None):
    """label-caps: 10px, bold, uppercase, wide tracking."""
    l = _style(QLabel(text.upper()), color or C["outline"], 10, bold=True); f = l.font()
    f.setLetterSpacing(QFont.AbsoluteSpacing, 0.9); l.setFont(f); return l

def icon(name, color=None, size=18):
    l = QLabel(icon_char(name))
    l.setStyleSheet(f"color:{color or C['on_surface_variant']}; background:transparent; font-size:{size}px; font-family:'Material Symbols Outlined';")
    l.setFixedSize(size + 2, size + 2)
    l.setAlignment(Qt.AlignCenter); return l

def dot(color, size=8):
    d = QFrame(); d.setFixedSize(size, size); d.setStyleSheet(f"background:{color}; border-radius:{size // 2}px;"); return d

def chip(text, color=None, high=True):
    w = QFrame(); w.setObjectName("chipHigh" if high else "chip"); l = QHBoxLayout(w); l.setContentsMargins(6, 2, 6, 2)
    l.addWidget(label(text, color or C["primary"], 11, mono=True)); return w

def button(text, kind="", icon_name=None, on_click=None):
    b = QPushButton((icon_char(icon_name) + "  " if icon_name else "") + text.upper()); 
    if kind: b.setProperty("kind", kind)
    if on_click: b.clicked.connect(on_click)
    b.setCursor(Qt.PointingHandCursor); return b

def hbox(*widgets, spacing=8, margins=(0, 0, 0, 0), stretch_end=False):
    w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(*margins); l.setSpacing(spacing)
    for x in widgets: l.addWidget(x)
    if stretch_end: l.addStretch()
    return w

class KpiCard(QFrame):
    """Dense metric tile: CAPS title + right accessory, big value, mono subtext."""
    def __init__(self, title, value, sub="", value_color=None, accessory=None):
        super().__init__(); self.setObjectName("card"); v = QVBoxLayout(self); v.setContentsMargins(10, 8, 10, 8); v.setSpacing(4)
        top = QHBoxLayout(); top.addWidget(caps(title)); top.addStretch()
        if accessory: top.addWidget(accessory)
        v.addLayout(top); v.addWidget(label(value, value_color or C["on_surface"], 16, weight=600)); s = label(sub, C["outline"], 11, mono=True)
        v.addWidget(s); self.setMinimumHeight(86)

class SectionCard(QFrame):
    """Card with icon + headline title + optional right-side caps tag; add content to .body."""
    def __init__(self, title, icon_name, tag=None, tag_color=None):
        super().__init__(); self.setObjectName("card"); v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        head = QFrame(); head.setObjectName("cardHead"); h = QHBoxLayout(head); h.setContentsMargins(14, 10, 14, 10)
        h.addWidget(icon(icon_name, C["primary"], 18)); h.addWidget(label(title, size=15, weight=600)); h.addStretch()
        if tag: h.addWidget(caps(tag, tag_color))
        v.addWidget(head); self.body = QVBoxLayout(); self.body.setContentsMargins(14, 12, 14, 12); self.body.setSpacing(8)
        bw = QWidget(); bw.setLayout(self.body); v.addWidget(bw)
    def clear(self):
        self._drop(self.body)
    @staticmethod
    def _drop(layout):
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w: w.setParent(None); w.deleteLater()
            elif it.layout(): SectionCard._drop(it.layout())

def glyph_icon(name, color=None, size=18) -> QIcon:
    """Render a Material Symbols glyph into a QIcon (for QLineEdit actions, tool buttons, etc.)."""
    pm = QPixmap(size * 2, size * 2); pm.fill(Qt.transparent); p = QPainter(pm)
    f = QFont("Material Symbols Outlined"); f.setPixelSize(size * 2 - 4); p.setFont(f); p.setPen(QColor(color or C["outline"]))
    p.drawText(pm.rect(), Qt.AlignCenter, icon_char(name)); p.end(); return QIcon(pm)
