"""Firewall rules (Phase 5).

Managed configuration: an ordered, visual rule list

    SOURCE -> DESTINATION -> SERVICE/PORT -> PROTOCOL -> ACTION -> LOGGING

Order is authoritative (position 1 is evaluated first) and the UI always shows it. Rules are
validated, stored and audited; enforcement requires a NetworkProvider that can push them
(`providers/base.py` -> `apply_firewall`). Until one exists, `push()` reports that honestly
and never pretends a rule is live.
"""
import sqlite3
from landar import storage
from landar.core.constants import PROTOCOLS
from landar.providers.registry import NETWORK_PROVIDERS
from landar.services import audit
from landar.services.guard import require

def list_rules(actor) -> list[dict]:
    require(actor, "firewall.view")
    with storage.connect() as c:
        out = []
        for r in c.execute("""SELECT f.*, s.name AS schedule FROM firewall_rules f
                              LEFT JOIN schedules s ON s.id=f.schedule_id ORDER BY f.position, f.id"""):
            d = dict(r); d["status"] = "Enabled" if r["enabled"] else "Disabled"; out.append(d)
        return out

def _validate(c, action, protocol, port, source, destination, schedule_id):
    if action not in ("Allow", "Deny", "Reject"): raise ValueError("Action must be Allow, Deny or Reject")
    if protocol not in PROTOCOLS: raise ValueError(f"Protocol must be one of {', '.join(PROTOCOLS)}")
    if port and protocol == "ICMP": raise ValueError("ICMP rules do not take a port")
    if port:
        for token in str(port).replace(" ", "").split(","):
            for part in token.split("-"):
                if not part.isdigit() or not 0 <= int(part) <= 65535: raise ValueError(f"Port '{port}' is not a valid port or range")
    if not (source or "").strip() or not (destination or "").strip(): raise ValueError("Source and destination are required (use 'Any')")
    if schedule_id and not c.execute("SELECT 1 FROM schedules WHERE id=?", (schedule_id,)).fetchone(): raise ValueError("Chosen schedule no longer exists")

def _next_position(c):
    return (c.execute("SELECT COALESCE(MAX(position), 0) FROM firewall_rules").fetchone()[0]) + 1

