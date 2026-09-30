from landar import storage
from landar.providers.registry import NETWORK_PROVIDERS
from landar.services import audit
from landar.services.guard import require

def _provider(provider=None):
    p = provider or (NETWORK_PROVIDERS[0] if NETWORK_PROVIDERS else None)
    if not p: raise ValueError("No network provider is configured")
    return p

def network_info(actor, provider=None) -> dict:
    require(actor, "network.view")
    try: return _provider(provider).network_info()
    except (RuntimeError, ValueError) as e: return {"error": str(e)}

def scan(actor, provider=None) -> dict:
    """Discover devices and upsert them into the inventory. New MACs enter as 'Unknown' (never auto-approved)."""
    require(actor, "network.scan")
    p = _provider(provider)
    try: found = p.discover_devices()
    except RuntimeError as e: raise ValueError(str(e))
    ts, new = audit.now(), 0
    with storage.connect() as c:
        c.execute("UPDATE devices SET online=0")
        for d in found:
            row = c.execute("SELECT id FROM devices WHERE mac=?", (d["mac"],)).fetchone()
            if row:
                c.execute("""UPDATE devices SET ip=?, hostname=COALESCE(NULLIF(?,''),hostname), vendor=COALESCE(?,vendor),
                             randomized_mac=?, online=1, last_seen=? WHERE id=?""",
                          (d["ip"], d.get("hostname", ""), d.get("vendor"), int(d.get("randomized", False)), ts, row["id"]))
            else:
                c.execute("""INSERT INTO devices(hostname,ip,mac,vendor,randomized_mac,online,state,first_seen,last_seen)
                             VALUES(?,?,?,?,?,1,'Unknown',?,?)""",
                          (d.get("hostname", ""), d["ip"], d["mac"], d.get("vendor"), int(d.get("randomized", False)), ts, ts))
                audit.record(c, actor.username, "device_discovered", d["mac"], new=f"ip={d['ip']}", source=p.name); new += 1
        audit.record(c, actor.username, "network_scan", p.name, new=f"found={len(found)}, new={new}")
    return {"found": len(found), "new": new}
