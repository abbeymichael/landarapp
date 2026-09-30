from PySide6.QtWidgets import QComboBox, QLineEdit, QMessageBox, QSpinBox
from landar.services import networks
from landar.ui.components import label
from landar.ui.pages.base import TablePage, confirm, form_dialog
from landar.ui.theme import C

class NetworksPage(TablePage):
    title, subtitle = "Networks & VLANs", "Network"
    headers = ["ID", "Name", "VLAN", "Subnet", "Gateway", "Purpose", "Devices", "DHCP"]
    mono_cols = ("ID", "VLAN", "Subnet", "Gateway", "Devices"); status_cols = ("DHCP",)
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Add network", self.add, "network.configure", "primary"); self.add_button("Edit", self.edit, "network.configure")
        self.add_button("Delete", self.delete, "network.configure", "danger"); self.bar.addStretch()
        self.add_button("Import detected network", lambda: self.safely(networks.import_detected, self.actor), "network.configure")
        self.add_button("Load school VLAN plan", self.template, "network.configure")
        self.note = label("Your network plan. Changes are recorded here and audited; nothing is pushed to switches or routers yet.", C["outline"], 11, mono=True)
        self.root.insertWidget(self.root.count() - 2, self.note)
    def load_rows(self):
        return [(n["id"], n["name"], n["vlan_id"] or "—", n["cidr"], n["gateway"] or "—", n["purpose"], n["devices"], n["dhcp"]) for n in networks.list_networks(self.actor)]

    def _form(self, title, n=None):
        name, cidr, gw, desc = QLineEdit(n["name"] if n else ""), QLineEdit(n["cidr"] if n else ""), QLineEdit((n or {}).get("gateway") or ""), QLineEdit((n or {}).get("description") or "")
        cidr.setPlaceholderText("192.168.10.0/24"); gw.setPlaceholderText("optional, e.g. 192.168.10.1")
        vlan = QSpinBox(); vlan.setRange(0, 4094); vlan.setSpecialValueText("Untagged"); vlan.setValue((n or {}).get("vlan_id") or 0)
        purpose = QComboBox(); purpose.addItems(networks.PURPOSES); purpose.setCurrentText((n or {}).get("purpose") or "Other")
        if form_dialog(self, title, [("Name", name), ("VLAN ID", vlan), ("Subnet (CIDR)", cidr), ("Gateway", gw), ("Purpose", purpose), ("Description", desc)]):
            return (name.text(), vlan.value() or None, cidr.text(), gw.text(), purpose.currentText(), desc.text())
    def add(self):
        v = self._form("Add network")
        if v: self.safely(networks.create_network, self.actor, *v)
    def edit(self):
        nid = self.selected_id(); n = next((x for x in networks.list_networks(self.actor) if x["id"] == nid), None)
        if n and (v := self._form("Edit network", n)): self.safely(networks.update_network, self.actor, nid, *v)
    def delete(self):
        nid = self.selected_id()
        if nid and confirm(self, "Delete this network and its DHCP scope and reservations?"): self.safely(networks.delete_network, self.actor, nid)
    def template(self):
        ok, n = self.call(networks.load_template, self.actor)
        if ok: QMessageBox.information(self, "LANDAR", f"Added {n} networks." if n else "All template networks already exist.")
        self.refresh()
