"""Regressionstests fuer den Sicherheitsfix v1.4.1 (Security-Header, Login-Drosselung)."""

from app.security import LoginThrottle


def test_security_headers_on_api_and_pages(client):
    for path in ("/api/health", "/login", "/static/app.js"):
        r = client.get(path)
        csp = r.headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]
        assert "frame-ancestors 'none'" in csp
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"


def test_security_headers_on_unauthorized_responses(client):
    r = client.get("/api/settings")
    assert r.status_code == 401
    assert "content-security-policy" in r.headers
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["x-frame-options"] == "DENY"


def test_embed_may_be_framed(auth_client):
    token = auth_client.post("/api/tokens", json={"expires_hours": 24}).json()["token"]
    r = auth_client.get(f"/embed?token={token}")
    assert r.status_code == 200
    assert "frame-ancestors *" in r.headers["content-security-policy"]
    assert "x-frame-options" not in r.headers
    assert r.headers["referrer-policy"] == "no-referrer"


def test_embed_ancestors_configurable(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.web import create_app

    s = Settings(data_dir=str(tmp_path), auth_enabled=False, embed_ancestors="https://wiki.example.org")
    with TestClient(create_app(s)) as c:
        assert "frame-ancestors https://wiki.example.org" in c.get("/embed").headers["content-security-policy"]


def test_login_page_has_no_inline_script(client):
    html = client.get("/login").text
    assert "<script>" not in html
    assert '<script src="/static/login.js"></script>' in html


def test_login_lockout_after_five_failures(client):
    for _ in range(5):
        assert client.post("/api/login", json={"username": "admin", "password": "falsch"}).status_code == 401
    # S-5: falsches Passwort bleibt waehrend der Sperre 429 ...
    r = client.post("/api/login", json={"username": "admin", "password": "falsch"})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    # ... aber das richtige kommt durch und hebt die Sperre auf
    r = client.post("/api/login", json={"username": "admin", "password": "secret"})
    assert r.status_code == 200


def test_login_success_resets_counter(client):
    for _ in range(4):
        client.post("/api/login", json={"username": "admin", "password": "falsch"})
    assert client.post("/api/login", json={"username": "admin", "password": "secret"}).status_code == 200
    for _ in range(4):
        assert client.post("/api/login", json={"username": "admin", "password": "falsch"}).status_code == 401


def test_login_rejects_oversized_input(client):
    r = client.post("/api/login", json={"username": "a" * 200, "password": "x"})
    assert r.status_code == 422


def test_throttle_per_ip_limit_and_expiry():
    t = LoginThrottle(max_per_user=5, max_per_ip=3, window=60, lockout=100)
    for i in range(3):
        t.register_failure("10.0.0.9", f"user{i}", now=1000.0)
    assert t.retry_after("10.0.0.9", "anderer", now=1001.0) > 0
    assert t.retry_after("10.0.0.8", "user0", now=1001.0) == 0
    assert t.retry_after("10.0.0.9", "anderer", now=1101.0) == 0


def test_note_length_limited(auth_client, app):
    from tests.test_api import insert_device

    insert_device(app)
    r = auth_client.patch("/api/device/aa:bb:cc:dd:ee:ff", json={"note": "x" * 2001})
    assert r.status_code == 422
