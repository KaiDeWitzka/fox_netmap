import logging
import os

import httpx

from app.config import Settings
from app.logsetup import get_logger
from app.scanner import notify


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code


def _settings(tmp_path, **kw):
    base = {"data_dir": str(tmp_path), "notify_webhook": "http://127.0.0.1:9/hook"}
    base.update(kw)
    return Settings(**base)


def _dev():
    return [{"mac": "aa:bb:cc:dd:ee:ff", "ip": "10.0.0.2", "hostname": "pc"}]


def test_redirect_status_counts_as_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **kw: _Resp(302))
    assert notify.notify_new_devices(_settings(tmp_path), _dev()) is False
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **kw: _Resp(500))
    assert notify.notify_new_devices(_settings(tmp_path), _dev()) is False
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **kw: _Resp(200))
    assert notify.notify_new_devices(_settings(tmp_path), _dev()) is True

    def boom(*a, **kw):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(notify.httpx, "post", boom)
    assert notify.notify_new_devices(_settings(tmp_path), _dev()) is False


def test_no_devices_is_success_without_http(tmp_path):
    assert notify.notify_new_devices(_settings(tmp_path), []) is True


def test_failure_is_written_to_log_file(monkeypatch, tmp_path):
    root = logging.getLogger("fox_netmap")
    old_handlers = root.handlers[:]
    root.handlers = []
    try:
        get_logger(data_dir=str(tmp_path))

        def boom(*a, **kw):
            raise httpx.ConnectError("nope")

        monkeypatch.setattr(notify.httpx, "post", boom)
        assert notify.notify_new_devices(_settings(tmp_path), _dev()) is False
        for h in root.handlers:
            h.flush()
        with open(os.path.join(str(tmp_path), "netmap.log"), encoding="utf-8") as fh:
            text = fh.read()
        assert "Webhook-Benachrichtigung fehlgeschlagen" in text
        assert "fox_netmap.notify" in text
    finally:
        root.handlers = old_handlers
