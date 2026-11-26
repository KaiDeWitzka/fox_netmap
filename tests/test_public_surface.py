"""W2 S-10: oeffentliche Oberflaeche ohne Anmeldung ist minimal."""


def test_health_returns_only_status(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_meta_sites_scan_status_require_session(client, auth_client, app):
    for path in ("/api/meta", "/api/sites", "/api/scan/status"):
        assert auth_client.get(path).status_code == 200, path
    client.cookies.clear()  # gleicher Client: ohne Session kein Zugriff
    for path in ("/api/meta", "/api/sites", "/api/scan/status"):
        assert client.get(path).status_code == 401, path


def test_meta_sites_scan_status_accept_valid_token(client, auth_client):
    tok = auth_client.post("/api/tokens", json={"expires_hours": 24}).json()["token"]
    client.cookies.clear()
    for path in ("/api/meta", "/api/sites", "/api/scan/status"):
        r = client.get(f"{path}?token={tok}")
        assert r.status_code == 200, (path, r.status_code)
    for path in ("/api/meta", "/api/sites", "/api/scan/status"):
        assert client.get(f"{path}?token=junk").status_code in (401, 403), path
