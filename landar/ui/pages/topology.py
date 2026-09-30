"""Interactive topology map: QGraphicsView canvas (pan, wheel-zoom, click to select) + node telemetry panel."""
import json
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGraphicsItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
                               QMessageBox, QScrollArea, QVBoxLayout, QWidget)
from landar.core.constants import DEVICE_TYPES
from landar.core.permissions import PermissionDenied
from landar.services import devices, monitoring, topology
from landar.ui.components import SectionCard, button, caps, chip, dot, hbox, icon, label
from landar.ui.fonts import icon_char
from landar.ui.pages.base import Page, confirm, time_ago
from landar.ui.theme import C, MONO, SANS
from landar.ui.workers import ServiceWorker
from landar.services import discovery

TYPE_ICON = {"Laptop": "laptop", "Desktop": "desktop_windows", "Phone": "smartphone", "Tablet": "tablet", "Server": "dns", "Printer": "print",
             "Router": "router", "Switch": "lan", "Access point": "wifi", "IoT": "memory", "Camera": "videocam", "Unknown": "help"}
STATE_COLOR = {"Approved": C["tertiary"], "Known": C["secondary"], "Unknown": C["warn"], "Blocked": C["error"]}
W, H, COLS, X_GAP, ROW_GAP = 200, 62, 5, 216, 100

class NodeItem(QGraphicsItem):
    def __init__(self, node):
        super().__init__(); self.node = node; self.hover = False; self.setFlag(QGraphicsItem.ItemIsSelectable); self.setAcceptHoverEvents(True); self.setCursor(Qt.PointingHandCursor)
    def boundingRect(self): return QRectF(-6, -6, W + 12, H + 12)
    def hoverEnterEvent(self, e): self.hover = True; self.update()
    def hoverLeaveEvent(self, e): self.hover = False; self.update()
    def color(self):
        n = self.node
        if n["kind"] != "device" and n["kind"] != "gateway": return C["outline_variant"]
        return STATE_COLOR.get(n.get("state"), C["outline_variant"])
    def glyph(self):
        n = self.node; return {"internet": "public", "segment": "lan"}.get(n["kind"]) or ("router" if n["kind"] == "gateway" else TYPE_ICON.get(n.get("device_type"), "help"))
    def paint(self, p, opt, w):
        n = self.node; p.setRenderHint(QPainter.Antialiasing); sel = self.isSelected(); col = QColor(C["primary"] if sel else self.color())
        if n.get("online") == 0: p.setOpacity(0.5)
        if sel:
            g = QColor(C["primary"]); g.setAlpha(45); p.setPen(Qt.NoPen); p.setBrush(g); p.drawRoundedRect(QRectF(-5, -5, W + 10, H + 10), 9, 9)
        p.setBrush(QColor(C["high"] if (self.hover or sel) else C["low"])); p.setPen(QPen(col, 2 if sel else 1.2)); p.drawRoundedRect(QRectF(0, 0, W, H), 7, 7)
        p.setPen(Qt.NoPen); p.setBrush(QColor(C["lowest"])); p.drawRoundedRect(QRectF(10, 11, 40, 40), 5, 5)
        f = QFont("Material Symbols Outlined"); f.setPixelSize(24); p.setFont(f); p.setPen(QColor(C["primary"]))
        p.drawText(QRectF(10, 11, 40, 40), Qt.AlignCenter, icon_char(self.glyph()))
        tf = QFont(SANS); tf.setPixelSize(12); tf.setWeight(QFont.DemiBold); p.setFont(tf); p.setPen(QColor(C["on_surface"]))
        title = n["label"] + ("  (you)" if n.get("is_self") else ""); p.drawText(QRectF(60, 12, W - 86, 18), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(tf).elidedText(title, Qt.ElideRight, W - 86))
        sf = QFont(MONO); sf.setPixelSize(10); p.setFont(sf); p.setPen(QColor(C["outline"])); p.drawText(QRectF(60, 32, W - 70, 16), Qt.AlignLeft | Qt.AlignVCenter, QFontMetrics(sf).elidedText(n["sub"], Qt.ElideRight, W - 70))
        if n["kind"] in ("device", "gateway") and "online" in n:
            p.setPen(Qt.NoPen); p.setBrush(QColor(C["tertiary"] if n["online"] else C["outline"])); p.drawEllipse(QPointF(W - 14, 16), 4, 4)

