"""Alerts & Incidents page (Phase 6)."""
from PySide6.QtWidgets import QComboBox
from landar.core.constants import ALERT_STATES, SEVERITIES
from landar.services import alerts
from landar.ui.pages.base import TablePage, confirm, time_ago

SEV_COLOR = {"CRITICAL": "CRITICAL", "WARNING": "WARNING", "INFO": "INFO"}

class AlertsPage(TablePage):
    title, subtitle = "Alerts & Incidents", "Observability"
    mono_cols = ("ID", "Age")
    headers = ["ID", "Severity", "Source", "Message", "Kind", "State", "Age"]
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Sync alerts", self.sync, "monitoring.view", "primary")
        self.add_button("Acknowledge", lambda: self.set("Acknowledged"), "monitoring.view")
        self.add_button("Resolve", lambda: self.set("Resolved"), "monitoring.view")
        self.add_button("Resolve all", self.resolve_all, "monitoring.view", "danger")
        self.sev = QComboBox(); self.sev.addItems(["All"] + list(SEVERITIES)); self.sev.currentIndexChanged.connect(self.refresh); self.bar.addWidget(self.sev)
        self.state = QComboBox(); self.state.addItems(["All"] + list(ALERT_STATES)); self.state.currentIndexChanged.connect(self.refresh); self.bar.addWidget(self.state)
        self.bar.addStretch()
    def load_rows(self):
        return [(a["id"], a["severity"], a["source"] or "—", a["message"], a["kind"], a["state"], time_ago(a["created_at"]))
                for a in alerts.list_alerts(self.actor, self.state.currentText(), self.sev.currentText())]
    def sync(self):
        ok, r = self.call(alerts.sync, self.actor)
        if ok: self.refresh()
    def set(self, state):
        aid = self.selected_id()
        if aid: self.safely(alerts.set_state, self.actor, aid, state)
    def resolve_all(self):
        if confirm(self, "Mark every open alert as resolved?"): self.safely(alerts.resolve_all, self.actor)
