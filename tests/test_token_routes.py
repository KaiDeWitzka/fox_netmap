"""W2 T-1: Schreibrouten unter den Token-Pfaden duerfen nie per Token erreichbar sein,
und jede Nicht-GET-Route verlangt eine Sitzung."""

import pytest

WRITE_ROUTES = [
    ("PATCH", "/api/device/aa:bb:cc:dd:ee:ff"),
    ("DELETE", "/api/device/aa:bb:cc:dd:ee:ff"),
    ("POST", "/api/devices/connect"),
    ("POST", "/api/scan"),
    # /api/export/pdf ist bewusst NICHT hier: read-only, mit Token ohne Bild erlaubt (S-6), siehe test_export_security
    ("PATCH", "/api/settings"),
    ("POST", "/api/tokens"),
    ("DELETE", "/api/tokens/abc"),
    ("POST", "/api/layout/reset"),
]


def _token(auth_client):
    r = auth_client.post("/api/tokens", json={"expires_hours": 24})
    return r.json()["token"]


@pytest.mark.parametrize("method,path", WRITE_ROUTES)
def test_write_routes_reject_junk_token(client, method, path):
    r = client.request(method, f"{path}?token=junk", json={})
    assert r.status_code in (401, 403), (method, path, r.status_code)


@pytest.mark.parametrize("method,path", WRITE_ROUTES)
def test_write_routes_reject_valid_read_token(client, auth_client, method, path):
    tok = _token(auth_client)
    client.cookies.clear()  # auth_client-Fixture teilt den Client - ohne Session darf nur der Token zaehlen
    r = client.request(method, f"{path}?token={tok}", json={})
    assert r.status_code in (401, 403), (method, path, r.status_code)


def test_every_non_get_api_route_requires_session(client, app):
    routes = [(getattr(r, "methods", set()), r.path) for r in app.routes if getattr(r, "path", "").startswith("/api/")]
    offenders = []
    for methods, path in routes:
        for m in methods - {"GET", "HEAD", "OPTIONS"}:
            r = client.request(m, path)
            if r.status_code not in (401, 403, 405, 422):
                offenders.append((m, path, r.status_code))
    assert not offenders, offenders
