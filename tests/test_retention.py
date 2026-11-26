from datetime import UTC, datetime, timedelta

from app import db
from app.config import Settings
from app.scanner import run


def make(tmp_path, **kw):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    base = dict(data_dir=str(tmp_path), history_hours=1, device_retention_days=30, event_retention_days=30)
    base.update(kw)
    return conn, Settings(**base)


def _ts(days_ago):
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def test_retention_boundaries_offline_29_kept_31_removed(tmp_path):
    conn, settings = make(tmp_path)
    for mac, days in (("aa:aa:aa:aa:aa:01", 29), ("bb:bb:bb:bb:bb:02", 31)):
        conn.execute(
            "INSERT INTO devices (mac, ip, status, last_seen, first_seen) VALUES (?, '10.0.0.2', 'offline', ?, ?)",
            (mac, _ts(days), _ts(days)),
        )
    conn.commit()
    assert run.apply_retention(conn, settings, db.utcnow()) == 1
    assert db.get_device(conn, "aa:aa:aa:aa:aa:01") is not None
    assert db.get_device(conn, "bb:bb:bb:bb:bb:02") is None


def test_old_online_device_is_kept(tmp_path):
    conn, settings = make(tmp_path)
    conn.execute(
        "INSERT INTO devices (mac, ip, status, last_seen, first_seen) VALUES ('cc:cc:cc:cc:cc:03', '10.0.0.3', 'online', ?, ?)",
        (_ts(100), _ts(100)),
    )
    conn.commit()
    assert run.apply_retention(conn, settings, db.utcnow()) == 0
    assert db.get_device(conn, "cc:cc:cc:cc:cc:03") is not None


def test_offline_without_last_seen_uses_first_seen(tmp_path):
    conn, settings = make(tmp_path)
    conn.execute(
        "INSERT INTO devices (mac, ip, status, last_seen, first_seen) VALUES ('dd:dd:dd:dd:dd:04', '10.0.0.4', 'offline', '', ?)",
        (_ts(40),),
    )
    conn.commit()
    assert run.apply_retention(conn, settings, db.utcnow()) == 1
    assert db.get_device(conn, "dd:dd:dd:dd:dd:04") is None


def test_event_retention_boundary(tmp_path):
    conn, _ = make(tmp_path)
    db.add_event(conn, "aa:aa:aa:aa:aa:01", "new", "alt", _ts(29))
    db.add_event(conn, "aa:aa:aa:aa:aa:01", "new", "neu", _ts(31))
    conn.commit()
    assert db.trim_events(conn, 30) == 1
    events = conn.execute("SELECT detail FROM device_events").fetchall()
    assert [e["detail"] for e in events] == ["alt"]
