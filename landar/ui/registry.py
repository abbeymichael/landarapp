"""THE extension point for the UI. To add a feature screen: write a Page subclass, add one PageSpec line here.
Unbuilt modules use soon(...) placeholders so the navigation already matches the design."""
from dataclasses import dataclass
from landar.ui.pages.alerts import AlertsPage
from landar.ui.pages.audit import AuditPage
from landar.ui.pages.bandwidth import BandwidthPage
from landar.ui.pages.dashboard import DashboardPage
from landar.ui.pages.devices import ApprovalsPage, DevicesPage
from landar.ui.pages.dhcp_dns import DhcpDnsPage
from landar.ui.pages.firewall import FirewallPage
from landar.ui.pages.monitoring import LiveMonitoringPage
from landar.ui.pages.networks import NetworksPage
from landar.ui.pages.placeholder import soon
from landar.ui.pages.policy_engine import PolicyEnginePage
from landar.ui.pages.schedules import SchedulesPage
from landar.ui.pages.sessions import SessionsPage
from landar.ui.pages.topology import TopologyPage
from landar.ui.pages.users import UsersPage

@dataclass(frozen=True)
class PageSpec:
    name: str
    factory: object       # callable(actor) -> Page
    permission: str       # page is hidden from roles lacking this permission
    group: str            # sidebar section
    icon: str             # Material Symbols name (must exist in assets/fonts/icons.json)

V = "monitoring.view"
PAGES = [
    PageSpec("Dashboard", DashboardPage, "monitoring.view", "Overview", "dashboard"),
    PageSpec("Topology", TopologyPage, "network.view", "Network", "hub"),
    PageSpec("Networks & VLANs", NetworksPage, "network.view", "Network", "lan"),
    PageSpec("DHCP & DNS", DhcpDnsPage, "network.view", "Network", "dns"),
    PageSpec("Users & Roles", UsersPage, "users.view", "People", "manage_accounts"),
    PageSpec("Active Sessions", SessionsPage, V, "People", "group_work"),
    PageSpec("Device Inventory", DevicesPage, "devices.view", "Devices", "router"),
    PageSpec("Approvals", ApprovalsPage, "devices.view", "Devices", "verified_user"),
    PageSpec("Policy Engine", PolicyEnginePage, "network.view", "Security & Access", "tune"),
    PageSpec("Firewall Rules", FirewallPage, "firewall.view", "Security & Access", "shield"),
    PageSpec("Bandwidth / QoS", BandwidthPage, "network.view", "Security & Access", "speed"),
    PageSpec("Access Schedules", SchedulesPage, "network.view", "Security & Access", "schedule"),
    PageSpec("Live Monitoring", LiveMonitoringPage, V, "Observability", "monitoring"),
    PageSpec("Alerts & Incidents", AlertsPage, V, "Observability", "notification_important"),
    PageSpec("Audit Logs", AuditPage, "audit.view", "Observability", "receipt_long"),
    PageSpec("Reports", soon("Reports", "Phase 8", "assessment"), V, "Observability", "assessment"),
    PageSpec("Credential Vault", soon("Credential Vault", "Phase 8", "key"), V, "System", "key"),
    PageSpec("Settings", soon("Settings", "Later", "settings"), V, "System", "settings"),
]
