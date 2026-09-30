"""Base classes for pages. New feature page = subclass Page (or TablePage), then register it in ui/registry.py."""
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QDialog, QFormLayout, QDialogButtonBox)
from landar.core.permissions import Actor, PermissionDenied
from landar.ui.theme import BAD_VALUES, WARN_VALUES

def confirm(parent, msg) -> bool:
    return QMessageBox.question(parent, "Confirm", msg) == QMessageBox.Yes

def form_dialog(parent, title, fields) -> bool:
    """fields: [(label, widget)]. Returns True if accepted."""
    d = QDialog(parent); d.setWindowTitle(title); f = QFormLayout(d)
    for label, w in fields: f.addRow(label, w)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
    return bool(d.exec())

class Page(QWidget):
    title = "Page"
    def __init__(self, actor: Actor):
        super().__init__(); self.actor = actor
        self.root = QVBoxLayout(self); h = QLabel(self.title); h.setObjectName("h"); self.root.addWidget(h)
    def refresh(self): """Called each time the page is shown."""
    def safely(self, fn, *args):
        """Run a service call; show validation/permission errors instead of crashing."""
        try: fn(*args)
        except (PermissionDenied, ValueError, sqlite3.Error) as e: QMessageBox.warning(self, "LANDAR", str(e))
        self.refresh()

class TablePage(Page):
    headers: list[str] = []
    def load_rows(self): raise NotImplementedError
    def __init__(self, actor):
        super().__init__(actor)
        self.bar = QHBoxLayout(); self.root.addLayout(self.bar)
        self.table = QTableWidget(); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().hide(); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.root.addWidget(self.table)
    def add_button(self, text, fn, perm=None):
        b = QPushButton(text); b.clicked.connect(fn); ok = perm is None or self.actor.can(perm)
        b.setEnabled(ok); b.setToolTip("" if ok else "Your role lacks this permission"); self.bar.addWidget(b); return b
    def selected_id(self):
        r = self.table.currentRow(); return int(self.table.item(r, 0).text()) if r >= 0 else None
    def refresh(self):
        try: rows = self.load_rows()
        except PermissionDenied: rows = []
        t = self.table; t.setColumnCount(len(self.headers)); t.setHorizontalHeaderLabels(self.headers); t.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate(tuple(row)):
                it = QTableWidgetItem("" if v is None else str(v)); it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if str(v) in BAD_VALUES: it.setForeground(Qt.red)
                if str(v) in WARN_VALUES: it.setForeground(Qt.yellow)
                t.setItem(r, c, it)
