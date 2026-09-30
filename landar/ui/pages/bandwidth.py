from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox
from landar.core.constants import BW_SCOPES, BW_UNITS, DEFAULT_GROUPS
from landar.core.permissions import ROLE_PERMS
from landar.services import bandwidth
from landar.ui.pages.base import TablePage, confirm, form_dialog

class BandwidthPage(TablePage):
    title, subtitle = "Bandwidth / QoS", "Security & Access"
    mono_cols = ("ID", "Target", "Download", "Upload", "Priority")
    headers = ["ID", "Name", "Scope", "Target", "Download", "Upload", "Priority", "Status"]
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Add policy", self.add, "network.configure", "primary")
        self.add_button("Edit", self.edit, "network.configure")
        self.add_button("Delete", self.delete, "network.configure", "danger"); self.bar.addStretch()
    def load_rows(self):
        return [(p["id"], p["name"], p["scope"], p["target"] or "any", p["down_disp"], p["up_disp"], p["priority"], p["status"])
                for p in bandwidth.list_display(self.actor)]

    def _target_widget(self, scope, current):
        """Role/Group are picked from a list; Network/VLAN/User/Device are typed."""
        if scope in ("Role", "Group"):
            cb = QComboBox(); cb.addItem("Any", None)
            for r in (ROLE_PERMS if scope == "Role" else DEFAULT_GROUPS):
                cb.addItem(r, r)
            if current: cb.setCurrentText(current)
            return cb, lambda w: w.currentData()
        e = QLineEdit(current or ""); e.setPlaceholderText({"VLAN": "e.g. 30", "User": "username", "Device": "AA:BB:CC:DD:EE:FF"}.get(scope, "name"))
        return e, lambda w: w.text().strip() or None

    def _form(self, title, p=None):
        name = QLineEdit((p or {}).get("name") or "")
        scope = QComboBox(); scope.addItems(BW_SCOPES); scope.setCurrentText((p or {}).get("scope") or "Role")
        unit = QComboBox(); unit.addItems(list(BW_UNITS)); unit.setCurrentText((p or {}).get("unit") or "Mbps")
        down = QSpinBox(); down.setRange(0, 100000); down.setSuffix("  down")
        up = QSpinBox(); up.setRange(0, 100000); up.setSuffix("  up")
        if p:   # show the authored value back in its own unit
            down.setValue(int(round(p["down"] / BW_UNITS.get(p["unit"], 1000))))
            up.setValue(int(round(p["up"] / BW_UNITS.get(p["unit"], 1000))))
        prio = QSpinBox(); prio.setRange(1, 9999); prio.setValue((p or {}).get("priority") or 100)
        on = QCheckBox("Enabled"); on.setChecked(True if not p else bool(p["enabled"]))
        tw, getter = self._target_widget(scope.currentText(), (p or {}).get("target"))
        if form_dialog(self, title, [("Name", name), ("Scope", scope), ("Target", tw), ("Download", down), ("Upload", up), ("Unit", unit), ("Priority", prio), ("", on)]):
            return (name.text(), scope.currentText(), getter(tw), down.value(), up.value(), unit.currentText(), prio.value(), on.isChecked())

    def add(self):
        v = self._form("Add bandwidth policy")
        if v: self.safely(bandwidth.create_policy, self.actor, *v)
    def edit(self):
        pid = self.selected_id(); p = next((x for x in bandwidth.list_policies(self.actor) if x["id"] == pid), None)
        if p and (v := self._form("Edit bandwidth policy", p)): self.safely(bandwidth.update_policy, self.actor, pid, *v)
    def delete(self):
        pid = self.selected_id()
        if pid and confirm(self, "Delete this bandwidth policy?"): self.safely(bandwidth.delete_policy, self.actor, pid)
