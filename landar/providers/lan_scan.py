"""Read-only LAN discovery: nudge every host on the local subnet so the OS learns its MAC (ARP), then read the OS neighbor table.
No admin rights, no packet sniffing, no credentials. Only scan networks you own or administer."""
import ipaddress, os, re, socket, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, wait
import psutil
from landar.providers import oui
from landar.providers.base import NetworkProvider

MAX_HOSTS = 1024
_MAC_RE = r"[0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5}"

def normalize_mac(m: str) -> str | None:
    parts = re.split(r"[:-]", m.strip())
    return ":".join(p.zfill(2) for p in parts).upper() if len(parts) == 6 else None

def _ignorable(mac: str) -> bool:
    return mac in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00") or mac.startswith(("01:00:5E", "33:33"))

def parse_arp_a(text: str) -> list[tuple[str, str]]:
    """Parses `arp -a` output from Windows, macOS and Linux."""
    out = []
    for m in re.finditer(rf"(\d{{1,3}}(?:\.\d{{1,3}}){{3}})\)?\s+(?:at\s+)?({_MAC_RE})", text):
        mac = normalize_mac(m.group(2))
        if mac and not _ignorable(mac): out.append((m.group(1), mac))
    return out

def parse_proc_arp(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 4 and cols[2] == "0x2":          # 0x2 = complete entry
            mac = normalize_mac(cols[3])
            if mac and not _ignorable(mac): out.append((cols[0], mac))
    return out

def read_neighbors() -> list[tuple[str, str]]:
    if os.path.exists("/proc/net/arp"):
        with open("/proc/net/arp") as f: return parse_proc_arp(f.read())
    flags = 0x08000000 if sys.platform == "win32" else 0   # no console flash on Windows
    res = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10, creationflags=flags)
    return parse_arp_a(res.stdout)

def local_network() -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]      # routing lookup only; sends nothing
    except OSError:
        raise RuntimeError("Not connected to a network")
    finally: s.close()
    for name, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family == socket.AF_INET and a.address == ip:
                net = ipaddress.ip_network(f"{ip}/{a.netmask}", strict=False)
                if net.num_addresses > MAX_HOSTS: net = ipaddress.ip_network(f"{ip}/24", strict=False)
                mac = next((normalize_mac(x.address) for x in addrs if x.family == psutil.AF_LINK and x.address), None)
                return {"interface": name, "ip": ip, "cidr": str(net), "mac": mac}
    raise RuntimeError("Could not identify the active network interface")

def _nudge(ip: str) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.sendto(b"\x00", (ip, 9))
    except OSError: pass
    finally: s.close()

def _resolve_names(ips: list[str], timeout=4.0) -> dict[str, str]:
    pool = ThreadPoolExecutor(max_workers=32)
    futs = {pool.submit(socket.gethostbyaddr, ip): ip for ip in ips}
    done, _ = wait(futs, timeout=timeout); pool.shutdown(wait=False)
    return {futs[f]: f.result()[0] for f in done if not f.exception()}

class LanScanProvider(NetworkProvider):
    name = "lan-scan"
    def network_info(self) -> dict: return local_network()

    def discover_devices(self) -> list[dict]:
        info = local_network(); net = ipaddress.ip_network(info["cidr"]); hosts = [str(h) for h in net.hosts()]
        with ThreadPoolExecutor(max_workers=128) as pool:
            for _ in range(2):                                    # two passes help sleeping Wi-Fi clients
                list(pool.map(_nudge, hosts)); time.sleep(1.5)
        found = {mac: ip for ip, mac in read_neighbors() if ipaddress.ip_address(ip) in net}
        if info["mac"]: found[info["mac"]] = info["ip"]
        names = _resolve_names(list(found.values())); names[info["ip"]] = socket.gethostname()
        result = []
        for mac, ip in found.items():
            rand = bool(int(mac[:2], 16) & 2)                    # locally-administered bit = private/randomized MAC
            result.append({"mac": mac, "ip": ip, "hostname": names.get(ip, ""),
                           "vendor": "Private (randomized MAC)" if rand else oui.lookup(mac), "randomized": rand})
        return sorted(result, key=lambda d: tuple(int(x) for x in d["ip"].split(".")))
