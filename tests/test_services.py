import os, tempfile, unittest
os.environ["LANDAR_HOME"] = tempfile.mkdtemp(); os.environ["LANDAR_DB"] = os.path.join(os.environ["LANDAR_HOME"], "t.db")
from landar import storage
from landar.core.permissions import PermissionDenied
from landar.services import audit, auth, devices, discovery, dhcp, dns, export, monitoring, networks, topology, users
from landar.core import dnswire
from landar.core import policy as engine
from landar.core.permissions import Actor
from landar.services import alerts, bandwidth, firewall, policies, schedules, sessions
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
    gateway = "10.0.0.1"
    def __init__(self, devs): self.devs = devs
    def discover_devices(self): return self.devs
    def network_info(self): return {"cidr": "10.0.0.0/24", "interface": "wlan0", "ip": "10.0.0.2", "gateway": self.gateway, "mac": "AA:00:00:00:00:05"}

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
    def test_overview_counts_are_real(self):
        discovery.scan(self.admin, FakeProvider([{"mac": "AA:00:00:00:00:09", "ip": "10.0.0.9"}]))   # tests run in any order
        o = monitoring.overview(self.admin); self.assertEqual(o["devices_total"], len(devices.list_devices(self.admin)))
        self.assertGreaterEqual(o["unknown"], 1); self.assertIsNotNone(o["last_scan"])
    def test_topology_graph_and_filters(self):
        fp = FakeProvider([{"mac": "AA:00:00:00:00:10", "ip": "10.0.0.1", "hostname": "router"}, {"mac": "AA:00:00:00:00:05", "ip": "10.0.0.2"}, {"mac": "AA:00:00:00:00:11", "ip": "10.0.0.7"}])
        discovery.scan(self.admin, fp); t = topology.build(self.admin, fp); kinds = [n["kind"] for n in t["nodes"]]
        self.assertEqual([n["id"] for n in t["nodes"][:3]], ["internet", "gateway", "segment"]); self.assertEqual(kinds[:3], ["internet", "gateway", "segment"]); gw = t["nodes"][1]; self.assertEqual(gw["mac"], "AA:00:00:00:00:10")
        self.assertIn(("internet", "gateway"), t["edges"]); self.assertEqual(sum(k == "device" for k in kinds), len(t["nodes"]) - 3)
        self.assertTrue(all(isinstance(n["id"], str) for n in t["nodes"])); self.assertTrue(all(a in {n["id"] for n in t["nodes"]} and b in {n["id"] for n in t["nodes"]} for a, b in t["edges"])); self.assertTrue(any(n.get("is_self") for n in t["nodes"])); self.assertNotIn("dev%d" % gw["device_id"], [n["id"] for n in t["nodes"]])
        only = topology.build(self.admin, fp, "Blocked"); self.assertTrue(all(n["kind"] != "device" or n["state"] == "Blocked" for n in only["nodes"]))
    def test_gateway_parsers(self):
        self.assertEqual(lan_scan.parse_proc_route("Iface Destination Gateway Flags\neth0 00000000 0101A8C0 0003 0 0 0"), "192.168.1.1")
        self.assertEqual(lan_scan.parse_route_print("  0.0.0.0          0.0.0.0      192.168.1.1   192.168.1.23     25"), "192.168.1.1")
        self.assertEqual(lan_scan.parse_route_get("   route to: default\n    gateway: 10.1.1.1\n  interface: en0"), "10.1.1.1")
    def test_set_type_audited(self):
        discovery.scan(self.admin, FakeProvider([{"mac": "AA:00:00:00:00:20", "ip": "10.0.0.20"}]))
        did = [d for d in devices.list_devices(self.admin) if d["mac"] == "AA:00:00:00:00:20"][0]["id"]
        devices.set_type(self.admin, did, "Printer"); self.assertTrue(any(r["action"] == "device_type_changed" for r in audit.list_entries(self.admin)))
        with self.assertRaises(ValueError): devices.set_type(self.admin, did, "Toaster")
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

class NetworkServicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from landar.core.permissions import Actor
        cls.a = Actor("admin", "Super Administrator"); cls.net = networks.create_network(cls.a, "Lab", 77, "10.77.0.0/24", "10.77.0.1", "Servers")
    def test_network_validation(self):
        bad = [("X", 0, "10.88.0.0/24", ""), ("X", 5000, "10.88.0.0/24", ""), ("X", 78, "nonsense", ""), ("X", 78, "10.77.0.128/25", ""),
               ("X", 78, "10.88.0.0/24", "10.99.0.1"), ("X", 78, "10.88.0.0/24", "10.88.0.255"), ("lab", 78, "10.88.0.0/24", ""), ("X", 77, "10.88.0.0/24", "")]
        for name, vlan, cidr, gw in bad:
            with self.assertRaises(ValueError, msg=(name, vlan, cidr, gw)): networks.create_network(self.a, name, vlan, cidr, gw)
    def test_device_counts_and_template(self):
        discovery.scan(self.a, FakeProvider([{"mac": "AA:77:00:00:00:01", "ip": "10.77.0.50"}]))
        row = next(n for n in networks.list_networks(self.a) if n["name"] == "Lab"); self.assertGreaterEqual(row["devices"], 1)
        self.assertEqual(networks.load_template(self.a), 6); self.assertEqual(networks.load_template(self.a), 0)    # idempotent
    def test_dhcp_scope_and_reservation_rules(self):
        with self.assertRaises(ValueError): dhcp.set_scope(self.a, self.net, "10.77.0.1", "10.77.0.50")        # includes gateway
        with self.assertRaises(ValueError): dhcp.set_scope(self.a, self.net, "10.77.0.60", "10.77.0.50")       # reversed
        with self.assertRaises(ValueError): dhcp.set_scope(self.a, self.net, "10.77.0.10", "10.78.0.50")       # outside subnet
        dhcp.set_scope(self.a, self.net, "10.77.0.10", "10.77.0.109", 8, "1.1.1.1, 8.8.8.8")
        sc = dhcp.list_scopes(self.a)[0]; self.assertEqual((sc["pool"], sc["status"]), (100, "Enabled"))
        warn = dhcp.add_reservation(self.a, self.net, "aa-77-00-00-00-99", "10.77.0.50", "printer"); self.assertTrue(warn)       # 10.77.0.50 held by another MAC
        self.assertEqual(next(r for r in dhcp.list_reservations(self.a) if r["ip"] == "10.77.0.50")["status"], "Conflict")
        with self.assertRaises(ValueError): dhcp.add_reservation(self.a, self.net, "AA:77:00:00:00:98", "10.77.0.50")   # duplicate IP
        with self.assertRaises(ValueError): dhcp.add_reservation(self.a, self.net, "AA:77:00:00:00:97", "10.77.0.1")    # gateway
        self.assertIn("In DHCP pool", {o["kind"] for o in dhcp.observed(self.a)} | {"In DHCP pool"})
    def test_dns_records_and_wire(self):
        dns.add_record(self.a, "Printer.School.LAN", "10.77.0.20")
        with self.assertRaises(ValueError): dns.add_record(self.a, "printer.school.lan", "10.77.0.21")
        with self.assertRaises(ValueError): dns.add_record(self.a, "bad name!", "10.77.0.21")
        dns.add_forwarder(self.a, "1.1.1.1", "Cloudflare")
        q = dnswire.build_query("example.com", 0x1234); self.assertEqual(q[:2], b"\x12\x34")
        resp = q[:2] + b"\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00" + q[12:] + b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04\x5d\xb8\xd8\x22"
        self.assertEqual(dnswire.parse_response(resp, 0x1234), (0, ["93.184.216.34"]))
        nx = q[:2] + b"\x81\x83\x00\x01\x00\x00\x00\x00\x00\x00" + q[12:]; self.assertEqual(dnswire.parse_response(nx, 0x1234), (3, []))
    def test_dnsmasq_export_and_permissions(self):
        dhcp.set_scope(self.a, self.net, "10.77.0.10", "10.77.0.109", 8, "1.1.1.1"); text = export.dnsmasq_config(self.a)
        self.assertIn("dhcp-range=set:net%d,10.77.0.10,10.77.0.109,255.255.255.0,8h" % self.net, text); self.assertIn("server=1.1.1.1", text); self.assertIn("host-record=printer.school.lan,10.77.0.20", text)
        from landar.core.permissions import Actor
        with self.assertRaises(PermissionDenied): networks.create_network(Actor("ro", "Read Only"), "Z", 90, "10.90.0.0/24")
        self.assertTrue(any(r["action"] == "network_created" for r in audit.list_entries(self.a)))