def _append(actor, c, name, action, protocol, source, destination, port, schedule_id, logging, enabled, description):
    _validate(c, action, protocol, port, source, destination, schedule_id)
    pos = _next_position(c)
    cur = c.execute("""INSERT INTO firewall_rules(position,name,action,protocol,source,destination,port,schedule_id,logging,enabled,description,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (pos, name.strip(), action, protocol, source.strip(), destination.strip(), (port or "").strip() or None,
                     schedule_id, int(bool(logging)), int(bool(enabled)), (description or "").strip(), audit.now()))
    return cur.lastrowid, pos

def add_rule(actor, name, action="Allow", protocol="Any", source="Any", destination="Any", port="",
             schedule_id=None, logging=True, enabled=True, description="") -> int:
    require(actor, "firewall.edit")
    with storage.connect() as c:
        rid, pos = _append(actor, c, name, action, protocol, source, destination, port, schedule_id, logging, enabled, description)
        audit.record(c, actor.username, "firewall_rule_added", name or f"rule {pos}", new=f"#{pos} {action} {source}->{destination} {protocol} {port or ''}".strip())
        return rid

def update_rule(actor, rule_id, name, action, protocol, source, destination, port="",
                schedule_id=None, logging=True, enabled=True, description=""):
    require(actor, "firewall.edit")
    with storage.connect() as c:
        old = c.execute("SELECT * FROM firewall_rules WHERE id=?", (rule_id,)).fetchone()
        if not old: raise ValueError("Rule not found")
        _validate(c, action, protocol, port, source, destination, schedule_id)
        c.execute("""UPDATE firewall_rules SET name=?,action=?,protocol=?,source=?,destination=?,port=?,schedule_id=?,logging=?,enabled=?,description=? WHERE id=?""",
                  (name.strip(), action, protocol, source.strip(), destination.strip(), (port or "").strip() or None,
                   schedule_id, int(bool(logging)), int(bool(enabled)), (description or "").strip(), rule_id))
        audit.record(c, actor.username, "firewall_rule_updated", name or f"rule {old['position']}",
                     old=f"{old['action']} {old['source']}->{old['destination']}", new=f"{action} {source}->{destination}")

def delete_rule(actor, rule_id):
    require(actor, "firewall.edit")
    with storage.connect() as c:
        r = c.execute("SELECT name,position FROM firewall_rules WHERE id=?", (rule_id,)).fetchone()
        if not r: raise ValueError("Rule not found")
        c.execute("DELETE FROM firewall_rules WHERE id=?", (rule_id,)); _resequence(c)
        audit.record(c, actor.username, "firewall_rule_deleted", r["name"] or f"rule {r['position']}")

def move_rule(actor, rule_id, direction):
    """Swap a rule with its neighbour. `direction` is 'up' (towards position 1) or 'down'."""
    require(actor, "firewall.edit")
    with storage.connect() as c:
        rows = [dict(r) for r in c.execute("SELECT id,position,name FROM firewall_rules ORDER BY position, id")]
        i = next((k for k, r in enumerate(rows) if r["id"] == rule_id), None)
        if i is None: raise ValueError("Rule not found")
        j = i - 1 if direction == "up" else i + 1
        if j < 0 or j >= len(rows): return
        a, b = rows[i], rows[j]
        c.execute("UPDATE firewall_rules SET position=? WHERE id=?", (b["position"], a["id"]))
        c.execute("UPDATE firewall_rules SET position=? WHERE id=?", (a["position"], b["id"]))
        audit.record(c, actor.username, "firewall_rule_moved", a["name"] or f"rule {a['position']}", new=f"{direction} to #{b['position']}")

def toggle_rule(actor, rule_id, enabled):
    require(actor, "firewall.edit")
    with storage.connect() as c:
        r = c.execute("SELECT name,enabled FROM firewall_rules WHERE id=?", (rule_id,)).fetchone()
        if not r: raise ValueError("Rule not found")
        c.execute("UPDATE firewall_rules SET enabled=? WHERE id=?", (int(bool(enabled)), rule_id))
        audit.record(c, actor.username, "firewall_rule_toggled", r["name"] or f"rule {rule_id}", old="Enabled" if r["enabled"] else "Disabled", new="Enabled" if enabled else "Disabled")

def _resequence(c):
    for pos, r in enumerate(c.execute("SELECT id FROM firewall_rules ORDER BY position, id"), start=1):
        c.execute("UPDATE firewall_rules SET position=? WHERE id=?", (pos, r["id"]))

def stats(actor) -> dict:
    require(actor, "firewall.view")
    with storage.connect() as c:
        q = lambda s: c.execute(s).fetchone()[0]
        return {"total": q("SELECT COUNT(*) FROM firewall_rules"), "allow": q("SELECT COUNT(*) FROM firewall_rules WHERE action='Allow'"),
                "deny": q("SELECT COUNT(*) FROM firewall_rules WHERE action IN ('Deny','Reject')"), "enabled": q("SELECT COUNT(*) FROM firewall_rules WHERE enabled=1")}

def _provider(provider=None):
    p = provider or (NETWORK_PROVIDERS[0] if NETWORK_PROVIDERS else None)
    if not p: raise ValueError("No network provider is configured")
    return p

def push(actor, provider=None) -> dict:
    """Attempt to push the ordered rule set to the active provider. Honest about capability."""
    require(actor, "firewall.edit")
    rules = list_rules(actor); p = _provider(provider)
    try:
        result = p.apply_firewall(rules)
    except NotImplementedError as e:
        result = {"applied": False, "message": str(e)}
    with storage.connect() as c:
        audit.record(c, actor.username, "firewall_pushed", p.name, result="success" if result.get("applied") else "denied", new=result.get("message", ""))
    return result
