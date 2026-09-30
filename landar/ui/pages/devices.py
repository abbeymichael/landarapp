from PySide6.QtWidgets import QLineEdit, QComboBox, QMessageBox
from landar.core.constants import DEVICE_TYPES
from landar.services import devices, discovery
from landar.ui.components import label
from landar.ui.theme import C
from landar.ui.workers import ServiceWorker
from landar.ui.pages.base import TablePage, confirm, form_dialog

class DevicesPage(TablePage):
    title, subtitle = "Device Inventory", "Devices"
    mono_cols = ("ID", "IP", "MAC", "Last seen")
    headers = ["ID", "Hostname", "IP", "MAC", "Vendor", "Type", "Owner", "State", "Presence", "Last seen"]
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Register device", self.add, "devices.manage")
        self.add_button("Approve", lambda: self.set_state("Approved"), "devices.manage")
        self.add_button("Block", lambda: self.set_state("Blocked"), "devices.manage", "danger")
        self.scan_btn = self.add_button("Scan network", self.scan, "network.scan", "primary"); self.bar.addStretch()
        self.note = ""; self.status = label("", C["outline"], 11, mono=True); self.root.insertWidget(self.root.count() - 2, self.status)
    def refresh(self):
        super().refresh(); info = discovery.network_info(self.actor) if self.actor.can("network.view") else {}
        net = info.get("error") or (f"Network {info['cidr']} on {info['interface']} (you: {info['ip']})" if info else "")
        self.status.setText(f"{net}   {self.note}".strip())
    def scan(self):
        self.scan_btn.setEnabled(False); self.scan_btn.setText("SCANNING…")
        self.worker = ServiceWorker(discovery.scan, self.actor)
        self.worker.succeeded.connect(self._scan_done); self.worker.failed.connect(self._scan_failed); self.worker.start()
    def _scan_reset(self): self.scan_btn.setEnabled(True); self.scan_btn.setText("SCAN NETWORK")
    def _scan_done(self, r):
        self._scan_reset(); self.note = f"| Last scan: {r['found']} devices, {r['new']} new"; self.refresh()
    def _scan_failed(self, msg):
        self._scan_reset(); QMessageBox.warning(self, "LANDAR", msg)
    def load_rows(self): return devices.list_devices(self.actor)
    def add(self):
        m, h, i = QLineEdit(), QLineEdit(), QLineEdit(); m.setPlaceholderText("AA:BB:CC:DD:EE:FF")
        t = QComboBox(); t.addItems(DEVICE_TYPES); t.setCurrentText("Unknown")
        if form_dialog(self, "Register device", [("MAC", m), ("Hostname", h), ("IP", i), ("Type", t)]):
            self.safely(devices.register, self.actor, m.text(), h.text(), i.text(), t.currentText())
    def set_state(self, state):
        did = self.selected_id()
        if did and (state == "Approved" or confirm(self, "Blocking a device cuts its access. Continue?")):
            self.safely(devices.set_state, self.actor, did, state)

class ApprovalsPage(DevicesPage):
    """Triage queue: only devices still in the 'Unknown' state."""
    title, subtitle = "Approvals", "Devices"
    def load_rows(self): return [r for r in super().load_rows() if r["state"] == "Unknown"]
