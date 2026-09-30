"""Active providers, tried in order. Add RadiusAuthProvider() etc. here."""
from landar.providers.local_auth import LocalAuthProvider
AUTH_PROVIDERS = [LocalAuthProvider()]
from landar.providers.lan_scan import LanScanProvider
NETWORK_PROVIDERS = [LanScanProvider()]   # read-only discovery. Add OPNsenseProvider() etc. in Phase 5
