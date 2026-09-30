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
