"""Active sessions (Phase 3).

A session is an authenticated user on a device for a period of time. Without a RADIUS
provider, LANDAR records sessions from the local auth flow and lets an administrator
start/end one manually (e.g. from a RADIUS accounting feed once that provider exists).
Nothing here fabricates live traffic; usage counters are only what is recorded.
"""
import sqlite3
from landar import storage
from landar.services import audit
from landar.services.guard import require

def _mac(text):
    from landar.providers.lan_scan import normalize_mac
    m = normalize_mac(text or "")
    if text and not m: raise ValueError("MAC must look like AA:BB:CC:DD:EE:FF")
    return m

def list_sessions(actor, state="All") -> list[dict]:
    require(actor, "monitoring.view")
    with storage.connect() as c:
        where, args = ("", ()) if state in ("All", None) else ("WHERE s.state=?", (state,))
        return [dict(r) for r in c.execute(f"""SELECT s.*, u.full_name, n.name AS network
            FROM sessions s LEFT JOIN users u ON u.id=s.user_id LEFT JOIN networks n ON n.id=s.network_id
            {where} ORDER BY CASE s.state WHEN 'Active' THEN 0 ELSE 1 END, s.id DESC""", args)]

def start_session(actor, username, ip="", mac="", network_id=None, auth_source="local"):
    require(actor, "network.configure")
    username = (username or "").strip()
    if not username: raise ValueError("Username is required")
    m = _mac(mac)
    with storage.connect() as c:
        u = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        dev = c.execute("SELECT id FROM devices WHERE mac=?", (m,)).fetchone() if m else None
        cur = c.execute("""INSERT INTO sessions(user_id,username,device_id,ip,mac,network_id,auth_source,state,started_at)
                           VALUES(?,?,?,?,?,?,?,'Active',?)""",
                        (u["id"] if u else None, username, dev["id"] if dev else None, ip.strip() or None, m,
                         network_id, auth_source, audit.now()))
        audit.record(c, actor.username, "session_started", username, new=f"ip={ip or '—'}"); return cur.lastrowid

def end_session(actor, session_id, reason="manual"):
    require(actor, "monitoring.view")
    with storage.connect() as c:
        s = c.execute("SELECT username,state FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not s: raise ValueError("Session not found")
        if s["state"] != "Active": raise ValueError("Session is already closed")
        c.execute("UPDATE sessions SET state='Ended', ended_at=? WHERE id=?", (audit.now(), session_id))
        audit.record(c, actor.username, "session_ended", s["username"], new=reason)

def end_all(actor) -> int:
    require(actor, "monitoring.view")
    with storage.connect() as c:
        n = c.execute("SELECT COUNT(*) FROM sessions WHERE state='Active'").fetchone()[0]
        c.execute("UPDATE sessions SET state='Ended', ended_at=? WHERE state='Active'", (audit.now(),))
        audit.record(c, actor.username, "sessions_cleared", new=f"{n} ended"); return n

def stats(actor) -> dict:
    require(actor, "monitoring.view")
    with storage.connect() as c:
        q = lambda s, *a: c.execute(s, a).fetchone()[0]
        return {"active": q("SELECT COUNT(*) FROM sessions WHERE state='Active'"),
                "total": q("SELECT COUNT(*) FROM sessions"),
                "users": q("SELECT COUNT(DISTINCT user_id) FROM sessions WHERE state='Active' AND user_id IS NOT NULL")}
