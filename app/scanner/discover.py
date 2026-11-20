import ipaddress
import logging
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

from . import topology

log = logging.getLogger("fox_netmap")

PROBE_PORTS = [80, 443, 22, 445, 8080]
MAX_SWEEP_HOSTS = 1024
SWEEP_NET_LIMIT = 2048


def parse_ip_addr(text: str, version: int = 4) -> list[str]:
    nets = []
    pat = r"inet6 ([0-9a-fA-F:]+/\d+)" if version == 6 else r"inet (\d+\.\d+\.\d+\.\d+/\d+)"
    for line in text.splitlines():
        if "scope host" in line:
            continue
        m = re.search(pat, line)
        if m:
            nets.append(str(ipaddress.ip_network(m.group(1), strict=False)))
    return nets


def local_subnets() -> list[str]:
    out: list[str] = []
    for args, ver in (
        (["ip", "-o", "-4", "addr", "show", "scope", "global"], 4),
        (["ip", "-o", "-6", "addr", "show", "scope", "global"], 6),
    ):
        try:
            text = subprocess.run(args, capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        out += parse_ip_addr(text, ver)
    return out


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


def parse_neigh6(text: str) -> dict[str, str]:
    table = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts or "lladdr" not in parts:
            continue
        mac = parts[parts.index("lladdr") + 1].lower()
        state = parts[-1] if parts else ""
        if mac != "00:00:00:00:00:00" and state not in ("FAILED", "INCOMPLETE"):
            table[parts[0]] = mac
    return table


def neigh6_table() -> dict[str, str]:
    try:
        out = subprocess.run(["ip", "-6", "neigh", "show"], capture_output=True, text=True, timeout=10).stdout
        return parse_neigh6(out)
    except (OSError, subprocess.SubprocessError):
        return {}


def in_net(ip: str, net) -> bool:
    try:
        return ipaddress.ip_address(ip) in net
    except ValueError:
        return False


def ping_host(ip: str, timeout: float) -> bool:
    try:
        ver = ipaddress.ip_address(ip).version
    except ValueError:
        return False
    flag = "-6" if ver == 6 else "-4"
    try:
        result = subprocess.run(
            ["ping", flag, "-c", "1", "-W", str(max(1, int(timeout))), ip],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def sweep_hosts(net, max_hosts: int = MAX_SWEEP_HOSTS) -> list[str]:
    if net.num_addresses > max_hosts * 2:
        return []
    return [str(h) for h in net.hosts()][:max_hosts]


def ping_sweep(subnet: str, timeout: float = 1.0, max_hosts: int = MAX_SWEEP_HOSTS) -> set[str]:
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return set()
    hosts = sweep_hosts(net, max_hosts)
    with ThreadPoolExecutor(max_workers=64) as pool:
        results = list(pool.map(lambda ip: ping_host(ip, timeout), hosts))
    return {ip for ip, ok in zip(hosts, results) if ok}


def tcp_probe(ip: str, timeout: float = 0.8, ports=PROBE_PORTS) -> bool:
    for p in ports:
        try:
            with socket.create_connection((ip, p), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def tcp_probe_sweep(subnet: str, skip: set, timeout: float = 0.8, max_hosts: int = MAX_SWEEP_HOSTS) -> set[str]:
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return set()
    candidates = [h for h in sweep_hosts(net, max_hosts) if h not in skip]
    with ThreadPoolExecutor(max_workers=64) as pool:
        results = list(pool.map(lambda ip: tcp_probe(ip, timeout), candidates))
    return {ip for ip, ok in zip(candidates, results) if ok}


def discover(subnets: list[str], timeout: float = 1.0) -> list[dict]:
    arp = arp_table()
    neigh6 = neigh6_table()
    live: dict[str, str] = {}
    for subnet in subnets:
        try:
            net = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            log.warning("Subnetz %s ungueltig, uebersprungen", subnet)
            continue
        if net.version == 6:
            ndp = [ip for ip in neigh6 if in_net(ip, net)]
            for ip in ndp:
                live.setdefault(ip, "ndp")
            gw = topology.gateway_ip6()
            if gw and in_net(gw, net) and ping_host(gw, timeout):
                live.setdefault(gw, "ping")
            if net.num_addresses <= SWEEP_NET_LIMIT:
                pinged = ping_sweep(subnet, timeout)
                log.info("Subnetz %s: %s Hosts antworten auf Ping", subnet, len(pinged))
                for ip in pinged:
                    live.setdefault(ip, "ping")
                probed = tcp_probe_sweep(subnet, set(pinged) | set(ndp), timeout)
                if probed:
                    log.info("Subnetz %s: zusaetzlich %s Hosts nur per TCP erreichbar", subnet, len(probed))
                for ip in probed:
                    live.setdefault(ip, "tcp")
            else:
                log.info(
                    "Subnetz %s: zu gross fuer Sweep (%s Adressen) -> NDP + Gateway (%s NDP-Eintraege)",
                    subnet, net.num_addresses, len(ndp),
                )
        else:
            pinged = ping_sweep(subnet, timeout)
            log.info("Subnetz %s: %s Hosts antworten auf Ping", subnet, len(pinged))
            for ip in pinged:
                live[ip] = "ping"
            probed = tcp_probe_sweep(subnet, set(pinged), timeout)
            if probed:
                log.info("Subnetz %s: zusaetzlich %s Hosts nur per TCP erreichbar (ICMP blockiert)", subnet, len(probed))
            for ip in probed:
                live.setdefault(ip, "tcp")
    devices: list[dict] = []
    for ip in sorted(live, key=lambda s: ipaddress.ip_address(s)):
        source = live[ip]
        v6 = ":" in ip
        mac = neigh6.get(ip) if v6 else arp.get(ip)
        if mac:
            base = "ndp" if v6 else "arp"
            if source != base and not source.endswith("+" + base):
                source = source + "+" + base
        devices.append({"ip": ip, "mac": mac, "source": source})
    arp_only = 0
    for ip, mac in arp.items():
        if ":" in ip:
            continue
        try:
            in_scope = any(in_net(ip, ipaddress.ip_network(sn, strict=False)) for sn in subnets if ":" not in sn)
        except ValueError:
            in_scope = False
        if in_scope and ip not in live:
            arp_only += 1
            devices.append({"ip": ip, "mac": mac, "source": "arp"})
    log.info("ARP: %s Eintraege im Subnetz-Umfang (nur gleiche L2-Schicht sichtbar)", arp_only)
    return devices
