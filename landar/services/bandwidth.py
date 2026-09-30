"""Bandwidth / QoS policies (Phase 4).

Rate limits are attached to a subject (role, group, network, VLAN, user or device). The
policy engine resolves the effective limit for a user; nothing is shaped on the wire until
a router/firewall provider can push it (Phase 5). Values are stored canonically in Kbps so
comparisons are unambiguous, while the UI shows the unit the admin chose.
"""
import ipaddress, sqlite3
from landar import storage
from landar.core.constants import BW_SCOPES, BW_UNITS
from landar.services import audit
from landar.services.guard import require

def to_kbps(value, unit) -> int:
    if unit not in BW_UNITS: raise ValueError(f"Unit must be one of {', '.join(BW_UNITS)}")
    try: v = float(value)
    except (TypeError, ValueError): raise ValueError("Bandwidth must be a number")
    if v < 0: raise ValueError("Bandwidth cannot be negative")
    return int(round(v * BW_UNITS[unit]))

def _validate(scope, target, down, up, unit, priority):
    if scope not in BW_SCOPES: raise ValueError(f"Scope must be one of {', '.join(BW_SCOPES)}")
    if priority is None or not 1 <= int(priority) <= 9999: raise ValueError("Priority must be between 1 and 9999")
    if down <= 0 and up <= 0: raise ValueError("Set a download and/or upload limit")
    return target or None

def _check_target(c, scope, target):
    """Warn-free validation: ensure the referenced object exists for scopes that name one."""
    if not target: return
    if scope == "Network": ok = c.execute("SELECT 1 FROM networks WHERE name=?", (target,)).fetchone()
    elif scope == "VLAN": ok = c.execute("SELECT 1 FROM networks WHERE vlan_id=?", (target,)).fetchone()
    elif scope == "Group": ok = c.execute("SELECT 1 FROM groups WHERE name=?", (target,)).fetchone()
    elif scope == "User": ok = c.execute("SELECT 1 FROM users WHERE username=?", (target,)).fetchone()
    elif scope == "Device": ok = c.execute("SELECT 1 FROM devices WHERE mac=?", (target,)).fetchone()
    else: ok = True
    if not ok: raise ValueError(f"No {scope.lower()} named '{target}' exists")

def list_policies(actor) -> list[dict]:
    require(actor, "network.view")
    with storage.connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM bandwidth_policies ORDER BY priority, id")]

def create_policy(actor, name, scope, target, down, up, unit, priority=100, enabled=True):
    require(actor, "network.configure")
    name = (name or "").strip()
    if not name: raise ValueError("Name is required")
    d, u = to_kbps(down or 0, unit), to_kbps(up or 0, unit)
    with storage.connect() as c:
        target = _validate(scope, target, d, u, unit, priority); _check_target(c, scope, target)
        cur = c.execute("""INSERT INTO bandwidth_policies(name,scope,target,down,up,unit,priority,enabled,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (name, scope, target, d, u, unit, int(priority), int(bool(enabled)), audit.now()))
        audit.record(c, actor.username, "bandwidth_policy_created", name, new=f"{scope}:{target or 'any'} {down}/{up} {unit}"); return cur.lastrowid

def update_policy(actor, policy_id, name, scope, target, down, up, unit, priority=100, enabled=True):
    require(actor, "network.configure")
    name = (name or "").strip()
    if not name: raise ValueError("Name is required")
    d, u = to_kbps(down or 0, unit), to_kbps(up or 0, unit)
    with storage.connect() as c:
        target = _validate(scope, target, d, u, unit, priority); _check_target(c, scope, target)
        old = c.execute("SELECT name FROM bandwidth_policies WHERE id=?", (policy_id,)).fetchone()
        if not old: raise ValueError("Policy not found")
        c.execute("""UPDATE bandwidth_policies SET name=?,scope=?,target=?,down=?,up=?,unit=?,priority=?,enabled=? WHERE id=?""",
                  (name, scope, target, d, u, unit, int(priority), int(bool(enabled)), policy_id))
        audit.record(c, actor.username, "bandwidth_policy_updated", name, new=f"{scope}:{target or 'any'} {down}/{up} {unit}")

def delete_policy(actor, policy_id):
    require(actor, "network.configure")
    with storage.connect() as c:
        r = c.execute("SELECT name FROM bandwidth_policies WHERE id=?", (policy_id,)).fetchone()
        if not r: raise ValueError("Policy not found")
        c.execute("DELETE FROM bandwidth_policies WHERE id=?", (policy_id,))
        audit.record(c, actor.username, "bandwidth_policy_deleted", r["name"])

def _display(kbps, unit):
    factor = BW_UNITS.get(unit, 1000)
    val = kbps / factor
    return f"{int(val) if val == int(val) else round(val, 2)} {unit}"

def list_display(actor) -> list[dict]:
    """Rows for the table, with human values in the unit each policy was authored in."""
    out = []
    for p in list_policies(actor):
        d = dict(p); d["down_disp"] = "—" if p["down"] == 0 else _display(p["down"], p["unit"])
        d["up_disp"] = "—" if p["up"] == 0 else _display(p["up"], p["unit"])
        d["status"] = "Enabled" if p["enabled"] else "Disabled"; out.append(d)
    return out

def role_matrix(actor) -> list[dict]:
    """Effective download/upload per user class (group), resolved by priority.
    Used by the Policy Engine page to show the spec's bandwidth table."""
    from landar.core.constants import DEFAULT_GROUPS
    rows = [dict(r) for r in list_display(actor) if r["enabled"]]
    out = []
    for grp in DEFAULT_GROUPS:
        hit = next((r for r in rows if r["scope"] in ("Role", "Group") and (r["target"] or "").lower() == grp.lower()), None)
        out.append({"role": grp, "down": hit["down_disp"] if hit else "Unlimited",
                    "up": hit["up_disp"] if hit else "Unlimited", "policy": hit["name"] if hit else "—"})
    return out
