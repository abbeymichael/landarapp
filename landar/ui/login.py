from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from landar.services import auth

def prompt_login(attempts=3):
    """Returns an Actor or None."""
    for _ in range(attempts):
        u, ok = QInputDialog.getText(None, "LANDAR login", "Username:")
        if not ok: return None
        p, ok = QInputDialog.getText(None, "LANDAR login", "Password:", QLineEdit.Password)
        if not ok: return None
        actor = auth.login(u.strip(), p)
        if actor: return actor
        QMessageBox.warning(None, "LANDAR", "Login failed.")
    return None
