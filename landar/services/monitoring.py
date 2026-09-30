from landar import storage
from landar.services.guard import require

def overview(actor) -> dict:
    """Real dashboard numbers (no simulated data). Extend with live metrics in Phase 6."""
    require(actor, "monitoring.view")
    with storage.connect() as c:
        q = lambda s, *a: c.execute(s, a).fetchone()[0]
        groups = {r[0]: r[1] for r in c.execute(
            "SELECT g.name, COUNT(*) FROM users u JOIN groups g ON g.id=u.group_id WHERE u.status='Active' GROUP BY g.name")}
        last = c.execute("SELECT ts FROM audit_logs WHERE action='network_scan' ORDER BY id DESC LIMIT 1").fetchone()
        return {
            "users_active": q("SELECT COUNT(*) FROM users WHERE status='Active'"), "users_total": q("SELECT COUNT(*) FROM users"),
            "groups": groups,
            "devices_total": q("SELECT COUNT(*) FROM devices"), "devices_online": q("SELECT COUNT(*) FROM devices WHERE online=1"),
            "unknown": q("SELECT COUNT(*) FROM devices WHERE state='Unknown'"),
            "blocked": q("SELECT COUNT(*) FROM devices WHERE state='Blocked'"),
            "auth_fail_24h": q("SELECT COUNT(*) FROM audit_logs WHERE action='login' AND result='failure' AND ts >= datetime('now','-1 day')"),
            "last_scan": last[0] if last else None,
        }

def unknown_devices(actor, limit=5):
    require(actor, "devices.view")
    with storage.connect() as c:
        return c.execute("SELECT id,mac,ip,hostname,vendor,first_seen FROM devices WHERE state='Unknown' ORDER BY first_seen DESC LIMIT ?", (limit,)).fetchall()

def recent_auth_failures(actor, limit=3):
    require(actor, "audit.view")
    with storage.connect() as c:
        return c.execute("SELECT ts,actor FROM audit_logs WHERE action='login' AND result='failure' ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

def online_devices(actor, limit=8):
    require(actor, "devices.view")
    with storage.connect() as c:
        return c.execute("SELECT hostname,ip,mac,vendor,state FROM devices WHERE online=1 ORDER BY ip LIMIT ?", (limit,)).fetchall()

def recent_activity(actor, limit=6):
    require(actor, "audit.view")
    with storage.connect() as c:
        return c.execute("SELECT ts,actor,action,target,result FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
