"""T-7 (W6): Ende-zu-Ende in pytest - Scanner-Lauf (collect_devices gepatcht) -> Datenbank -> API -> Export.
Web und Scanner laufen zusammen; nur die eigentliche Netz-Erkennung ist ersetzt."""

from app import db
from app.scanner import run


def _dev(mac: str, ip: str, **kw) -> dict:
    base = {
        "mac": mac,
        "ip": ip,
        "hostname": "nas",
        "vendor": "Synology",
        "category": "Server/NAS",
        "status": "online",
        "subnet": "10.0.0.0/24",
        "source": "ping+arp",
        "ports": [{"port": 443, "proto": "tcp", "service": "https"}],
        "layout": {"connected_to": "10.0.0.1"},
    }
    base.update(kw)
    return base


def test_scan_result_visible_via_api(auth_client, app, settings, monkeypatch):
    monkeypatch.setattr(run, "collect_devices", lambda s, c: [_dev("aa:bb:cc:dd:ee:ff", "10.0.0.5")])
    conn = db.connect(app.state.db_path)
    try:
        summary = run.run_once(settings, conn)
    finally:
        conn.close()
    assert summary["seen"] == 1 and summary["new"] == 1

    rows = auth_client.get("/api/devices").json()
    assert [r["mac"] for r in rows] == ["aa:bb:cc:dd:ee:ff"]
    assert rows[0]["hostname"] == "nas" and rows[0]["port_count"] == 1 and rows[0]["status"] == "online"

    detail = auth_client.get("/api/device/aa:bb:cc:dd:ee:ff").json()
    assert detail["ports"][0]["port"] == 443 and detail["layout"]["connected_to"] == "10.0.0.1"

    export = auth_client.get("/api/export/json")
    assert export.status_code == 200 and "aa:bb:cc:dd:ee:ff" in export.text

    pdf = auth_client.post("/api/export/pdf", json={})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    status = auth_client.get("/api/scan/status").json()
    assert status["scanning"] == 0 and status["last_scan"]
