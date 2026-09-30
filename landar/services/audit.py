"""Audit trail. NEVER pass passwords or secrets into record()."""
from datetime import datetime, timezone
from landar import storage

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def record(conn, actor, action, target=None, old=None, new=None, result="success", source="desktop"):
    conn.execute("INSERT INTO audit_logs(ts,actor,action,target,old_value,new_value,result,source) VALUES(?,?,?,?,?,?,?,?)",
                 (now(), actor, action, target, old, new, result, source))

def list_entries(actor, limit=500):
    from landar.services.guard import require
    require(actor, "audit.view")
    with storage.connect() as c:
        return c.execute("SELECT id,ts,actor,action,target,old_value,new_value,result FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
