import base64
import ipaddress
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import db, exporters
from .auth import is_valid_session
from .auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)
log = logging.getLogger("fox_netmap")

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
    "device_retention_days",
    "theme",
    "auto_export",
    "auto_export_dir",
    "auto_export_interval_hours",
    "mdns_enabled",
    "oui_online_enabled",
    "oui_online_max",
    "oui_online_url",
    "alarm_whitelist",
    "sites",
    "lang",
    "scan_timeout",
    "ports",
    "fritz_url",
    "fritz_urls",
    "fritz_user",
    "snmp_community",
    "notify_webhook",
    "notify_gotify",
    "notify_ntfy",
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


def _site_of(subnet: str, settings) -> str:
    if not subnet:
        return ""
    return settings.site_map.get(subnet, "")


def _filtered_devices(request: Request, conn, q: str, category: str, status: str, subnet: str, site: str, token: str | None):
    subnet, category = _token_filters(conn, token, subnet, category)
    rows = db.list_devices(conn, q=q, category=category, status=status, subnet=subnet)
    settings = request.app.state.settings
    for r in rows:
        r["site"] = _site_of(r.get("subnet", ""), settings)
    if site:
        rows = [r for r in rows if r["site"] == site]
    return rows


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
    site: str = "",
    token: str = "",
    conn=Depends(get_conn),
):
    return _filtered_devices(request, conn, q, category, status, subnet, site, token or None)


@router.get("/api/device/{mac}")
def device_detail(mac: str, request: Request, token: str = "", conn=Depends(get_conn)):
    if token and not db.get_valid_token(conn, token):
        raise HTTPException(status_code=403, detail="invalid or expired token")
    dev = db.get_device(conn, mac)
    if dev is None:
        raise HTTPException(status_code=404, detail="device not found")
    dev["site"] = _site_of(dev.get("subnet", ""), request.app.state.settings)
    return dev


class DevicePatch(BaseModel):
    category: str | None = None
    note: str | None = Field(default=None, max_length=2000)
    connected_to: str | None = None
    x: float | None = None
    y: float | None = None


@router.delete("/api/device/{mac}")
def delete_device(mac: str, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    """Löscht ein Gerät samt Verlauf (Recht auf Löschung). Ist es noch im Netz, erscheint es beim nächsten Scan neu."""
    if db.get_device(conn, mac) is None:
        raise HTTPException(status_code=404, detail="device not found")
    db.delete_device(conn, mac)
    conn.commit()
    log.info("Geraet %s manuell geloescht", mac)
    return {"ok": True}


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
    if body.connected_to is not None:
        if body.connected_to == "":
            conn.execute("UPDATE device_layout SET connected_to = NULL, connected_manual = 0 WHERE mac = ?", (mac,))
        else:
            db.set_layout(conn, mac, connected_to=body.connected_to, connected_manual=1)
    if body.x is not None or body.y is not None:
        db.set_layout(conn, mac, x=body.x, y=body.y)
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
def export_json(request: Request, q: str = "", category: str = "", status: str = "", subnet: str = "", site: str = "", token: str = "", conn=Depends(get_conn)):
    rows = _filtered_devices(request, conn, q, category, status, subnet, site, token or None)
    return exporters.devices_payload(request.app.state.settings, rows, conn)


class PdfExport(BaseModel):
    image: str | None = None
    title: str | None = None
    orientation: str | None = None


@router.post("/api/export/pdf")
def export_pdf(
    request: Request,
    payload: PdfExport,
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    site: str = "",
    token: str = "",
    conn=Depends(get_conn),
):
    rows = _filtered_devices(request, conn, q, category, status, subnet, site, token or None)
    image_bytes = None
    if payload.image:
        data = payload.image
        if data.startswith("data:"):
            data = data.split(",", 1)[1] if "," in data else ""
        try:
            image_bytes = base64.b64decode(data, validate=True)
        except Exception:
            raise HTTPException(422, "image ist kein gueltiges base64") from None
        if not image_bytes:
            raise HTTPException(422, "image ist leer")
        if len(image_bytes) > 12 * 1024 * 1024:
            raise HTTPException(422, "image zu gross (max 12 MB)")
        if not (image_bytes.startswith(b"\x89PNG") or image_bytes.startswith(b"\xff\xd8")):
            raise HTTPException(422, "image muss PNG oder JPEG sein")
    title = (payload.title or "").strip()[:120]
    orientation = (payload.orientation or "portrait").strip().lower()
    if orientation not in ("portrait", "landscape"):
        raise HTTPException(422, "orientation muss 'portrait' oder 'landscape' sein")
    try:
        pdf = exporters.build_pdf(request.app.state.settings, rows, conn, image_bytes=image_bytes, title=title, orientation=orientation)
    except HTTPException:
        raise
    except Exception:
        if image_bytes:
            raise HTTPException(422, "image konnte nicht gelesen werden (PNG/JPEG erwartet)") from None
        raise
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="fox_netmap.pdf"'},
    )


