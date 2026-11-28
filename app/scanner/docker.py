"""Docker Engine API (read-only) fuer den Containerlandschaft-Scan (E-8, Backlog #112 #12).

Nur lesende Endpunkte: /version, /containers/json?all=1, /networks. Der Docker-Socket
(/var/run/docker.sock) wird bewusst NICHT verwendet - der waere root-aequivalent am Host.
Der optionale Bearer-Token wird nur im Authorization-Header gesendet und nie geloggt.
"""

import json
import logging
import ssl
import urllib.error
import urllib.request
from typing import Any

from ..logsetup import warn_once
from ..types import Device

log = logging.getLogger("fox_netmap")

HTTP_PORT = 2375
HTTPS_PORT = 2376
DEFAULT_TIMEOUT = 10.0


class DockerError(Exception):
    """API nicht erreichbar oder Antwort nicht als JSON lesbar."""


def _ssl_context(verify: bool) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def api_get(base_url: str, path: str, token: str = "", verify: bool = True, timeout: float = DEFAULT_TIMEOUT) -> Any:
    """GET <base_url><path> als JSON. Read-only: der Aufrufer fragt nur lesende Pfade ab."""
    req = urllib.request.Request(base_url + path, headers={"Accept": "application/json"})  # noqa: S310 - Schema kommt aus candidate_bases (nur http/https)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(verify)) as resp:  # noqa: S310 - siehe Request oben
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise DockerError(f"{base_url}{path}: {type(exc).__name__}") from exc


