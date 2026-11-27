"""Gemeinsame Request-Dependencies der Router (W7/Q-4): DB-Verbindung + Auth-Pruefung."""

import sqlite3
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request

from .. import db
from ..auth import is_valid_session


def get_conn(request: Request) -> Generator[sqlite3.Connection, None, None]:
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


def require_auth_or_token(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    """S-10: Oeffentliche Pfade schrumpfen; diese Routen brauchen Sitzung oder gueltigen Embed-Token."""
    settings = request.app.state.settings
    if not settings.auth_enabled or is_valid_session(request.cookies.get("fox_session")):
        return
    token = request.query_params.get("token", "")
    if token and db.get_valid_token(conn, token):
        return
    raise HTTPException(status_code=401, detail="unauthorized")