class MapView(QGraphicsView):
    def __init__(self):
        super().__init__(); self.setScene(QGraphicsScene(self)); self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag); self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor(C["bg"])); p.setPen(QPen(QColor(C["outline_variant"]), 1.4)); step = 28
        x0, y0 = int(rect.left() // step) * step, int(rect.top() // step) * step
        for x in range(x0, int(rect.right()) + step, step):
            for y in range(y0, int(rect.bottom()) + step, step): p.drawPoint(x, y)
    def wheelEvent(self, e): k = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15; self.scale(k, k)
    def fit(self):
        r = self.scene().itemsBoundingRect().adjusted(-50, -50, 50, 50)
        if r.isEmpty(): return
        self.fitInView(r, Qt.KeepAspectRatio)
        if self.transform().m11() > 1.0: self.resetTransform(); self.centerOn(r.center())   # never zoom in past 100%

def layout(nodes):
    """id -> top-left position. Tiers: internet, gateway, segment, then host rows centred under the segment."""
    pos, y = {}, 0
    for kind in ("internet", "gateway", "segment"):
        for n in nodes:
            if n["kind"] == kind: pos[n["id"]] = (-W / 2, y); y += 130
    hosts = [n for n in nodes if n["kind"] == "device"]
    for i, n in enumerate(hosts):
        r, c = divmod(i, COLS); cnt = min(COLS, len(hosts) - r * COLS); pos[n["id"]] = ((c - (cnt - 1) / 2) * X_GAP - W / 2, y + 30 + r * ROW_GAP)
    return pos

class TopologyPage(Page):
    title, subtitle = "Topology", "Network"
    def __init__(self, actor):
        super().__init__(actor); self.graph = None; self.items = {}; self.worker = None; self._fitted = False
        bar = QHBoxLayout(); bar.setSpacing(8); self.root.addLayout(bar)
        tab = button("Logical Topology", "primary", "account_tree"); bar.addWidget(tab)
        for t in ("Physical Cabling / Rack", "VLAN Segmentation View"):
            b = button(t); b.setEnabled(False); b.setToolTip("Needs switch/VLAN integration (later phase)"); bar.addWidget(b)
        bar.addSpacing(12); self.flt = QComboBox(); self.flt.addItems(["Status: " + f for f in topology.FILTERS]); self.flt.currentIndexChanged.connect(self.refresh); bar.addWidget(self.flt)
        bar.addStretch()
        self.scan_btn = button("Run Discovery", "primary", "radar", self.scan); self.scan_btn.setEnabled(actor.can("network.scan")); bar.addWidget(self.scan_btn)
        bar.addWidget(button("Export JSON", "", "download", self.export))
        body = QHBoxLayout(); body.setSpacing(12); self.root.addLayout(body, 1)
        frame = QFrame(); frame.setObjectName("card"); fl = QVBoxLayout(frame); fl.setContentsMargins(0, 0, 0, 0)
        self.view = MapView(); fl.addWidget(self.view, 1); self.view.scene().selectionChanged.connect(self.on_select)
        tools = QHBoxLayout(); tools.setContentsMargins(10, 6, 10, 8); tools.addWidget(caps("Layer graph active")); tools.addWidget(chip("Discovery scan (ARP)", C["primary"])); tools.addStretch()
        for txt, fn in (("+", lambda: self.view.scale(1.2, 1.2)), ("−", lambda: self.view.scale(1 / 1.2, 1 / 1.2)), ("Fit", self.view.fit)):
            b = button(txt, "", None, fn); b.setMinimumWidth(36); tools.addWidget(b)
        fl.addLayout(tools); body.addWidget(frame, 1)
        side = QScrollArea(); side.setWidgetResizable(True); side.setFixedWidth(390); side.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); side.setFrameShape(QFrame.NoFrame); side.setObjectName("sideScroll")
        side.setStyleSheet("#sideScroll{background:transparent;}"); side.viewport().setObjectName("vp"); side.viewport().setStyleSheet("#vp{background:transparent;}")
        host = QWidget(); host.setObjectName("sideHost"); host.setStyleSheet("#sideHost{background:transparent;}"); hv = QVBoxLayout(host); hv.setContentsMargins(0, 0, 6, 0); hv.setSpacing(12)
        self.detail = SectionCard("Selected node telemetry", "radar"); self.events = SectionCard("Recent Discovery Events", "bolt", "Audit")
        hv.addWidget(self.detail); hv.addWidget(self.events); hv.addStretch(); side.setWidget(host); body.addWidget(side)
        self.legend = QHBoxLayout(); self.legend.setSpacing(18); self.root.addLayout(self.legend)

    # ---- data -> scene -----------------------------------------------------------
    def refresh(self):
        flt = self.flt.currentText().replace("Status: ", "")
        try: self.graph = topology.build(self.actor, state_filter=flt)
        except PermissionDenied: return
        sc = self.view.scene(); sc.blockSignals(True); sc.clear(); self.items = {}; pos = layout(self.graph["nodes"])
        for a, b in self.graph["edges"]:
            pa, pb = pos[a], pos[b]; s, t = QPointF(pa[0] + W / 2, pa[1] + H), QPointF(pb[0] + W / 2, pb[1]); mid = (s.y() + t.y()) / 2
            path = QPainterPath(s); path.cubicTo(QPointF(s.x(), mid), QPointF(t.x(), mid), t); it = QGraphicsPathItem(path)
            node = next(n for n in self.graph["nodes"] if n["id"] == b); off = node.get("online") == 0
            pen = QPen(QColor(C["outline_variant"] if off else C["primary"]), 1.4, Qt.DashLine if off else Qt.SolidLine); pen.setCosmetic(True); it.setPen(pen); it.setZValue(-1); sc.addItem(it)
        for n in self.graph["nodes"]:
            it = NodeItem(n); it.setPos(*pos[n["id"]]); sc.addItem(it); self.items[n["id"]] = it
        sc.blockSignals(False); self._legend(); self._events(); self.on_select()
        QTimer.singleShot(0, self.view.fit)

    def showEvent(self, e): super().showEvent(e); QTimer.singleShot(50, self.view.fit)

    def _legend(self):
        while self.legend.count():
            it = self.legend.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        c = self.graph["counts"]; self.legend.addWidget(chip(f"{c['online']} ONLINE / {c['total']} KNOWN", C["primary"]))
        for st, col in (("Approved", C["tertiary"]), ("Unknown", C["warn"]), ("Blocked", C["error"])):
            self.legend.addWidget(hbox(dot(col), label(f"{st} ({c['by_state'].get(st, 0)})", C["on_surface_variant"], 11, mono=True), spacing=6))
        self.legend.addWidget(label("Dashed line = offline in last scan", C["outline"], 11, mono=True)); self.legend.addStretch()
        if not self.graph["network"].get("gateway"): self.legend.addWidget(label("Gateway not detected", C["warn"], 11, mono=True))

    def _events(self):
        self.events.clear()
        try: rows = [r for r in monitoring.recent_activity(self.actor, 30) if r["action"] in ("device_discovered", "network_scan", "device_approved", "device_blocked")][:5]
        except PermissionDenied: rows = []
        if not rows: self.events.body.addWidget(label("No discovery events yet. Click Run Discovery.", C["outline"], 12))
        for r in rows:
            line = hbox(dot(C["primary"], 6), label(f"{r['action'].replace('_', ' ')} · {r['target'] or ''}", C["on_surface_variant"], 11, mono=True), spacing=8)
            line.layout().addStretch(); line.layout().addWidget(label(time_ago(r["ts"]), C["outline"], 10, mono=True)); self.events.body.addWidget(line)

    # ---- selection panel -----------------------------------------------------------
    def on_select(self):
        sel = [i for i in self.view.scene().selectedItems() if isinstance(i, NodeItem)]; self.detail.clear(); b = self.detail.body
        if not sel: b.addWidget(label("Click a node on the map to inspect it.", C["outline"], 12)); return
        n = sel[0].node; head = hbox(icon(sel[0].glyph(), C["primary"], 26), spacing=10); t = QVBoxLayout(); t.setSpacing(0)
        t.addWidget(label(n["label"], size=15, weight=600)); t.addWidget(caps({"internet": "Upstream", "gateway": "Default gateway", "segment": "LAN segment"}.get(n["kind"], n.get("device_type") or "Device")))
        head.layout().addLayout(t, 1)
        if n.get("state"): head.layout().addWidget(chip(n["state"].upper(), STATE_COLOR.get(n["state"], C["outline"])))
        b.addWidget(head)
        def grid(pairs):
            for i in range(0, len(pairs), 2):
                row = QHBoxLayout()
                for k, v in pairs[i:i + 2]:
                    col = QVBoxLayout(); col.setSpacing(1); col.addWidget(caps(k)); col.addWidget(label(str(v or "—"), C["primary"] if k.endswith("IP") else C["on_surface"], 11, mono=True)); row.addLayout(col, 1)
                b.addLayout(row)
        if n["kind"] == "internet": grid([("Reached via", n["sub"].replace("via ", ""))]); b.addWidget(self._note("Internet reachability is not measured yet (Phase 6)."))
        elif n["kind"] == "segment": grid([("Network", n["label"]), ("Interface", n.get("interface")), ("This host IP", n.get("ip")), ("Devices", n["sub"])])
        else:
            grid([("Management IP", n.get("ip")), ("Physical MAC", n.get("mac")), ("Vendor", n.get("vendor")), ("Type", n.get("device_type")),
                  ("Presence", "Online" if n.get("online") else "Offline"), ("Last seen", time_ago(n.get("last_seen"))), ("First seen", time_ago(n.get("first_seen"))), ("Hostname", n.get("hostname"))])
            if n.get("randomized_mac"): b.addWidget(self._note("Private (randomized) MAC: phones rotate these, so the vendor is hidden."))
            if n.get("is_self"): b.addWidget(label("This is the computer running LANDAR.", C["primary"], 11))
            if "device_id" in n: self._device_actions(n)

    def _device_actions(self, n):
        b = self.detail.body; b.addWidget(caps("Quick node operations")); can = self.actor.can("devices.manage")
        cb = QComboBox(); cb.addItems(DEVICE_TYPES); cb.setCurrentText(n.get("device_type") or "Unknown"); cb.setEnabled(can)
        save = button("Set type", "", None, lambda: self.safely(devices.set_type, self.actor, n["device_id"], cb.currentText())); save.setEnabled(can)
        b.addWidget(hbox(cb, save, spacing=8)); ap = button("Approve", "", "check_circle", lambda: self.safely(devices.set_state, self.actor, n["device_id"], "Approved"))
        bl = button("Block", "danger", "block", self._block(n)); ap.setEnabled(can); bl.setEnabled(can); b.addWidget(hbox(ap, bl, spacing=8))
        b.addWidget(self._note("Approve / Block record your decision. Enforcement needs a firewall provider (Phase 5)."))

    @staticmethod
    def _note(text):
        l = label(text, C["outline"], 11); l.setWordWrap(True); return l

    def _block(self, n):
        return lambda: confirm(self, "Blocking records the decision (nothing is enforced yet). Continue?") and self.safely(devices.set_state, self.actor, n["device_id"], "Blocked")

    def safely(self, fn, *args):
        sel = next((i.node["id"] for i in self.view.scene().selectedItems() if isinstance(i, NodeItem)), None); super().safely(fn, *args)
        if sel in self.items: self.items[sel].setSelected(True)

    # ---- actions -------------------------------------------------------------------
    def scan(self):
        self.scan_btn.setEnabled(False); self.scan_btn.setText("SCANNING…"); self.worker = ServiceWorker(discovery.scan, self.actor)
        done = lambda *_: (self.scan_btn.setEnabled(True), self.scan_btn.setText(icon_char("radar") + "  RUN DISCOVERY"), self.refresh())
        self.worker.succeeded.connect(done); self.worker.failed.connect(lambda m: (done(), QMessageBox.warning(self, "LANDAR", m))); self.worker.start()

    def export(self):
        if not self.graph: return
        path, _ = QFileDialog.getSaveFileName(self, "Export topology", "landar-topology.json", "JSON (*.json)")
        if path: open(path, "w").write(json.dumps(self.graph, indent=2, default=str))
