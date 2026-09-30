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
