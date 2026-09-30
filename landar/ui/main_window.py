from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QHBoxLayout, QLineEdit, QMainWindow, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)
from landar.config import APP_NAME
from landar.core.permissions import Actor, PermissionDenied
from landar.services import discovery, monitoring
from landar.ui.components import caps, chip, dot, icon, label
from landar.ui.registry import PAGES
from landar.ui.theme import C

class NavItem(QPushButton):
    def __init__(self, text, icon_name):
        super().__init__(); self.setObjectName("navItem"); self.setCheckable(True); self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self); h.setContentsMargins(8, 4, 8, 4); h.setSpacing(10)
        self.ic = icon(icon_name, C["on_surface_variant"], 18); self.tx = label(text, C["on_surface_variant"], 13)
        for w in (self.ic, self.tx): w.setAttribute(Qt.WA_TransparentForMouseEvents)
        h.addWidget(self.ic); h.addWidget(self.tx, 1); self.toggled.connect(self._recolor)
    def _recolor(self, on):
        col = C["on_primary_container"] if on else C["on_surface_variant"]
        self.ic.setStyleSheet(f"color:{col}; background:transparent;"); self.tx.setStyleSheet(f"color:{col}; background:transparent; font-size:13px; font-weight:{'600' if on else '400'}; font-family:'Inter';")

class Sidebar(QFrame):
    def __init__(self, pages):
        super().__init__(); self.setObjectName("sidebar"); self.setFixedWidth(288); v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        head = QFrame(); head.setObjectName("sideHead"); hv = QVBoxLayout(head); hv.setContentsMargins(14, 14, 14, 12); hv.setSpacing(10)
        brand = QHBoxLayout(); brand.addWidget(icon("hub", C["primary"], 30)); t = QVBoxLayout(); t.setSpacing(0)
        name = label("LANDAR", C["primary"], 16, bold=True); f = name.font(); f.setLetterSpacing(QFont.AbsoluteSpacing, 1.5); name.setFont(f)
        t.addWidget(name); t.addWidget(caps("Control Plane v0.2")); brand.addLayout(t); brand.addStretch(); hv.addLayout(brand)
        tenant = QFrame(); tenant.setObjectName("tenant"); tl = QHBoxLayout(tenant); tl.setContentsMargins(8, 8, 8, 8)
        tl.addWidget(icon("domain", C["primary"], 18)); tt = QVBoxLayout(); tt.setSpacing(0); tt.addWidget(caps("Active Network"))
        self.net = label("—", size=11, mono=True, weight=600); tt.addWidget(self.net); tl.addLayout(tt, 1); tl.addWidget(icon("unfold_more", C["outline_variant"], 14)); hv.addWidget(tenant)
        gw = QFrame(); gw.setObjectName("gateway"); gl = QHBoxLayout(gw); gl.setContentsMargins(8, 5, 8, 5)
        self.gdot = dot(C["tertiary"]); gl.addWidget(self.gdot); self.gtxt = label("NETWORK: ONLINE", C["tertiary"], 11, mono=True, bold=True); gl.addWidget(self.gtxt); gl.addStretch()
        self.gif = label("", C["outline"], 11, mono=True); gl.addWidget(self.gif); hv.addWidget(gw); v.addWidget(head)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;}"); scroll.viewport().setObjectName("vp"); scroll.viewport().setStyleSheet("#vp{background:transparent;}")
        host = QWidget(); host.setObjectName("navHost"); host.setStyleSheet("#navHost{background:transparent;}"); nv = QVBoxLayout(host)
        nv.setContentsMargins(8, 12, 8, 12); nv.setSpacing(2); self.group = QButtonGroup(self); self.group.setExclusive(True); self.items = []
        last = None
        for i, spec in enumerate(pages):
            if spec.group != last:
                last = spec.group; hdr = caps(spec.group); hdr.setContentsMargins(8, 12 if i else 0, 0, 4); nv.addWidget(hdr)
            b = NavItem(spec.name, spec.icon); self.group.addButton(b, i); nv.addWidget(b); self.items.append(b)
        nv.addStretch(); scroll.setWidget(host); v.addWidget(scroll, 1)
    def set_network(self, info):
        ok = "cidr" in info; col = C["tertiary"] if ok else C["error"]
        self.net.setText(info.get("cidr", "Not connected")); self.gtxt.setText("NETWORK: ONLINE" if ok else "NETWORK: OFFLINE")
        self.gtxt.setStyleSheet(f"color:{col}; background:transparent; font-weight:700; font-size:11px; font-family:'JetBrains Mono';"); self.gdot.setStyleSheet(f"background:{col}; border-radius:4px;")
        self.gif.setText(info.get("interface", ""))

