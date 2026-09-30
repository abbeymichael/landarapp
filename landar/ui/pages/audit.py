from landar.services import audit
from landar.ui.pages.base import TablePage

class AuditPage(TablePage):
    title = "Audit log"
    headers = ["ID", "Time (UTC)", "Actor", "Action", "Target", "Old", "New", "Result"]
    def load_rows(self): return audit.list_entries(self.actor)
