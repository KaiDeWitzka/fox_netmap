import socket
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress

COMMON_HIGH = [1433, 3306, 3389, 5432, 5900, 6379, 8000, 8080, 8443, 8888, 9000, 9090, 9100, 11211, 27017, 50000]
DEFAULT_PORTS = list(range(1, 1025)) + COMMON_HIGH


def port_list(top: int, custom: str = "") -> list[int]:
    if custom.strip():
        return sorted({int(p) for p in custom.split(",") if p.strip().isdigit()})
    if top <= 0:
        return list(range(1, 65536))
    return DEFAULT_PORTS[:top]


def check_port(ip: str, port: int, timeout: float) -> int | None:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return port
    except OSError:
        return None


def scan_ports(ip: str, port_numbers: list[int], timeout: float = 0.5, workers: int = 64) -> list[dict]:
    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for port in pool.map(lambda p: check_port(ip, p, timeout), port_numbers):
            if port is not None:
                service = ""
                with suppress(OSError):
                    service = socket.getservbyport(port, "tcp")
                found.append({"port": port, "proto": "tcp", "service": service})
    return sorted(found, key=lambda p: p["port"])
