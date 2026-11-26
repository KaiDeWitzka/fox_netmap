import base64

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
