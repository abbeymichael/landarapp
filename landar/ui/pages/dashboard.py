from PySide6.QtWidgets import QGridLayout, QFrame, QVBoxLayout, QLabel
from landar.core.permissions import PermissionDenied
from landar.services import monitoring
from landar.ui.pages.base import Page

class DashboardPage(Page):
    title = "Network Control Center"
    def __init__(self, actor):
        super().__init__(actor); self.grid = QGridLayout(); self.root.addLayout(self.grid); self.root.addStretch()
    def refresh(self):
        while self.grid.count(): self.grid.takeAt(0).widget().deleteLater()
        try: data = monitoring.summary(self.actor)
        except PermissionDenied: data = {}
        for i, (name, val) in enumerate(data.items()):
            card = QFrame(); card.setObjectName("card"); lay = QVBoxLayout(card)
            big = QLabel(str(val)); big.setObjectName("big"); lay.addWidget(big); lay.addWidget(QLabel(name))
            self.grid.addWidget(card, i // 3, i % 3)