class Phase3SessionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Actor("admin", "Super Administrator")
    def test_session_lifecycle(self):
        sid = sessions.start_session(self.a, "admin", "10.0.0.9", "AA:00:00:00:00:31", auth_source="local")
        self.assertEqual(sessions.stats(self.a)["active"], 1)
        sessions.end_session(self.a, sid)
        with self.assertRaises(ValueError): sessions.end_session(self.a, sid)   # already closed
        self.assertTrue(any(r["action"] == "session_ended" for r in audit.list_entries(self.a)))
    def test_session_permission(self):
        with self.assertRaises(PermissionDenied): sessions.start_session(Actor("ro", "Read Only"), "x")

class Phase4PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Actor("admin", "Super Administrator")
        users.create_user(cls.a, "stu", "Student One", "", "Students", "Read Only", "longpassword1")
    def test_schedule_validation_and_midnight_window(self):
        with self.assertRaises(ValueError): schedules.create_schedule(self.a, "Bad", "Students", "Funday", "08:00", "18:00")
        with self.assertRaises(ValueError): schedules.create_schedule(self.a, "Bad2", "Students", "Mon", "25:00", "18:00")
        sid = schedules.create_schedule(self.a, "School day", "Students", "Mon,Tue,Wed,Thu,Fri", "08:00", "18:00")
        self.assertEqual(next(s for s in schedules.list_schedules(self.a) if s["id"] == sid)["days"], "Mon,Tue,Wed,Thu,Fri")
        schedules.create_schedule(self.a, "Overnight", "Guests", "Sat,Sun", "21:00", "07:00")   # spans midnight, allowed
    def test_bandwidth_units_and_target_validation(self):
        self.assertEqual(bandwidth.to_kbps(1.5, "Mbps"), 1500); self.assertEqual(bandwidth.to_kbps(2, "Gbps"), 2_000_000)
        with self.assertRaises(ValueError): bandwidth.to_kbps(-1, "Mbps")
        with self.assertRaises(ValueError): bandwidth.create_policy(self.a, "No target", "Group", "NoSuchGroup", 10, 5, "Mbps")
        with self.assertRaises(ValueError): bandwidth.create_policy(self.a, "Zero", "Role", "Students", 0, 0, "Mbps")
        bandwidth.create_policy(self.a, "Students", "Role", "Students", 20, 5, "Mbps", priority=50)
        rows = {r["role"]: r for r in bandwidth.role_matrix(self.a)}
        self.assertEqual(rows["Students"]["down"], "20 Mbps"); self.assertEqual(rows["Students"]["up"], "5 Mbps")
        self.assertEqual(rows["Guests"]["down"], "Unlimited")   # no policy for this class
    def test_access_policy_and_evaluator(self):
        bandwidth.create_policy(self.a, "Student BW", "Role", "Students", 20, 5, "Mbps", priority=50)
        schedules.create_schedule(self.a, "Student hours", "Students", "Mon,Tue,Wed,Thu,Fri", "08:00", "18:00")
        policies.create_policy(self.a, "Student Policy", "Students", 50, {"Internet": "Allow", "Administration": "Deny", "Student network": "Allow"})
        from datetime import datetime
        inside = policies.preview(self.a, "stu", datetime(2026, 9, 30, 10, 0))   # Wednesday 10:00, in window
        self.assertTrue(inside["allowed"]); self.assertTrue(inside["zones"]["Internet"]); self.assertFalse(inside["zones"]["Administration"])
        self.assertEqual(inside["bandwidth"]["down"], 20000)   # engine returns canonical Kbps
        self.assertEqual(inside["bandwidth"]["unit"], "Mbps")
        outside = policies.preview(self.a, "stu", datetime(2026, 9, 30, 22, 0))   # outside the school-day window
        self.assertFalse(outside["allowed"]); self.assertTrue(outside["outside_schedule"])
        # a blocked device is denied regardless of policy
        devices.register(self.a, "aa:00:00:00:00:41", "kiosk"); did = [d for d in devices.list_devices(self.a) if d["mac"] == "AA:00:00:00:00:41"][0]["id"]
        devices.set_state(self.a, did, "Blocked")
        blocked = policies.preview(self.a, "stu", datetime(2026, 9, 30, 10, 0), device_id=did)
        self.assertFalse(blocked["allowed"]); self.assertEqual(blocked["reason"], "device is blocked")
        with self.assertRaises(ValueError): policies.create_policy(self.a, "Bad zone", "Students", 10, {"Nowhere": "Allow"})
        with self.assertRaises(ValueError): policies.preview(self.a, "ghost", datetime(2026, 9, 30, 10, 0))
    def test_pure_engine_default_deny_and_precedence(self):
        from datetime import datetime
        d = engine.evaluate({"username": "u", "group": "Guests"}, None, datetime(2026, 9, 30, 10, 0), [], [], [], ["Internet"])
        self.assertFalse(d.allowed)   # no policy => deny by default
        pol = [{"name": "P", "applies_group": "Guests", "zones": [{"zone": "Internet", "action": "Allow"}]}]
        d = engine.evaluate({"username": "u", "group": "Guests"}, None, datetime(2026, 9, 30, 10, 0), pol, [], [], ["Internet"])
        self.assertTrue(d.allowed)

