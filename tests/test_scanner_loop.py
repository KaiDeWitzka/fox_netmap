import logging
import os
import signal

import pytest

from app import db
from app.config import Settings
from app.scanner import run


def make(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    settings = Settings(data_dir=str(tmp_path), history_hours=1)
    return conn, settings


def dev(mac, ip, **kw):
    base = {
        "mac": mac,
        "ip": ip,
        "hostname": "",
        "vendor": "",
        "category": "Unbekannt",
        "status": "online",
        "subnet": "10.0.0.0/24",
        "source": "ping+arp",
        "ports": [],
        "layout": {},
    }
    base.update(kw)
    return base


def test_failed_apply_scan_rolls_back(tmp_path, monkeypatch):
    conn, settings = make(tmp_path)
    run.apply_scan(conn, settings, [dev("aa:aa:aa:aa:aa:01", "10.0.0.2")])
    n_hist = len(db.get_device(conn, "aa:aa:aa:aa:aa:01")["history"])

    def boom(c, mac, type_, detail, now):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(db, "add_event", boom)
    with pytest.raises(RuntimeError):
        run.apply_scan(
            conn,
            settings,
            [dev("aa:aa:aa:aa:aa:01", "10.0.0.2"), dev("bb:bb:bb:bb:bb:02", "10.0.0.3")],
        )
    assert not conn.in_transaction
    assert db.get_device(conn, "bb:bb:bb:bb:bb:02") is None
    d = db.get_device(conn, "aa:aa:aa:aa:aa:01")
    assert len(d["history"]) == n_hist
    conn.close()


def test_sigterm_stops_loop(tmp_path, monkeypatch):
    settings = Settings(data_dir=str(tmp_path), scan_interval=0, history_hours=1)
    monkeypatch.setattr(run, "get_settings", lambda: settings)
    calls = {"n": 0}

    def fake_run_once(s, c):
        calls["n"] += 1
        os.kill(os.getpid(), signal.SIGTERM)
        return {"seen": 0, "new": 0, "new_devices": [], "new_online": [], "removed": 0}

    monkeypatch.setattr(run, "run_once", fake_run_once)
    monkeypatch.setattr(run, "get_logger", lambda **kw: logging.getLogger("fox_netmap.test"))
    try:
        run.main()
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    assert calls["n"] >= 1
