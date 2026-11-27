"""Router Embed-Tokens (W7/Q-4): anlegen (Klartext nur in der Antwort), listen (nur Hash+Hint), loeschen."""

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import db
from ..models import TokenListItem
from .common import get_conn, require_auth

router = APIRouter()


class TokenCreate(BaseModel):
    expires_hours: int | None = Field(
        default=None, ge=1, le=8760
    )  # C-10: 0/unbegrenzt und abgelaufen-in-Vergangenheit raus
    subnets: str = ""
    categories: str = ""


@router.post("/api/tokens")
def create_token(
    body: TokenCreate, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)
) -> dict[str, Any]:
    token = secrets.token_urlsafe(24)
    expires = ""
    if body.expires_hours:
        expires = (datetime.now(UTC) + timedelta(hours=body.expires_hours)).isoformat(timespec="seconds")
    db.create_token(conn, token, expires, body.subnets, body.categories, db.utcnow())
    conn.commit()
    return {"token": token, "expires": expires, "embed_url": f"/embed?token={token}"}


@router.get("/api/tokens", response_model=list[TokenListItem])
def tokens_list(conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)) -> list[TokenListItem]:
    return db.list_tokens(conn)  # type: ignore[return-value]


@router.delete("/api/tokens/{ident}")
def delete_token(
    ident: str, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)
) -> dict[str, Any]:
    db.delete_token(conn, ident)
    conn.commit()
    return {"ok": True}
