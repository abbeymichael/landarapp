"""Builds the topology graph (pure data, no UI) from discovery results. Layout/drawing live in the UI layer.
Honest model: without LLDP/SNMP we only know the gateway and the hosts on the segment, so the map is gateway -> segment -> hosts."""
from landar import storage
from landar.services import discovery
from landar.services.guard import require

FILTERS = ("All", "Online only", "Unknown", "Approved", "Blocked")

def _ipkey(ip): 
    try: return tuple(int(x) for x in ip.split("."))
    except Exception: return (999,)

def build(actor, provider=None, state_filter="All") -> dict:
    require(actor, "network.view"); require(actor, "devices.view")
    info = discovery.network_info(actor, provider)
    gw_ip = info.get("gateway"); self_mac = info.get("mac")
    with storage.connect() as c:
        rows = [dict(r) for r in c.execute("""SELECT id,hostname,ip,mac,vendor,device_type,state,online,first_seen,last_seen,randomized_mac FROM devices""")]
    rows.sort(key=lambda r: _ipkey(r["ip"] or ""))
    by_state = {}
    for r in rows: by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    nodes = [{"id": "internet", "kind": "internet", "label": "Internet", "sub": f"via {gw_ip}" if gw_ip else "uplink unknown"}]
    edges, gw_row = [], next((r for r in rows if gw_ip and r["ip"] == gw_ip), None)
    top = "internet"
    if gw_ip:
        g = {"id": "gateway", "kind": "gateway", "label": (gw_row or {}).get("hostname") or "Default gateway", "sub": gw_ip, "ip": gw_ip}
        if gw_row: g.update({k: gw_row[k] for k in gw_row if k not in ("ip", "id")}); g["device_id"] = gw_row["id"]; g["label"] = gw_row["hostname"] or "Default gateway"
        nodes.append(g); edges.append(("internet", "gateway")); top = "gateway"
    visible = [r for r in rows if r is not gw_row and (state_filter in ("All", None) or (state_filter == "Online only" and r["online"]) or r["state"] == state_filter)]
    nodes.append({"id": "segment", "kind": "segment", "label": info.get("cidr", "LAN segment"), "sub": f"{sum(1 for r in rows if r['online'])} online / {len(rows)} known",
                  "interface": info.get("interface"), "ip": info.get("ip"), "error": info.get("error")}); edges.append((top, "segment"))
    for r in visible:
        nodes.append({**r, "id": f"dev{r['id']}", "kind": "device", "device_id": r["id"], "label": r["hostname"] or r["ip"] or r["mac"], "sub": r["ip"] or "no IP",
                      "is_self": bool(self_mac and r["mac"] == self_mac)}); edges.append(("segment", f"dev{r['id']}"))
    return {"network": info, "nodes": nodes, "edges": edges, "counts": {"online": sum(1 for r in rows if r["online"]), "total": len(rows), "by_state": by_state}}