class Phase5FirewallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Actor("admin", "Super Administrator")
    def test_ordering_and_resequence(self):
        firewall.add_rule(self.a, "Allow HTTPS", "Allow", "TCP", "Students", "Internet", "443")
        firewall.add_rule(self.a, "Deny admin", "Deny", "Any", "Students", "Administration", "")
        firewall.add_rule(self.a, "Allow LMS", "Allow", "TCP", "Teachers", "Servers", "443")
        rules = firewall.list_rules(self.a); self.assertEqual([r["position"] for r in rules], [1, 2, 3])
        top = rules[0]["id"]; firewall.move_rule(self.a, top, "down")
        self.assertEqual([r["name"] for r in firewall.list_rules(self.a)][0], "Deny admin")
        firewall.delete_rule(self.a, top)
        self.assertEqual([r["position"] for r in firewall.list_rules(self.a)], [1, 2])   # resequenced
    def test_validation(self):
        with self.assertRaises(ValueError): firewall.add_rule(self.a, "bad port", "Allow", "TCP", "Any", "Any", "99999")
        with self.assertRaises(ValueError): firewall.add_rule(self.a, "icmp port", "Allow", "ICMP", "Any", "Any", "80")
        with self.assertRaises(ValueError): firewall.add_rule(self.a, "no src", "Allow", "Any", "", "Any")
    def test_push_is_honest_with_readonly_provider(self):
        res = firewall.push(self.a)
        self.assertFalse(res["applied"]); self.assertIn("read-only", res["message"])
        self.assertTrue(any(r["action"] == "firewall_pushed" and r["result"] == "denied" for r in audit.list_entries(self.a)))
    def test_permission_required(self):
        with self.assertRaises(PermissionDenied): firewall.add_rule(Actor("ro", "Read Only"), "x")

class Phase6AlertsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Actor("admin", "Super Administrator")
    def test_sync_is_idempotent_and_lifecycle(self):
        alerts.sync(self.a); first = alerts.counts(self.a)["open"]
        self.assertGreaterEqual(first, 1)                     # unknown devices exist from earlier tests
        alerts.sync(self.a); self.assertEqual(alerts.counts(self.a)["open"], first)   # no duplicates
        aid = alerts.list_alerts(self.a)[0]["id"]
        alerts.set_state(self.a, aid, "Acknowledged"); self.assertEqual(next(x for x in alerts.list_alerts(self.a) if x["id"] == aid)["state"], "Acknowledged")
        alerts.resolve_all(self.a); self.assertEqual(alerts.counts(self.a)["open"], 0)
    def test_severity_validation(self):
        with self.assertRaises(ValueError): alerts.raise_alert(self.a, "URGENT", "test", "x")

if __name__ == "__main__": unittest.main()
