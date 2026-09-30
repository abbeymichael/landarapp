"""THE extension point for the UI. To add a feature screen: write a Page subclass, add one line here."""
from dataclasses import dataclass
from landar.ui.pages.audit import AuditPage
from landar.ui.pages.dashboard import DashboardPage
from landar.ui.pages.devices import DevicesPage
from landar.ui.pages.users import UsersPage

@dataclass(frozen=True)
class PageSpec:
    name: str
    factory: type
    permission: str   # page is hidden from roles lacking this permission

PAGES = [
    PageSpec("Dashboard", DashboardPage, "monitoring.view"),
    PageSpec("Users", UsersPage, "users.view"),
    PageSpec("Devices", DevicesPage, "devices.view"),
    PageSpec("Audit", AuditPage, "audit.view"),
    # Next: PageSpec("Topology", TopologyPage, "network.view"), PageSpec("Policies", ...), PageSpec("Firewall", ...)
]