def parse_hosts(spec: str) -> list[tuple[str, int | None]]:
    """NETZ_DOCKER_HOSTS parsen: "host1:2376, host2" -> [(host, port|None), ...]."""
    out: list[tuple[str, int | None]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        host, sep, port = part.rpartition(":")
        if sep and host and port.isdigit():
            out.append((host, int(port)))
        elif sep and host:
            continue  # ungueltiger Port (z. B. "h:abc") - Eintrag ueberspringen
        else:
            out.append((part, None))
    return out


def candidate_bases(host: str, port: int | None) -> list[str]:
    """Ohne Port: 2376/TLS zuerst, dann 2375/HTTP. Mit Port: Schema aus dem Port."""
    if port is not None:
        scheme = "https" if port == HTTPS_PORT else "http"
        return [f"{scheme}://{host}:{port}"]
    return [f"https://{host}:{HTTPS_PORT}", f"http://{host}:{HTTP_PORT}"]


def fetch_host_info(
    base_url: str, token: str = "", verify: bool = True, timeout: float = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Read-only-Abfrage eines Docker-Hosts: Version + Container + Netzwerke."""
    version = api_get(base_url, "/version", token, verify, timeout)
    containers = api_get(base_url, "/containers/json?all=1", token, verify, timeout)
    networks = api_get(base_url, "/networks", token, verify, timeout)
    if not isinstance(containers, list):
        raise DockerError(f"{base_url}/containers/json: keine Liste")
    return {"base": base_url, "version": version, "containers": containers, "networks": networks or []}


def network_subnets(networks: list[dict[str, Any]]) -> dict[str, str]:
    """Netzwerkname -> Subnetz aus der IPAM-Konfiguration."""
    out: dict[str, str] = {}
    for net in networks:
        name = net.get("Name", "")
        for cfg in (net.get("IPAM") or {}).get("Config") or []:
            subnet = cfg.get("Subnet")
            if name and subnet:
                out[name] = subnet
    return out


def parse_containers(containers: list[dict[str, Any]], subnets_by_net: dict[str, str]) -> list[dict[str, Any]]:
    """/containers/json-Eintraege -> normalisierte Container-Dicts.

    Host-Network-Container (NetworkMode "host") teilen die IP des Hosts und werden
    uebersprungen - sonst entstaende ein Duplikat des Host-Geraets.
    """
    out: list[dict[str, Any]] = []
    for c in containers:
        cid = (c.get("Id") or "")[:12]
        names = c.get("Names") or []
        name = (names[0] if names else cid).lstrip("/") or cid
        nets = (c.get("NetworkSettings") or {}).get("Networks") or {}
        if "host" in nets:
            continue
        ip = ""
        net_name = ""
        for net, cfg in sorted(nets.items()):
            if cfg.get("IPAddress"):
                ip = cfg["IPAddress"]
                net_name = net
                break
        if not ip:
            continue  # Container ohne IP (none/ingress-only) - nicht scanbar
        ports = sorted({p.get("PrivatePort") for p in (c.get("Ports") or []) if p.get("PrivatePort")})
        out.append(
            {
                "id": cid,
                "name": name,
                "image": c.get("Image", ""),
                "state": c.get("State", ""),
                "status": c.get("Status", ""),
                "ip": ip,
                "net": net_name,
                "subnet": subnets_by_net.get(net_name, ""),
                "ports": [int(p) for p in ports],
            }
        )
    return out


def to_device(c: dict[str, Any], host_ip: str, host_mac: str) -> Device:
    """Container -> Geraete-Dict (synthetische MAC wie beim VPN-Fall, Kategorie setzt classify)."""
    return {
        "ip": c["ip"],
        "mac": f"ip:{c['ip']}",
        "hostname": c["name"],
        "ports": [{"port": p} for p in c["ports"]],
        "is_container": True,
        "docker_host": host_ip,
        "docker_host_mac": host_mac,
        "subnet": c.get("subnet", ""),
        "source": "docker",
        "docker": {"id": c["id"], "image": c["image"], "state": c["state"], "status": c["status"]},
    }


def docker_stage(settings: Any, live: list[dict[str, Any]]) -> tuple[list[Device], dict[str, str], list[str]]:
    """Stufe nach SNMP: Docker-Hosts abfragen, Container als Geraete liefern.

    Rueckgabe: (Container-Devices, {Container-MAC: Host-MAC}, zusaetzliche Subnetze).
    """
    if not getattr(settings, "docker_enabled", False):
        return [], {}, []
    verify = not getattr(settings, "docker_insecure_tls", False)
    if not verify:
        log.warning(
            "Docker: NETZ_DOCKER_INSECURE_TLS=1 - TLS-Zertifikatspruefung deaktiviert; nur im eigenen LAN verwenden (MITM-Risiko)"
        )
    token = getattr(settings, "docker_token", "") or ""

    targets: dict[tuple[str, int | None], None] = {}
    for host, port in parse_hosts(getattr(settings, "docker_hosts", "") or ""):
        targets[(host, port)] = None
    for d in live:
        open_ports = {p["port"] for p in d.get("ports", []) if isinstance(p, dict) and p.get("port")}
        for p in (HTTP_PORT, HTTPS_PORT):
            if p in open_ports:
                targets.setdefault((d["ip"], p), None)
    if not targets:
        return [], {}, []

    host_mac_by_ip = {d["ip"]: d.get("mac", "") for d in live if d.get("ip")}
    existing_ips = {d.get("ip") for d in live if d.get("ip")}
    devices: list[Device] = []
    parent: dict[str, str] = {}
    extra_subnets: list[str] = []
    for host, port in targets:
        info = _fetch_host(host, port, token, verify)
        if info is None:
            continue
        subnets_by_net = network_subnets(info["networks"])
        host_mac = host_mac_by_ip.get(host, "")
        for c in parse_containers(info["containers"], subnets_by_net):
            if c["ip"] in existing_ips:
                continue  # IP schon als echtes Geraet erfasst (z. B. Host-Network oder Subnetz-Scan)
            dev = to_device(c, host, host_mac)
            devices.append(dev)
            parent[dev["mac"]] = host_mac
            if c.get("subnet"):
                extra_subnets.append(c["subnet"])
    if devices:
        log.info("Docker: %s Container erkannt", len(devices))
    return devices, parent, sorted(set(extra_subnets))


def _fetch_host(host: str, port: int | None, token: str, verify: bool) -> dict[str, Any] | None:
    """Ersten erreichbaren Kandidaten probieren; None wenn keiner antwortet."""
    for base in candidate_bases(host, port):
        try:
            info = fetch_host_info(base, token, verify)
        except DockerError as exc:
            warn_once(f"docker:{base}", "Docker-API nicht erreichbar (%s): %s", base, exc)
            continue
        log.info("Docker: %s (API %s, Version %s)", host, base, (info["version"] or {}).get("Version", "?"))
        return info
    return None
