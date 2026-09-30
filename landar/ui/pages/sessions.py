from PySide6.QtWidgets import QLineEdit, QComboBox
from landar.services import sessions
from landar.ui.pages.base import TablePage, confirm, form_dialog, time_ago

class SessionsPage(TablePage):
    title, subtitle = "Active Sessions", "People"
    mono_cols = ("ID", "IP", "MAC", "Started")
    headers = ["ID", "User", "Device", "IP", "MAC", "Network", "Source", "State", "Started"]
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Start session", self.add, "monitoring.view", "primary")
        self.add_button("End session", self.end, "monitoring.view", "danger")
        self.add_button("End all", self.end_all, "monitoring.view", "danger")
        self.filter = QComboBox(); self.filter.addItems(["All", "Active", "Ended", "Expired"])
        self.filter.currentIndexChanged.connect(self.refresh); self.bar.addWidget(self.filter); self.bar.addStretch()
    def load_rows(self):
        st = self.filter.currentText()
        return [(s["id"], s["username"], s["mac"] or "—", s["ip"] or "—", s["mac"] or "—", s["network"] or "—",
                 s["auth_source"], s["state"], time_ago(s["started_at"])) for s in sessions.list_sessions(self.actor, st)]
    def add(self):
        u, i, m = QLineEdit(), QLineEdit(), QLineEdit(); m.setPlaceholderText("AA:BB:CC:DD:EE:FF")
        i.setPlaceholderText("10.0.30.41"); u.setPlaceholderText("username")
        if form_dialog(self, "Start session", [("Username", u), ("IP address", i), ("Device MAC", m)]):
            self.safely(sessions.start_session, self.actor, u.text().strip(), i.text().strip(), m.text().strip())
    def end(self):
        sid = self.selected_id()
        if sid and confirm(self, "End this session?"): self.safely(sessions.end_session, self.actor, sid)
    def end_all(self):
        if confirm(self, "End every active session?"): self.safely(sessions.end_all, self.actor)
