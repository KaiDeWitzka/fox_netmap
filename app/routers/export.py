"""Router Export (W7/Q-4): JSON, CSV und serverseitiges PDF (S-6: 16 MP, Token nie mit Bild)."""

import base64
import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from PIL import UnidentifiedImageError
from pydantic import BaseModel

from .. import exporters
from ..services.devices import filtered_devices
from .common import get_conn, require_auth_or_token

router = APIRouter()
log = logging.getLogger("fox_netmap")


class PdfExport(BaseModel):
    image: str | None = None
    title: str | None = None
    orientation: str | None = None


def _rows(
    request: Request,
    conn: sqlite3.Connection,
    q: str,
    category: str,
    status: str,
    subnet: str,
    site: str,
    room: str,
    token: str,
) -> list[dict[str, Any]]:
    return filtered_devices(request, conn, q, category, status, subnet, site, room, token or None)


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
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict[str, Any]:
    rows = _rows(request, conn, q, category, status, subnet, site, room, token)
    return exporters.devices_payload(request.app.state.settings, rows, conn)


@router.post("/api/export/pdf")
def export_pdf(
    request: Request,
    payload: PdfExport,
    _: None = Depends(require_auth_or_token),  # Token erlaubt read-only Export, aber S-6: nie mit Bild
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    site: str = "",
    room: str = "",
    token: str = "",
    conn: sqlite3.Connection = Depends(get_conn),
) -> Response:
    rows = _rows(request, conn, q, category, status, subnet, site, room, token)
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
    except (UnidentifiedImageError, OSError):
        # N-4: nur echte Bild-Lesefehler werden als 422 gemeldet
        if image_bytes:
            raise HTTPException(422, "image konnte nicht gelesen werden (PNG/JPEG erwartet)") from None
        log.exception("PDF-Export fehlgeschlagen")
        raise HTTPException(500, "PDF-Export fehlgeschlagen") from None
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
    conn: sqlite3.Connection = Depends(get_conn),
) -> PlainTextResponse:
    delimiter = ";" if sep == "semicolon" else ","
    rows = _rows(request, conn, q, category, status, subnet, site, room, token)
    return PlainTextResponse(
        exporters.to_csv(rows, delimiter),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fox_netmap.csv"},
    )
