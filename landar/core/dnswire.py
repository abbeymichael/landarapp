"""Minimal DNS (RFC 1035) A-record query builder/parser so LANDAR can test resolvers without extra dependencies."""
import ipaddress, socket, struct

def build_query(name: str, qid: int) -> bytes:
    q = b"".join(bytes([len(p)]) + p.encode("idna") for p in name.rstrip(".").split(".")) + b"\x00"
    return struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + struct.pack(">HH", 1, 1)

def _skip_name(data: bytes, pos: int) -> int:
    while True:
        n = data[pos]
        if n == 0: return pos + 1
        if n & 0xC0 == 0xC0: return pos + 2          # compression pointer
        pos += n + 1

def parse_response(data: bytes, qid: int) -> tuple[int, list[str]]:
    """Returns (rcode, [A-record IPs]). rcode 0=OK, 3=NXDOMAIN."""
    rid, flags, qd, an, _, _ = struct.unpack(">HHHHHH", data[:12])
    if rid != qid: raise ValueError("Mismatched DNS reply")
    pos = 12
    for _ in range(qd): pos = _skip_name(data, pos) + 4
    ips = []
    for _ in range(an):
        pos = _skip_name(data, pos); rtype, _c, _ttl, rdlen = struct.unpack(">HHIH", data[pos:pos + 10]); pos += 10
        if rtype == 1 and rdlen == 4: ips.append(".".join(str(b) for b in data[pos:pos + 4]))
        pos += rdlen
    return flags & 0xF, ips

def query(server: str, name: str, timeout: float = 2.5) -> tuple[int, list[str]]:
    fam = socket.AF_INET6 if ipaddress.ip_address(server).version == 6 else socket.AF_INET
    qid = struct.unpack(">H", __import__("os").urandom(2))[0]; s = socket.socket(fam, socket.SOCK_DGRAM); s.settimeout(timeout)
    try: s.sendto(build_query(name, qid), (server, 53)); return parse_response(s.recvfrom(4096)[0], qid)
    finally: s.close()
