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


def test_run_once_notifies_only_new_non_vpn_devices(tmp_path, monkeypatch):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    settings = Settings(
        data_dir=str(tmp_path), history_hours=1, subnets="10.0.0.0/24", alarm_whitelist="cc:cc:cc:cc:cc:03"
    )
    devices = [
        dev("aa:aa:aa:aa:aa:01", "10.0.0.2"),
        dev("bb:bb:bb:bb:bb:02", "10.0.0.201", vpn=True),
        dev("cc:cc:cc:cc:cc:03", "10.0.0.3"),
    ]
    monkeypatch.setattr(run, "collect_devices", lambda s, c: devices)
    sent = []
    monkeypatch.setattr(run.notify, "notify_new_devices", lambda s, ds: sent.append([d["mac"] for d in ds]) or True)
    summary = run.run_once(settings, conn)
    assert summary["new"] == 3
    assert sent == [["aa:aa:aa:aa:aa:01"]]
    assert db.get_setting(conn, "last_notify_status") == "ok"
    assert db.get_setting(conn, "last_notify_at")
    conn.close()


def test_run_once_resets_scanning_after_exception(tmp_path, monkeypatch):
    conn, settings = make(tmp_path)

    def boom(s, c):
        raise RuntimeError("scan kaputt")

    monkeypatch.setattr(run, "collect_devices", boom)
    with pytest.raises(RuntimeError):
        run.run_once(settings, conn)
    state = db.get_scan_state(conn)
    assert state["scanning"] == 0
    assert "scan kaputt" in (state["last_error"] or "")
    assert state["consecutive_failures"] == 1
    assert state["last_error_at"]
    conn.close()


def test_main_loop_calls_run_once(tmp_path, monkeypatch):
    settings = Settings(data_dir=str(tmp_path), scan_interval=60, history_hours=1)
    monkeypatch.setattr(run, "get_settings", lambda: settings)
    calls = {"n": 0}

    def fake_run_once(s, c):
        calls["n"] += 1
        return {"seen": 0, "new": 0, "new_devices": [], "new_online": [], "removed": 0}

    monkeypatch.setattr(run, "run_once", fake_run_once)
    monkeypatch.setattr(run, "get_logger", lambda **kw: logging.getLogger("fox_netmap.test"))
    sleeps = {"n": 0}

    def fake_sleep(s):
        sleeps["n"] += 1
        if sleeps["n"] >= 3:
            raise RuntimeError("stop-loop")

    monkeypatch.setattr(run.time, "sleep", fake_sleep)
    try:
        with pytest.raises(RuntimeError, match="stop-loop"):
            run.main()
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    assert calls["n"] >= 1
    assert sleeps["n"] == 3
