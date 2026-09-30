"""Access policies + the Policy Engine (Phase 4).

`access_policies` name a subject group and a priority; `policy_zones` give the per-zone
verdict (Allow/Deny/Reject). The actual decision maths live in `core/policy.py` (pure).
`evaluate()` here only loads the rows, calls the engine, and audits the preview.
"""
import sqlite3
from landar import storage
from landar.core import policy as engine
from landar.core.constants import ACTIONS, ZONES
from landar.services import audit, bandwidth, schedules
from landar.services.guard import require

def list_policies(actor) -> list[dict]:
    require(actor, "network.view")
    with storage.connect() as c:
        out = []
        for p in c.execute("SELECT * FROM access_policies ORDER BY priority, id"):
            d = dict(p)
            d["zones"] = {z["zone"]: z["action"] for z in c.execute("SELECT zone,action FROM policy_zones WHERE policy_id=?", (p["id"],))}
            d["status"] = "Enabled" if p["enabled"] else "Disabled"; out.append(d)
        return out

def _load(c, pid):
    p = dict(c.execute("SELECT * FROM access_policies WHERE id=?", (pid,)).fetchone())
    p["zones"] = [dict(z) for z in c.execute("SELECT zone,action FROM policy_zones WHERE policy_id=?", (pid,))]
    return p

def _validate_zones(zones):
    clean = []
    for zone, action in zones.items():
        if zone not in ZONES: raise ValueError(f"Unknown zone '{zone}'")
        if action not in ACTIONS: raise ValueError(f"Unknown action '{action}' for {zone}")
        clean.append({"zone": zone, "action": action})
    if not clean: raise ValueError("Give the policy at least one zone rule")
    return clean

def create_policy(actor, name, applies_group, priority, zones, enabled=True, description=""):
    require(actor, "network.configure")
    name = (name or "").strip()
    if not name: raise ValueError("Name is required")
    if priority is None or not 1 <= int(priority) <= 9999: raise ValueError("Priority must be between 1 and 9999")
    zones = _validate_zones(zones)
    with storage.connect() as c:
        try:
            cur = c.execute("""INSERT INTO access_policies(name,applies_group,priority,enabled,description,created_at) VALUES(?,?,?,?,?,?)""",
                            (name, applies_group or None, int(priority), int(bool(enabled)), description.strip(), audit.now()))
        except sqlite3.IntegrityError: raise ValueError(f"A policy named '{name}' already exists")
        c.executemany("INSERT INTO policy_zones(policy_id,zone,action) VALUES(?,?,?)", [(cur.lastrowid, z["zone"], z["action"]) for z in zones])
        audit.record(c, actor.username, "policy_created", name, new=f"group={applies_group or 'any'}, {len(zones)} zone(s)"); return cur.lastrowid

def update_policy(actor, policy_id, name, applies_group, priority, zones, enabled=True, description=""):
    require(actor, "network.configure")
    name = (name or "").strip()
    if not name: raise ValueError("Name is required")
    if priority is None or not 1 <= int(priority) <= 9999: raise ValueError("Priority must be between 1 and 9999")
    zones = _validate_zones(zones)
    with storage.connect() as c:
        if not c.execute("SELECT 1 FROM access_policies WHERE id=?", (policy_id,)).fetchone(): raise ValueError("Policy not found")
        try:
            c.execute("UPDATE access_policies SET name=?,applies_group=?,priority=?,enabled=?,description=? WHERE id=?",
                      (name, applies_group or None, int(priority), int(bool(enabled)), description.strip(), policy_id))
        except sqlite3.IntegrityError: raise ValueError(f"A policy named '{name}' already exists")
        c.execute("DELETE FROM policy_zones WHERE policy_id=?", (policy_id,))
        c.executemany("INSERT INTO policy_zones(policy_id,zone,action) VALUES(?,?,?)", [(policy_id, z["zone"], z["action"]) for z in zones])
        audit.record(c, actor.username, "policy_updated", name, new=f"group={applies_group or 'any'}, {len(zones)} zone(s)")

def delete_policy(actor, policy_id):
    require(actor, "network.configure")
    with storage.connect() as c:
        r = c.execute("SELECT name FROM access_policies WHERE id=?", (policy_id,)).fetchone()
        if not r: raise ValueError("Policy not found")
        c.execute("DELETE FROM access_policies WHERE id=?", (policy_id,))     # cascades zones
        audit.record(c, actor.username, "policy_deleted", r["name"])

def preview(actor, username, when, device_id=None, record=False) -> dict:
    """Resolve the access decision for a user at a moment in time. Pure preview unless record=True."""
    require(actor, "network.view")
    from datetime import datetime
    with storage.connect() as c:
        u = c.execute("SELECT u.username, u.status, g.name AS grp, r.name AS role FROM users u "
                      "LEFT JOIN groups g ON g.id=u.group_id LEFT JOIN roles r ON r.id=u.role_id WHERE u.username=?", (username,)).fetchone()
        if not u: raise ValueError(f"No user named '{username}'")
        dev = None
        if device_id:
            row = c.execute("SELECT id,mac,state,online,device_type FROM devices WHERE id=?", (device_id,)).fetchone()
            dev = dict(row) if row else None
        pol = [_load(c, p["id"]) for p in c.execute("SELECT id FROM access_policies WHERE enabled=1 ORDER BY priority, id")]
    user = {"username": u["username"], "group": u["grp"], "role": u["role"]}
    bw = [{"scope": p["scope"], "target": p["target"], "down": p["down"], "up": p["up"], "unit": p["unit"], "name": p["name"]} for p in bandwidth.list_policies(actor)]
    sch = [{"name": s["name"], "applies_group": s["applies_group"], "days": (s["days"] or "").split(","), "start": s["start"], "end": s["end"]} for s in schedules.list_schedules(actor) if s["enabled"]]
    d = engine.evaluate(user, dev, when, pol, bw, sch, list(ZONES))
    out = {"username": u["username"], "group": u["grp"], "role": u["role"], "when": when.strftime("%Y-%m-%d %H:%M"),
           "allowed": d.allowed, "reason": d.reason, "matched_policy": d.matched_policy, "zones": d.zones,
           "bandwidth": d.bandwidth, "schedule": d.schedule, "outside_schedule": d.outside_schedule, "trace": d.trace,
           "device": (dev or {}).get("mac")}
    if record:
        with storage.connect() as c: audit.record(c, actor.username, "policy_evaluated", username, new=f"allowed={d.allowed}, {d.reason}")
    return out
