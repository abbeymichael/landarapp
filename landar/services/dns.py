"""DNS: local records, upstream forwarders, and live resolver tests (read-only probes)."""
import ipaddress, re, socket, sqlite3, time
from landar import storage
from landar.core import dnswire
from landar.services import audit
from landar.services.guard import require

_HOST = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")

def list_records(actor):
    require(actor, "network.view")
    with storage.connect() as c: return c.execute("SELECT id,name,ip,note FROM dns_records ORDER BY name").fetchall()

def add_record(actor, name, ip, note=""):
    require(actor, "network.configure"); name = (name or "").strip().lower()
    if not _HOST.match(name): raise ValueError("Enter a valid host name, e.g. printer.school.lan")
    try: addr = ipaddress.IPv4Address((ip or "").strip())
    except ValueError: raise ValueError("IP address is not a valid IPv4 address")
    with storage.connect() as c:
        try: c.execute("INSERT INTO dns_records(name,ip,note) VALUES(?,?,?)", (name, str(addr), note.strip()))
        except sqlite3.IntegrityError: raise ValueError(f"A record for {name} already exists")
        audit.record(c, actor.username, "dns_record_added", name, new=str(addr))

def delete_record(actor, rec_id):
    require(actor, "network.configure")
    with storage.connect() as c:
        r = c.execute("SELECT name,ip FROM dns_records WHERE id=?", (rec_id,)).fetchone()
        c.execute("DELETE FROM dns_records WHERE id=?", (rec_id,)); audit.record(c, actor.username, "dns_record_deleted", r["name"], old=r["ip"])

def list_forwarders(actor):
    require(actor, "network.view")
    with storage.connect() as c: return c.execute("SELECT id,address,label FROM dns_forwarders ORDER BY id").fetchall()

def add_forwarder(actor, address, label=""):
    require(actor, "network.configure")
    try: addr = ipaddress.ip_address((address or "").strip())
    except ValueError: raise ValueError("Forwarder must be an IP address, e.g. 1.1.1.1")
    with storage.connect() as c:
        try: c.execute("INSERT INTO dns_forwarders(address,label) VALUES(?,?)", (str(addr), label.strip()))
        except sqlite3.IntegrityError: raise ValueError(f"{addr} is already listed")
        audit.record(c, actor.username, "dns_forwarder_added", str(addr))

def delete_forwarder(actor, fid):
    require(actor, "network.configure")
    with storage.connect() as c:
        r = c.execute("SELECT address FROM dns_forwarders WHERE id=?", (fid,)).fetchone()
        c.execute("DELETE FROM dns_forwarders WHERE id=?", (fid,)); audit.record(c, actor.username, "dns_forwarder_deleted", r["address"])

def lookup(actor, name, server=None, timeout=2.5) -> dict:
    """Resolve `name` with the system resolver (server=None) or a specific DNS server. Blocking: run in a worker thread."""
    require(actor, "network.view"); name = (name or "").strip()
    if not _HOST.match(name): return {"ok": False, "error": "Enter a valid host name", "ms": None, "answers": []}
    t0 = time.perf_counter()
    try:
        if server is None: ips = sorted({i[4][0] for i in socket.getaddrinfo(name, None, socket.AF_INET)}); rcode = 0
        else: rcode, ips = dnswire.query(server, name, timeout)
    except socket.timeout: return {"ok": False, "error": "Timed out", "ms": None, "answers": []}
    except socket.gaierror: return {"ok": False, "error": "Name not found", "ms": round((time.perf_counter() - t0) * 1000), "answers": []}
    except (OSError, ValueError) as e: return {"ok": False, "error": f"Failed ({e})", "ms": None, "answers": []}
    ms = round((time.perf_counter() - t0) * 1000)
    if rcode == 3: return {"ok": False, "error": "Name not found (NXDOMAIN)", "ms": ms, "answers": []}
    return {"ok": bool(ips) and rcode == 0, "error": None if ips else f"No A records (rcode {rcode})", "ms": ms, "answers": ips}
