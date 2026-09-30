"""DHCP scopes and reservations (managed configuration) + observed addresses from discovery (NOT real leases)."""
import ipaddress, sqlite3
from landar import storage
from landar.providers.lan_scan import normalize_mac
from landar.services import audit
from landar.services.guard import require

def _net(c, network_id):
    r = c.execute("SELECT * FROM networks WHERE id=?", (network_id,)).fetchone()
    if not r: raise ValueError("Choose a network first")
    return r, ipaddress.ip_network(r["cidr"])

def _ip(text, what):
    try: return ipaddress.IPv4Address((text or "").strip())
    except ValueError: raise ValueError(f"{what} is not a valid IPv4 address")

def _usable(net, ip, gateway, what):
    if ip not in net or ip in (net.network_address, net.broadcast_address): raise ValueError(f"{what} must be a usable address inside {net}")
    if gateway and str(ip) == gateway: raise ValueError(f"{what} is the gateway address ({gateway})")

def set_scope(actor, network_id, start, end, lease_hours=12, dns_servers="", enabled=True):
    require(actor, "network.configure")
    with storage.connect() as c:
        n, net = _net(c, network_id); a, b = _ip(start, "Range start"), _ip(end, "Range end")
        _usable(net, a, None, "Range start"); _usable(net, b, None, "Range end")
        if a > b: raise ValueError("Range start must not be after range end")
        if n["gateway"] and a <= ipaddress.IPv4Address(n["gateway"]) <= b: raise ValueError(f"Range includes the gateway ({n['gateway']})")
        if not 1 <= int(lease_hours) <= 720: raise ValueError("Lease time must be between 1 and 720 hours")
        dns = ", ".join(str(_ip(x, "DNS server")) for x in dns_servers.replace(";", ",").split(",") if x.strip())
        had = c.execute("SELECT 1 FROM dhcp_scopes WHERE network_id=?", (network_id,)).fetchone()
        c.execute("""INSERT INTO dhcp_scopes(network_id,range_start,range_end,lease_hours,dns_servers,enabled) VALUES(?,?,?,?,?,?)
                     ON CONFLICT(network_id) DO UPDATE SET range_start=excluded.range_start, range_end=excluded.range_end,
                     lease_hours=excluded.lease_hours, dns_servers=excluded.dns_servers, enabled=excluded.enabled""",
                  (network_id, str(a), str(b), int(lease_hours), dns, int(bool(enabled))))
        audit.record(c, actor.username, "dhcp_scope_updated" if had else "dhcp_scope_created", n["name"], new=f"{a}-{b}, {lease_hours}h")

def delete_scope(actor, scope_id):
    require(actor, "network.configure")
    with storage.connect() as c:
        r = c.execute("SELECT s.range_start,s.range_end,n.name FROM dhcp_scopes s JOIN networks n ON n.id=s.network_id WHERE s.id=?", (scope_id,)).fetchone()
        c.execute("DELETE FROM dhcp_scopes WHERE id=?", (scope_id,)); audit.record(c, actor.username, "dhcp_scope_deleted", r["name"], old=f"{r['range_start']}-{r['range_end']}")

def list_scopes(actor) -> list[dict]:
    require(actor, "network.view")
    with storage.connect() as c:
        online = [r[0] for r in c.execute("SELECT ip FROM devices WHERE online=1 AND ip IS NOT NULL AND ip != ''")]; out = []
        for r in c.execute("""SELECT s.*, n.name AS network, n.vlan_id, (SELECT COUNT(*) FROM dhcp_reservations x WHERE x.network_id=n.id) AS reservations
                              FROM dhcp_scopes s JOIN networks n ON n.id=s.network_id ORDER BY n.id"""):
            a, b = ipaddress.IPv4Address(r["range_start"]), ipaddress.IPv4Address(r["range_end"]); size = int(b) - int(a) + 1
            used = sum(1 for ip in online if _valid(ip) and a <= ipaddress.ip_address(ip) <= b)
            d = dict(r); d.update(pool=size, observed=used, utilization=f"{round(100 * used / size)}%", status="Enabled" if r["enabled"] else "Disabled"); out.append(d)
        return out

