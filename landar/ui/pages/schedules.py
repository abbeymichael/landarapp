from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox
from landar.core.constants import DAYS, DEFAULT_GROUPS
from landar.services import schedules
from landar.ui.pages.base import TablePage, confirm, form_dialog

class SchedulesPage(TablePage):
    title, subtitle = "Access Schedules", "Security & Access"
    mono_cols = ("ID", "Window", "Max session")
    headers = ["ID", "Name", "Applies to", "Days", "Window", "Max session", "Status"]
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Add schedule", self.add, "network.configure", "primary")
        self.add_button("Edit", self.edit, "network.configure")
        self.add_button("Delete", self.delete, "network.configure", "danger"); self.bar.addStretch()
    def load_rows(self):
        return [(s["id"], s["name"], s["applies_group"] or "Any group", s["days"], f"{s['start']} – {s['end']}",
                 f"{s['max_session_minutes']} min" if s["max_session_minutes"] else "—",
                 "Enabled" if s["enabled"] else "Disabled") for s in schedules.list_schedules(self.actor)]

    def _day_picker(self, selected):
        box = QComboBox(); box.addItems(DAYS)
        for i, d in enumerate(DAYS): box.model().item(i).setCheckable(True)
        chosen = (selected or "Mon,Tue,Wed,Thu,Fri").split(",")
        for i, d in enumerate(DAYS): box.model().item(i).setCheckState(2 if d in chosen else 0)
        return box

    def _form(self, title, s=None):
        name = QLineEdit((s or {}).get("name") or "")
        grp = QComboBox(); grp.addItem("Any group", None)
        for g in DEFAULT_GROUPS: grp.addItem(g, g)
        if s and s.get("applies_group"): grp.setCurrentText(s["applies_group"])
        days = self._day_picker((s or {}).get("days"))
        start = QLineEdit((s or {}).get("start") or "08:00"); start.setPlaceholderText("08:00")
        end = QLineEdit((s or {}).get("end") or "18:00"); end.setPlaceholderText("18:00")
        mx = QSpinBox(); mx.setRange(0, 1440); mx.setSpecialValueText("No limit"); mx.setSuffix(" min"); mx.setValue((s or {}).get("max_session_minutes") or 0)
        on = QCheckBox("Enabled"); on.setChecked(True if not s else bool(s["enabled"]))
        note = QLineEdit((s or {}).get("note") or "")
        if form_dialog(self, title, [("Name", name), ("Applies to group", grp), ("Days", days), ("Start (HH:MM)", start), ("End (HH:MM)", end), ("Max session", mx), ("Note", note), ("", on)]):
            picked = ",".join(DAYS[i] for i in range(days.count()) if days.model().item(i).checkState() == 2)
            return (name.text(), grp.currentData(), picked, start.text(), end.text(), mx.value() or None, on.isChecked(), note.text())

    def add(self):
        v = self._form("Add schedule")
        if v: self.safely(schedules.create_schedule, self.actor, *v)
    def edit(self):
        sid = self.selected_id(); s = next((x for x in schedules.list_schedules(self.actor) if x["id"] == sid), None)
        if s and (v := self._form("Edit schedule", s)): self.safely(schedules.update_schedule, self.actor, sid, *v)
    def delete(self):
        sid = self.selected_id()
        if sid and confirm(self, "Delete this schedule?"): self.safely(schedules.delete_schedule, self.actor, sid)
