"""Embed-Token-Scope (S-1): reine Funktionen auf der DB-Verbindung, von Routern und Services geteilt."""

import sqlite3
from typing import Any

from fastapi import HTTPException

from .. import db


def token_row(conn: sqlite3.Connection, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    row = db.get_valid_token(conn, token)
    if row is None:
        raise HTTPException(status_code=403, detail="invalid or expired token")
    return row


def token_allows(row: dict[str, Any] | None, dev: dict[str, Any]) -> bool:
    """S-1: Token-Scope gegen ein einzelnes Geraet pruefen. Leer = alles erlaubt."""
    if row is None:
        return True
    subs = [s.strip() for s in (row["subnets"] or "").split(",") if s.strip()]
    cats = [c.strip() for c in (row["categories"] or "").split(",") if c.strip()]
    if subs and dev.get("subnet", "") not in subs:
        return False
    return not (cats and dev.get("category", "") not in cats)


def token_filters(
    conn: sqlite3.Connection, token: str | None, subnet: str, category: str
) -> tuple[list[str] | None, list[str] | None, dict[str, Any] | None]:
    row = token_row(conn, token)
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
