from fastapi.testclient import TestClient

from app import db


def insert_device(app, mac="aa:bb:cc:dd:ee:ff"):
    conn = db.connect(app.state.db_path)
    db.init_db(conn)
    now = db.utcnow()
    db.upsert_device(
        conn,
        {
            "mac": mac,
            "ip": "192.168.1.10",
            "hostname": "nas",
            "vendor": "Synology",
            "category": "Server/NAS",
            "status": "online",
            "subnet": "192.168.1.0/24",
            "source": "ping+arp",
        },
        now,
    )
    db.replace_ports(conn, mac, [{"port": 443, "service": "https"}], now)
    conn.commit()
    conn.close()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["devices"] == 0


def test_api_requires_auth(client):
    assert client.get("/api/devices").status_code == 401
    assert client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={}).status_code == 401
    assert client.post("/api/scan").status_code == 401
    assert client.get("/", follow_redirects=False).status_code == 303


def test_login_flow(client):
    assert client.post("/api/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    r = client.post("/api/login", json={"username": "admin", "password": "secret"})
    assert r.status_code == 200
    assert client.get("/api/me").status_code == 200
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_devices_list_filter_patch(auth_client, app):
    insert_device(app)
    rows = auth_client.get("/api/devices").json()
    assert len(rows) == 1
    assert rows[0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert len(auth_client.get("/api/devices?category=Drucker").json()) == 0
    assert len(auth_client.get("/api/devices?q=synology").json()) == 1
    r = auth_client.patch(
        "/api/device/aa:bb:cc:dd:ee:ff",
        json={"category": "Drucker", "note": "buero", "x": 10, "y": 20, "connected_to": "11:22:33:44:55:66"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "Drucker"
    assert body["note"] == "buero"
    assert body["layout"]["connected_to"] == "11:22:33:44:55:66"
    assert auth_client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={"category": "bogus"}).status_code == 422
    assert auth_client.patch("/api/device/00:00:00:00:00:00", json={"note": "x"}).status_code == 404
    detail = auth_client.get("/api/device/aa:bb:cc:dd:ee:ff").json()
    assert detail["ports"][0]["port"] == 443


def test_scan_trigger(auth_client, app):
    r = auth_client.post("/api/scan")
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "scan_requested")
    conn.close()
    status = auth_client.get("/api/scan/status").json()
    assert "scanning" in status


def test_export_json_csv(auth_client, app):
    insert_device(app)
    r = auth_client.get("/api/export/json")
    assert r.status_code == 200
    payload = r.json()
    assert payload["app"] == "fox_netmap"
    assert payload["device_count"] == 1
    assert payload["devices"][0]["ports"] == [443]
    assert payload["devices"][0]["mac"] == "aa:bb:cc:dd:ee:ff"
    r = auth_client.get("/api/export/csv?sep=semicolon")
    assert r.status_code == 200
    lines = r.text.splitlines()
    assert lines[0].startswith("mac;ip;")
    assert "aa:bb:cc:dd:ee:ff" in lines[1]
    assert "443" in lines[1]
    r = auth_client.get("/api/export/csv?sep=comma")
    assert lines[0].split(",")[0] == "mac" or r.text.splitlines()[0].startswith("mac,")


def test_embed_token_flow(auth_client, app):
    insert_device(app)
    r = auth_client.post("/api/tokens", json={"expires_hours": 24, "subnets": "192.168.1.0/24"})
    assert r.status_code == 200
    token = r.json()["token"]
    anon = TestClient(app)
    assert anon.get("/api/devices").status_code == 401
    assert anon.get(f"/api/devices?token={token}").status_code == 200
    assert len(anon.get(f"/api/devices?token={token}").json()) == 1
    assert anon.get("/api/devices?token=bogus").status_code == 403
    assert anon.get(f"/embed?token={token}").status_code == 200
    assert anon.get("/embed?token=bogus").status_code == 403
    assert auth_client.get("/api/tokens").status_code == 200
    assert auth_client.delete(f"/api/tokens/{token}").status_code == 200
    assert anon.get(f"/api/devices?token={token}").status_code == 403


def test_logs_endpoint(auth_client, app):
    from fastapi.testclient import TestClient

    logfile = app.state.settings.data_dir + "/netmap.log"
    with open(logfile, "w", encoding="utf-8") as fh:
        fh.write("2026-01-01 10:00:00 INFO fox_netmap: Scan fertig: 3 Geraete, 0 neu\n")
        fh.write("2026-01-01 10:00:01 ERROR fox_netmap scanner: Scan-Fehler: boom\n")
    r = auth_client.get("/api/logs")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2 and body["returned"] == 2
    assert any("ERROR" in line for line in body["lines"])
    r = auth_client.get("/api/logs?level=ERROR")
    assert r.json()["returned"] == 1
    assert "Scan-Fehler" in r.json()["lines"][0]
    r = auth_client.get("/api/logs?lines=1")
    assert r.json()["returned"] == 1
    r = auth_client.get("/api/logs/download")
    assert r.status_code == 200
    assert "Scan-Fehler" in r.text
    assert TestClient(app).get("/api/logs").status_code == 401


def test_settings_get_patch(auth_client, app):
    r = auth_client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["scan_interval"] == 60
    assert "auth_pass" not in body
    r = auth_client.patch("/api/settings", json={"theme": "light", "scan_interval": 120})
    assert r.status_code == 200
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "theme") == "light"
    assert db.get_setting(conn, "scan_interval") == "120"
    conn.close()
