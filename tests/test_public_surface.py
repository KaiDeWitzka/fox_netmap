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


def test_jede_schreibende_api_route_traegt_require_auth(app):
    """B2/B3-Killer (Mutations-Kill-Liste, W6): Jede mutierende /api-Route muss require_auth
    bzw. require_auth_or_token als explizite Dependency tragen - Defense in Depth neben der
    Auth-Middleware in web.py. Ohne diese Pruefung waeren entfernte Depends(...) an einzelnen
    Routen (B2: POST /api/devices/connect, B3: PATCH /api/device/{mac}) nicht sichtbar."""
    from app.api import require_auth, require_auth_or_token

    guards = {require_auth, require_auth_or_token}
    seen = set()

    def _all_routes():
        for route in app.routes:
            inner = getattr(route, "original_router", None)  # _IncludedRouter kapselt den APIRouter
            if inner is not None:
                yield from inner.routes
            else:
                yield route

    for route in _all_routes():
        path = getattr(route, "path", "")
        methods = set(getattr(route, "methods", set()) or set())
        # /api/login und /api/logout sind bewusst ohne Sitzung nutzbar (Login obviously, Logout ist ein No-Op)
        if (
            not path.startswith("/api/")
            or path in ("/api/login", "/api/logout")
            or not (methods & {"POST", "PATCH", "PUT", "DELETE"})
        ):
            continue
        dependant = getattr(route, "dependant", None)
        deps = [d.call for d in (dependant.dependencies if dependant else [])]
        assert any(d in guards for d in deps), f"{sorted(methods)} {path} ohne require_auth-Dependency"
        seen.add((path, tuple(sorted(methods))))
    assert ("/api/devices/connect", ("POST",)) in seen
    assert ("/api/device/{mac}", ("PATCH",)) in seen
    assert ("/api/export/pdf", ("POST",)) in seen
