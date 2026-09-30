from PySide6.QtCore import Qt
from landar.ui.components import SectionCard, caps, label, icon
from landar.ui.pages.base import Page
from landar.ui.theme import C

class PlaceholderPage(Page):
    """Shown for modules in the roadmap that are not built yet, so the navigation matches the design."""
    def __init__(self, actor, title, phase, icon_name="construction", blurb=""):
        self.title, self.subtitle = title, "Planned module"; super().__init__(actor)
        card = SectionCard("Not built yet", icon_name, tag=phase, tag_color=C["primary"])
        card.body.addWidget(label(blurb or "This module is on the roadmap and will appear here when its phase is built.", C["on_surface_variant"]))
        self.root.addWidget(card); self.root.addStretch()

def soon(title, phase, icon_name="construction", blurb=""):
    return lambda actor: PlaceholderPage(actor, title, phase, icon_name, blurb)
