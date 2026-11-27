"""T-13 (W6): API-Vertrag - Schluesselmengen der Antworten als Snapshot festgehalten.
Die jsdom-Fixture (tests/ui/devs_fixture.mjs) wird ueber tests/fixtures/api_devices_sample.json
(gegen die echte API erzeugt) auf Paritaet geprueft (tests/ui/fixture_parity.mjs)."""

import json
from pathlib import Path

from app import db
from app.scanner import run
from app.settings_schema import FIELDS, exposed_fields

REPO = Path(__file__).resolve().parents[1]

# devices-Tabelle (18 Spalten nach Migration) + port_count, ports_str, x, y, connected_to + site
DEVICE_ROW_KEYS = {
    "mac",
    "ip",
    "hostname",
    "vendor",
    "category",
    "category_override",
    "status",
    "subnet",
    "source",
    "note",
    "first_seen",
    "last_seen",
    "connection",
    "ip6",
    "link_port",
    "category_reason",
    "vpn",
    "room",
    "port_count",
    "ports_str",
    "x",
    "y",
    "connected_to",
    "site",
}
META_KEYS = {"version", "gateway", "gateway6", "wan_ip", "wan_status", "wan_endpoint"}


def _dev(mac: str, ip: str, **kw) -> dict:
    base = {
        "mac": mac,
        "ip": ip,
        "hostname": "",
        "vendor": "",
        "category": "Client",
        "status": "online",
        "subnet": "10.0.0.0/24",
        "source": "ping+arp",
        "ports": [],
        "layout": {},
    }
    base.update(kw)
    return base


def _seed_sample_devices(app, settings) -> None:
    """Dieselben fuenf Geraete wie die jsdom-Fixture tests/ui/devs_fixture.mjs."""
    devs = [
        _dev(
            "aa:bb:cc:dd:ee:ff",
            "10.0.0.5",
            hostname="nas",
            vendor="Synology",
            category="Server/NAS",
            ip6="2001:db8::10",
            subnet="10.0.0.0/24",
            room="Keller",
            source="ping+arp,tr064",
            ports=[{"port": 80, "proto": "tcp", "service": "http"}, {"port": 443, "proto": "tcp", "service": "https"}],
            layout={"connected_to": "10.0.0.1"},
        ),
        _dev(
            "ip:192.168.179.20",
            "192.168.179.20",
            hostname="remote-plug",
            category="Smart-Home/IoT",
            status="offline",
            subnet="192.168.179.0/24",
            source="tcp",
            layout={"connected_to": "02:00:00:8e:ee:06"},
        ),
        _dev(
            "02:00:00:8e:ee:06",
            "192.168.178.10",
            hostname="TL-SG108E-GZ",
            vendor="TP-Link",
            category="Switch",
            subnet="192.168.178.0/24",
            ports=[{"port": 80, "proto": "tcp", "service": "http"}],
            layout={"connected_to": "192.168.178.1"},
        ),
        _dev(
            "aa:bb:cc:00:11:22",
            "192.168.178.77",
            hostname="wlan-tv",
            category="Smart-Home/IoT",
            subnet="192.168.178.0/24",
            source="tr064",
            room="EG-Wohnzimmer",
            vpn=True,
            connection="wlan",
            layout={"connected_to": "wlan:192.168.178.1"},
        ),
        _dev(
            "76:84:18:83:f1:3c",
            "",
            hostname="PC-76-84-18-83-F1-3C",
            source="tr064",
            layout={"connected_to": "192.168.178.1"},
        ),
    ]
    conn = db.connect(app.state.db_path)
    try:
        run.apply_scan(conn, settings, devs)
    finally:
        conn.close()


def test_devices_response_keys_snapshot(auth_client, app, settings):
    _seed_sample_devices(app, settings)
    rows = auth_client.get("/api/devices").json()
    assert len(rows) == 5
    assert all(set(r) == DEVICE_ROW_KEYS for r in rows)


def test_meta_response_keys_snapshot(auth_client):
    assert set(auth_client.get("/api/meta").json()) == META_KEYS


def test_settings_response_keys_snapshot(auth_client):
    body = auth_client.get("/api/settings").json()
    assert set(body) == set(exposed_fields()) | {"version", "auth_user", "notify_configured"}
    # S-8: Secrets erscheinen nie im Klartext, nur als konfiguriert-Flag
    for key, field in FIELDS.items():
        if field.secret and field.exposed:
            assert set(body[key]) == {"configured"} and isinstance(body[key]["configured"], bool)


def test_api_devices_sample_matches_committed_fixture(auth_client, app, settings):
    """Die committete API-Beispielantwort (tests/fixtures/api_devices_sample.json) deckt dieselben
    Geraete und Schluessel ab wie eine frische Antwort der echten API."""
    _seed_sample_devices(app, settings)
    rows = auth_client.get("/api/devices").json()
    sample = json.loads((REPO / "tests" / "fixtures" / "api_devices_sample.json").read_text(encoding="utf-8"))
    assert sorted(r["mac"] for r in rows) == sorted(d["mac"] for d in sample)
    assert all(set(r) == set(d) == DEVICE_ROW_KEYS for r in rows for d in sample if r["mac"] == d["mac"])
