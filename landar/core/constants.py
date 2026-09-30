USER_STATES = ("Active", "Disabled", "Suspended", "Expired", "Pending", "Locked")
DEVICE_STATES = ("Known", "Approved", "Unknown", "Blocked", "Offline")
DEVICE_TYPES = ("Laptop", "Desktop", "Phone", "Tablet", "Server", "Printer", "Router",
                "Switch", "Access point", "IoT", "Camera", "Unknown")
DEFAULT_GROUPS = ("Administrators", "Teachers", "Staff", "Students", "Guests", "Contractors")

# --- Access / policy (Phase 4) -------------------------------------------------
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
ZONES = ("Internet", "Internal LAN", "Servers", "Administration", "Teacher network",
         "Student network", "Guest network", "IoT network", "Management")
ACTIONS = ("Allow", "Deny", "Reject")
BW_SCOPES = ("Role", "Group", "Network", "VLAN", "User", "Device")
BW_UNITS = {"Kbps": 1, "Mbps": 1000, "Gbps": 1_000_000}

# --- Firewall (Phase 5) --------------------------------------------------------
PROTOCOLS = ("Any", "TCP", "UDP", "ICMP")

# --- Observability (Phase 6) ---------------------------------------------------
SEVERITIES = ("INFO", "WARNING", "CRITICAL")
ALERT_STATES = ("Open", "Acknowledged", "Resolved")
