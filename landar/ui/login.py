"""Sign-in window: brand panel + form. Returns an Actor via LoginDialog.actor."""
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget
from landar.config import APP_NAME
from landar.services import auth
from landar.ui.components import button, caps, glyph_icon, hbox, icon, label
from landar.ui.dialogs import copy_to_clipboard
from landar.ui.theme import C

MAX_FREE_ATTEMPTS = 3   # after this, the form pauses with a growing countdown (UI-level throttle)

class LoginDialog(QDialog):
    def __init__(self, first_run_pw: str | None = None):
        super().__init__(); self.actor = None; self._fails = 0; self._wait = 0
        self.setWindowTitle(f"{APP_NAME} — Sign in"); self.setFixedSize(920, 620)
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self._brand_panel()); root.addWidget(self._form_panel(first_run_pw), 1)
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick)
        (self.password if first_run_pw else self.username).setFocus()

    # ---- left: brand ----------------------------------------------------------
    def _brand_panel(self):
        f = QFrame(); f.setObjectName("loginBrand"); f.setFixedWidth(380)
        f.setStyleSheet(f"#loginBrand{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['lowest']},stop:1 #10222b);}}")
        v = QVBoxLayout(f); v.setContentsMargins(40, 40, 40, 32); v.setSpacing(0)
        name = label("LANDAR", C["primary"], 20, bold=True); ft = name.font(); ft.setLetterSpacing(QFont.AbsoluteSpacing, 2); name.setFont(ft)
        v.addWidget(hbox(icon("hub", C["primary"], 34), name, spacing=10, stretch_end=True)); v.addSpacing(64)
        v.addWidget(caps("Network control & management", C["primary"])); v.addSpacing(10)
        head = label("Know who is on your network, and what they can do.", size=26, weight=600); head.setWordWrap(True); v.addWidget(head); v.addSpacing(28)
        for ic, title, sub in (("verified_user", "Least-privilege access", "Role-based permissions on every action."),
                               ("receipt_long", "Everything is audited", "Who changed what, and when."),
                               ("hub", "Vendor independent", "Routers, firewalls and RADIUS plug in as providers.")):
            text = QVBoxLayout(); text.setSpacing(1); text.addWidget(label(title, size=13, weight=600)); s = label(sub, C["outline"], 12); s.setWordWrap(True); text.addWidget(s)
            row = QHBoxLayout(); row.setSpacing(12); row.addWidget(icon(ic, C["primary"], 20), 0, Qt.AlignTop); row.addLayout(text, 1); v.addLayout(row); v.addSpacing(16)
        v.addStretch(); v.addWidget(caps("Control Plane v0.2  ·  Local deployment")); return f

    # ---- right: form ----------------------------------------------------------
    def _field(self, ic, placeholder, password=False):
        e = QLineEdit(); e.setPlaceholderText(placeholder); e.setMinimumHeight(42)
        e.setStyleSheet(f"QLineEdit{{padding:0 8px; font-size:13px;}}"); e.addAction(glyph_icon(ic, C["outline"]), QLineEdit.LeadingPosition)
        if password:
            e.setEchoMode(QLineEdit.Password); act = QAction(glyph_icon("visibility", C["outline"]), "Show password", e); act.setCheckable(True)
            def toggle(on):
                e.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password); act.setIcon(glyph_icon("visibility_off" if on else "visibility", C["outline"]))
            act.toggled.connect(toggle); e.addAction(act, QLineEdit.TrailingPosition)
        e.returnPressed.connect(self._submit); return e

    def _form_panel(self, first_run_pw):
        p = QFrame(); p.setObjectName("loginForm"); p.setStyleSheet(f"#loginForm{{background:{C['bg']};}}")
        v = QVBoxLayout(p); v.setContentsMargins(64, 48, 64, 28); v.setSpacing(0)
        v.addWidget(caps("Administrator sign in", C["primary"])); v.addSpacing(8); v.addWidget(label("Welcome back", size=30, weight=600)); v.addSpacing(6)
        sub = label("Sign in to manage your network, devices and policies.", C["on_surface_variant"], 13); sub.setWordWrap(True); v.addWidget(sub); v.addSpacing(22)
        if first_run_pw: v.addWidget(self._first_run_box(first_run_pw)); v.addSpacing(18)
        v.addWidget(caps("Username")); v.addSpacing(6); self.username = self._field("person", "e.g. admin"); v.addWidget(self.username); v.addSpacing(16)
        v.addWidget(caps("Password")); v.addSpacing(6); self.password = self._field("lock", "Enter your password", True); v.addWidget(self.password); v.addSpacing(14)
        self.error = hbox(icon("error", C["error"], 16), label("", C["error"], 12), spacing=6, stretch_end=True); self.error.setVisible(False)
        self.error_text = self.error.layout().itemAt(1).widget(); v.addWidget(self.error); v.addSpacing(10)
        self.submit = button("Sign in", "primary", "login", self._submit); self.submit.setMinimumHeight(44); self.submit.setStyleSheet("font-size:12px;"); v.addWidget(self.submit)
        if first_run_pw: self.username.setText("admin")
        v.addStretch(); v.addWidget(hbox(icon("lock", C["outline"], 14), label("Authorized administrators only. All sign-ins are recorded.", C["outline"], 11), spacing=6, stretch_end=True))
        return p

    def _first_run_box(self, pw):
        b = QFrame(); b.setObjectName("notice"); b.setStyleSheet(f"#notice{{background:#0f2530; border-left:3px solid {C['primary']}; border-radius:4px;}}")
        v = QVBoxLayout(b); v.setContentsMargins(14, 10, 12, 10); v.setSpacing(6)
        v.addWidget(caps("First-time setup", C["primary"])); note = label("Admin account created. Copy this password now. It is shown once.", C["on_surface_variant"], 12)
        note.setWordWrap(True); v.addWidget(note)
        row = QHBoxLayout(); e = QLineEdit(pw); e.setReadOnly(True); e.setCursorPosition(0); e.setStyleSheet("font-family:'JetBrains Mono'; font-size:12px;"); row.addWidget(e, 1)
        row.addWidget(button("Copy", "", None, lambda: copy_to_clipboard(pw))); v.addLayout(row); return b

    # ---- behaviour ------------------------------------------------------------
    def _show_error(self, text): self.error_text.setText(text); self.error.setVisible(True)

    def _submit(self):
        if self._wait > 0: return
        u, pw = self.username.text().strip(), self.password.text()
        if not u or not pw: self._show_error("Enter your username and password."); return
        self.submit.setEnabled(False); self.submit.setText("SIGNING IN…"); self.repaint()
        actor = auth.login(u, pw)
        if actor: self.actor = actor; self.accept(); return
        self._fails += 1; self.password.clear(); self.password.setFocus()
        self._show_error("Incorrect username or password.")          # never reveal which one was wrong
        if self._fails >= MAX_FREE_ATTEMPTS: self._wait = 5 * (self._fails - MAX_FREE_ATTEMPTS + 1); self._timer.start(1000); self._tick(first=True)
        else: self._reset_button()

    def _tick(self, first=False):
        if not first: self._wait -= 1
        if self._wait <= 0: self._timer.stop(); self._reset_button(); return
        self.submit.setEnabled(False); self.submit.setText(f"TOO MANY ATTEMPTS · TRY AGAIN IN {self._wait}S")

    def _reset_button(self): self.submit.setEnabled(True); self.submit.setText("SIGN IN")

def prompt_login(first_run_pw=None):
    """Returns an Actor or None (window closed)."""
    d = LoginDialog(first_run_pw); return d.actor if d.exec() == QDialog.Accepted else None
