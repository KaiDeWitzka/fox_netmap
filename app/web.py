import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import api, db
from .auth import ensure_default_user, is_valid_session
from .config import Settings, get_settings
from .logsetup import get_logger


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


PUBLIC_PATHS = ("/api/health", "/api/login", "/api/categories", "/api/scan/status", "/api/meta", "/static/", "/login", "/favicon.ico", "/embed")
TOKEN_PATHS = ("/api/devices", "/api/device/", "/api/export/")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    os.makedirs(settings.data_dir, exist_ok=True)
    log = get_logger(data_dir=settings.data_dir)
    log.info("fox_netmap %s startet: http://%s:%s (Daten: %s)", settings.app_version, settings.host, settings.port, settings.data_dir)
    app = FastAPI(title="fox_netmap", version=settings.app_version)
    app.state.settings = settings
    app.state.db_path = db.db_path(settings.data_dir)
    conn = db.connect(app.state.db_path)
    db.init_db(conn)
    ensure_default_user(conn, settings)
    conn.close()

    app.include_router(api.router)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
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

    static_dir = os.path.join(os.path.dirname(__file__), "static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    @app.get("/embed", include_in_schema=False)
    def embed(request: Request):
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
    def login_page():
        return FileResponse(os.path.join(static_dir, "login.html"))

    app.mount("/static", NoCacheStaticFiles(directory=static_dir), name="static")
    return app
