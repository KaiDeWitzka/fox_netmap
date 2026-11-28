"""Router Einstellungen (W7/Q-4): GET liefert getypte Werte, Secrets nur als {"configured": bool} (S-8)."""

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from .. import db, validation
from ..config import get_settings
from ..settings_schema import FIELDS, exposed_fields
from .common import get_conn, require_auth

router = APIRouter()


@router.get("/api/settings")
def get_settings_api(request: Request) -> dict[str, Any]:
    # Q-1/C-1: app.state.settings ist nach dem Start bereits Env+DB zusammengefuehrt und getypt (C-3).
    # S-8: Secrets werden nie im Klartext ausgeliefert, sondern nur als "configured".
    settings = request.app.state.settings
    out: dict[str, Any] = {}
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
    docker_enabled: bool | None = None
    docker_hosts: str | None = None
    docker_insecure_tls: bool | None = None
    docker_token: str | None = None
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


@router.patch("/api/settings")
def patch_settings(
    body: SettingsPatch, request: Request, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)
) -> dict[str, Any]:
    # Q-2: reine Pruefung in app/validation.py::validate_patch, Meldungen woertlich gleich
    data_all = body.model_dump(exclude_none=True)
    error = validation.validate_patch(data_all)
    if error:
        raise HTTPException(status_code=422, detail=error)
    settings = request.app.state.settings
    data = {k: v for k, v in body.model_dump().items() if k in body.model_fields_set}
    # S-7: wer den FRITZ!Box-Endpunkt aendert, darf das gespeicherte Passwort nicht an den neuen Host senden
    if any(k in data for k in ("fritz_url", "fritz_urls", "fritz_user")) and "fritz_pass" not in data:
        if get_settings().fritz_pass:  # Umgebungs-Passwort aktiv
            raise HTTPException(
                status_code=422,
                detail="bei Aenderung des TR-064-Endpunkts muss fritz_pass im selben PATCH stehen (Umgebungs-Passwort ist aktiv)",
            )
        db.set_setting(conn, "fritz_pass", "")
    for key, value in data.items():
        if value is None:
            # S-8 (Frontend "Loeschen"): explizites null bei einem Secret-Feld entfernt den gespeicherten
            # Wert (Zeile weg - C-2: ein leerer String wuerde die Umgebung ueberschreiben)
            if FIELDS[key].secret:
                db.delete_setting(conn, key)
                setattr(settings, key, "")
            continue
        if FIELDS[key].secret and value == "":
            continue  # S-8: leeres Secret-Feld im PATCH heisst "unveraendert", loescht nichts
        db.set_setting(conn, key, str(value).lower() if isinstance(value, bool) else str(value))
        setattr(settings, key, value)
    conn.commit()
    return {"ok": True}
