import sqlite3
from landar import storage
from landar.services import audit
from landar.services.guard import require

def list_devices(actor):
    require(actor, "devices.view")
    with storage.connect() as c:
        return c.execute("""SELECT d.id,d.hostname,d.ip,d.mac,d.vendor,d.device_type,u.username AS owner,d.state,
                                   CASE d.online WHEN 1 THEN 'Online' ELSE 'Offline' END AS presence,d.last_seen
                            FROM devices d LEFT JOIN users u ON u.id=d.owner_id ORDER BY d.id""").fetchall()

def register(actor, mac, hostname="", ip="", device_type="Unknown"):
    require(actor, "devices.manage")
    mac = mac.strip().upper().replace("-", ":")
    if len(mac.split(":")) != 6: raise ValueError("MAC must look like AA:BB:CC:DD:EE:FF")
    with storage.connect() as c:
        try: c.execute("INSERT INTO devices(hostname,ip,mac,device_type,first_seen,last_seen) VALUES(?,?,?,?,?,?)",
                       (hostname, ip, mac, device_type, audit.now(), audit.now()))
        except sqlite3.IntegrityError: raise ValueError(f"Device {mac} is already registered")
        audit.record(c, actor.username, "device_registered", mac, new="state=Unknown")

def set_state(actor, device_id, state):
    require(actor, "devices.manage")
    with storage.connect() as c:
        d = c.execute("SELECT mac,state FROM devices WHERE id=?", (device_id,)).fetchone()
        c.execute("UPDATE devices SET state=? WHERE id=?", (state, device_id))
        audit.record(c, actor.username, f"device_{state.lower()}", d["mac"], old=d["state"], new=state)

def set_type(actor, device_id, device_type):
    require(actor, "devices.manage")
    from landar.core.constants import DEVICE_TYPES
    if device_type not in DEVICE_TYPES: raise ValueError("Unknown device type")
    with storage.connect() as c:
        d = c.execute("SELECT mac,device_type FROM devices WHERE id=?", (device_id,)).fetchone()
        c.execute("UPDATE devices SET device_type=? WHERE id=?", (device_type, device_id))
        audit.record(c, actor.username, "device_type_changed", d["mac"], old=d["device_type"], new=device_type)
