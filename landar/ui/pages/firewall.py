"""Firewall Rules page (Phase 5). Ordered rule manager.

Rule order is authoritative, so the table shows Position and provides Move up/down. Rules
are managed configuration; the Push button attempts to apply them via a NetworkProvider and
reports honestly when the active (read-only) provider cannot enforce them yet.
"""
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QMessageBox
from landar.core.constants import PROTOCOLS
from landar.services import firewall, schedules
from landar.ui.components import label
from landar.ui.pages.base import TablePage, confirm, form_dialog
from landar.ui.theme import C


class FirewallPage(TablePage):
    title, subtitle = "Firewall Rules", "Security & Access"
    mono_cols = ("Pos", "Port")
    headers = ["ID", "Pos", "Name", "Action", "Protocol", "Source", "Destination", "Port", "Schedule", "Log", "Status"]
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Add rule", self.add, "firewall.edit", "primary")
        self.add_button("Edit", self.edit, "firewall.edit")
        self.add_button("Delete", self.delete, "firewall.edit", "danger")
        self.add_button("Move up", lambda: self.move("up"), "firewall.edit")
        self.add_button("Move down", lambda: self.move("down"), "firewall.edit")
        self.add_button("Enable", lambda: self.toggle(True), "firewall.edit")
        self.add_button("Disable", lambda: self.toggle(False), "firewall.edit")
        self.bar.addStretch()
        self.add_button("Push to device", self.push, "firewall.edit", "primary")
        self.note = label("", C["outline"], 11, mono=True); self.note.setWordWrap(True)
        self.root.insertWidget(self.root.count() - 2, self.note)

    def load_rows(self):
        return [(r["id"], r["position"], r["name"] or "—", r["action"], r["protocol"], r["source"], r["destination"],
                 r["port"] or "any", r["schedule"] or "Always", "on" if r["logging"] else "off", r["status"])
                for r in firewall.list_rules(self.actor)]

    def refresh(self):
        super().refresh()
        try: s = firewall.stats(self.actor)
        except Exception: s = {"total": 0, "allow": 0, "deny": 0, "enabled": 0}
        self.note.setText(f"Order is evaluated top-to-bottom. {s['total']} rule(s): {s['allow']} allow, {s['deny']} deny/reject, "
                          f"{s['enabled']} enabled. Stored + audited; enforcement needs a firewall provider (Phase 5).")

    def _form(self, title, r=None):
        name = QLineEdit((r or {}).get("name") or "")
        action = QComboBox(); action.addItems(["Allow", "Deny", "Reject"]); action.setCurrentText((r or {}).get("action") or "Allow")
        proto = QComboBox(); proto.addItems(PROTOCOLS); proto.setCurrentText((r or {}).get("protocol") or "Any")
        src = QLineEdit((r or {}).get("source") or "Any"); dst = QLineEdit((r or {}).get("destination") or "Any")
        port = QLineEdit((r or {}).get("port") or ""); port.setPlaceholderText("e.g. 443 or 8000-9000 (blank = any)")
        sched = QComboBox(); sched.addItem("Always", None)
        try:
            for s in schedules.list_schedules(self.actor): sched.addItem(s["name"], s["id"])
        except Exception: pass
        if r and r.get("schedule_id"): sched.setCurrentIndex(max(0, sched.findData(r["schedule_id"])))
        log = QCheckBox("Log matching traffic"); log.setChecked(True if not r else bool(r["logging"]))
        on = QCheckBox("Enabled"); on.setChecked(True if not r else bool(r["enabled"]))
        desc = QLineEdit((r or {}).get("description") or "")
        if form_dialog(self, title, [("Name", name), ("Action", action), ("Protocol", proto), ("Source", src),
                                     ("Destination", dst), ("Port / service", port), ("Schedule", sched), ("", log), ("", on), ("Description", desc)]):
            return (name.text(), action.currentText(), proto.currentText(), src.text(), dst.text(), port.text(),
                    sched.currentData(), log.isChecked(), on.isChecked(), desc.text())

    def add(self):
        v = self._form("Add firewall rule")
        if v: self.safely(firewall.add_rule, self.actor, *v)
    def edit(self):
        rid = self.selected_id(); r = next((x for x in firewall.list_rules(self.actor) if x["id"] == rid), None)
        if r and (v := self._form("Edit firewall rule", r)): self.safely(firewall.update_rule, self.actor, rid, *v)
    def delete(self):
        rid = self.selected_id()
        if rid and confirm(self, "Delete this firewall rule?"): self.safely(firewall.delete_rule, self.actor, rid)
    def move(self, direction):
        rid = self.selected_id()
        if rid: self.safely(firewall.move_rule, self.actor, rid, direction)
    def toggle(self, enabled):
        rid = self.selected_id()
        if rid: self.safely(firewall.toggle_rule, self.actor, rid, enabled)

    def push(self):
        ok, res = self.call(firewall.push, self.actor)
        if not ok: return
        if res.get("applied"): QMessageBox.information(self, "LANDAR", res.get("message", "Rules applied."))
        else: QMessageBox.warning(self, "LANDAR", "Not applied: " + res.get("message", "the active provider cannot push rules."))
