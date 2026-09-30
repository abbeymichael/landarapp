from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QListWidget, QStackedWidget
from landar.config import APP_NAME
from landar.core.permissions import Actor
from landar.ui.registry import PAGES

class MainWindow(QMainWindow):
    def __init__(self, actor: Actor):
        super().__init__(); self.setWindowTitle(f"{APP_NAME} — {actor.username} ({actor.role})"); self.resize(1200, 720)
        side = QListWidget(); side.setObjectName("side"); self.stack = QStackedWidget()
        for spec in PAGES:
            if actor.can(spec.permission): side.addItem(spec.name); self.stack.addWidget(spec.factory(actor))
        side.currentRowChanged.connect(self.show_page); side.setCurrentRow(0)
        root = QWidget(); lay = QHBoxLayout(root); lay.setContentsMargins(0, 0, 12, 0)
        lay.addWidget(side); lay.addWidget(self.stack, 1); self.setCentralWidget(root)
    def show_page(self, i):
        self.stack.setCurrentIndex(i); self.stack.currentWidget().refresh()