@router.get("/api/export/csv")
def export_csv(request: Request, sep: str = "semicolon", q: str = "", category: str = "", status: str = "", subnet: str = "", site: str = "", token: str = "", conn=Depends(get_conn)):
    delimiter = ";" if sep == "semicolon" else ","
    rows = _filtered_devices(request, conn, q, category, status, subnet, site, token or None)
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
    device_retention_days: int | None = None
    theme: str | None = None
    auto_export: bool | None = None
    auto_export_dir: str | None = None
    auto_export_interval_hours: int | None = None
    mdns_enabled: bool | None = None
    oui_online_enabled: bool | None = None
    oui_online_max: int | None = None
    oui_online_url: str | None = None
    alarm_whitelist: str | None = None
    sites: str | None = None
    lang: str | None = None
    scan_timeout: float | None = None
    ports: str | None = None
    fritz_url: str | None = None
    fritz_urls: str | None = None
    fritz_user: str | None = None
    fritz_pass: str | None = None
    snmp_community: str | None = None
    notify_webhook: str | None = None
    notify_gotify: str | None = None
    notify_ntfy: str | None = None
    auth_enabled: bool | None = None


def _valid_endpoint(s: str) -> bool:
    if s.startswith(("http://", "https://")):
        return True
    return bool(re.match(r"^[a-zA-Z0-9.\-]+(:\d+)?$", s))


