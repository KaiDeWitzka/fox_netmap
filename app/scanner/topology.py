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


def resolve_connected_to(
    mac: str,
    ip: str,
    snmp_map: dict | None = None,
    tr064_parent: dict | None = None,
    tr064_type: str = "",
    gateway: str = "",
    gateway6: str = "",
    manual: str | None = None,
) -> str:
    gw = gateway_for(ip, gateway, gateway6)
    if manual:
        return manual
    if snmp_map and mac in snmp_map:
        return snmp_map[mac]
    if tr064_parent and mac in tr064_parent:
        return tr064_parent[mac]
    if "wlan" in (tr064_type or "").lower() and gw:
        return "wlan:" + gw
    return gw
