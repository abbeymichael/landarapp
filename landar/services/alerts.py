"""Alerts / incidents (Phase 6).

Alerts are raised by LANDAR itself (from real observations: unknown devices, repeated auth
failures, blocked devices, expiring accounts) or manually. They carry a severity and a
lifecycle state. Nothing here is simulated: `sync()` derives alerts from current inventory
and the audit trail, and de-duplicates so the same condition is not raised twice.
"""
from landar import storage
from landar.core.constants import ALERT_STATES, SEVERITIES
from landar.services import audit
from landar.services.guard import require

def list_alerts(actor, state="All", severity="All") -> list[dict]:
    require(actor, "monitoring.view")
    with storage.connect() as c:
        sql, args = "SELECT * FROM alerts", []
        where = []
        if state not in ("All", None): where.append("state=?"); args.append(state)
        if severity not in ("All", None): where.append("severity=?"); args.append(severity)
        if where: sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END, id DESC"
        return [dict(r) for r in c.execute(sql, args)]

def raise_alert(actor, severity, kind, message, source=None):
    if severity not in SEVERITIES: raise ValueError(f"Severity must be one of {', '.join(SEVERITIES)}")
    message = (message or "").strip()
    if not message: raise ValueError("Message is required")
    with storage.connect() as c:
        cur = c.execute("""INSERT INTO alerts(severity,kind,source,message,state,created_at,updated_at)
                           VALUES(?,?,?,?,'Open',?,?)""", (severity, kind, source, message, audit.now(), audit.now()))
        audit.record(c, actor.username, "alert_raised", kind, new=f"{severity}: {message}"); return cur.lastrowid

def _raise_if_new(c, severity, kind, source, message):
    if c.execute("SELECT 1 FROM alerts WHERE kind=? AND source IS ? AND message=? AND state!='Resolved'", (kind, source, message)).fetchone():
        return 0
    c.execute("INSERT INTO alerts(severity,kind,source,message,state,created_at,updated_at) VALUES(?,?,?,?,'Open',?,?)",
              (severity, kind, source, message, audit.now(), audit.now()))
    return 1

def set_state(actor, alert_id, state):
    require(actor, "monitoring.view")
    if state not in ALERT_STATES: raise ValueError(f"State must be one of {', '.join(ALERT_STATES)}")
    with storage.connect() as c:
        a = c.execute("SELECT kind,state FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not a: raise ValueError("Alert not found")
        c.execute("UPDATE alerts SET state=?, updated_at=? WHERE id=?", (state, audit.now(), alert_id))
        audit.record(c, actor.username, f"alert_{state.lower()}", a["kind"], old=a["state"], new=state)

def resolve_all(actor) -> int:
    require(actor, "monitoring.view")
    with storage.connect() as c:
        n = c.execute("SELECT COUNT(*) FROM alerts WHERE state!='Resolved'").fetchone()[0]
        c.execute("UPDATE alerts SET state='Resolved', updated_at=? WHERE state!='Resolved'", (audit.now(),))
        audit.record(c, actor.username, "alerts_resolved", new=f"{n} resolved"); return n

def sync(actor) -> dict:
    """Derive alerts from the current inventory + audit trail. Idempotent."""
    require(actor, "monitoring.view")
    raised = 0
    with storage.connect() as c:
        for d in c.execute("SELECT mac,ip,hostname FROM devices WHERE state='Unknown'"):
            raised += _raise_if_new(c, "WARNING", "unknown_device", d["mac"],
                                    f"Unknown device {d['hostname'] or d['mac']} ({d['ip'] or 'no IP'}) needs a decision")
        for d in c.execute("SELECT mac FROM devices WHERE state='Blocked'"):
            raised += _raise_if_new(c, "INFO", "blocked_device", d["mac"], f"Device {d['mac']} is blocked (enforcement pending a firewall provider)")
        fails = c.execute("SELECT COUNT(*) FROM audit_logs WHERE action='login' AND result='failure' AND ts >= datetime('now','-1 day')").fetchone()[0]
        if fails >= 3:
            raised += _raise_if_new(c, "CRITICAL" if fails >= 10 else "WARNING", "auth_failures", None,
                                    f"{fails} failed logins in the last 24 hours")
        expired = c.execute("SELECT COUNT(*) FROM users WHERE status='Expired'").fetchone()[0]
        if expired:
            raised += _raise_if_new(c, "WARNING", "expired_accounts", None, f"{expired} account(s) are expired")
        if raised: audit.record(c, actor.username, "alerts_synced", new=f"{raised} new")
    return {"raised": raised, "total": len(list_alerts(actor))}

def counts(actor) -> dict:
    require(actor, "monitoring.view")
    with storage.connect() as c:
        q = lambda s, *a: c.execute(s, a).fetchone()[0]
        return {"open": q("SELECT COUNT(*) FROM alerts WHERE state='Open'"),
                "critical": q("SELECT COUNT(*) FROM alerts WHERE state!='Resolved' AND severity='CRITICAL'"),
                "warning": q("SELECT COUNT(*) FROM alerts WHERE state!='Resolved' AND severity='WARNING'"),
                "resolved": q("SELECT COUNT(*) FROM alerts WHERE state='Resolved'")}
