"""Gemeinsame Typen (W7, Q-3/TL-5): `Device` ist ein Geraet in der Scanner-Pipeline,
`DeviceRow` eine Zeile aus `devices` inkl. Joins und API-Ergaenzung. Beide sind
`total=False`, weil der Code ueberall mit .get() arbeitet und Stufen Felder schrittweise setzen."""

from typing import Any, TypedDict


class Device(TypedDict, total=False):
    """Ein Geraet waehrend der Scanner-Pipeline (app/scanner/pipeline.py)."""

    mac: str
    ip: str
    ip6: str
    hostname: str
    vendor: str
    category: str
    category_reason: str
    status: str
    subnet: str
    source: str
    connection: str
    link_port: str
    note: str
    vpn: bool
    tr064_type: str
    tr064_active: bool
    tr064_endpoint: str
    ports: list[dict[str, Any]]
    layout: dict[str, Any]


class PortRow(TypedDict, total=False):
    port: int
    proto: str
    service: str
    scan_ts: str


class LayoutRow(TypedDict, total=False):
    x: float | None
    y: float | None
    connected_to: str | None
    connected_manual: int


class HistoryRow(TypedDict, total=False):
    ts: str
    status: str


class EventRow(TypedDict, total=False):
    ts: str
    type: str
    detail: str


class DeviceRow(TypedDict, total=False):
    """devices-Tabelle (18 Spalten nach Migration) + Joins (port_count, ports_str, x, y,
    connected_to) + site (wird in der API gesetzt)."""

    mac: str
    ip: str
    hostname: str
    vendor: str
    category: str
    category_override: str | None
    status: str
    subnet: str
    source: str
    note: str
    first_seen: str
    last_seen: str
    connection: str
    ip6: str
    link_port: str
    category_reason: str
    vpn: int
    room: str
    port_count: int
    ports_str: str | None  # GROUP_CONCAT liefert NULL, wenn ein Geraet keine Ports hat
    x: float | None
    y: float | None
    connected_to: str | None
    site: str


class DeviceDetail(DeviceRow, total=False):
    """GET /api/device/{mac}: Zeile + verschachtelte Tabellen."""

    ports: list[PortRow]
    layout: LayoutRow
    history: list[HistoryRow]
    events: list[EventRow]
