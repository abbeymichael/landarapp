import sys
from PySide6.QtWidgets import QApplication
from landar import storage
from landar.services import auth
from landar.ui.fonts import load_fonts
from landar.ui.login import prompt_login
from landar.ui.main_window import MainWindow
from landar.ui.theme import QSS

def run() -> int:
    storage.init()
    first_pw = auth.bootstrap_admin()
    app = QApplication(sys.argv); load_fonts(app); app.setStyleSheet(QSS)
    actor = prompt_login(first_pw)
    if not actor: return 0
    win = MainWindow(actor); win.show()
    return app.exec()
