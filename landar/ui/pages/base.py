"""Base classes for pages. New feature page = subclass Page (or TablePage), then register it in ui/registry.py."""
import sqlite3
from datetime import datetime, timezone
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QDialog, QFormLayout, QDialogButtonBox, QAbstractItemView)
from landar.core.permissions import Actor, PermissionDenied
from landar.ui.components import button, caps, label
from landar.ui.theme import BAD_VALUES, C, GOOD_VALUES, MONO, WARN_VALUES

def confirm(parent, msg) -> bool:
    return QMessageBox.question(parent, "Confirm", msg) == QMessageBox.Yes

def time_ago(ts: str | None) -> str:
    if not ts: return "never"
    s = int((datetime.now(timezone.utc) - datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds())
    return "just now" if s < 60 else f"{s // 60}m ago" if s < 3600 else f"{s // 3600}h ago" if s < 86400 else f"{s // 86400}d ago"

def form_dialog(parent, title, fields) -> bool:
    """fields: [(label, widget)]. Returns True if accepted."""
    d = QDialog(parent); d.setWindowTitle(title); d.setMinimumWidth(420); f = QFormLayout(d); f.setContentsMargins(20, 20, 20, 16); f.setSpacing(10)
    for text, w in fields: f.addRow(caps(text), w)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
    return bool(d.exec())

def new_table() -> QTableWidget:
    t = QTableWidget(); t.setSelectionBehavior(QAbstractItemView.SelectRows); t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.verticalHeader().hide(); t.setShowGrid(False); t.setFocusPolicy(Qt.NoFocus)
    t.verticalHeader().setDefaultSectionSize(38); t.horizontalHeader().setHighlightSections(False)
    t.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter); return t

def fill_table(t, headers, rows, mono_cols=(), status_cols=()):
    """Shared renderer: styled cells, mono columns, good/warn/bad colors for status columns, compact columns fit content."""
    t.setColumnCount(len(headers)); t.setHorizontalHeaderLabels([h.upper() for h in headers]); t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(tuple(row)):
            s = "" if v is None else str(v); it = QTableWidgetItem(s); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            if headers[c] in mono_cols: f = QFont(MONO); f.setPixelSize(12); it.setFont(f)
            if headers[c] not in status_cols: pass
            elif s in BAD_VALUES: it.setForeground(QColor(C["error"]))
            elif s in WARN_VALUES: it.setForeground(QColor(C["warn"]))
            elif s in GOOD_VALUES: it.setForeground(QColor(C["tertiary"]))
            t.setItem(r, c, it)
    hh = t.horizontalHeader()
    for c, name in enumerate(headers): hh.setSectionResizeMode(c, QHeaderView.ResizeToContents if name in tuple(mono_cols) + tuple(status_cols) else QHeaderView.Stretch)

def selected_id(t):
    r = t.currentRow(); return int(t.item(r, 0).text()) if r >= 0 and t.item(r, 0) else None

class Page(QWidget):
    title, subtitle = "Page", ""
    def __init__(self, actor: Actor):
        super().__init__(); self.actor = actor
        self.root = QVBoxLayout(self); self.root.setContentsMargins(24, 20, 24, 20); self.root.setSpacing(12)
        if self.subtitle: self.root.addWidget(caps(self.subtitle))
        self.root.addWidget(label(self.title, size=24, weight=600))
    def refresh(self): """Called each time the page is shown."""
    def apply_filter(self, text: str): """Top-bar search hook (optional)."""
    def call(self, fn, *args):
        """Like safely() but returns (ok, result) so callers can use the return value."""
        try: return True, fn(*args)
        except (PermissionDenied, ValueError, sqlite3.Error) as e: QMessageBox.warning(self, "LANDAR", str(e)); return False, None
    def safely(self, fn, *args):
        """Run a service call; show validation/permission errors instead of crashing."""
        try: fn(*args)
        except (PermissionDenied, ValueError, sqlite3.Error) as e: QMessageBox.warning(self, "LANDAR", str(e))
        self.refresh()

class TablePage(Page):
    headers: list[str] = []
    status_cols = ("State", "Status", "Presence", "Result")   # only these columns get good/warn/bad colors
    mono_cols: tuple = ()          # header names rendered in JetBrains Mono (IDs, IPs, MACs, times)
    def load_rows(self): raise NotImplementedError
    def __init__(self, actor):
        super().__init__(actor); self._filter = ""
        self.bar = QHBoxLayout(); self.bar.setSpacing(8); self.root.addLayout(self.bar)
        self.table = new_table(); self.root.addWidget(self.table, 1)
    def add_button(self, text, fn, perm=None, kind=""):
        b = button(text, kind, on_click=fn); ok = perm is None or self.actor.can(perm)
        b.setEnabled(ok); b.setToolTip("" if ok else "Your role lacks this permission"); self.bar.addWidget(b); return b
    def selected_id(self): return selected_id(self.table)
    def apply_filter(self, text):
        self._filter = text.lower(); t = self.table
        for r in range(t.rowCount()):
            hit = not self._filter or any(t.item(r, c) and self._filter in t.item(r, c).text().lower() for c in range(t.columnCount()))
            t.setRowHidden(r, not hit)
    def refresh(self):
        try: rows = self.load_rows()
        except PermissionDenied: rows = []
        fill_table(self.table, self.headers, rows, self.mono_cols, self.status_cols); self.apply_filter(self._filter)