def validate_settings(body: SettingsPatch) -> str | None:
    if body.scan_interval is not None and not 30 <= body.scan_interval <= 86400:
        return "scan_interval muss zwischen 30 und 86400 Sekunden liegen"
    if body.port_top is not None and not 0 <= body.port_top <= 65535:
        return "port_top muss zwischen 0 (alle Ports) und 65535 liegen"
    if body.history_hours is not None and not 1 <= body.history_hours <= 87600:
        return "history_hours muss zwischen 1 und 87600 liegen"
    if body.device_retention_days is not None and not 0 <= body.device_retention_days <= 3650:
        return "device_retention_days muss zwischen 0 (nie löschen) und 3650 liegen"
    if body.theme is not None and body.theme not in ("dark", "light"):
        return "theme muss 'dark' oder 'light' sein"
    if body.lang is not None and body.lang not in ("de", "en", "fr", "es", "it", "pt"):
        return "lang muss de, en, fr, es, it oder pt sein"
    if body.scan_timeout is not None and not 0.2 <= body.scan_timeout <= 10:
        return "scan_timeout muss zwischen 0.2 und 10 Sekunden liegen"
    if body.ports is not None and body.ports.strip():
        for p in body.ports.split(","):
            p = p.strip()
            if not p.isdigit() or not 1 <= int(p) <= 65535:
                return f"ungueltiger Port in eigener Portliste: {p!r}"
    if body.fritz_url is not None and body.fritz_url.strip() and not _valid_endpoint(body.fritz_url.strip()):
        return f"ungueltiges TR-064-Hauptgeraet: {body.fritz_url.strip()!r} (URL oder host:port erwartet)"
    if body.fritz_urls is not None and body.fritz_urls.strip():
        for u in body.fritz_urls.split(","):
            u = u.strip()
            if u and not _valid_endpoint(u):
                return f"ungueltiger weiterer TR-064-Endpunkt: {u!r} (URL oder host:port erwartet)"
    for key in ("notify_webhook", "notify_gotify", "notify_ntfy"):
        val = getattr(body, key)
        if val is not None and val.strip() and not val.strip().startswith(("http://", "https://")):
            return f"{key} muss eine http(s)-URL sein: {val.strip()!r}"
    if body.snmp_community is not None and body.snmp_community.strip() and re.search(r"\s", body.snmp_community.strip()):
        return "snmp_community darf keine Leerzeichen enthalten"
    if body.fritz_pass is not None and len(body.fritz_pass) > 256:
        return "fritz_pass darf hoechstens 256 Zeichen haben"
    if body.oui_online_max is not None and not 0 <= body.oui_online_max <= 200:
        return "oui_online_max muss zwischen 0 und 200 liegen"
    if body.oui_online_url is not None and body.oui_online_url.strip() and not body.oui_online_url.strip().startswith(("http://", "https://")):
        return f"oui_online_url muss eine http(s)-URL sein: {body.oui_online_url.strip()!r}"
    if body.subnets is not None and body.subnets.strip():
        for sn in body.subnets.split(","):
            try:
                ipaddress.ip_network(sn.strip(), strict=False)
            except ValueError:
                return f"ungültiges Subnetz: {sn.strip()!r} (CIDR erwartet, z. B. 192.168.178.0/24)"
    if body.snmp_switches is not None and body.snmp_switches.strip():
        for ip in body.snmp_switches.split(","):
            try:
                ipaddress.ip_address(ip.strip())
            except ValueError:
                return f"ungültige IP für SNMP-Switch: {ip.strip()!r}"
    if body.auto_export_dir is not None:
        d = body.auto_export_dir.strip()
        if not d or d.startswith("/") or ".." in d.split("/"):
            return "auto_export_dir muss ein relativer Ordnername innerhalb des Daten-Volumes sein"
    if body.auto_export_interval_hours is not None and not 0 <= body.auto_export_interval_hours <= 720:
        return "auto_export_interval_hours muss zwischen 0 (jeder Scan) und 720 liegen"
    if body.alarm_whitelist is not None and body.alarm_whitelist.strip():
        for entry in body.alarm_whitelist.split(","):
            e = entry.strip()
            if not e:
                continue
            try:
                ipaddress.ip_address(e)
                continue
            except ValueError:
                pass
            parts = e.replace("-", ":").split(":")
            is_mac = len(parts) == 6 and all(len(p) in (1, 2) and all(c in "0123456789abcdefABCDEF" for c in p) for p in parts)
            if not is_mac:
                return f"ungueltiger Whitelist-Eintrag: {e!r} (MAC oder IP erwartet)"
    if body.sites is not None and body.sites.strip():
        for part in body.sites.split(";"):
            part = part.strip()
            if not part:
                continue
            if ":" not in part:
                return f"ungueltiger Standort-Eintrag: {part!r} (Format: Name:Subnetz[,Subnetz]; ...)"
            name, _, subs = part.partition(":")
            if not name.strip():
                return f"Standort ohne Namen: {part!r}"
            for sn in subs.split(","):
                sn = sn.strip()
                if not sn:
                    continue
                try:
                    ipaddress.ip_network(sn, strict=False)
                except ValueError:
                    return f"ungueltiges Subnetz im Standort {name.strip()!r}: {sn!r}"
    return None


@router.patch("/api/settings")
def patch_settings(body: SettingsPatch, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    error = validate_settings(body)
    if error:
        raise HTTPException(status_code=422, detail=error)
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


@router.get("/api/sites")
def sites_api(request: Request):
    s = request.app.state.settings
    return {"names": s.site_names, "map": s.site_map}


@router.get("/api/meta")
def meta(conn=Depends(get_conn)):
    return {
        "gateway": db.get_setting(conn, "gateway") or "",
        "gateway6": db.get_setting(conn, "gateway6") or "",
        "wan_ip": db.get_setting(conn, "wan_ip") or "",
        "wan_status": db.get_setting(conn, "wan_status") or "",
    }


@router.post("/api/layout/reset")
def layout_reset(conn=Depends(get_conn), _=Depends(require_auth)):
    conn.execute("UPDATE device_layout SET x = NULL, y = NULL")
    conn.commit()
    return {"ok": True}


@router.get("/api/logs")
def get_logs(request: Request, lines: int = 300, level: str = "", _=Depends(require_auth)):
    path = os.path.join(request.app.state.settings.data_dir, "netmap.log")
    all_lines: list[str] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            all_lines = fh.read().splitlines()
    out = all_lines[-lines:] if lines > 0 else all_lines
    if level:
        marker = f" {level.upper()} "
        out = [line for line in out if marker in line]
    return {"file": path, "total": len(all_lines), "returned": len(out), "lines": out}


@router.get("/api/logs/download")
def download_logs(request: Request, _=Depends(require_auth)):
    path = os.path.join(request.app.state.settings.data_dir, "netmap.log")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="noch keine Log-Datei vorhanden")
    return FileResponse(path, media_type="text/plain", filename="netmap.log")
