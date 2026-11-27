"""Sicherheits- und Datenschutzpunkte v1.6.0: Ereignis-Loeschfrist, Gotify-Header, gehashte Embed-Tokens, SNMP ohne Default."""

import logging
from datetime import UTC, datetime, timedelta

from app import db
from app.config import Settings
from app.scanner import notify, run


def _ts(days_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def _conn(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    return conn


# ---- Ereignisse ----


def test_ereignisse_aktiver_geraete_werden_nach_frist_geloescht(tmp_path):
    conn = _conn(tmp_path)
    db.upsert_device(conn, {"mac": "aa:aa:aa:aa:aa:01", "ip": "10.0.0.1", "status": "online"}, _ts(0))
    db.add_event(conn, "aa:aa:aa:aa:aa:01", "ports", "alt", _ts(120))
    db.add_event(conn, "aa:aa:aa:aa:aa:01", "online", "neu", _ts(1))
    assert db.trim_events(conn, 90) == 1
    left = [r["detail"] for r in conn.execute("SELECT detail FROM device_events")]
    assert left == ["neu"]


def test_ereignisse_frist_null_loescht_nie(tmp_path):
    conn = _conn(tmp_path)
    db.add_event(conn, "aa:aa:aa:aa:aa:01", "ports", "alt", _ts(5000))
    assert db.trim_events(conn, 0) == 0
    assert conn.execute("SELECT COUNT(*) FROM device_events").fetchone()[0] == 1


def test_apply_scan_wendet_frist_an(tmp_path):
    conn = _conn(tmp_path)
    db.add_event(conn, "aa:aa:aa:aa:aa:01", "ports", "alt", _ts(40))
    run.apply_scan(conn, Settings(data_dir=str(tmp_path), event_retention_days=30), [])
    assert conn.execute("SELECT COUNT(*) FROM device_events").fetchone()[0] == 0


def test_standard_frist_90_tage():
    # T-8 (W6): billiger Wachposten - Konstanten-Check, kein Verhaltenstest
    assert Settings().event_retention_days == 90


def test_settings_api_frist(auth_client):
    assert auth_client.patch("/api/settings", json={"event_retention_days": 30}).status_code == 200
    assert auth_client.get("/api/settings").json()["event_retention_days"] in (30, "30")
    assert auth_client.patch("/api/settings", json={"event_retention_days": 4000}).status_code == 422
    assert auth_client.patch("/api/settings", json={"event_retention_days": -1}).status_code == 422


# ---- Gotify ----


class _Resp:
    def __init__(self, code=200):
        self.status_code = code


def test_gotify_token_im_header_nicht_in_url(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.httpx, "post", lambda url, **kw: calls.append((url, kw)) or _Resp())
    s = Settings(notify_gotify="https://gotify.local/", notify_gotify_token="geheim123")
    notify.notify_new_devices(s, [{"mac": "aa:bb:cc:dd:ee:ff", "ip": "10.0.0.5", "hostname": "x"}])
    url, kw = calls[0]
    assert url == "https://gotify.local/message"
    assert "geheim123" not in url
    assert kw["headers"]["X-Gotify-Key"] == "geheim123"
    assert kw["follow_redirects"] is False


def test_benachrichtigungsfehler_ohne_geheimnisse_im_log(monkeypatch, caplog):
    def boom(url, **kw):
        raise RuntimeError(f"connect failed {url} {kw.get('headers')}")

    monkeypatch.setattr(notify.httpx, "post", boom)
    s = Settings(
        notify_gotify="https://gotify.local",
        notify_gotify_token="geheim123",
        notify_webhook="https://hook.local/x?key=hooksecret",
    )
    with caplog.at_level(logging.WARNING, logger="netmap.notify"):
        notify.notify_new_devices(s, [{"mac": "aa:bb:cc:dd:ee:ff", "ip": "10.0.0.5"}])
    assert "Gotify-Benachrichtigung fehlgeschlagen: RuntimeError" in caplog.text
    assert "geheim123" not in caplog.text and "hooksecret" not in caplog.text


def test_benachrichtigung_http_fehler_wird_gemeldet(monkeypatch, caplog):
    monkeypatch.setattr(notify.httpx, "post", lambda url, **kw: _Resp(401))
    with caplog.at_level(logging.WARNING, logger="netmap.notify"):
        notify.notify_new_devices(Settings(notify_ntfy="https://ntfy.local/t"), [{"mac": "m", "ip": "i"}])
    assert "ntfy-Benachrichtigung abgelehnt: HTTP 401" in caplog.text


# ---- Embed-Tokens ----


def test_token_nur_als_hash_gespeichert(auth_client, app):
    tok = auth_client.post("/api/tokens", json={"expires_hours": 24}).json()["token"]
    conn = db.connect(app.state.db_path)
    stored = [r["token"] for r in conn.execute("SELECT token FROM embed_tokens")]
    assert stored == [db.token_key(tok)] and tok not in stored[0]
    listing = auth_client.get("/api/tokens").json()
    assert "token" not in listing[0] and listing[0]["hint"] == tok[:6]
    assert tok not in auth_client.get("/api/tokens").text
    assert auth_client.get(f"/api/devices?token={tok}").status_code == 200
    assert auth_client.delete(f"/api/tokens/{listing[0]['id']}").status_code == 200
    assert auth_client.get("/api/tokens").json() == []


def test_alte_klartext_tokens_werden_migriert(tmp_path):
    conn = _conn(tmp_path)
    conn.execute(
        "INSERT INTO embed_tokens (token, expires, subnets, categories, created) VALUES ('altestoken123', '', '', '', 'x')"
    )
    conn.commit()
    db.init_db(conn)
    row = conn.execute("SELECT token, hint FROM embed_tokens").fetchone()
    assert row["token"] == db.token_key("altestoken123") and row["hint"] == "altest"
    assert db.get_valid_token(conn, "altestoken123") is not None
    assert db.get_valid_token(conn, row["token"]) is None  # der Hash selbst ist kein gueltiges Token
    db.init_db(conn)  # idempotent
    assert conn.execute("SELECT COUNT(*) FROM embed_tokens").fetchone()[0] == 1


def test_leeres_token_ungueltig(tmp_path):
    assert db.get_valid_token(_conn(tmp_path), "") is None


# ---- SNMP ----


def test_snmp_ohne_community_wird_uebersprungen(tmp_path, monkeypatch, caplog):
    assert Settings().snmp_community == ""
    conn = _conn(tmp_path)

    def nie(*a, **k):
        raise AssertionError("SNMP darf ohne Community nicht abgefragt werden")

    monkeypatch.setattr(run.snmp, "cam_map", nie)
    monkeypatch.setattr(run.snmp, "lldp_map", nie)
    monkeypatch.setattr(
        run.discover,
        "discover",
        lambda subnets, timeout: [{"ip": "10.0.0.2", "mac": "aa:aa:aa:aa:aa:02", "source": "ping"}],
    )
    monkeypatch.setattr(run.ports, "scan_ports", lambda *a, **k: [{"port": 161}])
    monkeypatch.setattr(run.names, "resolve_all", lambda ips_, use_mdns=False: {})
    monkeypatch.setattr(run.topology, "gateway_ip", lambda: "10.0.0.1")
    monkeypatch.setattr(run.topology, "gateway_ip6", lambda: "")
    s = Settings(
        data_dir=str(tmp_path), subnets="10.0.0.0/24", snmp_enabled=True, mdns_enabled=False, snmp_switches="10.0.0.2"
    )
    with caplog.at_level(logging.INFO):
        run.collect_devices(s, conn)
    assert "SNMP übersprungen" in caplog.text


def test_compose_ohne_public_default():
    import pathlib

    # T-8 (W6): billiger Wachposten - Literal-Vergleich gegen docker-compose.yml
    text = (pathlib.Path(__file__).parent.parent / "docker-compose.yml").read_text()
    assert ":-public" not in text
