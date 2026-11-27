import base64
from contextlib import suppress

from PIL import UnidentifiedImageError

from app import exporters


def _png_b64():
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()


def test_pdf_internal_error_not_reported_as_422(auth_client, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("db kaputt")

    monkeypatch.setattr(exporters, "build_pdf", boom)
    r = auth_client.post("/api/export/pdf", json={})
    assert r.status_code == 500


def test_pdf_internal_error_with_image_is_500_not_422(auth_client, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("reportlab kaputt")

    monkeypatch.setattr(exporters, "build_pdf", boom)
    r = auth_client.post("/api/export/pdf", json={"image": f"data:image/png;base64,{_png_b64()}"})
    assert r.status_code == 500


def test_pdf_image_decode_error_is_422(auth_client, monkeypatch):
    def boom(*a, **kw):
        raise UnidentifiedImageError("cannot identify image file")

    monkeypatch.setattr(exporters, "build_pdf", boom)
    r = auth_client.post("/api/export/pdf", json={"image": f"data:image/png;base64,{_png_b64()}"})
    assert r.status_code == 422
    assert "image" in r.json()["detail"]


def _decode_pdf_streams(pdf: bytes) -> bytes:
    """reportlab komprimiert Seiten mit ASCII85+Flate oder Flate - beides dekodieren."""
    import base64
    import re
    import zlib

    out = b""
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        raw = m.group(1).strip()
        for candidate in (raw, raw.removesuffix(b"~>")):
            try:
                out += zlib.decompress(candidate)
                break
            except zlib.error:
                continue
        else:
            with suppress(Exception):  # fremde Streams (z. B. Bilder) ignorieren
                out += zlib.decompress(base64.a85decode(raw.removesuffix(b"~>"), adobe=False))
    return out


def test_pdf_long_text_is_wrapped_not_overlapping(auth_client, app, settings):
    """3846cc9-Killer: Zellen sind Paragraphs - ein 300-Zeichen-Hostname wird umgebrochen
    (viele kurze Text-Ops, max. ~14 Zeichen). Bei rohen Strings kaeme ein einzelner
    300-Zeichen-Lauf, der die Zelle ueberlappt."""
    from app import db
    from app.scanner import run

    conn = db.connect(app.state.db_path)
    try:
        run.apply_scan(
            conn,
            settings,
            [
                {
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "ip": "10.0.0.5",
                    "hostname": "H" * 300,
                    "vendor": "",
                    "category": "Client",
                    "status": "online",
                    "subnet": "10.0.0.0/24",
                    "source": "ping",
                    "ports": [],
                    "layout": {},
                }
            ],
        )
    finally:
        conn.close()
    r = auth_client.post("/api/export/pdf", json={})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    content = _decode_pdf_streams(r.content)
    assert b"H" * 10 in content  # der Text ist im PDF enthalten
    assert b"H" * 200 not in content  # ...aber umgebrochen, kein einzelner ueberlappender Lauf
