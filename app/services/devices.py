"""Geraete-Service (W7/Q-4): Listenfilter inkl. Token-Scope, Standort, manuelle Zuordnung (Zykluspruefung)."""

import sqlite3
from typing import Any

from fastapi import Request

from .. import db
from ..config import Settings
from .authz import token_filters


def site_of(subnet: str, settings: Settings) -> str:
    if not subnet:
        return ""
    return settings.site_map.get(subnet, "")


def filtered_devices(
    request: Request,
    conn: sqlite3.Connection,
    q: str,
    category: str,
    status: str,
    subnet: str,
    site: str,
    room: str,
    token: str | None,
) -> list[dict[str, Any]]:
    """Geraete-Liste mit Suche/Filter + Token-Scope (S-1) + Standort/Raum."""
    subs, cats, _row = token_filters(conn, token, subnet, category)
    rows = db.list_devices(conn, q=q, categories=cats, status=status, subnets=subs)
    settings = request.app.state.settings
    for r in rows:
        r["site"] = site_of(r.get("subnet", ""), settings)
    if site:
        rows = [r for r in rows if r["site"] == site]
    if room:
        rows = [r for r in rows if (r.get("room") or "") == room]
    return rows


def check_parent(conn: sqlite3.Connection, macs: set[str], parent: str) -> str | None:
    """Manuelle Zuordnung pruefen. None = ok, sonst Fehlertext fuer HTTP 422."""
    if not parent:
        return None
    if parent in macs:
        return "device cannot be connected to itself"
    if not db.device_exists(conn, parent):
        return "unknown parent device"
    chain = db.parent_chain(conn, parent)
    if any(node in macs for node in chain[1:]):
        return "assignment would create a cycle"
    return None
