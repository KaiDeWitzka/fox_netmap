import socket
from concurrent.futures import ThreadPoolExecutor


def resolve_hostname(ip: str) -> str:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name.split(".")[0]
    except (socket.herror, socket.gaierror, OSError, TimeoutError):
        return ""


def resolve_all(ips: list[str], workers: int = 32) -> dict[str, str]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(ips, pool.map(resolve_hostname, ips)))
