"""Access schedules (Phase 4): when a group is allowed on the network.

Time windows with days-of-week, plus an optional maximum session length. Validation is
strict (HH:MM, real day names) and every change is audited. A window whose end is not
after its start is allowed and interpreted as spanning midnight (e.g. 21:00 -> 07:00).
"""
import re, sqlite3
from landar import storage
from landar.core.constants import DAYS
from landar.services import audit
from landar.services.guard import require

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

def _time(text, what):
    text = (text or "").strip()
    if not _HHMM.match(text): raise ValueError(f"{what} must be HH:MM (24-hour), e.g. 08:00")
    return text

def _days(text_or_list):
    items = text_or_list if isinstance(text_or_list, (list, tuple)) else str(text_or_list or "").split(",")
    picked = [d.strip() for d in items if d.strip()]
    if not picked: raise ValueError("Pick at least one day")
    bad = [d for d in picked if d not in DAYS]
    if bad: raise ValueError(f"Unknown day(s): {', '.join(bad)}")
    return ",".join(d for d in DAYS if d in picked)     # normalise to Mon..Sun order

def list_schedules(actor) -> list[dict]:
    require(actor, "network.view")
    with storage.connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM schedules ORDER BY name")]

def create_schedule(actor, name, applies_group, days, start, end, max_session_minutes=None, enabled=True, note=""):
    require(actor, "network.configure")
    name = (name or "").strip()
    if not name: raise ValueError("Name is required")
    days, start, end = _days(days), _time(start, "Start"), _time(end, "End")
    if max_session_minutes in ("", None): max_session_minutes = None
    elif not 1 <= int(max_session_minutes) <= 1440: raise ValueError("Max session must be between 1 and 1440 minutes")
    with storage.connect() as c:
        try:
            cur = c.execute("""INSERT INTO schedules(name,applies_group,days,start,end,max_session_minutes,enabled,note,created_at)
                               VALUES(?,?,?,?,?,?,?,?,?)""",
                            (name, applies_group or None, days, start, end, max_session_minutes, int(bool(enabled)), note.strip(), audit.now()))
        except sqlite3.IntegrityError: raise ValueError(f"A schedule named '{name}' already exists")
        audit.record(c, actor.username, "schedule_created", name, new=f"{days} {start}-{end}"); return cur.lastrowid

def update_schedule(actor, schedule_id, name, applies_group, days, start, end, max_session_minutes=None, enabled=True, note=""):
    require(actor, "network.configure")
    name = (name or "").strip()
    if not name: raise ValueError("Name is required")
    days, start, end = _days(days), _time(start, "Start"), _time(end, "End")
    if max_session_minutes in ("", None): max_session_minutes = None
    elif not 1 <= int(max_session_minutes) <= 1440: raise ValueError("Max session must be between 1 and 1440 minutes")
    with storage.connect() as c:
        old = c.execute("SELECT name,days,start,end FROM schedules WHERE id=?", (schedule_id,)).fetchone()
        if not old: raise ValueError("Schedule not found")
        try:
            c.execute("""UPDATE schedules SET name=?,applies_group=?,days=?,start=?,end=?,max_session_minutes=?,enabled=?,note=? WHERE id=?""",
                      (name, applies_group or None, days, start, end, max_session_minutes, int(bool(enabled)), note.strip(), schedule_id))
        except sqlite3.IntegrityError: raise ValueError(f"A schedule named '{name}' already exists")
        audit.record(c, actor.username, "schedule_updated", name, old=f"{old['days']} {old['start']}-{old['end']}", new=f"{days} {start}-{end}")

def delete_schedule(actor, schedule_id):
    require(actor, "network.configure")
    with storage.connect() as c:
        r = c.execute("SELECT name FROM schedules WHERE id=?", (schedule_id,)).fetchone()
        if not r: raise ValueError("Schedule not found")
        c.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        audit.record(c, actor.username, "schedule_deleted", r["name"])
