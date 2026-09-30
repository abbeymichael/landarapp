"""Provider interfaces. Implement these to add RADIUS, LDAP, OPNsense, MikroTik, etc.
The rest of the app talks only to these interfaces, so vendors can be swapped without touching services or UI."""
from abc import ABC, abstractmethod

class AuthProvider(ABC):
    name = "base"
    @abstractmethod
    def authenticate(self, username: str, password: str) -> bool: ...

class NetworkProvider(ABC):
    """Talks to routers/firewalls/switches. Discovery != control: keep read and write methods separate."""
    name = "base"
    @abstractmethod
    def discover_devices(self) -> list[dict]: ...           # read-only
    def network_info(self) -> dict:                         # read-only: {'interface','ip','cidr'}
        return {}
    def block_mac(self, mac: str) -> None:                  # control: opt-in per provider
        raise NotImplementedError(f"{self.name} does not support blocking")
