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
    assert body["version"] == "1.6.18"


def test_meta_public(client, app):
    conn = db.connect(app.state.db_path)
    db.set_setting(conn, "gateway", "192.168.178.1")
    db.set_setting(conn, "wan_ip", "203.0.113.10")
    db.set_setting(conn, "wan_status", "Connected")
    db.set_setting(conn, "wan_endpoint", "fritz.box")
    conn.commit()
    conn.close()
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["gateway"] == "192.168.178.1" and body["wan_ip"] == "203.0.113.10"
    assert body["wan_endpoint"] == "fritz.box"  # TR-064-Router-Endpunkt wird mitgeliefert
    assert body["version"]  # Version wird mitgeliefert


def insert_parent(app, mac="11:22:33:44:55:66"):
    conn = db.connect(app.state.db_path)
    db.upsert_device(conn, {"mac": mac, "ip": "192.168.1.2", "status": "online", "category": "Switch"}, db.utcnow())
    conn.commit()
    conn.close()


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
    insert_parent(app)
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


def test_patch_room_and_rooms_api(auth_client, app):
    insert_device(app)
    r = auth_client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={"room": "  EG Wohnzimmer  "})
    assert r.status_code == 200
    assert r.json()["room"] == "EG Wohnzimmer"  # getrimmt
    assert len(r.json()["room"]) <= 64
    assert auth_client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={"room": "x" * 65}).status_code == 422
    rooms = auth_client.get("/api/rooms").json()
    assert rooms == ["EG Wohnzimmer"]
    # Listen-API liefert room mit und filtert danach
    lst = auth_client.get("/api/devices").json()
    assert lst[0]["room"] == "EG Wohnzimmer"
    assert auth_client.get("/api/devices?room=EG%20Wohnzimmer").json()[0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert auth_client.get("/api/devices?room=OG").json() == []
    # Exporte enthalten room (JSON + CSV-Header)
    assert auth_client.get("/api/export/json").json()["devices"][0]["room"] == "EG Wohnzimmer"
    header = auth_client.get("/api/export/csv").text.splitlines()[0]
    assert "room" in header
    # Leerer Raum loeschen
    r = auth_client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={"room": ""})
    assert r.json()["room"] == ""
    assert auth_client.get("/api/rooms").json() == []


def test_patch_connected_to_set_and_clear(auth_client, app):
    insert_device(app)
    insert_parent(app)
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
    assert (
        auth_client.patch(
            "/api/settings", json={"fritz_urls": "http://192.168.178.14:49000, 192.168.178.16:49000"}
        ).status_code
        == 200
    )
    assert auth_client.patch("/api/settings", json={"notify_webhook": "keine-url"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"notify_webhook": "https://hook.example/x"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"notify_ntfy": "https://ntfy.example/t"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"snmp_community": "mit leerzeichen"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"snmp_community": "public"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"oui_online_max": -1}).status_code == 422
    assert auth_client.patch("/api/settings", json={"oui_online_max": 25}).status_code == 200
    assert auth_client.patch("/api/settings", json={"oui_online_url": "keine-url"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"oui_online_url": "https://api.macvendors.com"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"oui_online_enabled": False}).status_code == 200
    body = auth_client.get("/api/settings").json()
    # S-8: Secrets nie im Klartext, sondern als {"configured": bool}; auth_pass ist env-only und gar nicht im GET
    assert "auth_pass" not in body
    for secret in ("fritz_pass", "notify_gotify_token", "notify_ntfy_token"):
        assert body[secret] == {"configured": False}, secret
    assert body["snmp_community"] == {"configured": True}  # wurde oben auf "public" gesetzt
    assert body["fritz_url"] == "192.168.178.1:49000"
    assert body["scan_timeout"] in (2.5, "2.5")
    assert auth_client.patch("/api/settings", json={"auto_export_dir": "../etc"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_dir": "/abs"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_interval_hours": -1}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_interval_hours": 721}).status_code == 422
    assert auth_client.patch("/api/settings", json={"auto_export_interval_hours": 24}).status_code == 200
    assert auth_client.patch("/api/settings", json={"alarm_whitelist": "bogus!!"}).status_code == 422
    assert (
        auth_client.patch(
            "/api/settings", json={"alarm_whitelist": "AA:BB:CC:DD:EE:FF, 192.168.178.50, 2003::1"}
        ).status_code
        == 200
    )
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
    r = auth_client.patch(
        "/api/settings", json={"sites": "Zuhause:192.168.178.0/24; Remote:192.168.179.0/24, 10.9.0.0/16"}
    )
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
        db.upsert_device(
            conn,
            {
                "mac": mac,
                "ip": ip,
                "hostname": "h-" + ip,
                "vendor": "",
                "category": "Client",
                "status": "online",
                "subnet": subnet,
                "source": "ping",
                "ports": [],
                "layout": {},
            },
            now,
        )
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


def test_fritz_pass_write_only(auth_client, app):
    r = auth_client.patch("/api/settings", json={"fritz_pass": "geheim123"})
    assert r.status_code == 200
    body = auth_client.get("/api/settings").json()
    assert body["fritz_pass"] == {"configured": True}  # S-8: write-only, nur configured im GET
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "fritz_pass") == "geheim123"
    conn.close()
    assert auth_client.patch("/api/settings", json={"fritz_pass": "x" * 257}).status_code == 422


