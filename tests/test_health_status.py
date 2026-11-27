from datetime import UTC, datetime, timedelta

from app import db, healthcheck


def _state(tmp_path, **fields):
    conn = db.connect(db.db_path(str(tmp_path)))
    db.init_db(conn)
    db.set_scan_state(conn, **fields)
    conn.commit()
    conn.close()


def test_healthcheck_unhealthy_after_three_failures(tmp_path):
    now = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    future = (now + timedelta(minutes=10)).isoformat()
    _state(tmp_path, scanning=0, consecutive_failures=2, last_error="boom", next_scan=future)
    ok, _ = healthcheck.check_scanner(str(tmp_path), scan_interval=60, now=now)
    assert ok
    _state(tmp_path, scanning=0, consecutive_failures=3, last_error="boom", next_scan=future)
    ok, msg = healthcheck.check_scanner(str(tmp_path), scan_interval=60, now=now)
    assert not ok
    assert "fehlgeschlagen" in msg and "boom" in msg


def test_stale_scanning_flag_is_unhealthy(tmp_path):
    now = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    _state(tmp_path, scanning=1, scan_started_at=(now - timedelta(hours=2)).isoformat())
    ok, msg = healthcheck.check_scanner(str(tmp_path), scan_interval=60, now=now)
    assert not ok and "haengt" in msg
    _state(tmp_path, scanning=1, scan_started_at=(now - timedelta(minutes=10)).isoformat())
    ok, msg = healthcheck.check_scanner(str(tmp_path), scan_interval=60, now=now)
    assert ok and "laeuft" in msg
