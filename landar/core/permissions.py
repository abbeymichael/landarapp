"""RBAC. Add new permission strings here as features arrive (e.g. 'firewall.edit')."""
from dataclasses import dataclass

ROLE_PERMS = {
    "Super Administrator": {"*"},
    "Network Administrator": {"users.view", "devices.view", "devices.manage", "network.view", "network.scan", "network.configure", "audit.view", "monitoring.view", "reports.view"},
    "IT Administrator": {"users.view", "users.create", "users.edit", "devices.view", "devices.manage", "network.view", "network.scan", "network.configure", "audit.view", "monitoring.view"},
    "Help Desk": {"users.view", "users.edit", "devices.view", "network.view", "monitoring.view"},
    "Auditor": {"users.view", "devices.view", "network.view", "audit.view", "reports.view", "monitoring.view"},
    "Read Only": {"users.view", "devices.view", "network.view", "monitoring.view"},
}

class PermissionDenied(Exception):
    pass

@dataclass(frozen=True)
class Actor:
    """The authenticated administrator performing an action."""
    username: str
    role: str

    def can(self, perm: str) -> bool:
        perms = ROLE_PERMS.get(self.role, set())
        return "*" in perms or perm in perms
