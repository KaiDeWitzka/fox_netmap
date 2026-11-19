import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.config import Settings
from app.web import create_app


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
