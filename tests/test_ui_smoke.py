"""UI smoke test: build the real MainWindow offscreen and refresh every page a Super Admin can see.
Skips automatically when PySide6 is not installed (services still have full coverage in test_services)."""
import os, tempfile, unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LANDAR_HOME"] = tempfile.mkdtemp(); os.environ["LANDAR_DB"] = os.path.join(os.environ["LANDAR_HOME"], "ui.db")

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except Exception:
    HAVE_QT = False

from landar import storage
from landar.services import auth
from landar.core.permissions import Actor

@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        storage.init(); cls.pw = auth.bootstrap_admin()
        cls.app = QApplication.instance() or QApplication([])
        from landar.ui.fonts import load_fonts
        load_fonts(cls.app)
    def test_every_page_builds_and_refreshes(self):
        from landar.ui.main_window import MainWindow
        win = MainWindow(Actor("admin", "Super Administrator"))
        self.assertEqual(win.stack.count(), len(win.specs))
        for i in range(win.stack.count()):
            win.show_page(i)                      # builds + refreshes the page
            win.stack.currentWidget().apply_filter("")   # top-bar filter hook
        win.close()
    def test_login_dialog_builds(self):
        from landar.ui.login import LoginDialog
        d = LoginDialog(self.pw); self.assertIsNotNone(d.username); d.close()

if __name__ == "__main__": unittest.main()
