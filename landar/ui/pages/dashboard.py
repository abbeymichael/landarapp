from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QMessageBox, QAbstractItemView
from PySide6.QtGui import QColor, QFont
from landar.core.permissions import PermissionDenied
from landar.services import devices, discovery, monitoring
from landar.ui.components import KpiCard, SectionCard, button, caps, chip, dot, hbox, icon, label
from landar.ui.pages.base import Page, confirm, time_ago
from landar.ui.theme import C, MONO

ABBR = {"Students": "S", "Teachers": "T", "Staff": "F", "Guests": "G", "Administrators": "A", "Contractors": "C"}

class DashboardPage(Page):
    title, subtitle = "Network Control Center", ""
    def __init__(self, actor):
        super().__init__(actor)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); self.root.addWidget(scroll, 1)
        scroll.setStyleSheet("QScrollArea{background:transparent;}"); scroll.viewport().setObjectName("vp"); scroll.viewport().setStyleSheet("#vp{background:transparent;}")
        host = QWidget(); host.setObjectName("dashHost"); host.setStyleSheet("#dashHost{background:transparent;}"); scroll.setWidget(host); self.body = QVBoxLayout(host); self.body.setContentsMargins(0, 0, 0, 0); self.body.setSpacing(14)
        self.ribbon = QHBoxLayout(); self.body.addLayout(self.ribbon)
        self.kpis = QHBoxLayout(); self.kpis.setSpacing(6); self.body.addLayout(self.kpis)
        cols = QHBoxLayout(); cols.setSpacing(14); self.body.addLayout(cols, 1)
        left, right = QVBoxLayout(), QVBoxLayout(); left.setSpacing(14); right.setSpacing(14); cols.addLayout(left, 2); cols.addLayout(right, 1)
        self.stream = SectionCard("Security & Anomaly Stream", "warning", "Real-time")
        self.snapshot = SectionCard("Online Devices Live Snapshot", "sync", "From last scan")
        self.guard = SectionCard("Boundary Guard State", "verified_user", "Security model")
        self.activity = SectionCard("Recent Activity", "receipt_long", "Audit trail")
        left.addWidget(self.stream); left.addWidget(self.snapshot); left.addStretch()
        right.addWidget(self.guard); right.addWidget(self.activity); right.addStretch()

    @staticmethod
    def _clear(layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            elif it.layout(): DashboardPage._clear(it.layout())

    def refresh(self):
        try: o = monitoring.overview(self.actor)
        except PermissionDenied: return
        net = discovery.network_info(self.actor) if self.actor.can("network.view") else {}
        for lay in (self.ribbon, self.kpis): self._clear(lay)
        # breadcrumb ribbon
        self.ribbon.addWidget(caps("Operations Node")); self.ribbon.addWidget(icon("chevron_right", C["outline"], 14))
        self.ribbon.addWidget(label("LIVE TELEMETRY PLANE", C["primary"], 10, bold=True)); self.ribbon.addSpacing(8)
        self.ribbon.addWidget(chip(f"NET: {net['cidr']}" if "cidr" in net else "NET: NOT CONNECTED"))
        self.ribbon.addWidget(chip(f"LAST SCAN: {time_ago(o['last_scan']).upper()}", C["primary"])); self.ribbon.addStretch()
        self.ribbon.addWidget(button("Re-Poll", icon_name="refresh", on_click=self.refresh))
        # KPI ribbon (real values only)
        groups = " · ".join(f"{n}{ABBR.get(g, g[0])}" for g, n in sorted(o["groups"].items(), key=lambda x: -x[1])[:4]) or "no users"
        unk = o["unknown"]; fail = o["auth_fail_24h"]
        tiles = [
            ("Network", "ONLINE" if "cidr" in net else "OFFLINE", net.get("interface", "—"), C["tertiary"] if "cidr" in net else C["error"], dot(C["tertiary"] if "cidr" in net else C["error"])),
            ("This Host", net.get("ip", "—"), net.get("cidr", ""), None, icon("router", C["primary"], 14)),
            ("Active Users", str(o["users_active"]), groups, None, icon("group", C["secondary"], 14)),
            ("Endpoints", str(o["devices_total"]), f"{o['devices_online']} online", None, icon("devices", C["primary"], 14)),
            ("Auth Fail (24h)", str(fail), "failed logins", C["error"] if fail else None, icon("lock", C["error"] if fail else C["outline"], 14)),
            ("Unknown MACs", str(unk), "require approval" if unk else "none pending", C["warn"] if unk else None, icon("fingerprint", C["warn"] if unk else C["outline"], 14)),
            ("Blocked", str(o["blocked"]), "devices", None, icon("block", C["outline"], 14)),
        ]
        for t in tiles:
            self.kpis.addWidget(KpiCard(t[0], t[1], t[2], t[3], t[4]), 1)
        self._fill_stream(); self._fill_snapshot(); self._fill_guard(); self._fill_activity()

    # ---- panels -----------------------------------------------------------------
    def _alert_row(self, title, color, icon_name, chips, desc, actions=()):
        row = QFrame(); row.setObjectName("row"); row.setMinimumHeight(96 if actions else 84); h = QHBoxLayout(row); h.setContentsMargins(12, 10, 12, 10); h.setSpacing(12)
        box = QFrame(); box.setFixedSize(40, 40); box.setStyleSheet(f"background:{C['lowest']}; border-radius:4px;")
        bl = QVBoxLayout(box); bl.setContentsMargins(0, 0, 0, 0); bl.addWidget(icon(icon_name, color, 20), 0, Qt.AlignCenter); h.addWidget(box, 0, Qt.AlignTop)
        mid = QVBoxLayout(); mid.setSpacing(4); mid.addWidget(label(title.upper(), color, 12, mono=True, bold=True))
        mid.addWidget(hbox(*[chip(c) for c in chips], stretch_end=True)); d = label(desc, C["on_surface_variant"], 12); d.setWordWrap(True); d.setMinimumHeight(34); mid.addWidget(d)
        h.addLayout(mid, 1)
        if actions: h.addLayout(self._col(actions), 0)
        return row

    @staticmethod
    def _col(widgets):
        v = QVBoxLayout(); v.setSpacing(6)
        for w in widgets: v.addWidget(w)
        v.addStretch(); return v

    def _fill_stream(self):
        self.stream.clear(); n = 0
        try: unknown = monitoring.unknown_devices(self.actor, 4)
        except PermissionDenied: unknown = []
        for d in unknown:
            n += 1; who = d["hostname"] or "unnamed device"
            approve = button("Approve", "", "check_circle", lambda _=False, i=d["id"]: self._set(i, "Approved"))
            block = button("Block MAC", "danger", "block", lambda _=False, i=d["id"]: self._set(i, "Blocked"))
            for b in (approve, block): b.setEnabled(self.actor.can("devices.manage"))
            self.stream.body.addWidget(self._alert_row(
                "Unknown MAC discovered", C["error"], "fingerprint", [d["mac"], d["ip"] or "no IP"],
                f"{who} · {d['vendor'] or 'vendor unknown'}. First detected {time_ago(d['first_seen'])}. Approve it if you recognise it.", (approve, block)))
        try: fails = monitoring.recent_auth_failures(self.actor, 2)
        except PermissionDenied: fails = []
        for f in fails:
            n += 1
            self.stream.body.addWidget(self._alert_row("Authentication failure", C["warn"], "lock", [f["actor"] or "unknown"], f"Failed login attempt {time_ago(f['ts'])}."))
        if not n: self.stream.body.addWidget(label("Nothing needs attention. Run a scan from Device Inventory to look for unknown devices.", C["outline"], 12))

    def _set(self, dev_id, state):
        if state == "Blocked" and not confirm(self, "Blocking records the decision (enforcement needs a firewall provider). Continue?"): return
        self.safely(devices.set_state, self.actor, dev_id, state)

    def _fill_snapshot(self):
        self.snapshot.clear()
        try: rows = monitoring.online_devices(self.actor, 8)
        except PermissionDenied: rows = []
        if not rows: self.snapshot.body.addWidget(label("No devices online. Use Scan network in Device Inventory.", C["outline"], 12)); return
        heads = ["HOST / DEVICE", "IP", "MAC", "VENDOR", "STATE"]; t = QTableWidget(len(rows), len(heads)); t.setHorizontalHeaderLabels(heads)
        t.verticalHeader().hide(); t.setShowGrid(False); t.setEditTriggers(QAbstractItemView.NoEditTriggers); t.setSelectionMode(QAbstractItemView.NoSelection)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); t.setFixedHeight(40 + 34 * len(rows)); t.verticalHeader().setDefaultSectionSize(34)
        for r, d in enumerate(rows):
            for c, v in enumerate((d["hostname"] or "—", d["ip"], d["mac"], d["vendor"] or "—", d["state"])):
                it = QTableWidgetItem(str(v))
                if c in (1, 2): f = QFont(MONO); f.setPixelSize(12); it.setFont(f)
                if c == 4: it.setForeground(QColor({"Approved": C["tertiary"], "Blocked": C["error"], "Unknown": C["warn"]}.get(str(v), C["on_surface"])))
                t.setItem(r, c, it)
        self.snapshot.body.addWidget(t)

    def _fill_guard(self):
        self.guard.clear()
        items = [("Discovery", "ARP scan, read-only", "READ-ONLY", C["primary"]),
                 ("Monitoring", "Live telemetry", "NOT BUILT", C["outline"]),
                 ("Configuration", "Router / firewall control", "NO PROVIDER", C["outline"]),
                 ("Control Plane", "RBAC + audit on every action", "ENFORCED", C["tertiary"])]
        for i, (name, sub, tag, col) in enumerate(items, 1):
            row = QFrame(); row.setObjectName("row"); h = QHBoxLayout(row); h.setContentsMargins(10, 8, 10, 8)
            num = label(str(i), C["primary"], 11, bold=True); num.setFixedSize(22, 22); num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"background:{C['lowest']}; border-radius:11px; color:{C['primary']};"); h.addWidget(num)
            mid = QVBoxLayout(); mid.setSpacing(0); mid.addWidget(label(name, size=13, weight=600)); mid.addWidget(caps(sub)); h.addLayout(mid, 1)
            h.addWidget(chip(tag, col)); self.guard.body.addWidget(row)

    def _fill_activity(self):
        self.activity.clear()
        try: rows = monitoring.recent_activity(self.actor, 6)
        except PermissionDenied: rows = []
        for r in rows:
            bad = r["result"] != "success"
            txt = label(f"{r['actor']} · {r['action']}" + (f" · {r['target']}" if r["target"] else ""), C["on_surface_variant"], 11, mono=True)
            line = hbox(dot(C["error"] if bad else C["tertiary"], 6), txt, spacing=8); line.layout().addStretch(); line.layout().addWidget(label(time_ago(r["ts"]), C["outline"], 10, mono=True))
            self.activity.body.addWidget(line)
