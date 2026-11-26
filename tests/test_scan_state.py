from datetime import UTC, datetime, timedelta

import pytest

from app import db
from app.config import Settings
from app.scanner import run


def make(tmp_path, **kw):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    base = dict(data_dir=str(tmp_path), history_hours=1, subnets="10.0.0.0/24")
    base.update(kw)
    return conn, Settings(**base)


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


def _ts(days_ago):
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def test_empty_discovery_does_not_mark_offline_or_retain(tmp_path, monkeypatch):
    conn, settings = make(tmp_path, device_retention_days=30)
    now = db.utcnow()
    db.upsert_device(conn, dev("aa:aa:aa:aa:aa:01", "10.0.0.2", status="online"), now)
    conn.execute(
        "INSERT INTO devices (mac, ip, status, last_seen, first_seen) VALUES ('bb:bb:bb:bb:bb:02', '10.0.0.3', 'offline', ?, ?)",
        (_ts(40), _ts(40)),
    )
    conn.commit()
    monkeypatch.setattr(run, "collect_devices", lambda s, c: [])
    monkeypatch.setattr(run.discover, "binaries_available", lambda: False)
    summary = run.run_once(settings, conn)
    assert summary["seen"] == 0
    assert db.get_device(conn, "aa:aa:aa:aa:aa:01")["status"] == "online"
    assert db.get_device(conn, "bb:bb:bb:bb:bb:02") is not None
    state = db.get_scan_state(conn)
    assert state["scanning"] == 0
    assert state["consecutive_failures"] == 0


def test_empty_discovery_with_working_probes_marks_offline(tmp_path, monkeypatch):
    conn, settings = make(tmp_path)
    now = db.utcnow()
    db.upsert_device(conn, dev("aa:aa:aa:aa:aa:01", "10.0.0.2", status="online"), now)
    conn.commit()
    monkeypatch.setattr(run, "collect_devices", lambda s, c: [])
    monkeypatch.setattr(run.discover, "binaries_available", lambda: True)
    run.run_once(settings, conn)
    assert db.get_device(conn, "aa:aa:aa:aa:aa:01")["status"] == "offline"


def test_scan_error_recorded_and_cleared(tmp_path, monkeypatch):
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

    monkeypatch.setattr(run, "collect_devices", lambda s, c: [dev("aa:aa:aa:aa:aa:01", "10.0.0.2")])
    run.run_once(settings, conn)
    state = db.get_scan_state(conn)
    assert state["last_error"] is None
    assert state["last_error_at"] is None
    assert state["consecutive_failures"] == 0


def test_offline_record_keeps_last_seen(tmp_path):
    conn, _ = make(tmp_path)
    mac = "aa:aa:aa:aa:aa:01"
    db.upsert_device(conn, {"mac": mac, "ip": "10.0.0.2", "status": "offline"}, "2026-01-01T00:00:00+00:00")
    conn.commit()
    assert db.get_device(conn, mac)["last_seen"] == ""
    now = db.utcnow()
    db.upsert_device(conn, {"mac": mac, "ip": "10.0.0.2", "status": "online"}, now)
    conn.commit()
    assert db.get_device(conn, mac)["last_seen"] == now
    db.upsert_device(conn, {"mac": mac, "ip": "10.0.0.2", "status": "offline"}, db.utcnow())
    conn.commit()
    assert db.get_device(conn, mac)["last_seen"] == now
    conn.close()
