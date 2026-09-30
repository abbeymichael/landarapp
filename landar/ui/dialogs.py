"""Reusable dialogs/widgets for handling secrets. Secrets are selectable and copyable, never logged."""
import secrets
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QWidget)

def copy_to_clipboard(text: str) -> None:
    QGuiApplication.clipboard().setText(text)

class PasswordField(QWidget):
    """Password input with Show toggle (so it can be selected/copied), Generate, and Copy. Paste always works."""
    def __init__(self):
        super().__init__(); lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(); self.edit.setEchoMode(QLineEdit.Password)
        show = QCheckBox("Show"); show.toggled.connect(lambda on: self.edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        gen = QPushButton("Generate"); gen.clicked.connect(self._generate)
        cp = QPushButton("Copy"); cp.clicked.connect(lambda: copy_to_clipboard(self.edit.text()))
        self._show = show
        for w in (self.edit, show, gen, cp): lay.addWidget(w)
    def _generate(self):
        self.edit.setText(secrets.token_urlsafe(12)); self._show.setChecked(True)
    def text(self) -> str: return self.edit.text()

def show_secret_once(parent, title: str, message: str, username: str, secret: str) -> None:
    """Display a credential the admin must save. Both fields are selectable; Copy buttons provided."""
    d = QDialog(parent); d.setWindowTitle(title); d.setMinimumWidth(460); v = QVBoxLayout(d)
    v.addWidget(QLabel(message))
    for label, value in (("Username", username), ("Password", secret)):
        row = QHBoxLayout(); row.addWidget(QLabel(label + ":")); e = QLineEdit(value); e.setReadOnly(True)
        e.setCursorPosition(0); row.addWidget(e, 1)
        b = QPushButton(f"Copy {label.lower()}"); b.clicked.connect(lambda _=False, val=value: copy_to_clipboard(val)); row.addWidget(b)
        v.addLayout(row)
    v.addWidget(QLabel("Shown once. Save it now."))
    ok = QPushButton("I've saved it"); ok.clicked.connect(d.accept); v.addWidget(ok)
    d.exec()
