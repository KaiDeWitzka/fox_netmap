"""W1-A1: zentrales Einstellungs-Schema (Q-1), Zusammenfuehrung Env+DB (C-1, C-2, SF-4), E-2."""

import logging

import pytest

from app import db
from app.config import Settings, effective_settings, get_settings
from app.settings_schema import FIELDS


def _conn(tmp_path):
    conn = db.connect(db.db_path(str(tmp_path)))
    db.init_db(conn)
    return conn


def test_every_setting_field_has_schema_entry():
    assert set(Settings.model_fields) == set(FIELDS)


def test_patchable_fields_are_scanner_overridable():
    # N-2: jedes per UI patchbare Feld muss der Scanner aus der DB uebernehmen
    for key, f in FIELDS.items():
        if f.patchable:
            assert f.scanner, key


def test_effective_settings_typed_and_env_wins_for_auth_enabled(tmp_path):
    conn = _conn(tmp_path)
    db.set_setting(conn, "scan_interval", "60")
    db.set_setting(conn, "auth_enabled", "true")
    conn.commit()
    base = Settings(auth_enabled=False, netzz_scan_interval=900) if False else Settings(auth_enabled=False)
    eff = effective_settings(conn, base)
    assert eff.scan_interval == 60 and isinstance(eff.scan_interval, int)
    assert eff.auth_enabled is False  # E-2: Umgebung gewinnt


def test_invalid_stored_value_logs_warning_and_keeps_env(tmp_path, caplog):
    conn = _conn(tmp_path)
    db.set_setting(conn, "scan_interval", "abc")
    conn.commit()
    base = Settings(scan_interval=900)
    with caplog.at_level(logging.WARNING, logger="fox_netmap"):
        eff = effective_settings(conn, base)
    assert eff.scan_interval == 900
    assert any("scan_interval" in r.message for r in caplog.records)


def test_out_of_range_stored_value_keeps_env(tmp_path):
    conn = _conn(tmp_path)
    db.set_setting(conn, "scan_interval", "5")  # minimum 30
    conn.commit()
    eff = effective_settings(conn, Settings(scan_interval=900))
    assert eff.scan_interval == 900


def test_empty_string_overrides_env(tmp_path):
    # C-2: gespeicherter leerer String ist ein bewusstes Leeren und ueberschreibt die Umgebung
    conn = _conn(tmp_path)
    db.set_setting(conn, "notify_ntfy", "")
    conn.commit()
    eff = effective_settings(conn, Settings(notify_ntfy="http://ntfy/x"))
    assert eff.notify_ntfy == ""


def test_migration_drops_legacy_empty_rows(tmp_path):
    conn = db.connect(db.db_path(str(tmp_path)))
    conn.executescript(db.SCHEMA)
    conn.execute("INSERT INTO settings (key, value) VALUES ('subnets', '')")
    conn.commit()
    db.init_db(conn)
    assert db.get_setting(conn, "subnets") is None


def test_web_applies_stored_settings_at_startup(tmp_path):
    # C-1: ein zweites create_app auf demselben Datenverzeichnis uebernimmt gespeicherte Werte
    from app.web import create_app

    conn = _conn(tmp_path)
    db.set_setting(conn, "sites", "Zuhause:192.0.2.0/24")
    conn.commit()
    conn.close()
    import os

    os.environ["NETZ_DATA_DIR"] = str(tmp_path)
    try:
        get_settings.cache_clear()
        app1 = create_app()
        assert app1.state.settings.site_map.get("192.0.2.0/24") == "Zuhause"
        app2 = create_app()
        assert app2.state.settings.site_map.get("192.0.2.0/24") == "Zuhause"
    finally:
        os.environ.pop("NETZ_DATA_DIR", None)
        get_settings.cache_clear()


def test_settings_patch_model_matches_patchable_fields():
    from app.api import SettingsPatch

    assert set(SettingsPatch.model_fields) == {k for k, f in FIELDS.items() if f.patchable}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_legacy_alias_migrated(tmp_path):
    """Q-16 (W7): Alt-Schluessel subnet/fritz_url in der Datenbank werden beim Start auf die
    kanonischen subnets/fritz_urls migriert und geloescht (fritz_url bleibt als erster Endpunkt erhalten)."""
    conn = _conn(tmp_path)
    db.set_setting(conn, "subnet", "10.0.0.0/24")
    db.set_setting(conn, "fritz_url", "192.168.178.1:49000")
    db.set_setting(conn, "fritz_urls", "192.168.178.2:49000")
    conn.commit()
    db.init_db(conn)  # zweiter Start fuehrt die Alias-Migration aus
    assert db.get_setting(conn, "subnet") is None
    assert db.get_setting(conn, "fritz_url") is None
    assert db.get_setting(conn, "subnets") == "10.0.0.0/24"
    assert db.get_setting(conn, "fritz_urls") == "192.168.178.1:49000,192.168.178.2:49000"
    conn.close()


def test_legacy_alias_migrated_allein(tmp_path):
    """Q-16: nur fritz_url gesetzt -> landet komplett in fritz_urls."""
    conn = _conn(tmp_path)
    db.set_setting(conn, "fritz_url", "192.168.178.1:49000")
    conn.commit()
    db.init_db(conn)
    assert db.get_setting(conn, "fritz_url") is None
    assert db.get_setting(conn, "fritz_urls") == "192.168.178.1:49000"
    conn.close()


def test_empty_env_vars_fall_back_to_defaults(monkeypatch, tmp_path):
    """PR #115 CI: Compose reicht unsetzte NETZ_* als leere Strings durch (${VAR:-}).

    Leer muss "nicht gesetzt" heissen (env_ignore_empty) - sonst wirft pydantic bei
    Bool-/Int-Feldern einen ValidationError und der Container startet nicht (unhealthy).
    """
    monkeypatch.setenv("NETZ_AUTH_ENABLED", "")
    monkeypatch.setenv("NETZ_SCAN_INTERVAL", "")
    monkeypatch.setenv("NETZ_SNMP_ENABLED", "")
    monkeypatch.setenv("NETZ_AUTH_PASS", "")
    s = Settings(data_dir=str(tmp_path))
    assert s.auth_enabled is True
    assert s.scan_interval == 900
    assert s.snmp_enabled is True
    assert s.auth_pass == ""
    monkeypatch.setenv("NETZ_AUTH_ENABLED", "false")
    assert Settings(data_dir=str(tmp_path)).auth_enabled is False
