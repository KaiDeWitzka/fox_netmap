import re
import subprocess

QBRIDGE_FDB = "1.3.6.1.2.1.17.7.1.2.2.1.2"
BRIDGE_FDB = "1.3.6.1.2.1.17.4.3.1.2"

LINE_RE = re.compile(r"((?:\d+\.){5}\d+)\s*=\s*INTEGER:\s*(\d+)")


def snmp_walk(ip: str, community: str, oid: str, timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, "-t", str(timeout), "-On", ip, oid],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_cam(output: str) -> dict[str, int]:
    result = {}
    for line in output.splitlines():
        m = LINE_RE.search(line)
        if m:
            mac = ":".join(f"{int(octet):02x}" for octet in m.group(1).split("."))
            result[mac] = int(m.group(2))
    return result


def cam_map(switch_ips: list[str], community: str) -> dict[str, str]:
    mapping = {}
    for ip in switch_ips:
        output = snmp_walk(ip, community, QBRIDGE_FDB) or snmp_walk(ip, community, BRIDGE_FDB)
        for mac, _port in parse_cam(output).items():
            mapping[mac] = ip
    return mapping
