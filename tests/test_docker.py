"""Tests fuer den Containerlandschaft-Scan ueber die Docker Engine API (E-8, Backlog #112 #12).

Fixture: lokaler HTTP-Server (127.0.0.1, ephemerer Port), der die read-only Endpunkte
/version, /containers/json, /networks answered. Kein Docker noetig.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

from app.config import Settings
from app.scanner import categorize, docker
from app.settings_schema import FIELDS

CONTAINERS = [
    {
        "Id": "abcdef1234567890",
        "Names": ["/web"],
        "Image": "nginx:1.27",
        "State": "running",
        "Status": "Up 2 hours",
        "Ports": [{"PrivatePort": 80, "PublicPort": 8080, "IP": "192.0.2.1"}],  # TEST-NET-Adresse, kein echtes Bind
        "NetworkSettings": {"Networks": {"bridge": {"IPAddress": "172.17.0.2"}}},
    },
    {
        "Id": "1111222233334444",
        "Names": ["/hostnet"],
        "Image": "agent:2",
        "State": "running",
        "Status": "Up 2 hours",
        "Ports": [],
        "NetworkSettings": {"Networks": {"host": {"IPAddress": ""}}},
    },
    {
        "Id": "5555666677778888",
        "Names": ["/db", "/postgres"],
        "Image": "postgres:16",
        "State": "exited",
        "Status": "Exited (0) 3 days ago",
        "Ports": [{"PrivatePort": 5432}],
        "NetworkSettings": {"Networks": {"backend": {"IPAddress": "172.18.0.5"}}},
    },
]

NETWORKS = [
    {"Name": "bridge", "IPAM": {"Config": [{"Subnet": "172.17.0.0/16", "Gateway": "172.17.0.1"}]}},
    {"Name": "backend", "IPAM": {"Config": [{"Subnet": "172.18.0.0/16"}]}},
]


class DockerHandler(BaseHTTPRequestHandler):
    seen_headers: ClassVar[list[dict[str, str]]] = []

    def _json(self, payload: Any) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        type(self).seen_headers.append(dict(self.headers))
        if self.path.startswith("/version"):
            self._json({"Version": "27.3.1", "ApiVersion": "1.46"})
        elif self.path.startswith("/containers/json"):
            self._json(CONTAINERS)
        elif self.path.startswith("/networks"):
            self._json(NETWORKS)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture()
def docker_server():
    DockerHandler.seen_headers = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), DockerHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1]
    srv.shutdown()
    t.join(timeout=5)


def make_settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {"auth_enabled": False, "docker_enabled": True}
    base.update(kw)
    return Settings(**base)


def test_parse_hosts() -> None:
    assert docker.parse_hosts("h1:2376, h2 ,h3:abc") == [("h1", 2376), ("h2", None)]
    assert docker.parse_hosts("") == []


def test_candidate_bases_prefers_tls() -> None:
    assert docker.candidate_bases("h", None) == ["https://h:2376", "http://h:2375"]
    assert docker.candidate_bases("h", 2375) == ["http://h:2375"]
    assert docker.candidate_bases("h", 2376) == ["https://h:2376"]


def test_api_get_sends_bearer_token_and_parses_json(docker_server: int) -> None:
    base = f"http://127.0.0.1:{docker_server}"
    data = docker.api_get(base, "/version", token="s3cr3t-token")
    assert data["Version"] == "27.3.1"
    auth = [h.get("Authorization", "") for h in DockerHandler.seen_headers]
    assert auth == ["Bearer s3cr3t-token"]


def test_api_get_error_contains_no_token(docker_server: int, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING), pytest.raises(docker.DockerError) as exc:
        docker.api_get(f"http://127.0.0.1:{docker_server}", "/missing", token="s3cr3t-token")
    assert "s3cr3t-token" not in str(exc.value)
    assert "s3cr3t-token" not in caplog.text


def test_parse_containers_skips_host_network_and_picks_ip() -> None:
    subs = docker.network_subnets(NETWORKS)
    assert subs == {"bridge": "172.17.0.0/16", "backend": "172.18.0.0/16"}
    parsed = docker.parse_containers(CONTAINERS, subs)
    by_name = {c["name"]: c for c in parsed}
    assert "hostnet" not in by_name  # NetworkMode host -> kein eigenes Geraet
    assert by_name["web"]["ip"] == "172.17.0.2"
    assert by_name["web"]["subnet"] == "172.17.0.0/16"
    assert by_name["web"]["ports"] == [80]
    assert by_name["db"]["name"] == "db" and by_name["db"]["ip"] == "172.18.0.5"


def test_to_device_synthetic_mac_and_container_flag() -> None:
    c = {
        "id": "abc",
        "name": "web",
        "image": "nginx",
        "state": "running",
        "status": "Up",
        "ip": "172.17.0.2",
        "net": "bridge",
        "subnet": "172.17.0.0/16",
        "ports": [80],
    }
    dev = docker.to_device(c, "192.168.1.10", "aa:bb:cc:dd:ee:ff")
    assert dev["mac"] == "ip:172.17.0.2"
    assert dev["is_container"] is True
    assert dev["docker_host"] == "192.168.1.10"
    assert dev["docker_host_mac"] == "aa:bb:cc:dd:ee:ff"
    assert dev["ports"] == [{"port": 80}]


def test_stage_disabled_by_default() -> None:
    s = Settings(auth_enabled=False)  # docker_enabled default False
    assert docker.docker_stage(s, []) == ([], {}, [])


def test_stage_reads_explicit_host(docker_server: int) -> None:
    s = make_settings(docker_hosts=f"127.0.0.1:{docker_server}")
    live = [{"ip": "127.0.0.1", "mac": "aa:bb:cc:dd:ee:ff", "ports": []}]
    devs, parent, subnets = docker.docker_stage(s, live)
    assert {d["hostname"] for d in devs} == {"web", "db"}
    assert parent["ip:172.17.0.2"] == "aa:bb:cc:dd:ee:ff"
    assert "172.17.0.0/16" in subnets and "172.18.0.0/16" in subnets


def test_stage_auto_detects_open_docker_port(docker_server: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docker, "HTTP_PORT", docker_server)  # Fixture-Port simuliert 2375 (HTTP)
    s = make_settings(docker_hosts="")  # kein expliziter Host
    live = [{"ip": "127.0.0.1", "mac": "aa:bb:cc:dd:ee:ff", "ports": [{"port": docker_server}]}]
    devs, _, _ = docker.docker_stage(s, live)
    assert {d["hostname"] for d in devs} == {"web", "db"}


def test_stage_skips_ip_already_scanned(docker_server: int) -> None:
    s = make_settings(docker_hosts=f"127.0.0.1:{docker_server}")
    live = [
        {"ip": "127.0.0.1", "mac": "aa:bb:cc:dd:ee:ff", "ports": []},
        {"ip": "172.17.0.2", "mac": "02:42:ac:11:00:02", "ports": []},
    ]
    devs, _, _ = docker.docker_stage(s, live)
    assert {d["hostname"] for d in devs} == {"db"}  # web hat IP, die schon als Geraet existiert


def test_stage_unreachable_host_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    s = make_settings(docker_hosts="127.0.0.1:1")  # Port 1: Verbindung verweigert
    with caplog.at_level(logging.WARNING):
        devs, parent, subnets = docker.docker_stage(s, [])
    assert devs == [] and parent == {} and subnets == []
    assert "Docker-API nicht erreichbar" in caplog.text


def test_classify_container_wins() -> None:
    cat, reason = categorize.classify(hostname="web", ports=[{"port": 80}], is_container=True)
    assert cat == categorize.CONTAINER
    assert reason == "docker:container"
    assert categorize.CONTAINER in categorize.CATEGORIES


def test_docker_ports_are_fingerprint_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    assert 2375 in categorize.FINGERPRINT_PORTS
    assert 2376 in categorize.FINGERPRINT_PORTS
    assert categorize.PORT_RULES[2376][0] == categorize.SERVER


def test_settings_schema_docker_fields() -> None:
    for key in ("docker_enabled", "docker_hosts", "docker_insecure_tls", "docker_token"):
        assert key in FIELDS
    assert FIELDS["docker_token"].secret is True
    s = Settings(auth_enabled=False)
    assert s.docker_enabled is False
    assert s.docker_hosts == ""
