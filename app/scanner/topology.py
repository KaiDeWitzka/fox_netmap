import ipaddress
import subprocess


def _default_gateway(args: list[str]) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=5).stdout
        parts = out.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    except (OSError, subprocess.SubprocessError):
        pass
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


def resolve_connected_to(
    mac: str,
    ip: str,
    snmp_map: dict | None = None,
    tr064_parent: dict | None = None,
    tr064_type: str = "",
    mesh_parent: dict | None = None,
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


def assign_behind_switch(devices: list[dict], ports: dict[str, tuple[str, str]], fixed: set[str]) -> int:
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
