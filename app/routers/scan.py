"""Router Scan (W7/Q-4): manueller Scan anstossen, Status inkl. Fehler-/Haenger-Markern."""

import sqlite3
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from .. import db
from ..models import ScanStatusResponse
from .common import get_conn, require_auth, require_auth_or_token

router = APIRouter()


@router.post("/api/scan")
def trigger_scan(
    request: Request, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)
) -> dict[str, Any]:
    db.set_setting(conn, "scan_requested", db.utcnow())
    conn.commit()
    return {"status": "queued"}


@router.get("/api/scan/status", response_model=ScanStatusResponse)
def scan_status(
    request: Request, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth_or_token)
) -> ScanStatusResponse:
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
    # SF-5 (Anzeige): letzter Zustellstatus der Benachrichtigungen (Frontend zeigt ihn in den Einstellungen)
    state["last_notify_status"] = db.get_setting(conn, "last_notify_status") or ""
    state["last_notify_at"] = db.get_setting(conn, "last_notify_at") or ""
    return state  # type: ignore[return-value]
