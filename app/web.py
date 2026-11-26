import os
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .auth import ensure_default_user, is_valid_session
from .auth import router as auth_router
from .config import Settings, effective_settings, get_settings
from .logsetup import get_logger
from .routers import devices, export, meta, scan, settings, tokens
from .security import LoginThrottle, security_headers


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Any) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# S-10: oeffentlich ohne Anmeldung nur Health/Login/Categories/Static/Embed.
# /api/meta, /api/sites, /api/scan/status stehen in TOKEN_PATHS und brauchen Sitzung oder gueltigen Token.
PUBLIC_PATHS = (
    "/api/health",
    "/api/login",
    "/api/categories",
    "/static/",
    "/login",
    "/favicon.ico",
    "/embed",
)
TOKEN_PATHS = ("/api/devices", "/api/device/", "/api/export/", "/api/meta", "/api/sites", "/api/scan/status")

_CallNext = Callable[[Request], Awaitable[Response]]

ROUTERS = (auth_router, devices.router, scan.router, export.router, settings.router, tokens.router, meta.router)


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    # Reihenfolge: zuletzt registrierte Middleware laeuft aussen -> Header auch auf 401/303-Antworten.
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next: _CallNext) -> Response:
        path = request.url.path
        if not settings.auth_enabled or path.startswith(PUBLIC_PATHS):
            return await call_next(request)
        if is_valid_session(request.cookies.get("fox_session")):
            return await call_next(request)
        if path.startswith(TOKEN_PATHS) and request.query_params.get("token"):
            return await call_next(request)
        if path.startswith("/api/"):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    @app.middleware("http")
    async def csrf_origin_middleware(request: Request, call_next: _CallNext) -> Response:
        # S-16: unsichere Methoden mit Sitzungscookie brauchen passenden Origin/Referer
        # (Schutz gegen same-origin-CSRF; ohne Origin/Referer bleiben Skripte/Clients erlaubt)
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.cookies.get("fox_session"):
            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin:
                host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
                if urlparse(origin).netloc and urlparse(origin).netloc != host:
                    return JSONResponse({"detail": "forbidden origin"}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: _CallNext) -> Response:
        response = await call_next(request)
        for name, value in security_headers(request.url.path, settings.embed_ancestors).items():
            response.headers.setdefault(name, value)
        return response


def _register_pages(app: FastAPI, static_dir: str, settings: Settings) -> None:
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(os.path.join(static_dir, "index.html"))

    @app.get("/embed", include_in_schema=False)
    def embed(request: Request) -> Any:  # Any: 403 als JSONResponse, sonst Datei - kein response_model
        if settings.auth_enabled:
            token = request.query_params.get("token", "")
            conn = db.connect(app.state.db_path)
            try:
                if db.get_valid_token(conn, token) is None:
                    return JSONResponse({"detail": "invalid or expired token"}, status_code=403)
            finally:
                conn.close()
        return FileResponse(os.path.join(static_dir, "index.html"))

    @app.get("/login", include_in_schema=False)
    def login_page() -> FileResponse:
        return FileResponse(os.path.join(static_dir, "login.html"))

    app.mount("/static", NoCacheStaticFiles(directory=static_dir), name="static")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    os.makedirs(settings.data_dir, exist_ok=True)
    log = get_logger(data_dir=settings.data_dir)
    log.info(
        "fox_netmap %s startet: http://%s:%s (Daten: %s)",
        settings.app_version,
        settings.host,
        settings.port,
        settings.data_dir,
    )
    app = FastAPI(title="fox_netmap", version=settings.app_version)
    app.state.settings = settings
    app.state.db_path = db.db_path(settings.data_dir)
    app.state.login_throttle = LoginThrottle()
    conn = db.connect(app.state.db_path)
    db.init_db(conn)
    ensure_default_user(conn, settings)
    # C-1/K-7: gespeicherte Einstellungen werden beim Start geladen, fuer Web und Scanner gleich
    settings = effective_settings(conn, settings)
    app.state.settings = settings
    conn.close()

    for r in ROUTERS:  # W7/Q-4: Router je Bereich statt einem api.py-Monolithen
        app.include_router(r)
    _register_middleware(app, settings)
    _register_pages(app, os.path.join(os.path.dirname(__file__), "static"), settings)
    return app
