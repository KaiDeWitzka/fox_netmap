import subprocess


def gateway_ip() -> str:
    try:
        out = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5).stdout
        parts = out.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def resolve_connected_to(
    mac: str,
    ip: str,
    snmp_map: dict | None = None,
    tr064_parent: dict | None = None,
    tr064_type: str = "",
    gateway: str = "",
    manual: str | None = None,
) -> str:
    if manual:
        return manual
    if snmp_map and mac in snmp_map:
        return snmp_map[mac]
    if tr064_parent and mac in tr064_parent:
        return tr064_parent[mac]
    if "wlan" in (tr064_type or "").lower() and gateway:
        return "wlan:" + gateway
    return gateway
