from PySide6.QtWidgets import QLineEdit, QComboBox
from landar.core.constants import DEFAULT_GROUPS
from landar.core.permissions import ROLE_PERMS
from landar.services import users
from landar.ui.dialogs import PasswordField
from landar.ui.pages.base import TablePage, confirm, form_dialog

class UsersPage(TablePage):
    title = "Users"
    headers = ["ID", "Username", "Name", "Email", "Group", "Role", "Status"]
    def __init__(self, actor):
        super().__init__(actor)
        self.add_button("Add user", self.add, "users.create")
        self.add_button("Enable", lambda: self.set_status("Active"), "users.edit")
        self.add_button("Disable", lambda: self.set_status("Disabled"), "users.edit")
        self.add_button("Lock", lambda: self.set_status("Locked"), "users.edit"); self.bar.addStretch()
    def load_rows(self): return users.list_users(self.actor)
    def add(self):
        u, n, e, p = QLineEdit(), QLineEdit(), QLineEdit(), PasswordField()
        g = QComboBox(); g.addItems(DEFAULT_GROUPS); r = QComboBox(); r.addItems(ROLE_PERMS); r.setCurrentText("Read Only")
        if form_dialog(self, "Add user", [("Username", u), ("Full name", n), ("Email", e), ("Group", g), ("Role", r), ("Password (10+)", p)]):
            self.safely(users.create_user, self.actor, u.text().strip(), n.text().strip(), e.text().strip(), g.currentText(), r.currentText(), p.text())
    def set_status(self, status):
        uid = self.selected_id()
        if uid and (status == "Active" or confirm(self, f"Set this account to {status}?")):
            self.safely(users.set_status, self.actor, uid, status)
