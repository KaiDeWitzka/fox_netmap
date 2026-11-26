"""W7 Q-4/Q-12: Routentabelle als Charakterisierung - der Umbau api.py -> routers/ darf die
Tabelle (Pfade + Methoden) nicht aendern. test_no_unreferenced_routes stellt sicher, dass keine
neue /api-Route ohne Bezug in Frontend/Healthcheck landet."""

from pathlib import Path

from app.config import Settings
from app.web import create_app

REPO = Path(__file__).resolve().parents[1]

# gepinnte Tabelle (Stand vor W7); /api/rooms bleibt vorerst erhalten (Q-12: API-Stabilitaet,
# Ersatz fuer die Raumliste im Frontend bzw. Entfernung in einer groesseren Version dokumentiert)
EXPECTED_ROUTES = {
    ("/api/categories", ("GET",)),
    ("/api/device/{mac}", ("DELETE",)),
    ("/api/device/{mac}", ("GET",)),
    ("/api/device/{mac}", ("PATCH",)),
    ("/api/devices", ("GET",)),
    ("/api/devices/connect", ("POST",)),
    ("/api/export/csv", ("GET",)),
    ("/api/export/json", ("GET",)),
    ("/api/export/pdf", ("POST",)),
    ("/api/health", ("GET",)),
    ("/api/layout/reset", ("POST",)),
    ("/api/login", ("POST",)),
    ("/api/logout", ("POST",)),
    ("/api/logs", ("GET",)),
    ("/api/logs/download", ("GET",)),
    ("/api/me", ("GET",)),
    ("/api/meta", ("GET",)),
    ("/api/rooms", ("GET",)),
    ("/api/scan", ("POST",)),
    ("/api/scan/status", ("GET",)),
    ("/api/settings", ("GET",)),
    ("/api/settings", ("PATCH",)),
    ("/api/sites", ("GET",)),
    ("/api/tokens", ("GET",)),
    ("/api/tokens", ("POST",)),
    ("/api/tokens/{ident}", ("DELETE",)),
}

# Routen ohne literalem Bezug in app/static: /api/health nutzt der Docker-HEALTHCHECK
# (app/healthcheck.py), /api/rooms ist Legacy (nur Tests, siehe Q-12-Entscheid in STAND.md).
KEEP_WITHOUT_STATIC_REF = {"/api/health", "/api/rooms"}


def _api_routes(app):
    out = set()

    def walk(routes):
        for r in routes:
            inner = getattr(r, "original_router", None)  # _IncludedRouter kapselt den APIRouter
            if inner is not None:
                walk(inner.routes)
            elif str(getattr(r, "path", "")).startswith("/api/"):
                out.add((r.path, tuple(sorted(r.methods))))

    walk(app.routes)
    return out


def test_route_table_unchanged(tmp_path):
    app = create_app(Settings(data_dir=str(tmp_path), auth_pass="x"))
    assert _api_routes(app) == EXPECTED_ROUTES


def test_no_unreferenced_routes(tmp_path):
    app = create_app(Settings(data_dir=str(tmp_path), auth_pass="x"))
    static = ""
    for p in (REPO / "app" / "static").iterdir():
        if p.suffix in (".js", ".html"):
            static += p.read_text(encoding="utf-8")
    healthcheck = (REPO / "app" / "healthcheck.py").read_text(encoding="utf-8")
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    import re

    for path, _methods in sorted(_api_routes(app)):
        if path in KEEP_WITHOUT_STATIC_REF:
            continue
        base = re.sub(r"\{[^}]*\}", "", path)  # "/api/device/{mac}" -> "/api/device/"
        assert base in static or base in healthcheck or base in dockerfile, f"{path} ohne Bezug in app/static"
