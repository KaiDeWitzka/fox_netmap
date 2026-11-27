"""Router Meta/Health/Logs/Layout (W7/Q-4): oeffentliche Health, Meta/Sites (S-10), Logs, Layout-Reset."""

import os
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from .. import db
from ..models import HealthResponse, MetaResponse, SitesResponse
from ..scanner.categorize import CATEGORIES
from .common import get_conn, require_auth, require_auth_or_token

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # S-10: oeffentlicher Healthcheck liefert keine Metadaten mehr (Version, WAN-IP, Geraetezahl, Scanzeiten)
    return HealthResponse(status="ok")


@router.get("/api/categories", response_model=list[str])
def categories() -> list[str]:
    return CATEGORIES


@router.get("/api/meta", response_model=MetaResponse)
def meta(
    request: Request, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth_or_token)
) -> MetaResponse:
    return MetaResponse(
        version=request.app.state.settings.app_version,
        gateway=db.get_setting(conn, "gateway") or "",
        gateway6=db.get_setting(conn, "gateway6") or "",
        wan_ip=db.get_setting(conn, "wan_ip") or "",
        wan_status=db.get_setting(conn, "wan_status") or "",
        wan_endpoint=db.get_setting(conn, "wan_endpoint") or "",
    )


@router.get("/api/sites", response_model=SitesResponse)
def sites_api(request: Request, _: None = Depends(require_auth_or_token)) -> SitesResponse:
    s = request.app.state.settings
    return SitesResponse(names=s.site_names, map=s.site_map)


@router.post("/api/layout/reset")
def layout_reset(conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)) -> dict[str, Any]:
    db.reset_layout(conn)
    conn.commit()
    return {"ok": True}


@router.get("/api/logs")
def get_logs(request: Request, lines: int = 300, level: str = "", _: None = Depends(require_auth)) -> dict[str, Any]:
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
def download_logs(request: Request, _: None = Depends(require_auth)) -> FileResponse:
    path = os.path.join(request.app.state.settings.data_dir, "netmap.log")
    return FileResponse(path, media_type="text/plain", filename="netmap.log")
