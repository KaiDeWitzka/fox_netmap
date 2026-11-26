import ipaddress
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor

MDNS_V4 = ("224.0.0.251", 5353)
MDNS_V6 = ("ff02::fb", 5353, 0, 0)


def resolve_hostname(ip: str) -> str:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name.split(".")[0]
    except (socket.herror, socket.gaierror, OSError, TimeoutError):
        return ""


def resolve_aaaa(hostname: str) -> str:
    """AAAA-Adresse eines Hostnamens per DNS (z. B. FRITZ!Box-DNS fuer bekannte Geraete), ohne Link-Local."""
    if not hostname:
        return ""
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET6)
    except (socket.herror, socket.gaierror, OSError, TimeoutError):
        return ""
    for info in infos:
        addr = str(info[4][0])
        if addr and not addr.lower().startswith("fe80:"):
            return addr
    return ""


def ptr_name(ip: str) -> str | None:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if addr.version == 4:
        return ".".join(reversed(str(addr).split("."))) + ".in-addr.arpa"
    return ".".join(reversed(addr.exploded.replace(":", ""))) + ".ip6.arpa"


def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.rstrip(".").split("."):
        raw = label.encode("ascii", "ignore")
        out += bytes([len(raw)]) + raw
    return out + b"\x00"


def _decode_name(data: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    end = offset
    jumped = False
    hops = 0  # Schutz gegen Zeiger-Schleifen in manipulierten Paketen (v1.6.0)
    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset += 1
            if not jumped:
                end = offset
            break
        if length & 0xC0 == 0xC0:
            hops += 1
            if offset + 1 >= len(data) or hops > 16:
                break
            ptr = ((length & 0x3F) << 8) | data[offset + 1]
            if not jumped:
                end = offset + 2
            offset = ptr
            jumped = True
            continue
        labels.append(data[offset + 1 : offset + 1 + length].decode("ascii", "ignore"))
        offset += 1 + length
    return ".".join(labels), end


def parse_mdns_answers(data: bytes) -> list[str]:
    if len(data) < 12:
        return []
    _, _, qd, an, _, _ = struct.unpack(">HHHHHH", data[:12])
    offset = 12
    for _ in range(qd):
        _, offset = _decode_name(data, offset)
        offset += 4
    names: list[str] = []
    for _ in range(an):
        if offset + 10 > len(data):
            break
        _, offset = _decode_name(data, offset)
        rtype, _rclass, _ttl, rdlen = struct.unpack(">HHIH", data[offset : offset + 10])
        offset += 10
        if rtype == 12 and offset + rdlen <= len(data):
            name, _ = _decode_name(data, offset)
            if name:
                names.append(name)
        offset += rdlen
    return names


def resolve_hostname_mdns(ip: str, timeout: float = 1.0) -> str:
    name = ptr_name(ip)
    if not name:
        return ""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    family = socket.AF_INET if addr.version == 4 else socket.AF_INET6
    group = MDNS_V4 if addr.version == 4 else MDNS_V6
    query = struct.pack(">HHHHHH", 0, 0x0100, 1, 0, 0, 0) + _encode_name(name) + struct.pack(">HH", 12, 1)
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
    except OSError:
        return ""
    sock.settimeout(timeout)
    try:
        if addr.version == 6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 255)
        sock.sendto(query, group)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, _ = sock.recvfrom(9000)
            except (TimeoutError, OSError):
                break
            for hostname in parse_mdns_answers(data):
                host = hostname.rstrip(".")
                if host.endswith(".local"):
                    return host[: -len(".local")]
                return host.split(".")[0]
    except OSError:
        return ""
    finally:
        sock.close()
    return ""


def resolve_all(ips: list[str], workers: int = 32, use_mdns: bool = False, mdns_timeout: float = 1.0) -> dict[str, str]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        result = dict(zip(ips, pool.map(resolve_hostname, ips), strict=True))
    if use_mdns:
        missing = [ip for ip, name in result.items() if not name]
        if missing:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for ip, name in zip(
                    missing, pool.map(lambda i: resolve_hostname_mdns(i, mdns_timeout), missing), strict=True
                ):
                    if name:
                        result[ip] = name
    return result
