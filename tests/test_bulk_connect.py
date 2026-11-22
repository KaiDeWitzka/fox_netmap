"""Mehrfach-Zuordnung von Hand: mehrere Geräte gemeinsam an einen Netzknoten hängen (v1.6.0)."""

from app import db

SW = "02:00:00:8e:ee:06"
A = "aa:aa:aa:aa:aa:01"
B = "aa:aa:aa:aa:aa:02"
C = "aa:aa:aa:aa:aa:03"


def _setup(app):
    conn = db.connect(app.state.db_path)
    now = db.utcnow()
    for mac, ip, cat in [(SW, "192.168.178.10", "Switch"), (A, "192.168.178.21", "Client"),
                         (B, "192.168.178.22", "Client"), (C, "192.168.178.23", "Switch")]:
        db.upsert_device(conn, {"mac": mac, "ip": ip, "status": "online", "category": cat}, now)
    conn.commit()
    conn.close()


def _layout(app, mac):
    conn = db.connect(app.state.db_path)
    try:
        row = conn.execute("SELECT connected_to, connected_manual FROM device_layout WHERE mac = ?", (mac,)).fetchone()
        return (row["connected_to"], row["connected_manual"]) if row else (None, 0)
    finally:
        conn.close()


def test_mehrere_geraete_gemeinsam_zuordnen(auth_client, app):
    _setup(app)
    r = auth_client.post("/api/devices/connect", json={"macs": [A, B, A], "connected_to": SW})
    assert r.status_code == 200 and r.json() == {"ok": True, "count": 2}
    assert _layout(app, A) == (SW, 1) and _layout(app, B) == (SW, 1)


def test_zuordnung_zuruecksetzen_auf_automatisch(auth_client, app):
    _setup(app)
    auth_client.post("/api/devices/connect", json={"macs": [A, B], "connected_to": SW})
    assert auth_client.post("/api/devices/connect", json={"macs": [A, B], "connected_to": ""}).status_code == 200
    assert _layout(app, A) == (None, 0) and _layout(app, B) == (None, 0)


def test_manuelle_zuordnung_ueberlebt_scan(auth_client, app, settings):
    from app.scanner.run import apply_scan

    _setup(app)
    auth_client.post("/api/devices/connect", json={"macs": [A], "connected_to": SW})
    conn = db.connect(app.state.db_path)
    apply_scan(conn, settings, [{"mac": A, "ip": "192.168.178.21", "ports": [], "layout": {"connected_to": "192.168.178.1"}}])
    conn.close()
    assert _layout(app, A) == (SW, 1)


def test_unbekanntes_geraet_alles_oder_nichts(auth_client, app):
    _setup(app)
    r = auth_client.post("/api/devices/connect", json={"macs": [A, "00:00:00:00:00:99"], "connected_to": SW})
    assert r.status_code == 404
    assert _layout(app, A) == (None, 0)


def test_unbekanntes_ziel_abgelehnt(auth_client, app):
    _setup(app)
    assert auth_client.post("/api/devices/connect", json={"macs": [A], "connected_to": "00:00:00:00:00:99"}).status_code == 422


def test_selbstbezug_abgelehnt(auth_client, app):
    _setup(app)
    assert auth_client.post("/api/devices/connect", json={"macs": [A, SW], "connected_to": SW}).status_code == 422
    assert auth_client.patch(f"/api/device/{SW}", json={"connected_to": SW}).status_code == 422


def test_zyklus_abgelehnt(auth_client, app):
    _setup(app)
    # C haengt am Switch; den Switch an C zu haengen ergaebe einen Kreis
    assert auth_client.post("/api/devices/connect", json={"macs": [C], "connected_to": SW}).status_code == 200
    r = auth_client.post("/api/devices/connect", json={"macs": [SW, A], "connected_to": C})
    assert r.status_code == 422 and "cycle" in r.json()["detail"]
    assert _layout(app, SW) == (None, 0) and _layout(app, A) == (None, 0)
    # auch ueber die Einzelzuordnung
    assert auth_client.patch(f"/api/device/{SW}", json={"connected_to": C}).status_code == 422


def test_zyklus_ueber_ip_kette_erkannt(auth_client, app):
    _setup(app)
    conn = db.connect(app.state.db_path)
    db.set_layout(conn, C, connected_to="192.168.178.10")  # automatisch: C haengt per IP am Switch
    conn.commit()
    conn.close()
    assert auth_client.post("/api/devices/connect", json={"macs": [SW], "connected_to": C}).status_code == 422


def test_grenzen_und_login(client, auth_client, app):
    _setup(app)
    assert auth_client.post("/api/devices/connect", json={"macs": [], "connected_to": SW}).status_code == 422
    assert auth_client.post("/api/devices/connect", json={"macs": [A] * 1001, "connected_to": SW}).status_code == 422
    assert auth_client.post("/api/devices/connect", json={"macs": [A], "connected_to": "x" * 65}).status_code == 422
    auth_client.post("/api/logout")
    assert client.post("/api/devices/connect", json={"macs": [A], "connected_to": SW}).status_code == 401
