import ipaddress
import subprocess
from typing import Any

from ..logsetup import warn_once


def _default_gateway(args: list[str]) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=5).stdout  # noqa: S603 - feste Systemprogramme (ip), keine Nutzereingabe
        parts = out.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    except (OSError, subprocess.SubprocessError) as exc:
        warn_once("bin:ip-route", "ip route nicht ausfuehrbar (%s) - Gateway unbekannt", type(exc).__name__)
    return ""


def gateway_ip() -> str:
    return _default_gateway(["ip", "route", "show", "default"])


def gateway_ip6() -> str:
    return _default_gateway(["ip", "-6", "route", "show", "default"])


def gateway_for(ip: str, gateway: str = "", gateway6: str = "") -> str:
    try:
        v6 = ipaddress.ip_address(ip).version == 6
    except ValueError:
        v6 = False
    return (gateway6 or gateway) if v6 else gateway


def conn_type(interface_type: str) -> str:
    """TR-064 NewInterfaceType ("Ethernet", "802.11", "HomePlug", "") -> "lan" | "wlan" | "plc" | ""."""
    t = (interface_type or "").strip().lower()
    if "802.11" in t or "wlan" in t or "wifi" in t or "wi-fi" in t:
        return "wlan"
    if "homeplug" in t or "plc" in t:
        return "plc"
    if "ethernet" in t or "lan" in t:
        return "lan"
    return ""


def vpn_pool_rules(
    vpn_pool: str, gateway: str = ""
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network | None, int, list[Any], list[Any]]:
    """Parst das Setting vpn_pool.

    Rueckgabe: (auto_net, auto_min, nets, ranges)
      - auto_net/auto_min: Token "auto" -> FRITZ!-Konvention: im /24 des Gateways zaehlt
        die letzte Oktett >= auto_min (201) als VPN-Pool (DHCP endet bei .200).
      - nets: CIDR-Eintraege (ip_network)
      - ranges: Bereiche "a-b" als (start, ende)
    Leer/"off"/"0" (Default) deaktiviert die Pool-Heuristik komplett - es wird kein VPN-Pool
    angenommen; dann greift nur die TR-064-Erkennung (siehe is_vpn_tr064).
    """
    nets: list[Any] = []
    ranges: list[Any] = []
    auto_net = None
    auto_min = 0
    pool = (vpn_pool or "").strip()
    if not pool or pool.lower() in ("off", "0"):
        return auto_net, auto_min, nets, ranges
    for tok in pool.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.lower() == "auto":
            try:
                gw = ipaddress.ip_address(gateway)
            except ValueError:
                continue
            if gw.version == 4:
                auto_net = ipaddress.ip_network(f"{gw}/24", strict=False)
                auto_min = 201
            continue
        if "-" in tok:
            a, _, b = tok.partition("-")
            try:
                ia = ipaddress.ip_address(a.strip())
                ib = ipaddress.ip_address(b.strip())
            except ValueError:
                raise ValueError(f"ungueltiger VPN-Bereich: {tok!r}") from None
            if ia.version != ib.version or ia.packed > ib.packed:
                raise ValueError(f"ungueltiger VPN-Bereich: {tok!r}")
            ranges.append((ia, ib))
        else:
            nets.append(ipaddress.ip_network(tok, strict=False))
    return auto_net, auto_min, nets, ranges


def is_vpn_ip(ip: str, vpn_pool: str, gateway: str = "") -> bool:
    """True, wenn die IP laut vpn_pool-Heuristik zum VPN-Adresspool gehoert."""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    auto_net, auto_min, nets, ranges = vpn_pool_rules(vpn_pool, gateway)
    if (
        auto_net is not None
        and addr.version == 4
        and addr in auto_net
        and int(addr) - int(auto_net.network_address) >= auto_min
    ):
        return True
    if any(addr in n for n in nets):
        return True
    return any(a <= addr <= b for a, b in ranges)


def is_vpn_tr064(interface_type: str) -> bool:
    """TR-064 meldet VPN-Clients (z. B. IPSec) mit InterfaceType wie 'VPN'."""
    return "vpn" in (interface_type or "").lower()


def resolve_connected_to(
    mac: str,
    ip: str,
    snmp_map: dict[str, str] | None = None,
    tr064_parent: dict[str, str] | None = None,
    tr064_type: str = "",
    mesh_parent: dict[str, str] | None = None,
    gateway: str = "",
    gateway6: str = "",
    manual: str | None = None,
) -> str:
    gw = gateway_for(ip, gateway, gateway6)
    if manual:
        return manual
    if snmp_map and mac in snmp_map:
        return snmp_map[mac]
    # FRITZ!Box-Mesh-Topologie: genauer als der TR-064-Endpunkt, ungenauer als SNMP am Switch
    if mesh_parent and mac in mesh_parent:
        return mesh_parent[mac]
    if tr064_parent and mac in tr064_parent:
        return tr064_parent[mac]
    if conn_type(tr064_type) == "wlan" and gw:
        return "wlan:" + gw
    return gw


def assign_behind_switch(devices: list[dict[str, Any]], ports: dict[str, tuple[str, str]], fixed: set[str]) -> int:
    """Ordnet Geraete einem Switch zu, der am selben LAN-Port des Elternknotens haengt.

    Ein LAN-Port einer FRITZ!Box hat genau eine Leitung. Sieht die Box dort mehrere Geraete und ist genau
    eines davon ein Switch, haengen die uebrigen hinter diesem Switch (unmanaged/Easy-Smart-Switche ohne SNMP).
    ports: {mac: (eltern_mac, port_name)} nur fuer LAN-Verbindungen aus der Mesh-Topologie.
    fixed: MACs mit manueller oder SNMP-Zuordnung, die nicht veraendert werden.
    """
    by_mac = {d["mac"]: d for d in devices if d.get("mac")}
    groups: dict[tuple[str, str], list[str]] = {}
    for mac, key in ports.items():
        if mac in by_mac and key[1]:
            groups.setdefault(key, []).append(mac)
    moved = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        switches = [m for m in members if by_mac[m].get("category") == "Switch"]
        if len(switches) != 1:
            continue
        sw = switches[0]
        for m in members:
            if m == sw or m in fixed:
                continue
            by_mac[m]["layout"]["connected_to"] = sw
            by_mac[m]["link_port"] = ""  # Port gehoert zur Box, nicht zum Switch
            moved += 1
    return moved
