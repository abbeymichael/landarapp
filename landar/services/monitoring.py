from landar import storage
from landar.services.guard import require

def summary(actor) -> dict:
    """Dashboard numbers. Extend with live metrics in Phase 6."""
    require(actor, "monitoring.view")
    with storage.connect() as c:
        q = lambda s: c.execute(s).fetchone()[0]
        return {"Users": q("SELECT COUNT(*) FROM users"), "Active users": q("SELECT COUNT(*) FROM users WHERE status='Active'"),
                "Devices": q("SELECT COUNT(*) FROM devices"), "Unknown devices": q("SELECT COUNT(*) FROM devices WHERE state='Unknown'"),
                "Blocked devices": q("SELECT COUNT(*) FROM devices WHERE state='Blocked'"),
                "Auth failures": q("SELECT COUNT(*) FROM audit_logs WHERE action='login' AND result='failure'")}
