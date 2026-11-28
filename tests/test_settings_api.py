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
    for extra in ("NETZ_DATA_DIR", "NETZ_HOST", "NETZ_PORT", "NETZ_SQLITE_JOURNAL", "TZ"):
        assert re.search(rf"^  {extra}:", compose, re.M), extra


def test_null_secret_in_patch_deletes_stored_value(auth_client, app):
    auth_client.patch("/api/settings", json={"snmp_community": "geheim"})
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "snmp_community") == "geheim"
    conn.close()
    r = auth_client.patch("/api/settings", json={"snmp_community": None})
    assert r.status_code == 200
    conn = db.connect(app.state.db_path)
    assert db.get_setting(conn, "snmp_community") is None  # W5/S-8: explizites null loescht (Zeile weg, nicht "")
    conn.close()
    body = auth_client.get("/api/settings").json()
    assert body["snmp_community"] == {"configured": False}


# --- E-9: Proxmox VE (Backlog #112 #13) ---

PVE_FULL = {
    "pve_enabled": True,
    "pve_urls": "https://192.168.178.10:8006, https://pve2:8006/api2/json",
    "pve_user": "root@pam",
    "pve_token_id": "root@pam!fox_netmap",
    "pve_token_secret": "00000000-0000-0000-0000-000000000000",
    "pve_insecure_tls": False,
}


def test_pve_full_patch_ok_and_secret_masked(auth_client):
    r = auth_client.patch("/api/settings", json=PVE_FULL)
    assert r.status_code == 200, r.text
    body = auth_client.get("/api/settings").json()
    assert body["pve_enabled"] is True
    assert body["pve_urls"] == PVE_FULL["pve_urls"]
    assert body["pve_user"] == "root@pam"
    assert body["pve_token_id"] == "root@pam!fox_netmap"
    assert body["pve_token_secret"] == {"configured": True}  # S-8: nie Klartext
    assert body["pve_insecure_tls"] is False


def test_pve_enabled_without_complete_config_rejected(auth_client):
    # aktiv ohne Token-Secret -> 422 (Querfeldpruefung gegen den Ist-Zustand)
    r = auth_client.patch("/api/settings", json={k: v for k, v in PVE_FULL.items() if k != "pve_token_secret"})
    assert r.status_code == 422
    assert "Token-Secret" in r.json()["detail"]
    r = auth_client.patch("/api/settings", json={**PVE_FULL, "pve_token_secret": ""})
    assert r.status_code == 422  # leer = unveraendert, hier ist nichts gespeichert -> fehlt
    r = auth_client.patch("/api/settings", json={"pve_enabled": True, "pve_urls": "https://pve:8006"})
    assert r.status_code == 422
    assert "Proxmox" in r.json()["detail"]


def test_pve_invalid_values_rejected(auth_client):
    bad_urls = ["https://user:pass@pve:8006", "ftp://pve:8006", "https://pve:8006/irgendwas", "https://pve:99999"]
    for u in bad_urls:
        r = auth_client.patch("/api/settings", json={"pve_urls": u})
        assert r.status_code == 422, u
    assert auth_client.patch("/api/settings", json={"pve_user": "kein-realm"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"pve_user": "root@pam"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"pve_token_id": "ohne-bang"}).status_code == 422
    assert auth_client.patch("/api/settings", json={"pve_token_id": "root@pam!fox_netmap"}).status_code == 200
    assert auth_client.patch("/api/settings", json={"pve_token_secret": "x" * 257}).status_code == 422


def test_pve_enable_with_stored_secret_ok_and_null_deletes(auth_client, app):
    # Secret zuerst (deaktiviert) speichern, dann aktivieren -> Querfeldpruefung greift auf Ist-Zustand
    r = auth_client.patch("/api/settings", json={**PVE_FULL, "pve_enabled": False})
    assert r.status_code == 200
    r = auth_client.patch("/api/settings", json={"pve_enabled": True})
    assert r.status_code == 200, r.text
    assert auth_client.get("/api/settings").json()["pve_token_secret"] == {"configured": True}
    r = auth_client.patch("/api/settings", json={"pve_token_secret": None})
    assert r.status_code == 200
    body = auth_client.get("/api/settings").json()
    assert body["pve_token_secret"] == {"configured": False}
    # jetzt ist "aktiv ohne Secret" wieder ein Fehler
    r = auth_client.patch("/api/settings", json={"pve_enabled": True})
    assert r.status_code == 422


def test_validate_patch_pve_pure_function():
    from app.validation import validate_patch

    assert validate_patch({"pve_urls": "https://pve:8006"}) is None
    assert validate_patch({"pve_urls": "https://pve:8006/"}) is None
    assert validate_patch({"pve_urls": "https://pve:8006/api2/json"}) is None
    assert validate_patch({"pve_urls": "http://[::1]:8006"}) is None
    assert validate_patch({"pve_urls": "https://pve:8006", "pve_enabled": False}) is None
    err = validate_patch({"pve_urls": "https://pve:8006", "pve_enabled": True})
    assert err and "fehlt" in err
    err = validate_patch({"pve_user": "root"})
    assert err and "user@realm" in err
    err = validate_patch({"pve_token_id": "root@pam"})
    assert err and "!name" in err
