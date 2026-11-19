import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import db, exporters
from .auth import is_valid_session
from .auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)

CATEGORIES = ["Router", "Switch", "Server/NAS", "Client", "Drucker", "Smart-Home/IoT", "Unbekannt"]

SAFE_SETTINGS = [
    "subnets",
    "scan_interval",
    "scan_timeout",
    "port_top",
    "snmp_enabled",
    "snmp_switches",
    "auth_enabled",
    "history_hours",
    "theme",
    "auto_export",
    "auto_export_dir",
]


def get_conn(request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def require_auth(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.auth_enabled or is_valid_session(request.cookies.get("fox_session")):
        return
    raise HTTPException(status_code=401, detail="unauthorized")


def _token_filters(conn, token: str | None, subnet: str, category: str) -> tuple[str, str]:
    if not token:
        return subnet, category
    row = db.get_valid_token(conn, token)
    if row is None:
        raise HTTPException(status_code=403, detail="invalid or expired token")
    allowed_subnets = [s.strip() for s in row["subnets"].split(",") if s.strip()]
    allowed_categories = [c.strip() for c in row["categories"].split(",") if c.strip()]
    if allowed_subnets:
        subnet = subnet if subnet in allowed_subnets else allowed_subnets[0]
    if allowed_categories:
        category = category if category in allowed_categories else allowed_categories[0]
    return subnet, category


def _filtered_devices(request: Request, conn, q: str, category: str, status: str, subnet: str, token: str | None):
    subnet, category = _token_filters(conn, token, subnet, category)
    return db.list_devices(conn, q=q, category=category, status=status, subnet=subnet)


@router.get("/api/health")
def health(request: Request, conn=Depends(get_conn)):
    settings = request.app.state.settings
    state = db.get_scan_state(conn)
    count = conn.execute("SELECT COUNT(*) AS c FROM devices").fetchone()["c"]
    return {
        "status": "ok",
        "version": settings.app_version,
        "devices": count,
        "scanning": bool(state["scanning"]),
        "last_scan": state["last_scan"],
        "next_scan": state["next_scan"],
    }


@router.get("/api/categories")
def categories():
    return CATEGORIES


@router.get("/api/devices")
def devices(
    request: Request,
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    token: str = "",
    conn=Depends(get_conn),
):
    return _filtered_devices(request, conn, q, category, status, subnet, token or None)


@router.get("/api/device/{mac}")
def device_detail(mac: str, request: Request, token: str = "", conn=Depends(get_conn)):
    if token and not db.get_valid_token(conn, token):
        raise HTTPException(status_code=403, detail="invalid or expired token")
    dev = db.get_device(conn, mac)
    if dev is None:
        raise HTTPException(status_code=404, detail="device not found")
    return dev


class DevicePatch(BaseModel):
    category: str | None = None
    note: str | None = None
    connected_to: str | None = None
    x: float | None = None
    y: float | None = None


@router.patch("/api/device/{mac}")
def patch_device(mac: str, body: DevicePatch, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    if db.get_device(conn, mac) is None:
        raise HTTPException(status_code=404, detail="device not found")
    if body.category is not None:
        if body.category not in CATEGORIES:
            raise HTTPException(status_code=422, detail="unknown category")
        conn.execute(
            "UPDATE devices SET category_override = ?, category = ? WHERE mac = ?",
            (body.category, body.category, mac),
        )
    if body.note is not None:
        conn.execute("UPDATE devices SET note = ? WHERE mac = ?", (body.note, mac))
    if body.x is not None or body.y is not None or body.connected_to is not None:
        db.set_layout(
            conn,
            mac,
            x=body.x,
            y=body.y,
            connected_to=body.connected_to,
            connected_manual=1 if body.connected_to is not None else None,
        )
    conn.commit()
    return db.get_device(conn, mac)


@router.post("/api/scan")
def trigger_scan(request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    db.set_setting(conn, "scan_requested", db.utcnow())
    conn.commit()
    return {"status": "queued"}


@router.get("/api/scan/status")
def scan_status(conn=Depends(get_conn)):
    return db.get_scan_state(conn)


@router.get("/api/export/json")
def export_json(request: Request, q: str = "", category: str = "", status: str = "", subnet: str = "", token: str = "", conn=Depends(get_conn)):
    rows = _filtered_devices(request, conn, q, category, status, subnet, token or None)
    return exporters.devices_payload(request.app.state.settings, rows, conn)


@router.get("/api/export/csv")
def export_csv(request: Request, sep: str = "semicolon", q: str = "", category: str = "", status: str = "", subnet: str = "", token: str = "", conn=Depends(get_conn)):
    delimiter = ";" if sep == "semicolon" else ","
    rows = _filtered_devices(request, conn, q, category, status, subnet, token or None)
    return PlainTextResponse(
        exporters.to_csv(rows, delimiter),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fox_netmap.csv"},
    )


@router.get("/api/settings")
def get_settings_api(request: Request, conn=Depends(get_conn)):
    settings = request.app.state.settings
    out = {k: getattr(settings, k) for k in SAFE_SETTINGS}
    out["version"] = settings.app_version
    out["auth_user"] = settings.auth_user
    for key in SAFE_SETTINGS:
        stored = db.get_setting(conn, key)
        if stored not in (None, ""):
            out[key] = stored
    out["notify_configured"] = {
        "webhook": bool(settings.notify_webhook),
        "gotify": bool(settings.notify_gotify and settings.notify_gotify_token),
        "ntfy": bool(settings.notify_ntfy),
    }
    return out


class SettingsPatch(BaseModel):
    scan_interval: int | None = None
    subnets: str | None = None
    port_top: int | None = None
    snmp_enabled: bool | None = None
    snmp_switches: str | None = None
    history_hours: int | None = None
    theme: str | None = None
    auto_export: bool | None = None
    auto_export_dir: str | None = None
    auth_enabled: bool | None = None


@router.patch("/api/settings")
def patch_settings(body: SettingsPatch, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    settings = request.app.state.settings
    for key, value in body.model_dump(exclude_none=True).items():
        db.set_setting(conn, key, str(value).lower() if isinstance(value, bool) else str(value))
        setattr(settings, key, value)
    conn.commit()
    return {"ok": True}


class TokenCreate(BaseModel):
    expires_hours: int | None = None
    subnets: str = ""
    categories: str = ""


@router.post("/api/tokens")
def create_token(body: TokenCreate, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    token = secrets.token_urlsafe(24)
    expires = ""
    if body.expires_hours:
        expires = (datetime.now(timezone.utc) + timedelta(hours=body.expires_hours)).isoformat(timespec="seconds")
    db.create_token(conn, token, expires, body.subnets, body.categories, db.utcnow())
    conn.commit()
    return {"token": token, "expires": expires, "embed_url": f"/embed?token={token}"}


@router.get("/api/tokens")
def tokens_list(conn=Depends(get_conn), _=Depends(require_auth)):
    return db.list_tokens(conn)


@router.delete("/api/tokens/{token}")
def delete_token(token: str, conn=Depends(get_conn), _=Depends(require_auth)):
    db.delete_token(conn, token)
    conn.commit()
    return {"ok": True}
