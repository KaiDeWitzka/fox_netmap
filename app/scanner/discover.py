import ipaddress
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor


def parse_ip_addr(text: str) -> list[str]:
    nets = []
    for line in text.splitlines():
        if "scope host" in line:
            continue
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", line)
        if m:
            nets.append(str(ipaddress.ip_network(m.group(1), strict=False)))
    return nets


def local_subnets() -> list[str]:
    try:
        out = subprocess.run(
            ["ip", "-o", "-4", "addr", "show", "scope", "global"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_ip_addr(out)


def parse_arp(text: str) -> dict[str, str]:
    table = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
            table[parts[0]] = parts[3].lower()
    return table


def arp_table() -> dict[str, str]:
    try:
        with open("/proc/net/arp", encoding="utf-8") as fh:
            return parse_arp(fh.read())
    except OSError:
        return {}


def ping_host(ip: str, timeout: float) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(max(1, int(timeout))), ip],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ping_sweep(subnet: str, timeout: float = 1.0, max_hosts: int = 1024) -> set[str]:
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return set()
    hosts = [str(h) for h in net.hosts()]
    if len(hosts) > max_hosts:
        hosts = hosts[:max_hosts]
    with ThreadPoolExecutor(max_workers=64) as pool:
        results = list(pool.map(lambda ip: ping_host(ip, timeout), hosts))
    return {ip for ip, ok in zip(hosts, results) if ok}


def discover(subnets: list[str], timeout: float = 1.0) -> list[dict]:
    arp = arp_table()
    live: set[str] = set()
    for subnet in subnets:
        live |= ping_sweep(subnet, timeout)
    devices: list[dict] = []
    for ip in sorted(live, key=lambda s: ipaddress.ip_address(s)):
        devices.append({"ip": ip, "mac": arp.get(ip), "source": "ping+arp" if arp.get(ip) else "ping"})
    for ip, mac in arp.items():
        try:
            in_scope = any(ipaddress.ip_address(ip) in ipaddress.ip_network(sn, strict=False) for sn in subnets)
        except ValueError:
            in_scope = False
        if in_scope and ip not in live:
            devices.append({"ip": ip, "mac": mac, "source": "arp"})
    return devices
