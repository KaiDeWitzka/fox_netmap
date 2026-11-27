"""W7 Q-3: Charakterisierungstest fuer collect_devices - die Zerlegung in pipeline.py
(app/scanner/pipeline.py) darf die Ausgabe byte-identisch lassen. Alle Sonden sind gepatcht,
Datenbank und Settings sind echt."""

import sys

import pytest

from app import db
from app.config import Settings
from app.scanner import run

PC = "aa:aa:aa:00:00:01"
NAS = "aa:aa:aa:00:00:02"
TV = "aa:aa:aa:00:00:03"

# gepinnte Ausgabe von collect_devices (Stand vor W7), sortiert nach mac
EXPECTED = [
    {
        "ip": "192.168.178.100",
        "mac": PC,
        "source": "ping+arp,tr064",
        "hostname": "pc-1",
        "tr064_type": "802.11",
        "tr064_active": True,
        "tr064_endpoint": "192.168.178.1",
        "ports": [],
        "ip6": "",
        "vendor": "",
        "status": "online",
        "subnet": "192.168.178.0/24",
        "vpn": False,
        "connection": "wlan",
        "category": "Client",
        "category_reason": "host:pc",
        "layout": {"connected_to": "192.168.178.1"},
    },
    {
        "ip": "192.168.178.101",
        "mac": NAS,
        "source": "ping,tr064",
        "hostname": "nas",
        "tr064_type": "LAN",
        "tr064_active": True,
        "tr064_endpoint": "192.168.178.1",
        "ports": [{"port": 445, "proto": "tcp", "service": "microsoft-ds"}],
        "ip6": "",
        "vendor": "",
        "status": "online",
        "subnet": "192.168.178.0/24",
        "vpn": False,
        "connection": "lan",
        "category": "Server/NAS",
        "category_reason": "host:nas",
        "layout": {"connected_to": "192.168.178.1"},
    },
    {
        "ip": "192.168.178.103",
        "mac": TV,
        "hostname": "tv-vpn",
        "source": "tr064",
        "tr064_type": "VPN",
        "tr064_active": True,
        "vpn": True,
        "ports": [],
        "ip6": "",
        "vendor": "",
        "status": "online",
        "subnet": "192.168.178.0/24",
        "connection": "",
        "category": "Multimedia",
        "category_reason": "host:tv",
        "layout": {"connected_to": "192.168.178.1"},
    },
    {
        "ip": "192.168.178.102",
        "mac": "ip:192.168.178.102",
        "source": "tcp",
        "ports": [],
        "ip6": "",
        "vendor": "",
        "hostname": "",
        "status": "online",
        "subnet": "192.168.178.0/24",
        "vpn": False,
        "connection": "",
        "category": "Unbekannt",
        "category_reason": "",
        "layout": {"connected_to": "192.168.178.1"},
    },
]


@pytest.fixture()
def patched_scan(monkeypatch, tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    settings = Settings(
        data_dir=str(tmp_path),
        subnets="192.168.178.0/24",
        fritz_user="u",
        fritz_pass="p",
        snmp_enabled=False,
        mdns_enabled=False,
    )
    monkeypatch.setattr(
        run.discover,
        "discover",
        lambda subnets, timeout: [
            {"ip": "192.168.178.100", "mac": PC, "source": "ping+arp"},
            {"ip": "192.168.178.101", "mac": NAS, "source": "ping"},
            {"ip": "192.168.178.102", "mac": None, "source": "tcp"},
        ],
    )
    monkeypatch.setattr(run.discover, "neigh6_table", lambda: {})
    monkeypatch.setattr(
        run.ports,
        "scan_ports",
        lambda ip, ports_, timeout=0.5, workers=64: (
            [{"port": 445, "proto": "tcp", "service": "microsoft-ds"}] if ip == "192.168.178.101" else []
        ),
    )
    monkeypatch.setattr(
        run.names, "resolve_all", lambda ips_, use_mdns=False: {"192.168.178.100": "pc-1", "192.168.178.101": "nas"}
    )
    monkeypatch.setattr(run.names, "resolve_aaaa", lambda h: "")
    monkeypatch.setattr(run.topology, "gateway_ip", lambda: "192.168.178.1")
    monkeypatch.setattr(run.topology, "gateway_ip6", lambda: "")
    monkeypatch.setattr(run.oui, "lookup_online", lambda *a, **k: "")
    monkeypatch.setattr(run, "load_oui_table", lambda s: {})
    pipeline = sys.modules.get("app.scanner.pipeline")  # ab W7 liegt collect_devices dort
    if pipeline is not None:
        monkeypatch.setattr(pipeline, "load_oui_table", lambda s: {})
    hosts = [
        {"mac": PC, "ip": "192.168.178.100", "hostname": "pc-1", "active": True, "type": "802.11", "source": "tr064"},
        {"mac": NAS, "ip": "192.168.178.101", "hostname": "nas", "active": True, "type": "LAN", "source": "tr064"},
        {"mac": TV, "ip": "192.168.178.103", "hostname": "tv-vpn", "active": True, "type": "VPN", "source": "tr064"},
    ]
    monkeypatch.setattr(run.tr064, "fetch_hosts_with_fallback", lambda *a, **k: [dict(h) for h in hosts])
    monkeypatch.setattr(
        run.tr064,
        "fetch_wan_with_fallback",
        lambda *a, **k: {
            "wan_ip": "203.0.113.9",
            "status": "Connected",
            "error": "",
            "uptime": "100",
            "service": "urn:dslforum-org:service:WANIPConnection:1",
        },
    )
    return settings, conn


def test_collect_devices_output_unchanged(patched_scan):
    settings, conn = patched_scan
    devices = run.collect_devices(settings, conn)
    conn.close()
    assert sorted(devices, key=lambda d: d["mac"]) == EXPECTED