def _valid(ip):
    try: ipaddress.ip_address(ip); return True
    except ValueError: return False

def add_reservation(actor, network_id, mac, ip, hostname="", description="") -> list[str]:
    """Returns warnings (e.g. the IP is currently used by another device)."""
    require(actor, "network.configure")
    m = normalize_mac(mac or "")
    if not m: raise ValueError("MAC must look like AA:BB:CC:DD:EE:FF")
    with storage.connect() as c:
        n, net = _net(c, network_id); addr = _ip(ip, "IP address"); _usable(net, addr, n["gateway"], "IP address")
        try: c.execute("INSERT INTO dhcp_reservations(network_id,mac,ip,hostname,description) VALUES(?,?,?,?,?)", (network_id, m, str(addr), hostname.strip(), description.strip()))
        except sqlite3.IntegrityError: raise ValueError("That MAC or IP already has a reservation")
        audit.record(c, actor.username, "dhcp_reservation_added", m, new=str(addr))
        other = c.execute("SELECT mac FROM devices WHERE ip=? AND online=1 AND mac!=?", (str(addr), m)).fetchone()
        return [f"{addr} is currently in use by {other['mac']}. The reservation will conflict until that device gets another address."] if other else []

def delete_reservation(actor, res_id):
    require(actor, "network.configure")
    with storage.connect() as c:
        r = c.execute("SELECT mac,ip FROM dhcp_reservations WHERE id=?", (res_id,)).fetchone()
        c.execute("DELETE FROM dhcp_reservations WHERE id=?", (res_id,)); audit.record(c, actor.username, "dhcp_reservation_deleted", r["mac"], old=r["ip"])

def list_reservations(actor) -> list[dict]:
    require(actor, "network.view")
    with storage.connect() as c:
        out = []
        for r in c.execute("SELECT x.*, n.name AS network FROM dhcp_reservations x JOIN networks n ON n.id=x.network_id ORDER BY x.network_id, x.ip"):
            holder = c.execute("SELECT mac FROM devices WHERE ip=? AND online=1", (r["ip"],)).fetchone()
            d = dict(r); d["status"] = "Idle" if not holder else ("In use" if holder["mac"] == r["mac"] else "Conflict"); out.append(d)
        return out

def observed(actor) -> list[dict]:
    """Addresses seen by discovery. These are NOT DHCP leases; LANDAR cannot read a router's lease table yet."""
    require(actor, "network.view")
    with storage.connect() as c:
        nets = [(r["name"], ipaddress.ip_network(r["cidr"])) for r in c.execute("SELECT name,cidr FROM networks")]
        scopes = [(ipaddress.IPv4Address(r["range_start"]), ipaddress.IPv4Address(r["range_end"])) for r in c.execute("SELECT * FROM dhcp_scopes WHERE enabled=1")]
        reserved = {(r["mac"], r["ip"]) for r in c.execute("SELECT mac,ip FROM dhcp_reservations")}; out = []
        for d in c.execute("SELECT id,hostname,ip,mac,online FROM devices WHERE ip IS NOT NULL AND ip != '' ORDER BY id"):
            if not _valid(d["ip"]): continue
            a = ipaddress.ip_address(d["ip"]); net = next((n for n, x in nets if a in x), "— (no network defined)")
            kind = "Reserved" if any(d["ip"] == ip for _, ip in reserved) else ("In DHCP pool" if any(s <= a <= e for s, e in scopes) else "Outside pool")
            out.append({"id": d["id"], "hostname": d["hostname"], "ip": d["ip"], "mac": d["mac"], "network": net, "kind": kind, "presence": "Online" if d["online"] else "Offline"})
        return out