class TopBar(QFrame):
    def __init__(self, actor, on_bell):
        super().__init__(); self.setObjectName("topbar"); self.setFixedHeight(64); h = QHBoxLayout(self); h.setContentsMargins(16, 0, 16, 0); h.setSpacing(14)
        box = QWidget(); box.setFixedWidth(520); box.setFixedHeight(34); self.search = QLineEdit(box); self.search.setObjectName("search"); self.search.setGeometry(0, 0, 520, 34)
        self.search.setPlaceholderText("Filter this table: users, IP, MAC, hostname...")
        ic = icon("search", C["outline"], 18); ic.setParent(box); ic.move(10, 8); k = chip("CTRL K", C["outline"]); k.setParent(box); k.move(440, 6); k.setObjectName("kbd")
        for w in (ic, k): w.show()
        h.addWidget(box); h.addStretch()
        self.bell = QPushButton(); self.bell.setFlat(True); self.bell.setCursor(Qt.PointingHandCursor); self.bell.clicked.connect(on_bell)
        bl = QHBoxLayout(self.bell); bl.setContentsMargins(6, 4, 6, 4); bl.addWidget(icon("notifications", C["on_surface_variant"], 22)); self.bell.setFixedSize(40, 36)
        self.badge = label("0", C["on_error"], 10, mono=True, bold=True); self.badge.setParent(self.bell); self.badge.setAlignment(Qt.AlignCenter); self.badge.setFixedSize(18, 16)
        self.badge.setStyleSheet(f"background:{C['error']}; color:{C['on_error']}; border-radius:8px;"); self.badge.move(20, 2); self.badge.hide(); h.addWidget(self.bell)
        who = QVBoxLayout(); who.setSpacing(0); n = label(actor.username, size=12, weight=600); n.setAlignment(Qt.AlignRight); r = caps(actor.role); r.setAlignment(Qt.AlignRight)
        who.addWidget(n); who.addWidget(r); h.addLayout(who); h.setAlignment(who, Qt.AlignVCenter)
        av = label(actor.username[:2].upper(), C["on_primary_container"], 12, bold=True); av.setFixedSize(32, 32); av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"background:{C['primary_container']}; color:{C['on_primary_container']}; border-radius:16px;"); h.addWidget(av)
    def set_badge(self, n): self.badge.setText(str(min(n, 99))); self.badge.setVisible(n > 0)

class MainWindow(QMainWindow):
    def __init__(self, actor: Actor):
        super().__init__(); self.actor = actor; self.setWindowTitle(f"{APP_NAME} — Control Plane"); self.resize(1440, 860); self.setMinimumSize(1100, 700)
        self.specs = [s for s in PAGES if actor.can(s.permission)]
        root = QWidget(); root.setObjectName("root"); lay = QHBoxLayout(root); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0); self.setCentralWidget(root)
        self.side = Sidebar(self.specs); lay.addWidget(self.side)
        right = QVBoxLayout(); right.setSpacing(0); lay.addLayout(right, 1)
        self.top = TopBar(actor, self.open_approvals); right.addWidget(self.top)
        self.stack = QStackedWidget(); self.stack.setObjectName("content"); right.addWidget(self.stack, 1)
        self.pages = [s.factory(actor) for s in self.specs]
        for p in self.pages: self.stack.addWidget(p)
        self.side.group.idClicked.connect(self.show_page); self.top.search.textChanged.connect(lambda t: self.stack.currentWidget().apply_filter(t))
        QShortcut(QKeySequence("Ctrl+K"), self, activated=lambda: (self.top.search.setFocus(), self.top.search.selectAll()))
        self.show_page(0)
    def open_approvals(self):
        for i, s in enumerate(self.specs):
            if s.name == "Approvals": self.show_page(i); return
    def show_page(self, i):
        self.side.items[i].setChecked(True); self.top.search.clear(); self.stack.setCurrentIndex(i); self.pages[i].refresh()
        info = discovery.network_info(self.actor) if self.actor.can("network.view") else {}
        self.side.set_network(info)
        try: self.top.set_badge(monitoring.overview(self.actor)["unknown"])
        except PermissionDenied: self.top.set_badge(0)
