"""SQLite connection + schema. For schema changes, append to MIGRATIONS (never edit old entries)."""
import sqlite3
from landar import config
from landar.core.constants import DEFAULT_GROUPS
from landar.core.permissions import ROLE_PERMS

MIGRATIONS = [
"""
CREATE TABLE roles(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE groups(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, email TEXT,
  group_id INTEGER REFERENCES groups(id), role_id INTEGER REFERENCES roles(id),
  status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Disabled','Suspended','Expired','Pending','Locked')),
  pw_salt BLOB, pw_hash BLOB, created_at TEXT NOT NULL);
CREATE TABLE devices(
  id INTEGER PRIMARY KEY, hostname TEXT, ip TEXT, mac TEXT UNIQUE NOT NULL, device_type TEXT DEFAULT 'Unknown',
  owner_id INTEGER REFERENCES users(id),
  state TEXT NOT NULL DEFAULT 'Unknown' CHECK(state IN ('Known','Approved','Unknown','Blocked','Offline')),
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
CREATE TABLE audit_logs(
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT,
  old_value TEXT, new_value TEXT, result TEXT NOT NULL DEFAULT 'success', source TEXT DEFAULT 'desktop');
""",
"""
ALTER TABLE devices ADD COLUMN online INTEGER NOT NULL DEFAULT 0;
ALTER TABLE devices ADD COLUMN vendor TEXT;
ALTER TABLE devices ADD COLUMN randomized_mac INTEGER NOT NULL DEFAULT 0;
""",
"""
CREATE TABLE networks(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  vlan_id INTEGER UNIQUE CHECK(vlan_id IS NULL OR vlan_id BETWEEN 1 AND 4094), cidr TEXT UNIQUE NOT NULL, gateway TEXT,
  purpose TEXT NOT NULL DEFAULT 'Other', description TEXT, created_at TEXT NOT NULL);
CREATE TABLE dhcp_scopes(id INTEGER PRIMARY KEY, network_id INTEGER NOT NULL UNIQUE REFERENCES networks(id) ON DELETE CASCADE,
  range_start TEXT NOT NULL, range_end TEXT NOT NULL, lease_hours INTEGER NOT NULL DEFAULT 12, dns_servers TEXT, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE dhcp_reservations(id INTEGER PRIMARY KEY, network_id INTEGER NOT NULL REFERENCES networks(id) ON DELETE CASCADE,
  mac TEXT UNIQUE NOT NULL, ip TEXT UNIQUE NOT NULL, hostname TEXT, description TEXT);
CREATE TABLE dns_records(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, ip TEXT NOT NULL, note TEXT);
CREATE TABLE dns_forwarders(id INTEGER PRIMARY KEY, address TEXT UNIQUE NOT NULL, label TEXT);
""",
"""
-- Phase 3: sessions + network-scoped credentials ---------------------------------
CREATE TABLE sessions(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, username TEXT NOT NULL,
  device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL, ip TEXT, mac TEXT, network_id INTEGER REFERENCES networks(id) ON DELETE SET NULL,
  auth_source TEXT NOT NULL DEFAULT 'local', state TEXT NOT NULL DEFAULT 'Active' CHECK(state IN ('Active','Ended','Expired')),
  started_at TEXT NOT NULL, ended_at TEXT, bytes_down INTEGER NOT NULL DEFAULT 0, bytes_up INTEGER NOT NULL DEFAULT 0);
CREATE TABLE credentials(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'Service',
  target TEXT, username TEXT, secret_enc TEXT, note TEXT, created_at TEXT NOT NULL);
""",
"""
-- Phase 4: schedules, bandwidth policies, access policies ------------------------
CREATE TABLE schedules(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, applies_group TEXT,
  days TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri', start TEXT NOT NULL DEFAULT '08:00', end TEXT NOT NULL DEFAULT '18:00',
  max_session_minutes INTEGER, enabled INTEGER NOT NULL DEFAULT 1, note TEXT, created_at TEXT NOT NULL);
CREATE TABLE bandwidth_policies(id INTEGER PRIMARY KEY, name TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'Role',
  target TEXT, down INTEGER NOT NULL DEFAULT 0, up INTEGER NOT NULL DEFAULT 0, unit TEXT NOT NULL DEFAULT 'Mbps',
  priority INTEGER NOT NULL DEFAULT 100, enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE access_policies(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, applies_group TEXT,
  priority INTEGER NOT NULL DEFAULT 100, enabled INTEGER NOT NULL DEFAULT 1, description TEXT, created_at TEXT NOT NULL);
CREATE TABLE policy_zones(id INTEGER PRIMARY KEY, policy_id INTEGER NOT NULL REFERENCES access_policies(id) ON DELETE CASCADE,
  zone TEXT NOT NULL, action TEXT NOT NULL DEFAULT 'Deny' CHECK(action IN ('Allow','Deny','Reject')), UNIQUE(policy_id, zone));
""",
"""
-- Phase 5: firewall rules (managed configuration; enforcement needs a provider) ---
CREATE TABLE firewall_rules(id INTEGER PRIMARY KEY, position INTEGER NOT NULL, name TEXT,
  action TEXT NOT NULL DEFAULT 'Allow' CHECK(action IN ('Allow','Deny','Reject')), protocol TEXT NOT NULL DEFAULT 'Any',
  source TEXT NOT NULL DEFAULT 'Any', destination TEXT NOT NULL DEFAULT 'Any', port TEXT,
  schedule_id INTEGER REFERENCES schedules(id) ON DELETE SET NULL, logging INTEGER NOT NULL DEFAULT 1,
  enabled INTEGER NOT NULL DEFAULT 1, description TEXT, hits INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
""",
"""
-- Phase 6: alerts / incidents ----------------------------------------------------
CREATE TABLE alerts(id INTEGER PRIMARY KEY, severity TEXT NOT NULL DEFAULT 'INFO' CHECK(severity IN ('INFO','WARNING','CRITICAL')),
  kind TEXT NOT NULL, source TEXT, message TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'Open' CHECK(state IN ('Open','Acknowledged','Resolved')),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
""",
]

def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init() -> None:
    with connect() as c:
        v = c.execute("PRAGMA user_version").fetchone()[0]
        for i, sql in enumerate(MIGRATIONS[v:], start=v + 1):
            c.executescript(sql)
            c.execute(f"PRAGMA user_version={i}")
        for r in ROLE_PERMS: c.execute("INSERT OR IGNORE INTO roles(name) VALUES(?)", (r,))
        for g in DEFAULT_GROUPS: c.execute("INSERT OR IGNORE INTO groups(name) VALUES(?)", (g,))
