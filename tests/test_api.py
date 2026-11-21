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
    assert body["version"] == "1.3.0"


def test_meta_public(client, app):
    conn = db.connect(app.state.db_path)
    db.set_setting(conn, "gateway", "192.168.178.1")
    db.set_setting(conn, "wan_ip", "79.227.229.246")
    db.set_setting(conn, "wan_status", "Connected")
    conn.commit()
    conn.close()
    r = client.get("/api/meta")
    assert r.status_code == 200
    assert r.json() == {"gateway": "192.168.178.1", "gateway6": "", "wan_ip": "79.227.229.246", "wan_status": "Connected"}


def test_layout_reset(auth_client, app):
    insert_device(app)
    conn = db.connect(app.state.db_path)
    db.set_layout(conn, "aa:bb:cc:dd:ee:ff", x=1.0, y=2.0, connected_to="11:22:33:44:55:66", connected_manual=1)
    conn.commit()
    conn.close()
    r = auth_client.post("/api/layout/reset")
    assert r.status_code == 200
    conn = db.connect(app.state.db_path)
    lay = db.get_layout(conn, "aa:bb:cc:dd:ee:ff")
    conn.close()
    assert lay["x"] is None and lay["y"] is None
    assert lay["connected_to"] == "11:22:33:44:55:66"
    assert lay["connected_manual"] == 1


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


def test_patch_connected_to_set_and_clear(auth_client, app):
    insert_device(app)
    r = auth_client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={"connected_to": "11:22:33:44:55:66"})
    assert r.status_code == 200
    assert r.json()["layout"]["connected_to"] == "11:22:33:44:55:66"
    assert r.json()["layout"]["connected_manual"] == 1
    r = auth_client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={"connected_to": ""})
    assert r.json()["layout"]["connected_to"] is None
    assert r.json()["layout"]["connected_manual"] == 0


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


def test_settings_validation(auth_client, app):
    assert auth_client.patch("/api/settings", json={"scan_interval": 5}).status_code == 422
    assert auth_client.patch("/api/settings", json={"scan_interval": 100000}).status_code == 422
    assert auth_client.patch("/api/settings", json={"port_top": 70000}).status_code == 422
    assert auth_client.patch("/api/settings", json={"port_top": -1}).status_code == 422
    assert auth_client.patch("/api/settings", json={"history_hours": 0}).status_code == 422
    assert auth_client.patch("/api/settings", json={"device_retention_days": -1}).status_code == 422
    assert auth_client.patch("/api/settings", json={"device_retention_days": 3651}).status_code == 422
    assert auth_client.patch("/api/settings", json={"device_retention_days": 0}).status_code == 200
    assert auth_client.patch("/api/settings", json={"device_retention_days": 14}).status_code == 200
    assert auth_client.patch("/api/settings", json={"subnets": "keine-ip"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"subnets": "192.168.1.0/24,10.0.0.0/8"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"subnets": "2003:db8::/64, 192.168.1.0/24"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"subnets": "2003:db8::/999"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"snmp_switches": "999.1.1.1"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"snmp_switches": "192.168.1.20, 10.0.0.5"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"theme": "blue"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"lang": "xx"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"lang": "pt"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"scan_timeout": 0.1}).status_code == 422
    assert auth_client.patch("/api/settings", json={"scan_timeout": 2.5}).status_code == 200
    assert auth_client.patch("/api/settings", json={"ports": "80,abc"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"ports": "80,443,8080"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"fritz_url": "192.168.178.1:49000"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"fritz_url": "kein endpoint!"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"fritz_urls": "http://192.168.178.14:49000, 192.168.178.16:49000"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"notify_webhook": "keine-url"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"notify_webhook": "https://hook.example/x"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"notify_ntfy": "https://ntfy.example/t"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"snmp_community": "mit leerzeichen"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"snmp_community": "public"}).status_code == 200
    body = auth_client.get("/api/settings").json()
    for secret in ("fritz_pass", "auth_pass", "notify_gotify_token", "notify_ntfy_token"):
        assert secret not in body, secret
    assert body["fritz_url"] == "192.168.178.1:49000"
    assert body["scan_timeout"] in (2.5, "2.5")
    assert auth_client.patch("/api/settings", json={"auto_export_dir": "../etc"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_dir": "/abs"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_interval_hours": -1}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_interval_hours": 721}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_interval_hours": 24}).status_code == 200
    assert auth_client.patch("/api/settings", json={"alarm_whitelist": "bogus!!"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"alarm_whitelist": "AA:BB:CC:DD:EE:FF, 192.168.178.50, 2003::1"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"mdns_enabled": False}).status_code == 200
    r = auth_client.patch("/api/settings", json={"scan_interval": 600})
    assert r.status_code == 200
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "scan_interval") == "600"
    conn.close()


def test_settings_get_patch(auth_client, app):
    r = auth_client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["scan_interval"] == 60
    assert body["auto_export_interval_hours"] == 24
    assert body["mdns_enabled"] is True
    assert body["alarm_whitelist"] == ""
    assert body["lang"] == "de"
    assert "auth_pass" not in body
    r = auth_client.patch("/api/settings", json={"theme": "light", "scan_interval": 120})
    assert r.status_code == 200
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "theme") == "light"
    assert db.get_setting(conn, "scan_interval") == "120"
    conn.close()


def test_sites_api_filter_export(auth_client, app):
    r = auth_client.get("/api/sites")
    assert r.status_code == 200
    assert r.json() == {"names": [], "map": {}}
    assert auth_client.patch("/api/settings", json={"sites": "Kaputt"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"sites": ":192.168.1.0/24"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"sites": "X:keine-ip"}).status_code == 422
    r = auth_client.patch("/api/settings", json={"sites": "Zuhause:192.168.178.0/24; Remote:192.168.179.0/24, 10.9.0.0/16"})
    assert r.status_code == 200
    body = auth_client.get("/api/sites").json()
    assert body["names"] == ["Remote", "Zuhause"]
    assert body["map"]["192.168.179.0/24"] == "Remote"
    assert body["map"]["10.9.0.0/16"] == "Remote"

    conn = db.connect(app.state.db_path)
    now = db.utcnow()
    for mac, ip, subnet in [
        ("aa:bb:cc:00:00:01", "192.168.178.10", "192.168.178.0/24"),
        ("aa:bb:cc:00:00:02", "192.168.179.20", "192.168.179.0/24"),
    ]:
        db.upsert_device(conn, {"mac": mac, "ip": ip, "hostname": "h-" + ip, "vendor": "", "category": "Client", "status": "online", "subnet": subnet, "source": "ping", "ports": [], "layout": {}}, now)
    conn.commit()
    conn.close()

    rows = {r["mac"]: r for r in auth_client.get("/api/devices").json()}
    assert rows["aa:bb:cc:00:00:01"]["site"] == "Zuhause"
    assert rows["aa:bb:cc:00:00:02"]["site"] == "Remote"
    only_remote = auth_client.get("/api/devices?site=Remote").json()
    assert [r["mac"] for r in only_remote] == ["aa:bb:cc:00:00:02"]
    assert auth_client.get("/api/device/aa:bb:cc:00:00:01").json()["site"] == "Zuhause"
    payload = auth_client.get("/api/export/json").json()
    sites = {d["mac"]: d["site"] for d in payload["devices"]}
    assert sites["aa:bb:cc:00:00:01"] == "Zuhause"
    csv_text = auth_client.get("/api/export/csv?sep=semicolon").text
    assert "site" in csv_text.splitlines()[0]