def test_export_pdf(auth_client, client, app):
    import base64 as b64

    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    r = auth_client.post("/api/export/pdf", json={"image": "data:image/png;base64," + png_b64, "title": "Testkarte"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert "fox_netmap.pdf" in r.headers.get("content-disposition", "")
    # ohne Bild -> nur Kopf + Tabelle
    r2 = auth_client.post("/api/export/pdf", json={})
    assert r2.status_code == 200 and r2.content.startswith(b"%PDF")
    # ungueltiges base64
    assert auth_client.post("/api/export/pdf", json={"image": "data:image/png;base64,!!!"}).status_code == 422
    # falsches Format (GIF-Magic)
    gif = b64.b64encode(b"GIF89a").decode()
    assert auth_client.post("/api/export/pdf", json={"image": "data:image/gif;base64," + gif}).status_code == 422
    # kaputtes PNG (Magic ok, Daten Muell)
    bad = b64.b64encode(b"\x89PNG\r\n\x1a\n" + b"garbage").decode()
    assert auth_client.post("/api/export/pdf", json={"image": "data:image/png;base64," + bad}).status_code == 422
    # ohne Session -> 401; mit gueltigem Token -> 200 (TOKEN_PATHS deckt /api/export/ ab)
    from fastapi.testclient import TestClient

    anon0 = TestClient(app)
    assert anon0.post("/api/export/pdf", json={}).status_code == 401
    insert_device(app)
    tok = auth_client.post("/api/tokens", json={"expires_hours": 24}).json()["token"]
    r3 = anon0.post(f"/api/export/pdf?token={tok}", json={})
    assert r3.status_code == 200 and r3.content.startswith(b"%PDF")


def _pdf_mediabox(pdf: bytes):
    import re

    m = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
    assert m, "kein MediaBox gefunden"
    return float(m.group(1)), float(m.group(2))


def _pdf_text(pdf: bytes) -> bytes:
    """Rohe PDF-Bytes + alle FlateDecode-Streams entpackt (damit Text assertions greifen)."""
    import re
    import zlib
    from contextlib import suppress

    out = pdf
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        with suppress(Exception):
            out += zlib.decompress(m.group(1))
    return out


def test_export_pdf_orientation(auth_client):
    r = auth_client.post("/api/export/pdf", json={})
    assert r.status_code == 200
    w, h = _pdf_mediabox(r.content)
    assert w < h  # A4 portrait
    r = auth_client.post("/api/export/pdf", json={"orientation": "landscape"})
    assert r.status_code == 200
    w, h = _pdf_mediabox(r.content)
    assert w > h  # A4 quer
    assert auth_client.post("/api/export/pdf", json={"orientation": "diagonal"}).status_code == 422


def test_build_pdf_wraps_long_cells(app):
    from app import exporters

    settings = app.state.settings
    rows = [
        {
            "hostname": "Sehr-Langer-Hostname-" * 5,
            "ip": "192.168.178.10",
            "mac": "02:00:00:8e:ee:06",
            "vendor": "TP-LINK TECHNOLOGIES CO.,LTD. International",
            "category": "Switch",
            "status": "online",
            "subnet": "192.168.178.0/24",
            "connected_to": "192.168.178.1",
            "ports_str": ";".join(str(p) for p in range(1, 200)),
        }
    ]
    pdf = exporters.build_pdf(settings, rows, None, title="T<b>bold</b>&Co")
    assert pdf.startswith(b"%PDF")
    # escaping greift: Markup landet literal im Text, wird nicht als Tag geparst
    assert b"T<b>bold</b>&Co" in _pdf_text(pdf)
    w, h = _pdf_mediabox(pdf)
    assert w < h
    pdf_ls = exporters.build_pdf(settings, rows, None, orientation="landscape")
    assert pdf_ls.startswith(b"%PDF")
    w, h = _pdf_mediabox(pdf_ls)
    assert w > h


def test_meta_includes_version(auth_client, app):
    body = auth_client.get("/api/meta").json()
    assert body["version"] == app.state.settings.app_version


def test_ip6_column_and_upsert(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)")}
    assert "ip6" in cols
    db.upsert_device(conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.10", "ip6": "2001:db8::10"}, db.utcnow())
    conn.commit()
    row = db.get_device(conn, "aa:bb:cc:dd:ee:ff")
    assert row["ip6"] == "2001:db8::10"
    # Update ohne ip6-Schlüssel -> leer, bleibt erhalten bei gesetztem Wert
    db.upsert_device(conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.10", "ip6": "2001:db8::11"}, db.utcnow())
    conn.commit()
    assert db.get_device(conn, "aa:bb:cc:dd:ee:ff")["ip6"] == "2001:db8::11"
    conn.close()


def test_device_detail_and_export_include_ip6(auth_client, app):
    conn = db.connect(app.state.db_path)
    db.upsert_device(conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.10", "ip6": "2001:db8::10"}, db.utcnow())
    conn.commit()
    conn.close()
    d = auth_client.get("/api/device/aa:bb:cc:dd:ee:ff").json()
    assert d["ip6"] == "2001:db8::10"
    payload = auth_client.get("/api/export/json").json()
    assert payload["devices"][0]["ip6"] == "2001:db8::10"
    csv_text = auth_client.get("/api/export/csv").text
    assert "ip6" in csv_text.splitlines()[0]
    assert "2001:db8::10" in csv_text


def test_settings_vpn_pool(auth_client, app):
    r = auth_client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["vpn_pool"] == "off"  # Default: keine Pool-Annahme
    assert auth_client.patch("/api/settings", json={"vpn_pool": "keine-ip"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"vpn_pool": "192.168.178.210-192.168.178.201"}).status_code == 422
    assert (
        auth_client.patch(
            "/api/settings", json={"vpn_pool": "auto, 10.8.0.0/24, 192.168.178.201-192.168.178.210"}
        ).status_code
        == 200
    )
    assert auth_client.patch("/api/settings", json={"vpn_pool": "off"}).status_code == 200
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "vpn_pool") == "off"
    conn.close()


def test_devices_api_und_export_mit_vpn(auth_client, app):
    conn = db.connect(app.state.db_path)
    db.upsert_device(
        conn,
        {
            "mac": "00:7a:a4:9b:d9:68",
            "ip": "192.168.178.201",
            "vpn": True,
            "status": "online",
            "category": "Unbekannt",
            "hostname": "fritz.box",
            "link_port": "LAN:2",
            "connection": "lan",
        },
        db.utcnow(),
    )
    conn.commit()
    conn.close()
    rows = auth_client.get("/api/devices").json()
    dev = next(r for r in rows if r["mac"] == "00:7a:a4:9b:d9:68")
    assert dev["vpn"] == 1
    assert auth_client.get("/api/device/00:7a:a4:9b:d9:68").json()["vpn"] == 1
    payload = auth_client.get("/api/export/json").json()
    jdev = next(d for d in payload["devices"] if d["mac"] == "00:7a:a4:9b:d9:68")
    assert jdev["vpn"] is True
    assert jdev["link_port"] == "LAN:2"
    csv_text = auth_client.get("/api/export/csv").text
    lines = csv_text.splitlines()
    header = lines[0].split(";")
    assert "vpn" in header
    assert "link_port" in header
    row = next(line for line in lines[1:] if line.startswith("00:7a:a4:9b:d9:68"))
    assert row.split(";")[header.index("vpn")] == "ja"
    assert row.split(";")[header.index("link_port")] == "LAN:2"


def test_settings_tr064_insecure_tls_roundtrip(auth_client):
    body = auth_client.get("/api/settings").json()
    assert "tr064_insecure_tls" in body
    assert auth_client.patch("/api/settings", json={"tr064_insecure_tls": True}).status_code == 200
    assert str(auth_client.get("/api/settings").json()["tr064_insecure_tls"]).lower() == "true"
    assert auth_client.patch("/api/settings", json={"tr064_insecure_tls": False}).status_code == 200
    assert str(auth_client.get("/api/settings").json()["tr064_insecure_tls"]).lower() == "false"
