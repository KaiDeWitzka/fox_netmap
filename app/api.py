import base64
import logging
import os
import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from PIL import UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from . import db, exporters, validation
from .auth import is_valid_session
from .auth import router as auth_router
from .config import Settings, get_settings
from .netutil import normalize_mac_key
from .scanner.categorize import CATEGORIES
from .scanner.topology import vpn_pool_rules
from .settings_schema import FIELDS, exposed_fields

router = APIRouter()
router.include_router(auth_router)
log = logging.getLogger("fox_netmap")


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


def _token_row(conn, token: str | None):
    if not token:
        return None
    row = db.get_valid_token(conn, token)
    if row is None:
        raise HTTPException(status_code=403, detail="invalid or expired token")
    return row


def token_allows(row, dev: dict) -> bool:
    """S-1: Token-Scope gegen ein einzelnes Geraet pruefen. Leer = alles erlaubt."""
    if row is None:
        return True
    subs = [s.strip() for s in (row["subnets"] or "").split(",") if s.strip()]
    cats = [c.strip() for c in (row["categories"] or "").split(",") if c.strip()]
    if subs and dev.get("subnet", "") not in subs:
        return False
    return not (cats and dev.get("category", "") not in cats)


def _token_filters(
    conn, token: str | None, subnet: str, category: str
) -> tuple[list[str] | None, list[str] | None, object]:
    row = _token_row(conn, token)
    if row is None:
        return ([subnet] if subnet else None), ([category] if category else None), None
    subs = [s.strip() for s in (row["subnets"] or "").split(",") if s.strip()] or None
    cats = [c.strip() for c in (row["categories"] or "").split(",") if c.strip()] or None
    # S-1: ein angefragter Wert ausserhalb des Token-Scopes erweitert den Bereich nie (leere Liste = keine Treffer)
    if subs is not None:
        subs = [subnet] if subnet and subnet in subs else ([] if subnet else subs)
    if cats is not None:
        cats = [category] if category and category in cats else ([] if category else cats)
    return subs, cats, row


def require_auth_or_token(request: Request, conn=Depends(get_conn)) -> None:
    """S-10: Oeffentliche Pfade schrumpfen; diese Routen brauchen Sitzung oder gueltigen Embed-Token."""
    settings = request.app.state.settings
    if not settings.auth_enabled or is_valid_session(request.cookies.get("fox_session")):
        return
    token = request.query_params.get("token", "")
    if token and db.get_valid_token(conn, token):
        return
    raise HTTPException(status_code=401, detail="unauthorized")


def _site_of(subnet: str, settings: Settings) -> str:
    if not subnet:
        return ""
    site: str = settings.site_map.get(subnet, "")
    return site


def _filtered_devices(
    request: Request, conn, q: str, category: str, status: str, subnet: str, site: str, room: str, token: str | None
):
    subs, cats, _row = _token_filters(conn, token, subnet, category)
    rows = db.list_devices(conn, q=q, categories=cats, status=status, subnets=subs)
    settings = request.app.state.settings
    for r in rows:
        r["site"] = _site_of(r.get("subnet", ""), settings)
    if site:
        rows = [r for r in rows if r["site"] == site]
    if room:
        rows = [r for r in rows if (r.get("room") or "") == room]
    return rows


@router.get("/api/health")
def health():
    # S-10: oeffentlicher Healthcheck liefert keine Metadaten mehr (Version, WAN-IP, Geraetezahl, Scanzeiten)
    return {"status": "ok"}


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
    room: str = "",
    token: str = "",
    conn=Depends(get_conn),
):
    return _filtered_devices(request, conn, q, category, status, subnet, site, room, token or None)


@router.get("/api/rooms")
def list_rooms(conn=Depends(get_conn), _=Depends(require_auth)):
    rows = conn.execute("SELECT DISTINCT room FROM devices WHERE room != '' ORDER BY room").fetchall()
    return [r["room"] for r in rows]


@router.get("/api/device/{mac}")
def device_detail(mac: str, request: Request, token: str = "", conn=Depends(get_conn)):
    mac = normalize_mac_key(mac)  # C-15/Q-9: Pfad-MAC case-insensitive, ip:-Platzhalter unveraendert
    row = _token_row(conn, token or None)
    dev = db.get_device(conn, mac)
    if dev is None or not token_allows(row, dev):
        raise HTTPException(status_code=404, detail="device not found")
    dev["site"] = _site_of(dev.get("subnet", ""), request.app.state.settings)
    return dev


