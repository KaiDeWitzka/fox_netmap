"""Router Geraete (W7/Q-4): Liste, Detail, Bearbeiten, Loeschen, Mehrfach-Zuordnung."""

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..netutil import normalize_mac_key
from ..scanner.categorize import CATEGORIES
from ..services.authz import token_allows, token_row
from ..services.devices import check_parent, filtered_devices, site_of
from ..types import DeviceDetail, DeviceRow
from .common import get_conn, require_auth

router = APIRouter()


@router.get("/api/devices", response_model=list[DeviceRow])
def devices(
    request: Request,
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    site: str = "",
    room: str = "",
    token: str = "",
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[DeviceRow]:
    return filtered_devices(request, conn, q, category, status, subnet, site, room, token or None)  # type: ignore[return-value]


@router.get("/api/rooms", response_model=list[str])
def list_rooms(conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)) -> list[str]:
    return db.list_rooms(conn)


@router.get("/api/device/{mac}", response_model=DeviceDetail)
def device_detail(
    mac: str, request: Request, token: str = "", conn: sqlite3.Connection = Depends(get_conn)
) -> DeviceDetail:
    mac = normalize_mac_key(mac)  # C-15/Q-9: Pfad-MAC case-insensitive, ip:-Platzhalter unveraendert
    row = token_row(conn, token or None)
    dev = db.get_device(conn, mac)
    if dev is None or not token_allows(row, dev):
        raise HTTPException(status_code=404, detail="device not found")
    dev["site"] = site_of(dev.get("subnet", ""), request.app.state.settings)
    return dev  # type: ignore[return-value]


class DevicePatch(BaseModel):
    category: str | None = None
    note: str | None = Field(default=None, max_length=2000)
    room: str | None = Field(default=None, max_length=64)
    connected_to: str | None = Field(default=None, max_length=64)
    x: float | None = None
    y: float | None = None


class BulkConnect(BaseModel):
    """Mehrfach-Zuordnung von Hand: mehrere Geraete gemeinsam an einen Netzknoten haengen ("" = automatisch)."""

    macs: list[str] = Field(min_length=1, max_length=1000)
    connected_to: str = Field(default="", max_length=64)


@router.delete("/api/device/{mac}")
def delete_device(
    mac: str, request: Request, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)
) -> dict[str, Any]:
    mac = normalize_mac_key(mac)  # C-15/Q-9: Pfad-MAC case-insensitive, ip:-Platzhalter unveraendert
    """Loescht ein Geraet samt Verlauf (Recht auf Loeschung). Ist es noch im Netz, erscheint es beim naechsten Scan neu."""
    if not db.device_exists(conn, mac):
        raise HTTPException(status_code=404, detail="device not found")
    db.delete_device(conn, mac)
    conn.commit()
    import logging

    logging.getLogger("fox_netmap").info("Geraet %s manuell geloescht", mac)
    return {"ok": True}


@router.patch("/api/device/{mac}", response_model=DeviceDetail)
def patch_device(
    mac: str,
    body: DevicePatch,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    _: None = Depends(require_auth),
) -> DeviceDetail:
    mac = normalize_mac_key(mac)  # C-15/Q-9: Pfad-MAC case-insensitive, ip:-Platzhalter unveraendert
    if not db.device_exists(conn, mac):
        raise HTTPException(status_code=404, detail="device not found")
    if body.category is not None and body.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="unknown category")
    if body.connected_to is not None:
        err = check_parent(conn, {mac}, body.connected_to)
        if err:
            raise HTTPException(status_code=422, detail=err)
    db.update_device(
        conn,
        mac,
        category=body.category,
        note=body.note,
        room=body.room,
        connected_to=body.connected_to,
        x=body.x,
        y=body.y,
    )
    conn.commit()
    return db.get_device(conn, mac)  # type: ignore[return-value]


@router.post("/api/devices/connect")
def bulk_connect(
    body: BulkConnect, request: Request, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)
) -> dict[str, Any]:
    """Setzt \"Verbunden mit\" fuer mehrere Geraete in einer Transaktion. Alles oder nichts."""
    import logging

    macs = list(dict.fromkeys(body.macs))
    unknown = [m for m in macs if not db.device_exists(conn, m)]
    if unknown:
        raise HTTPException(status_code=404, detail=f"{len(unknown)} device(s) not found")
    err = check_parent(conn, set(macs), body.connected_to)
    if err:
        raise HTTPException(status_code=422, detail=err)
    for mac in macs:
        if body.connected_to == "":
            conn.execute("UPDATE device_layout SET connected_to = NULL, connected_manual = 0 WHERE mac = ?", (mac,))
        else:
            db.set_layout(conn, mac, connected_to=body.connected_to, connected_manual=1)
    conn.commit()
    logging.getLogger("fox_netmap").info(
        "Zuordnung von Hand: %d Geraet(e) -> %s", len(macs), body.connected_to or "automatisch"
    )
    return {"ok": True, "count": len(macs)}
