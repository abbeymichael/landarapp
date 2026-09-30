"""Live Monitoring page (Phase 6): an honest, real-data snapshot.

LANDAR has no SNMP/agent provider yet, so this page shows what it can actually measure from
the local host (interface throughput via psutil, reachability of the default gateway, the
last discovery scan) and clearly labels the parts that need a monitoring provider.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
import psutil
from landar.core.permissions import PermissionDenied
from landar.services import alerts, discovery, monitoring
from landar.ui.components import KpiCard, SectionCard, button, caps, chip, dot, hbox, icon, label
from landar.ui.pages.base import Page, time_ago
from landar.ui.theme import C, MONO


class LiveMonitoringPage(Page):
    title, subtitle = "Live Monitoring", "Observability"
    def __init__(self, actor):
        super().__init__(actor); self._last = None; self._pinging = False
        bar = QHBoxLayout(); bar.setSpacing(8)
        self.auto = button("Auto-refresh: off", on_click=self.toggle_auto)
        bar.addWidget(self.auto); bar.addWidget(button("Poll now", "primary", "refresh", self.poll)); bar.addStretch()
        self.root.addLayout(bar)
        self.kpis = QHBoxLayout(); self.kpis.setSpacing(6); self.root.addLayout(self.kpis)
        self.net = SectionCard("Local interface throughput", "sync", "Measured on this host")
        self.reach = SectionCard("Reachability", "public", "ICMP")
        self.health = SectionCard("Network health", "monitoring", "From last scan")
        cols = QHBoxLayout(); cols.setSpacing(14); cols.addWidget(self.net, 2); cols.addWidget(self.reach, 1)
        self.root.addLayout(cols); self.root.addWidget(self.health); self.root.addStretch()
        self.timer = QTimer(self); self.timer.timeout.connect(self.poll)
        self._gw = None

    def toggle_auto(self):
        if self.timer.isActive(): self.timer.stop(); self.auto.setText("AUTO-REFRESH: OFF")
        else: self.timer.start(4000); self.auto.setText("AUTO-REFRESH: ON")

    # ---- data ------------------------------------------------------------------
    def _throughput(self):
        counters = psutil.net_io_counters(pernic=True)
        if not self._last: self._last = counters; return None
        info = discovery.network_info(self.actor) if self.actor.can("network.view") else {}
        iface = info.get("interface")
        rows = []
        for name, cur in counters.items():
            if iface and name != iface: continue
            prev = self._last.get(name)
            if not prev: continue
            rows.append((name, cur.bytes_recv - prev.bytes_recv, cur.bytes_sent - prev.bytes_sent))
        self._last = counters
        return rows

    def poll(self):
        try: o = monitoring.overview(self.actor)
        except PermissionDenied: return
        info = discovery.network_info(self.actor) if self.actor.can("network.view") else {}
        gw = info.get("gateway")
        self._fill_kpis(o, info)
        self._fill_net(self._throughput())
        self._fill_reach(gw)
        self._fill_health(o)

    @staticmethod
    def _clear(layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            elif it.layout(): LiveMonitoringPage._clear(it.layout())

    def _fill_kpis(self, o, info):
        self._clear(self.kpis)
        tiles = [("Devices online", str(o["devices_online"]), f"of {o['devices_total']} known", None, icon("devices", C["primary"], 14)),
                 ("Unknown MACs", str(o["unknown"]), "need approval", C["warn"] if o["unknown"] else None, icon("fingerprint", C["warn"] if o["unknown"] else C["outline"], 14)),
                 ("Auth fails (24h)", str(o["auth_fail_24h"]), "failed logins", C["error"] if o["auth_fail_24h"] else None, icon("lock", C["outline"], 14)),
                 ("Last scan", time_ago(o["last_scan"]), "discovery", None, icon("radar", C["primary"], 14)),
                 ("This host", info.get("ip", "—"), info.get("cidr", "no network"), None, icon("router", C["primary"], 14))]
        for t in tiles: self.kpis.addWidget(KpiCard(*t), 1)

    def _fill_net(self, rows):
        self.net.clear()
        if rows is None: self.net.body.addWidget(label("Measuring… press Poll now again for a rate.", C["outline"], 12)); return
        for name, rx, tx in rows:
            self.net.body.addWidget(hbox(caps(name), label(f"↓ {_rate(rx)}", C["tertiary"], 12, mono=True),
                                         label(f"↑ {_rate(tx)}", C["secondary"], 12, mono=True), spacing=14, stretch_end=True))
        if not rows: self.net.body.addWidget(label("Active interface not found.", C["outline"], 12))

    def _fill_reach(self, gw):
        self.reach.clear()
        if not gw: self.reach.body.addWidget(label("Default gateway not detected.", C["outline"], 12)); return
        self.reach.body.addWidget(label(f"Gateway {gw}", C["on_surface"], 12, mono=True))
        self.reach.body.addWidget(label("Use the button to probe (ICMP may be blocked).", C["outline"], 11))
        self.reach.body.addWidget(button("Ping gateway", "", "network_ping", lambda: self._ping(gw)))
        self._reach_status = label("", C["outline"], 11, mono=True); self.reach.body.addWidget(self._reach_status)

    def _ping(self, gw):
        import subprocess, sys
        self._reach_status.setText("probing…")
        cmd = ["ping", "-n", "1", "-w", "1000", gw] if sys.platform == "win32" else ["ping", "-c", "1", "-W", "1", gw]
        try: ok = subprocess.run(cmd, capture_output=True, timeout=3).returncode == 0
        except Exception: ok = False
        self._reach_status.setText("Reachable" if ok else "No reply (may be blocked)")
        self._reach_status.setStyleSheet(f"color:{C['tertiary'] if ok else C['error']}; background:transparent; font-size:11px; font-family:'JetBrains Mono';")

    def _fill_health(self, o):
        self.health.clear()
        try: ac = alerts.counts(self.actor)
        except PermissionDenied: ac = {"open": 0, "critical": 0, "warning": 0}
        grid = QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(8)
        items = [("Discovery", "ARP scan", "READ-ONLY", C["primary"]), ("SNMP / agent metrics", "Interface, CPU, RAM", "NO PROVIDER", C["outline"]),
                 ("Gateway / internet uptime", "ICMP history", "NOT BUILT", C["outline"]), ("Open alerts", f"{ac['open']} open", f"{ac['critical']} critical", C["warn"] if ac["open"] else C["tertiary"])]
        for i, (name, sub, tag, col) in enumerate(items):
            row = hbox(icon("check_circle" if tag == "READ-ONLY" else "schedule", col, 16), spacing=8)
            txt = QVBoxLayout(); txt.setSpacing(0); txt.addWidget(label(name, size=12, weight=600)); txt.addWidget(caps(sub))
            row.layout().addLayout(txt, 1); row.layout().addWidget(chip(tag, col)); grid.addWidget(row, i // 2, i % 2)
        self.health.body.addLayout(grid)


def _rate(bps):
    for unit, div in (("MB/s", 1_000_000), ("KB/s", 1000)):
        if bps >= div: return f"{bps / div:.1f} {unit}"
    return f"{bps} B/s"
