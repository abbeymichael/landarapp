import os, tempfile, unittest
os.environ["LANDAR_HOME"] = tempfile.mkdtemp(); os.environ["LANDAR_DB"] = os.path.join(os.environ["LANDAR_HOME"], "t.db")
from landar import storage
from landar.core.permissions import PermissionDenied
from landar.services import audit, auth, devices, discovery, users
from landar.providers import lan_scan
from landar.providers.base import NetworkProvider

storage.init(); ADMIN_PW = auth.bootstrap_admin()   # one shared DB for all tests

class Phase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = ADMIN_PW; cls.admin = auth.login("admin", cls.pw)

    def test_login_and_bad_login(self):
        self.assertEqual(self.admin.role, "Super Administrator"); self.assertIsNone(auth.login("admin", "wrong"))
    def test_rbac_denies_and_audits(self):
        users.create_user(self.admin, "ro", "Read Only", "", "Guests", "Read Only", "longpassword1")
        ro = auth.login("ro", "longpassword1")
        with self.assertRaises(PermissionDenied): users.create_user(ro, "x", "x", "", "Guests", "Read Only", "longpassword1")
        self.assertTrue(any(r["result"] == "denied" for r in audit.list_entries(self.admin)))
    def test_device_flow_and_audit_has_no_secrets(self):
        devices.register(self.admin, "aa-bb-cc-dd-ee-ff", "pc1"); did = devices.list_devices(self.admin)[0]["id"]
        devices.set_state(self.admin, did, "Blocked")
        self.assertEqual(devices.list_devices(self.admin)[0]["state"], "Blocked")
        self.assertNotIn(self.pw, str([tuple(r) for r in audit.list_entries(self.admin)]))
    def test_validation(self):
        with self.assertRaises(ValueError): users.create_user(self.admin, "s", "S", "", "Guests", "Read Only", "short")
        with self.assertRaises(ValueError): users.set_status(self.admin, 1, "Disabled")   # self-lockout blocked

class FakeProvider(NetworkProvider):
    name = "fake"
    def __init__(self, devs): self.devs = devs
    def discover_devices(self): return self.devs
    def network_info(self): return {"cidr": "10.0.0.0/24", "interface": "wlan0", "ip": "10.0.0.2"}

class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from landar.core.permissions import Actor
        cls.admin = Actor("admin", "Super Administrator")
    def test_scan_upserts_and_marks_offline(self):
        a, b = {"mac": "AA:00:00:00:00:01", "ip": "10.0.0.5", "hostname": "x"}, {"mac": "AA:00:00:00:00:02", "ip": "10.0.0.6"}
        r = discovery.scan(self.admin, FakeProvider([a, b])); self.assertEqual((r["found"], r["new"]), (2, 2))
        r = discovery.scan(self.admin, FakeProvider([a])); self.assertEqual((r["found"], r["new"]), (1, 0))
        rows = {d["mac"]: d for d in devices.list_devices(self.admin)}
        self.assertEqual(rows["AA:00:00:00:00:01"]["presence"], "Online"); self.assertEqual(rows["AA:00:00:00:00:02"]["presence"], "Offline")
        self.assertEqual(rows["AA:00:00:00:00:02"]["state"], "Unknown")     # never auto-approved
    def test_scan_requires_permission(self):
        from landar.core.permissions import Actor
        with self.assertRaises(PermissionDenied): discovery.scan(Actor("x", "Read Only"), FakeProvider([]))
    def test_parsers(self):
        win = "  192.168.1.1           aa-bb-cc-dd-ee-ff     dynamic\n  192.168.1.255         ff-ff-ff-ff-ff-ff     static"
        mac = "? (192.168.1.7) at 0:1a:2b:3c:4d:5e on en0 ifscope [ethernet]\n? (224.0.0.251) at 1:0:5e:0:0:fb on en0"
        proc = "IP address HW type Flags HW address Mask Device\n192.168.1.9 0x1 0x2 aa:bb:cc:dd:ee:09 * wlan0\n192.168.1.10 0x1 0x0 00:00:00:00:00:00 * wlan0"
        self.assertEqual(lan_scan.parse_arp_a(win), [("192.168.1.1", "AA:BB:CC:DD:EE:FF")])
        self.assertEqual(lan_scan.parse_arp_a(mac), [("192.168.1.7", "00:1A:2B:3C:4D:5E")])
        self.assertEqual(lan_scan.parse_proc_arp(proc), [("192.168.1.9", "AA:BB:CC:DD:EE:09")])

if __name__ == "__main__": unittest.main()
