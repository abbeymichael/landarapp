"""Networks & VLANs: the source of truth for segments. Records intent; nothing is pushed to switches yet."""
import ipaddress
from landar import storage
from landar.services import audit, discovery
from landar.services.guard import require

PURPOSES = ("Administration", "Teachers", "Students", "Guests", "IoT", "Management", "Servers", "Other")
TEMPLATES = {"school": [(10, "Administration", "Administration"), (20, "Teachers", "Teachers"), (30, "Students", "Students"),
                        (40, "Guests", "Guests"), (50, "IoT", "IoT"), (99, "Network Management", "Management")]}

def parse_net(cidr: str) -> ipaddress.IPv4Network:
    try: n = ipaddress.ip_network((cidr or "").strip(), strict=False)
    except ValueError: raise ValueError("Subnet must look like 192.168.10.0/24")
    if n.version != 4 or not 8 <= n.prefixlen <= 30: raise ValueError("Subnet must be IPv4 with a prefix between /8 and /30")
    return n

def _validate(c, name, vlan_id, cidr, gateway, exclude_id=None):
    name = (name or "").strip()
    if not name: raise ValueError("Name is required")
    if vlan_id is not None and not 1 <= int(vlan_id) <= 4094: raise ValueError("VLAN ID must be between 1 and 4094")
    net = parse_net(cidr); gw = None
    if gateway and gateway.strip():
        try: gw = ipaddress.ip_address(gateway.strip())
        except ValueError: raise ValueError("Gateway is not a valid IP address")
        if gw not in net or gw in (net.network_address, net.broadcast_address): raise ValueError(f"Gateway must be a usable address inside {net}")
    for o in c.execute("SELECT id,name,vlan_id,cidr FROM networks WHERE id IS NOT ?", (exclude_id,)):
        if o["name"].lower() == name.lower(): raise ValueError(f"A network named '{o['name']}' already exists")
        if vlan_id is not None and o["vlan_id"] == int(vlan_id): raise ValueError(f"VLAN {vlan_id} is already used by '{o['name']}'")
        if net.overlaps(ipaddress.ip_network(o["cidr"])): raise ValueError(f"{net} overlaps '{o['name']}' ({o['cidr']})")
    return name, (int(vlan_id) if vlan_id is not None else None), str(net), (str(gw) if gw else None)

def list_networks(actor) -> list[dict]:
    require(actor, "network.view")
    with storage.connect() as c:
        ips = [r[0] for r in c.execute("SELECT ip FROM devices WHERE ip IS NOT NULL AND ip != ''")]
        out = []
        for r in c.execute("""SELECT n.*, s.enabled AS scope_enabled FROM networks n LEFT JOIN dhcp_scopes s ON s.network_id=n.id ORDER BY COALESCE(n.vlan_id, 9999), n.id"""):
            net = ipaddress.ip_network(r["cidr"]); d = dict(r)
            d["devices"] = sum(1 for ip in ips if _in(ip, net)); d["dhcp"] = "—" if r["scope_enabled"] is None else ("Enabled" if r["scope_enabled"] else "Disabled"); out.append(d)
        return out

def _in(ip, net):
    try: return ipaddress.ip_address(ip) in net
    except ValueError: return False

def create_network(actor, name, vlan_id, cidr, gateway="", purpose="Other", description="") -> int:
    require(actor, "network.configure")
    with storage.connect() as c:
        name, vlan_id, cidr, gateway = _validate(c, name, vlan_id, cidr, gateway)
        cur = c.execute("INSERT INTO networks(name,vlan_id,cidr,gateway,purpose,description,created_at) VALUES(?,?,?,?,?,?,?)",
                        (name, vlan_id, cidr, gateway, purpose if purpose in PURPOSES else "Other", description, audit.now()))
        audit.record(c, actor.username, "network_created", name, new=f"vlan={vlan_id}, {cidr}"); return cur.lastrowid

def update_network(actor, network_id, name, vlan_id, cidr, gateway="", purpose="Other", description=""):
    require(actor, "network.configure")
    with storage.connect() as c:
        old = c.execute("SELECT * FROM networks WHERE id=?", (network_id,)).fetchone()
        name, vlan_id, cidr, gateway = _validate(c, name, vlan_id, cidr, gateway, exclude_id=network_id)
        c.execute("UPDATE networks SET name=?,vlan_id=?,cidr=?,gateway=?,purpose=?,description=? WHERE id=?",
                  (name, vlan_id, cidr, gateway, purpose if purpose in PURPOSES else "Other", description, network_id))
        audit.record(c, actor.username, "network_updated", name, old=f"vlan={old['vlan_id']}, {old['cidr']}", new=f"vlan={vlan_id}, {cidr}")

def delete_network(actor, network_id):
    require(actor, "network.configure")
    with storage.connect() as c:
        old = c.execute("SELECT name,cidr FROM networks WHERE id=?", (network_id,)).fetchone()
        c.execute("DELETE FROM networks WHERE id=?", (network_id,))            # cascades scopes + reservations
        audit.record(c, actor.username, "network_deleted", old["name"], old=old["cidr"])

def import_detected(actor, provider=None) -> int:
    """Create a network from the subnet this computer is connected to (found by discovery)."""
    require(actor, "network.configure")
    info = discovery.network_info(actor, provider)
    if "error" in info: raise ValueError(info["error"])
    gw = info.get("gateway") if info.get("gateway") and _in(info["gateway"], ipaddress.ip_network(info["cidr"])) else ""
    return create_network(actor, "Local network", None, info["cidr"], gw, "Other", f"Detected on {info.get('interface', 'this host')}")

def load_template(actor, key="school") -> int:
    """Adds the standard VLAN plan (10.0.<vlan>.0/24). Skips entries that already exist. Returns how many were added."""
    require(actor, "network.configure"); added = 0
    for vlan, name, purpose in TEMPLATES[key]:
        try: create_network(actor, name, vlan, f"10.0.{vlan}.0/24", f"10.0.{vlan}.1", purpose, f"From {key} template"); added += 1
        except ValueError: pass
    return added
