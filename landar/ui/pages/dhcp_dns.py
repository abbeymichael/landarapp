import os
from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QMessageBox, QSpinBox, QStackedWidget, QVBoxLayout, QWidget, QCheckBox
from landar.core.permissions import PermissionDenied
from landar.services import dhcp, dns, export, networks
from landar.ui.components import SectionCard, button, label
from landar.ui.pages.base import Page, confirm, fill_table, form_dialog, new_table, selected_id
from landar.ui.theme import C
from landar.ui.workers import ServiceWorker

class DhcpDnsPage(Page):
    title, subtitle = "DHCP & DNS", "Network"
    def __init__(self, actor):
        super().__init__(actor); self.tested = {}; self.workers = []; self._obs = {}
        top = QHBoxLayout(); self.tabs = []
        for i, name in enumerate(("DHCP", "DNS", "Observed Addresses")):
            b = button(name, on_click=lambda _=False, i=i: self.set_tab(i)); top.addWidget(b); self.tabs.append(b)
        top.addStretch(); top.addWidget(button("Export dnsmasq config", "", "download", self.export)); self.root.addLayout(top)
        self.stack = QStackedWidget(); self.root.addWidget(self.stack, 1)
        for build in (self._dhcp_tab, self._dns_tab, self._observed_tab): self.stack.addWidget(build())
        self.set_tab(0)

    def set_tab(self, i):
        for k, b in enumerate(self.tabs):
            b.setProperty("kind", "primary" if k == i else ""); b.style().unpolish(b); b.style().polish(b)
        self.stack.setCurrentIndex(i)

    def _panel(self, title, icon_name, tag, buttons):
        card = SectionCard(title, icon_name, tag); bar = QHBoxLayout(); bar.setSpacing(8)
        for text, fn, perm, kind in buttons:
            b = button(text, kind, on_click=fn); b.setEnabled(perm is None or self.actor.can(perm)); bar.addWidget(b)
        bar.addStretch(); card.body.addLayout(bar); t = new_table(); t.setMinimumHeight(140); card.body.addWidget(t); return card, t

    def _page(self, *widgets):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 4, 0, 0); v.setSpacing(12)
        for x in widgets: v.addWidget(x)
        v.addStretch(); return w

    # ---- tabs ----------------------------------------------------------------------
    def _dhcp_tab(self):
        self.banner = label("", C["outline"], 11, mono=True)
        c1, self.t_scope = self._panel("DHCP Scopes", "dns", "Managed config", [("Set scope", self.set_scope, "network.configure", "primary"), ("Remove scope", self.del_scope, "network.configure", "danger")])
        c2, self.t_res = self._panel("Reservations", "lock", "MAC → fixed IP", [("Add reservation", lambda: self.reserve(), "network.configure", "primary"), ("Remove", self.del_res, "network.configure", "danger")])
        return self._page(self.banner, c1, c2)

    def _dns_tab(self):
        c1, self.t_rec = self._panel("Local DNS Records", "dns", "Internal names", [("Add record", self.add_rec, "network.configure", "primary"), ("Remove", self.del_rec, "network.configure", "danger")])
        c2, self.t_fwd = self._panel("Upstream Forwarders", "public", "Resolvers", [("Add forwarder", self.add_fwd, "network.configure", "primary"), ("Test selected", self.test_fwd, None, ""), ("Remove", self.del_fwd, "network.configure", "danger")])
        tool = SectionCard("Resolver Test", "search", "Live lookup"); row = QHBoxLayout(); self.host = QLineEdit("example.com"); self.srv = QComboBox(); self.srv.setMinimumWidth(200)
        self.host.returnPressed.connect(self.lookup); row.addWidget(self.host, 1); row.addWidget(self.srv); row.addWidget(button("Lookup", "primary", None, self.lookup)); tool.body.addLayout(row)
        self.result = label("Enter a name and press Lookup.", C["outline"], 12, mono=True); self.result.setWordWrap(True); tool.body.addWidget(self.result)
        return self._page(c1, c2, tool)

    def _observed_tab(self):
        c, self.t_obs = self._panel("Observed Addresses", "sync", "From scans", [("Reserve selected", self.reserve_selected, "network.configure", "primary")])
        c.body.insertWidget(0, label("Seen by discovery scans. These are not real DHCP leases: LANDAR cannot read your router's lease table yet.", C["outline"], 11))
        return self._page(c)

    # ---- data ----------------------------------------------------------------------
    def refresh(self):
        a = self.actor
        try: sc, res, obs, recs, fwd = dhcp.list_scopes(a), dhcp.list_reservations(a), dhcp.observed(a), dns.list_records(a), dns.list_forwarders(a)
        except PermissionDenied: return
        fill_table(self.t_scope, ["ID", "Network", "VLAN", "Range", "Pool", "Observed", "Usage", "Lease", "DNS servers", "Status"],
                   [(s["id"], s["network"], s["vlan_id"] or "—", f"{s['range_start']} – {s['range_end']}", s["pool"], s["observed"], s["utilization"], f"{s['lease_hours']}h", s["dns_servers"] or "—", s["status"]) for s in sc],
                   ("ID", "VLAN", "Range", "Pool", "Observed", "Usage", "Lease"), ("Status",))
        fill_table(self.t_res, ["ID", "Network", "MAC", "IP", "Hostname", "Status"], [(r["id"], r["network"], r["mac"], r["ip"], r["hostname"] or "—", r["status"]) for r in res], ("ID", "MAC", "IP"), ("Status",))
        bad = sum(r["status"] == "Conflict" for r in res)
        self.banner.setText(f"⚠ {bad} reservation conflict(s): another device is using a reserved address." if bad else "No reservation conflicts. Pool usage counts devices seen online in the last scan.")
        self.banner.setStyleSheet(f"color:{C['error'] if bad else C['outline']}; background:transparent; font-size:11px; font-family:'JetBrains Mono';")
        fill_table(self.t_rec, ["ID", "Name", "Address", "Note"], [(r["id"], r["name"], r["ip"], r["note"] or "") for r in recs], ("ID", "Name", "Address"))
        fill_table(self.t_fwd, ["ID", "Address", "Label", "Status", "Latency"],
                   [(f["id"], f["address"], f["label"] or "—", self.tested.get(f["address"], ("Not tested", ""))[0], self.tested.get(f["address"], ("", "—"))[1]) for f in fwd], ("ID", "Address", "Latency"), ("Status",))
        self._obs = {o["id"]: o for o in obs}
        fill_table(self.t_obs, ["ID", "Hostname", "IP", "MAC", "Network", "Address type", "Presence"], [(o["id"], o["hostname"] or "—", o["ip"], o["mac"], o["network"], o["kind"], o["presence"]) for o in obs],
                   ("ID", "IP", "MAC"), ("Address type", "Presence"))
        cur = self.srv.currentText(); self.srv.clear(); self.srv.addItem("System resolver", None)
        for f in fwd: self.srv.addItem(f["address"], f["address"])
        self.srv.setCurrentText(cur if self.srv.findText(cur) >= 0 else "System resolver")

    def _net_combo(self, select=None):
        nets = networks.list_networks(self.actor)
        if not nets: QMessageBox.information(self, "LANDAR", "Add a network first (Networks & VLANs)."); return None
        cb = QComboBox()
        for n in nets: cb.addItem(f"{n['name']} ({n['cidr']})", n["id"])
        if select:
            i = cb.findText(select, flags=0)
            for k in range(cb.count()):
                if cb.itemText(k).startswith(select): cb.setCurrentIndex(k)
        return cb

    # ---- DHCP actions ---------------------------------------------------------------
    def set_scope(self):
        cb = self._net_combo()
        if not cb: return
        s, e, dnsf = QLineEdit(), QLineEdit(), QLineEdit(); s.setPlaceholderText("192.168.10.50"); e.setPlaceholderText("192.168.10.200"); dnsf.setPlaceholderText("1.1.1.1, 8.8.8.8 (optional)")
        lease = QSpinBox(); lease.setRange(1, 720); lease.setValue(12); lease.setSuffix(" hours"); on = QCheckBox("Enabled"); on.setChecked(True)
        if form_dialog(self, "DHCP scope", [("Network", cb), ("Range start", s), ("Range end", e), ("Lease time", lease), ("DNS servers", dnsf), ("", on)]):
            self.safely(dhcp.set_scope, self.actor, cb.currentData(), s.text(), e.text(), lease.value(), dnsf.text(), on.isChecked())
    def del_scope(self):
        i = selected_id(self.t_scope)
        if i and confirm(self, "Remove this DHCP scope?"): self.safely(dhcp.delete_scope, self.actor, i)
    def reserve(self, mac="", ip="", host="", net_ip_hint=None):
        cb = self._net_combo(net_ip_hint)
        if not cb: return
        m, i, h, d = QLineEdit(mac), QLineEdit(ip), QLineEdit(host), QLineEdit(); m.setPlaceholderText("AA:BB:CC:DD:EE:FF")
        if form_dialog(self, "Add reservation", [("Network", cb), ("MAC", m), ("IP address", i), ("Hostname", h), ("Description", d)]):
            ok, warn = self.call(dhcp.add_reservation, self.actor, cb.currentData(), m.text(), i.text(), h.text(), d.text())
            if ok and warn: QMessageBox.information(self, "LANDAR", "\n".join(warn))
            self.refresh()
    def reserve_selected(self):
        o = self._obs.get(selected_id(self.t_obs))
        if o: self.reserve(o["mac"], o["ip"], o["hostname"] or "", o["network"] if not o["network"].startswith("—") else None)
    def del_res(self):
        i = selected_id(self.t_res)
        if i: self.safely(dhcp.delete_reservation, self.actor, i)

    # ---- DNS actions ----------------------------------------------------------------
    def add_rec(self):
        n, ip, note = QLineEdit(), QLineEdit(), QLineEdit(); n.setPlaceholderText("printer.school.lan"); ip.setPlaceholderText("192.168.10.20")
        if form_dialog(self, "Add DNS record (A)", [("Name", n), ("IP address", ip), ("Note", note)]): self.safely(dns.add_record, self.actor, n.text(), ip.text(), note.text())
    def del_rec(self):
        i = selected_id(self.t_rec)
        if i: self.safely(dns.delete_record, self.actor, i)
    def add_fwd(self):
        a, l = QLineEdit(), QLineEdit(); a.setPlaceholderText("1.1.1.1")
        if form_dialog(self, "Add forwarder", [("Address", a), ("Label", l)]): self.safely(dns.add_forwarder, self.actor, a.text(), l.text())
    def del_fwd(self):
        i = selected_id(self.t_fwd)
        if i: self.safely(dns.delete_forwarder, self.actor, i)

    def _run(self, fn, args, done):
        w = ServiceWorker(fn, *args); self.workers.append(w); w.succeeded.connect(done)
        w.failed.connect(lambda m: self._show("Failed: " + m, C["error"])); w.finished.connect(lambda w=w: self.workers.remove(w) if w in self.workers else None); w.start()
    def _show(self, text, color):
        self.result.setText(text); self.result.setStyleSheet(f"color:{color}; background:transparent; font-size:12px; font-family:'JetBrains Mono';")
    def lookup(self):
        self._show("Resolving…", C["outline"]); name = self.host.text(); srv = self.srv.currentData()
        self._run(dns.lookup, (self.actor, name, srv), lambda r: self._show(f"{', '.join(r['answers'])}   ({r['ms']} ms)" if r["ok"] else f"{r['error']}" + (f"   ({r['ms']} ms)" if r["ms"] is not None else ""), C["tertiary"] if r["ok"] else C["error"]))
    def test_fwd(self):
        row = self.t_fwd.currentRow()
        if row < 0: return
        addr = self.t_fwd.item(row, 1).text(); self.tested[addr] = ("Not tested", "testing…"); self.refresh()
        def done(r): self.tested[addr] = ("Reachable", f"{r['ms']} ms") if r["ok"] else ("Unreachable", r["error"]); self.refresh()
        self._run(dns.lookup, (self.actor, "example.com", addr), done)

    def export(self):
        ok, text = self.call(export.dnsmasq_config, self.actor)
        if not ok: return
        path, _ = QFileDialog.getSaveFileName(self, "Export dnsmasq config", "landar-dnsmasq.conf", "Config (*.conf);;All files (*)")
        if path: open(path, "w").write(text)
