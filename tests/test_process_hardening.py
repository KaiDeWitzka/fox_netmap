"""W2 S-12 (Token im Accesslog schwaerzen), S-13 (X-Forwarded-For default aus), S-17 (Dateirechte 0600)."""

import logging
import os
import stat


def test_access_log_redacts_token():
    from app.logsetup import TokenRedactFilter

    f = TokenRedactFilter()
    rec = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '127.0.0.1 "GET /api/devices?token=abc123secret HTTP/1.1" 200',
        (),
        None,
    )
    assert f.filter(rec)
    msg = rec.getMessage()
    assert "abc123secret" not in msg
    assert "token=***" in msg


def test_uvicorn_proxy_headers_default_off(monkeypatch):
    # S-13: ohne NETZ_FORWARDED_ALLOW_IPS wertet uvicorn X-Forwarded-For nicht aus
    import app.__main__ as m

    monkeypatch.delenv("NETZ_FORWARDED_ALLOW_IPS", raising=False)
    assert m._uvicorn_kwargs()["proxy_headers"] is False
    monkeypatch.setenv("NETZ_FORWARDED_ALLOW_IPS", "10.0.0.0/8")
    assert m._uvicorn_kwargs()["proxy_headers"] is True
    assert m._uvicorn_kwargs()["forwarded_allow_ips"] == "10.0.0.0/8"


def test_data_files_not_world_readable(app):
    # S-17: netmap.db und netmap.log sind 0600
    import logging as _logging

    from app.logsetup import get_logger

    root = _logging.getLogger("fox_netmap")
    old = root.handlers[:]
    root.handlers = []
    try:
        get_logger(data_dir=app.state.settings.data_dir)
        root.warning("hardening-test")  # Log-Datei anlegen
        for h in root.handlers:
            h.flush()
        for name in ("netmap.db", "netmap.log"):
            path = os.path.join(app.state.settings.data_dir, name)
            assert os.path.exists(path), name
            mode = stat.S_IMODE(os.stat(path).st_mode)
            assert mode & 0o077 == 0, (name, oct(mode))
    finally:
        root.handlers = old