class DevicePatch(BaseModel):
    category: str | None = None
    note: str | None = Field(default=None, max_length=2000)
    room: str | None = Field(default=None, max_length=64)
    connected_to: str | None = Field(default=None, max_length=64)
    x: float | None = None
    y: float | None = None


class BulkConnect(BaseModel):
    """Mehrfach-Zuordnung von Hand: mehrere Geräte gemeinsam an einen Netzknoten hängen ("" = automatisch)."""

    macs: list[str] = Field(min_length=1, max_length=1000)
    connected_to: str = Field(default="", max_length=64)


def _device_exists(conn, mac: str) -> bool:
    return conn.execute("SELECT 1 FROM devices WHERE mac = ?", (mac,)).fetchone() is not None


def _check_parent(conn, macs: set[str], parent: str) -> None:
    """Prüft eine manuelle Zuordnung: Ziel existiert, kein Selbstbezug, kein Zyklus über die bestehende Kette."""
    if not parent:
        return
    if parent in macs:
        raise HTTPException(status_code=422, detail="device cannot be connected to itself")
    if not _device_exists(conn, parent):
        raise HTTPException(status_code=422, detail="unknown parent device")
    seen: set[str] = set()
    cur: str | None = parent
    while cur and cur not in seen and len(seen) < 10000:
        seen.add(cur)
        row = conn.execute("SELECT connected_to FROM device_layout WHERE mac = ?", (cur,)).fetchone()
        nxt = row["connected_to"] if row else None
        if nxt and not _device_exists(conn, nxt):
            by_ip = conn.execute("SELECT mac FROM devices WHERE ip = ?", (nxt,)).fetchone()
            nxt = by_ip["mac"] if by_ip else None
        if nxt in macs:
            raise HTTPException(status_code=422, detail="assignment would create a cycle")
        cur = nxt


