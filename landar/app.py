import sys
from PySide6.QtWidgets import QApplication
from landar import storage
from landar.services import auth
from landar.ui.dialogs import show_secret_once
from landar.ui.login import prompt_login
from landar.ui.main_window import MainWindow
from landar.ui.theme import QSS

def run() -> int:
    storage.init()
    first_pw = auth.bootstrap_admin()
    app = QApplication(sys.argv); app.setStyleSheet(QSS)
    if first_pw:
        show_secret_once(None, "First run", "Admin account created.", "admin", first_pw)
    actor = prompt_login()
    if not actor: return 0
    win = MainWindow(actor); win.show()
    return app.exec()
