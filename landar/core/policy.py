"""Pure access-decision logic (no DB, no UI).

One place decides whether a user is allowed onto the network:

    USER + GROUP + DEVICE + NETWORK + TIME + POLICY = ACCESS DECISION

Inputs are plain dicts (the services layer loads them from the DB and passes them in),
so this file stays unit-testable and vendor-independent. The Policy Engine page shows the
resulting decision; the UI never re-implements the rules.
"""
from dataclasses import dataclass, field
from datetime import datetime, time as dtime


def _to_time(hhmm: str) -> dtime:
    h, m = (hhmm or "00:00").split(":")[:2]
    return dtime(int(h), int(m))


def window_contains(day: str, start: str, end: str, when: datetime, days) -> bool:
    """True if `when` falls inside the schedule window. A window whose end <= start is
    treated as spanning midnight (e.g. 21:00 -> 07:00)."""
    if days and day not in days:
        return False
    s, e, t = _to_time(start), _to_time(end), when.time()
    return s <= t <= e if s <= e else (t >= s or t <= e)


@dataclass
class Decision:
    """The verdict for one user/device/time, plus the trace that produced it."""
    allowed: bool = True
    reason: str = ""
    matched_policy: str | None = None
    matched_rule: int | None = None
    zones: dict = field(default_factory=dict)      # zone -> True/False
    bandwidth: dict | None = None                  # {'down': int, 'up': int, 'unit': str}
    schedule: dict | None = None                   # {'name': ..., 'window': ...}
    outside_schedule: bool = False
    trace: list = field(default_factory=list)      # ordered human-readable steps


def _group_match(selector, group) -> bool:
    sel = (selector or "").strip().lower()
    return sel in ("", "any", "*", "all") or (group is not None and sel == str(group).lower())


def _zone_allowed(zone: str, policies, group) -> tuple[bool, str, int | None, str]:
    """A zone is allowed if an explicit policy names it and none of the matching policies
    deny it. Deny always wins; default is deny (safe defaults)."""
    allow_by, deny_by = None, None
    for idx, p in enumerate(policies):
        if not _group_match(p.get("applies_group"), group):
            continue
        for entry in p.get("zones", []):
            if entry["zone"].lower() == zone.lower():
                if entry["action"] == "Allow" and allow_by is None:
                    allow_by = (p["name"], idx)
                elif entry["action"] != "Allow":
                    deny_by = deny_by or (p["name"], idx, entry["action"])
    if deny_by:
        return False, f"denied by '{deny_by[0]}'", deny_by[1], deny_by[2]
    if allow_by:
        return True, f"allowed by '{allow_by[0]}'", allow_by[1], "Allow"
    return False, "no policy grants this zone", None, "default"


def evaluate(user: dict, device: dict | None, when: datetime, policies, bandwidth_rules,
             schedules, networks, *, online: bool | None = None) -> Decision:
    """Return a Decision. `user` needs {'username','group'}; `device` may be None.
    `policies`, `bandwidth_rules`, `schedules` are lists of dicts (already parsed).
    `networks` maps network name -> True (a list of names is fine too)."""
    group = user.get("group")
    d = Decision()
    d.trace.append(f"subject={user.get('username')} group={group or '—'}")

    # 1) Device block state -----------------------------------------------------
    if device is not None:
        if device.get("state") == "Blocked":
            d.allowed, d.reason = False, "device is blocked"
            d.trace.append("device state=Blocked -> denied")
            return d
        if online is False:
            d.trace.append("device offline (last scan)")

    # 2) Policy resolution ------------------------------------------------------
    d.trace.append(f"policies considered: {[p['name'] for p in policies]}")
    names = list(networks) if not isinstance(networks, dict) else list(networks)
    for zone in names:
        ok, why, idx, act = _zone_allowed(zone, policies, group)
        d.zones[zone] = ok
        if ok and d.matched_policy is None:
            d.matched_policy, d.matched_rule = policies[idx]["name"] if idx is not None else None, idx
        d.trace.append(f"zone '{zone}': {act if act in ('Allow', 'Deny', 'Reject') else '—'} ({why})")

    d.allowed = any(d.zones.values())
    d.reason = "access granted by policy" if d.allowed else "no zone granted; default deny"

    # 3) Bandwidth --------------------------------------------------------------
    # 'Role' and 'Group' are both matched against the user's network group (Students,
    # Teachers, Guests...), which is the user class the spec's bandwidth table refers to.
    for r in bandwidth_rules:
        if r.get("scope") in ("Role", "Group") and _group_match(r.get("target"), group):
            d.bandwidth = {"down": r["down"], "up": r["up"], "unit": r["unit"]}
            d.trace.append(f"bandwidth from '{r['name']}': {r['down']}/{r['up']} {r['unit']}")
            break

    # 4) Schedule ---------------------------------------------------------------
    for s in schedules:
        if not _group_match(s.get("applies_group"), group):
            continue
        inside = window_contains(when.strftime("%a")[:3], s["start"], s["end"], when, s.get("days"))
        d.schedule = {"name": s["name"], "window": f"{s['start']}–{s['end']} {'/'.join(s.get('days') or [])}".strip()}
        if not inside:
            d.outside_schedule = True
            d.allowed = False
            d.reason = f"outside schedule '{s['name']}'"
            d.trace.append(f"schedule '{s['name']}': outside {s['start']}–{s['end']} -> denied")
        else:
            d.trace.append(f"schedule '{s['name']}': inside window")
        break

    return d
