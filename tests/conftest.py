import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.config import Settings
from app.web import create_app


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """600.000 PBKDF2-Runden kosten ~0,3 s pro Hash. Für die übrigen Tests reichen wenige Runden;
    test_hardening.py prüft den Produktionswert explizit."""
    from app import auth

    monkeypatch.setattr(auth, "PBKDF2_ITERATIONS", 1_000)
    monkeypatch.setattr(auth, "_DUMMY_HASH", None)


@pytest.fixture(autouse=True)
def clean_auth_state():
    """T-15 (W6): globaler Auth-Zustand zwischen Tests isolieren. auth.SESSIONS und der
    Prune-Zeitpunkt sind modul-global und wuerden sonst von einem frueheren Test ueberleben.
    Die Login-Drossel lebt in app.state je App-Instanz und ist damit pro Test frisch."""
    from app import auth

    auth.SESSIONS.clear()
    auth._last_prune = 0.0
    yield
    auth.SESSIONS.clear()
    auth._last_prune = 0.0


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        data_dir=str(tmp_path),
        auth_enabled=True,
        auth_user="admin",
        auth_pass="secret",
        scan_interval=60,
        history_hours=1,
        snmp_enabled=False,
    )


@pytest.fixture()
def app(settings):
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    r = client.post("/api/login", json={"username": "admin", "password": "secret"})
    assert r.status_code == 200
    return client
