from landar.services import audit
from landar.ui.pages.base import TablePage

class AuditPage(TablePage):
    title, subtitle = "Audit Logs", "Observability"
    mono_cols = ("ID", "Time (UTC)")
    headers = ["ID", "Time (UTC)", "Actor", "Action", "Target", "Old", "New", "Result"]
    def load_rows(self): return audit.list_entries(self.actor)