@router.delete("/api/device/{mac}")
def delete_device(mac: str, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    mac = normalize_mac_key(mac)  # C-15/Q-9: Pfad-MAC case-insensitive, ip:-Platzhalter unveraendert
    """Löscht ein Gerät samt Verlauf (Recht auf Löschung). Ist es noch im Netz, erscheint es beim nächsten Scan neu."""
    if db.get_device(conn, mac) is None:
        raise HTTPException(status_code=404, detail="device not found")
    db.delete_device(conn, mac)
    conn.commit()
    log.info("Geraet %s manuell geloescht", mac)
    return {"ok": True}


@router.patch("/api/device/{mac}")
def patch_device(mac: str, body: DevicePatch, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    mac = normalize_mac_key(mac)  # C-15/Q-9: Pfad-MAC case-insensitive, ip:-Platzhalter unveraendert
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
    if body.room is not None:
        conn.execute("UPDATE devices SET room = ? WHERE mac = ?", (body.room.strip(), mac))
    if body.connected_to is not None:
        _check_parent(conn, {mac}, body.connected_to)
        if body.connected_to == "":
            conn.execute("UPDATE device_layout SET connected_to = NULL, connected_manual = 0 WHERE mac = ?", (mac,))
        else:
            db.set_layout(conn, mac, connected_to=body.connected_to, connected_manual=1)
    if body.x is not None or body.y is not None:
        db.set_layout(conn, mac, x=body.x, y=body.y)
    conn.commit()
    return db.get_device(conn, mac)


@router.post("/api/devices/connect")
def bulk_connect(body: BulkConnect, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    """Setzt \"Verbunden mit\" für mehrere Geräte in einer Transaktion. Alles oder nichts."""
    macs = list(dict.fromkeys(body.macs))
    unknown = [m for m in macs if not _device_exists(conn, m)]
    if unknown:
        raise HTTPException(status_code=404, detail=f"{len(unknown)} device(s) not found")
    _check_parent(conn, set(macs), body.connected_to)
    for mac in macs:
        if body.connected_to == "":
            conn.execute("UPDATE device_layout SET connected_to = NULL, connected_manual = 0 WHERE mac = ?", (mac,))
        else:
            db.set_layout(conn, mac, connected_to=body.connected_to, connected_manual=1)
    conn.commit()
    log.info("Zuordnung von Hand: %d Geraet(e) -> %s", len(macs), body.connected_to or "automatisch")
    return {"ok": True, "count": len(macs)}


@router.post("/api/scan")
def trigger_scan(request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    db.set_setting(conn, "scan_requested", db.utcnow())
    conn.commit()
    return {"status": "queued"}


@router.get("/api/scan/status")
def scan_status(request: Request, conn=Depends(get_conn), _=Depends(require_auth_or_token)):
    state = db.get_scan_state(conn)
    # SF-2/SF-3 (Leseseite): Fehlerfelder liegen in state; SF-3 markiert haengende Laeufe als veraltet
    settings = request.app.state.settings
    limit = max(1800, 3 * settings.scan_interval)
    stale = False
    started = state.get("scan_started_at")
    if state.get("scanning") and started:
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(started)).total_seconds()
            stale = age > limit
        except ValueError:
            stale = False
    state["scan_age_limit_s"] = limit
    state["stale_scanning"] = stale
    return state


@router.get("/api/export/json")
def export_json(
    request: Request,
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    site: str = "",
    room: str = "",
    token: str = "",
    conn=Depends(get_conn),
):
    rows = _filtered_devices(request, conn, q, category, status, subnet, site, room, token or None)
    return exporters.devices_payload(request.app.state.settings, rows, conn)


class PdfExport(BaseModel):
    image: str | None = None
    title: str | None = None
    orientation: str | None = None


@router.post("/api/export/pdf")
def export_pdf(
    request: Request,
    payload: PdfExport,
    _=Depends(require_auth_or_token),  # Token erlaubt read-only Export, aber S-6: nie mit Bild
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    site: str = "",
    room: str = "",
    token: str = "",
    conn=Depends(get_conn),
):
    rows = _filtered_devices(request, conn, q, category, status, subnet, site, room, token or None)
    image_bytes = None
    if payload.image:
        data = payload.image
        if data.startswith("data:"):
            data = data.split(",", 1)[1] if "," in data else ""
        try:
            image_bytes = base64.b64decode(data, validate=True)
        except Exception:  # noqa: BLE001 - W4/N-4: nur Decode-Fehler als 422, Rest -> 500 + log.exception
            raise HTTPException(422, "image ist kein gueltiges base64") from None
        if not image_bytes:
            raise HTTPException(422, "image ist leer")
        if len(image_bytes) > 12 * 1024 * 1024:
            raise HTTPException(422, "image zu gross (max 12 MB)")
        if not (image_bytes.startswith(b"\x89PNG") or image_bytes.startswith(b"\xff\xd8")):
            raise HTTPException(422, "image muss PNG oder JPEG sein")
        if request.query_params.get("token"):
            raise HTTPException(422, "image bei Token-Export nicht erlaubt")  # S-6
    title = (payload.title or "").strip()[:120]
    orientation = (payload.orientation or "portrait").strip().lower()
    if orientation not in ("portrait", "landscape"):
        raise HTTPException(422, "orientation muss 'portrait' oder 'landscape' sein")
    try:
        pdf = exporters.build_pdf(
            request.app.state.settings, rows, conn, image_bytes=image_bytes, title=title, orientation=orientation
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except (UnidentifiedImageError, OSError) as exc:
        # N-4: nur echte Bild-Lesefehler werden als 422 gemeldet
        if image_bytes:
            raise HTTPException(422, "image konnte nicht gelesen werden (PNG/JPEG erwartet)") from None
        log.exception("PDF-Export fehlgeschlagen")
        raise HTTPException(500, "PDF-Export fehlgeschlagen") from exc
    except Exception as exc:
        # N-4: Serverfehler (DB, reportlab) landen mit Logzeile als 500, nicht als Eingabefehler 422
        log.exception("PDF-Export fehlgeschlagen")
        raise HTTPException(500, "PDF-Export fehlgeschlagen") from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="fox_netmap.pdf"'},
    )


@router.get("/api/export/csv")
def export_csv(
    request: Request,
    sep: str = "semicolon",
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    site: str = "",
    room: str = "",
    token: str = "",
    conn=Depends(get_conn),
):
    delimiter = ";" if sep == "semicolon" else ","
    rows = _filtered_devices(request, conn, q, category, status, subnet, site, room, token or None)
    return PlainTextResponse(
        exporters.to_csv(rows, delimiter),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fox_netmap.csv"},
    )


@router.get("/api/settings")
def get_settings_api(request: Request):
    # Q-1/C-1: app.state.settings ist nach dem Start bereits Env+DB zusammengefuehrt und getypt (C-3).
    # S-8: Secrets werden nie im Klartext ausgeliefert, sondern nur als "configured".
    settings = request.app.state.settings
    out: dict = {}
    for key in exposed_fields():
        value = getattr(settings, key)
        out[key] = {"configured": bool(value)} if FIELDS[key].secret else value
    out["version"] = settings.app_version
    out["auth_user"] = settings.auth_user
    out["notify_configured"] = {
        "webhook": bool(settings.notify_webhook),
        "gotify": bool(settings.notify_gotify and settings.notify_gotify_token),
        "ntfy": bool(settings.notify_ntfy),
    }
    return out


class SettingsPatch(BaseModel):
    # Q-1: Feldmenge wird durch tests/test_settings_schema.py::test_settings_patch_model_matches_patchable_fields
    # gegen FIELDS in app/settings_schema.py abgeglichen. auth_enabled fehlt bewusst (S-9/E-2: nur NETZ_AUTH_ENABLED).
    model_config = ConfigDict(extra="ignore")

    subnets: str | None = None
    sites: str | None = None
    scan_interval: int | None = None
    scan_timeout: float | None = None
    port_top: int | None = None
    ports: str | None = None
    fritz_url: str | None = None
    fritz_urls: str | None = None
    fritz_user: str | None = None
    fritz_pass: str | None = None
    fritz_mesh: bool | None = None
    tr064_insecure_tls: bool | None = None
    vpn_pool: str | None = None
    snmp_enabled: bool | None = None
    snmp_community: str | None = None
    snmp_switches: str | None = None
    notify_webhook: str | None = None
    notify_gotify: str | None = None
    notify_gotify_token: str | None = None
    notify_ntfy: str | None = None
    notify_ntfy_token: str | None = None
    alarm_whitelist: str | None = None
    history_hours: int | None = None
    device_retention_days: int | None = None
    event_retention_days: int | None = None
    theme: str | None = None
    lang: str | None = None
    auto_export: bool | None = None
    auto_export_dir: str | None = None
    auto_export_interval_hours: int | None = None
    mdns_enabled: bool | None = None
    oui_online_enabled: bool | None = None
    oui_online_max: int | None = None
    oui_online_url: str | None = None


def validate_settings(body: BaseModel) -> str | None:  # noqa: C901 - Zerlegung in W7 (Q-2)
    # Q-2: reine Pruefer in app/validation.py, Meldungen woertlich gleich; Grenzen/Enums ueber FIELDS.
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        err = validation.check_range(key, value, FIELDS[key])
        if err:
            return err
    if str(data.get("ports", "")).strip():
        try:
            validation.parse_ports(data["ports"])
        except ValueError as exc:
            return str(exc)
    if str(data.get("fritz_url", "")).strip():
        try:
            validation.parse_endpoint(data["fritz_url"])
        except ValueError as exc:
            return f"ungueltiges TR-064-Hauptgeraet: {exc}"
    if str(data.get("fritz_urls", "")).strip():
        for u in data["fritz_urls"].split(","):
            u = u.strip()
            if u:
                try:
                    validation.parse_endpoint(u)
                except ValueError as exc:
                    return f"ungueltiger weiterer TR-064-Endpunkt: {exc}"
    for key in ("notify_webhook", "notify_gotify", "notify_ntfy"):
        val = data.get(key)
        if val is not None and str(val).strip():
            try:
                validation.parse_notify_url(key, val)
            except ValueError as exc:
                return str(exc)
    if str(data.get("snmp_community", "")).strip() and re.search(r"\s", data["snmp_community"].strip()):
        return "snmp_community darf keine Leerzeichen enthalten"
    if data.get("fritz_pass") is not None and len(data["fritz_pass"]) > 256:
        return "fritz_pass darf hoechstens 256 Zeichen haben"
    if str(data.get("oui_online_url", "")).strip():
        try:
            validation.parse_notify_url("oui_online_url", data["oui_online_url"])
        except ValueError as exc:
            return str(exc)
    if "vpn_pool" in data:
        try:
            vpn_pool_rules(data["vpn_pool"], "")
        except ValueError as exc:
            return f"ungueltiger vpn_pool-Eintrag: {exc}"
    if str(data.get("subnets", "")).strip():
        try:
            validation.parse_subnets(data["subnets"])
        except ValueError as exc:
            return str(exc)
    if str(data.get("snmp_switches", "")).strip():
        try:
            validation.parse_snmp_switches(data["snmp_switches"])
        except ValueError as exc:
            return str(exc)
    if "auto_export_dir" in data:
        try:
            validation.parse_auto_export_dir(data["auto_export_dir"])
        except ValueError as exc:
            return str(exc)
    if str(data.get("alarm_whitelist", "")).strip():
        try:
            validation.parse_whitelist(data["alarm_whitelist"])
        except ValueError as exc:
            return str(exc)
    if str(data.get("sites", "")).strip():
        try:
            validation.parse_sites(data["sites"])
        except ValueError as exc:
            return str(exc)
    return None


@router.patch("/api/settings")
def patch_settings(body: SettingsPatch, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    error = validate_settings(body)
    if error:
        raise HTTPException(status_code=422, detail=error)
    settings = request.app.state.settings
    data = body.model_dump(exclude_none=True)
    # S-7: wer den FRITZ!Box-Endpunkt aendert, darf das gespeicherte Passwort nicht an den neuen Host senden
    if any(k in data for k in ("fritz_url", "fritz_urls", "fritz_user")) and "fritz_pass" not in data:
        if get_settings().fritz_pass:  # Umgebungs-Passwort aktiv
            raise HTTPException(
                status_code=422,
                detail="bei Aenderung des TR-064-Endpunkts muss fritz_pass im selben PATCH stehen (Umgebungs-Passwort ist aktiv)",
            )
        db.set_setting(conn, "fritz_pass", "")
    for key, value in data.items():
        if FIELDS[key].secret and value == "":
            continue  # S-8: leeres Secret-Feld im PATCH heisst "unveraendert", loescht nichts
        db.set_setting(conn, key, str(value).lower() if isinstance(value, bool) else str(value))
        setattr(settings, key, value)
    conn.commit()
    return {"ok": True}


class TokenCreate(BaseModel):
    expires_hours: int | None = Field(
        default=None, ge=1, le=8760
    )  # C-10: 0/unbegrenzt und abgelaufen-in-Vergangenheit raus
    subnets: str = ""
    categories: str = ""


@router.post("/api/tokens")
def create_token(body: TokenCreate, request: Request, conn=Depends(get_conn), _=Depends(require_auth)):
    token = secrets.token_urlsafe(24)
    expires = ""
    if body.expires_hours:
        expires = (datetime.now(UTC) + timedelta(hours=body.expires_hours)).isoformat(timespec="seconds")
    db.create_token(conn, token, expires, body.subnets, body.categories, db.utcnow())
    conn.commit()
    return {"token": token, "expires": expires, "embed_url": f"/embed?token={token}"}


@router.get("/api/tokens")
def tokens_list(conn=Depends(get_conn), _=Depends(require_auth)):
    return db.list_tokens(conn)


@router.delete("/api/tokens/{ident}")
def delete_token(ident: str, conn=Depends(get_conn), _=Depends(require_auth)):
    db.delete_token(conn, ident)
    conn.commit()
    return {"ok": True}


@router.get("/api/sites")
def sites_api(request: Request, _=Depends(require_auth_or_token)):
    s = request.app.state.settings
    return {"names": s.site_names, "map": s.site_map}


@router.get("/api/meta")
def meta(request: Request, conn=Depends(get_conn), _=Depends(require_auth_or_token)):
    return {
        "version": request.app.state.settings.app_version,
        "gateway": db.get_setting(conn, "gateway") or "",
        "gateway6": db.get_setting(conn, "gateway6") or "",
        "wan_ip": db.get_setting(conn, "wan_ip") or "",
        "wan_status": db.get_setting(conn, "wan_status") or "",
        "wan_endpoint": db.get_setting(conn, "wan_endpoint") or "",
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
