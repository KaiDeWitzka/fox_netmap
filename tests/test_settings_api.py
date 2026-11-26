"""W1-A2: Einstellungs-API aus dem Schema - S-7, S-8, S-9 (E-2), C-3."""

from app import db


def test_get_settings_masks_secrets(auth_client):
    auth_client.patch("/api/settings", json={"fritz_pass": "geheim123", "snmp_community": "public"})
    body = auth_client.get("/api/settings").json()
    assert body["fritz_pass"] == {"configured": True}
    assert body["snmp_community"] == {"configured": True}
    assert body["notify_gotify_token"] == {"configured": False}
    assert "auth_pass" not in body  # env-only
    # C-3: getypte Werte, keine Strings
    assert body["scan_interval"] == 60 and isinstance(body["scan_interval"], int)
    assert body["oui_online_enabled"] is False


def test_empty_secret_in_patch_keeps_stored_value(auth_client, app):
    auth_client.patch("/api/settings", json={"fritz_pass": "geheim123"})
    auth_client.patch("/api/settings", json={"subnets": "192.168.178.0/24", "fritz_pass": ""})
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "fritz_pass") == "geheim123"  # S-8: leer heisst unveraendert
    conn.close()


def test_auth_enabled_not_patchable(auth_client, app):
    # S-9/E-2: nur NETZ_AUTH_ENABLED steuert den Login, PATCH darf ihn nicht aendern
    r = auth_client.patch("/api/settings", json={"auth_enabled": False})
    assert r.status_code == 200  # Feld wird ignoriert, nicht gespeichert
    assert auth_client.get("/api/settings").json()["auth_enabled"] is True
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "auth_enabled") is None
    conn.close()
    assert auth_client.get("/api/devices").status_code == 200  # Session besteht weiter


def test_fritz_endpoint_change_clears_stored_pass(auth_client, app):
    # S-7: Endpunktwechsel ohne fritz_pass im selben PATCH verwirft das gespeicherte Passwort
    auth_client.patch("/api/settings", json={"fritz_pass": "geheim123", "fritz_url": "192.168.178.1:49000"})
    auth_client.patch("/api/settings", json={"fritz_url": "192.168.178.2:49000"})
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "fritz_pass") in (None, "")
    conn.close()


def test_fritz_endpoint_change_with_env_pass_rejected(auth_client, app, monkeypatch):
    # S-7: mit Umgebungs-Passwort muss das neue Passwort im selben PATCH stehen
    from app.config import get_settings

    monkeypatch.setenv("NETZ_FRITZ_PASS", "env-pass")
    get_settings.cache_clear()
    try:
        r = auth_client.patch("/api/settings", json={"fritz_url": "192.168.178.2:49000"})
        assert r.status_code == 422
        r = auth_client.patch("/api/settings", json={"fritz_url": "192.168.178.2:49000", "fritz_pass": "neu"})
        assert r.status_code == 200
    finally:
        monkeypatch.delenv("NETZ_FRITZ_PASS")
        get_settings.cache_clear()


def test_endpoint_with_userinfo_rejected(auth_client):
    # S-8: Zugangsdaten in URLs duerfen nicht gespeichert/angezeigt werden
    r = auth_client.patch("/api/settings", json={"fritz_url": "http://admin:pw@192.168.178.1:49000"})
    assert r.status_code == 422
    r = auth_client.patch("/api/settings", json={"notify_gotify": "https://user:tok@gotify.example/t"})
    assert r.status_code == 422


def test_compose_passes_every_config_field():
    # D-2: jede NETZ_*-Variable aus dem Schema muss in docker-compose.yml durchgereicht werden
    import re

    from app.settings_schema import FIELDS

    with open("docker-compose.yml", encoding="utf-8") as fh:
        compose = fh.read()
    for key in FIELDS:
        assert f"NETZ_{key.upper()}:" in compose, key
    for extra in ("NETZ_DATA_DIR", "NETZ_HOST", "NETZ_PORT", "TZ"):
        assert re.search(rf"^  {extra}:", compose, re.M), extra
