import sqlite3

import pytest

from app import db


def make_conn(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    return conn


def insert_device(conn, mac, ip, source="ping+arp", status="offline", last_seen="2026-01-01T00:00:00+00:00"):
    conn.execute(
        "INSERT INTO devices (mac, ip, hostname, status, subnet, source, last_seen, first_seen)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (mac, ip, "host-" + mac[-5:].replace(":", ""), status, "10.0.0.0/24", source, last_seen, last_seen),
    )


def test_two_real_macs_same_ip_are_kept(tmp_path):
    conn = make_conn(tmp_path)
    insert_device(conn, "aa:aa:aa:aa:aa:01", "10.0.0.7", status="online", last_seen="2026-02-01T00:00:00+00:00")
    insert_device(conn, "bb:bb:bb:bb:bb:02", "10.0.0.7", last_seen="2026-01-01T00:00:00+00:00")
    conn.commit()
    assert db.dedupe.merge_placeholders(conn) == 0
    conn.commit()
    rows = {r["mac"] for r in db.list_devices(conn)}
    assert rows == {"aa:aa:aa:aa:aa:01", "bb:bb:bb:bb:bb:02"}


def test_placeholder_merges_into_real_mac(tmp_path):
    conn = make_conn(tmp_path)
    insert_device(conn, "aa:aa:aa:aa:aa:01", "10.0.0.7", status="online", last_seen="2026-02-01T00:00:00+00:00")
    insert_device(conn, "ip:10.0.0.7", "10.0.0.7", source="tr064", last_seen="2026-03-01T00:00:00+00:00")
    conn.execute(
        "INSERT INTO device_ports (mac, port, scan_ts) VALUES ('ip:10.0.0.7', 443, '2026-03-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO device_events (ts, mac, type, detail) VALUES ('2026-03-01T00:00:00+00:00', 'ip:10.0.0.7', 'new', 'x')"
    )
    conn.execute("INSERT INTO device_layout (mac, x, y) VALUES ('ip:10.0.0.7', 5, 6)")
    conn.execute("INSERT INTO device_layout (mac, x, y) VALUES ('aa:aa:aa:aa:aa:01', 1, 2)")
    conn.commit()
    assert db.dedupe.merge_placeholders(conn) == 1
    conn.commit()
    rows = db.list_devices(conn)
    assert len(rows) == 1
    assert rows[0]["mac"] == "aa:aa:aa:aa:aa:01"
    assert rows[0]["source"] == "ping+arp,tr064"
    assert rows[0]["status"] == "online"
    assert rows[0]["last_seen"] == "2026-03-01T00:00:00+00:00"
    assert rows[0]["ports_str"] == "443"
    assert rows[0]["x"] == 1
    ev = conn.execute("SELECT mac FROM device_events WHERE type = 'new'").fetchone()
    assert ev["mac"] == "aa:aa:aa:aa:aa:01"


def test_known_mac_ignores_stale_ip(tmp_path):
    conn = make_conn(tmp_path)
    now = db.utcnow()
    db.upsert_device(conn, {"mac": "aa:aa:aa:aa:aa:01", "ip": "10.0.0.7", "status": "offline", "hostname": "alt"}, now)
    conn.commit()
    db.upsert_device(conn, {"mac": "bb:bb:bb:bb:bb:02", "ip": "10.0.0.7", "status": "online", "hostname": "neu"}, now)
    conn.commit()
    rows = {r["mac"]: r["ip"] for r in db.list_devices(conn)}
    assert rows["bb:bb:bb:bb:bb:02"] == "10.0.0.7"
    assert rows["aa:aa:aa:aa:aa:01"] == ""


def test_dedupe_failure_rolls_back(tmp_path):
    conn = make_conn(tmp_path)
    insert_device(conn, "aa:aa:aa:aa:aa:01", "10.0.0.7", status="online")
    insert_device(conn, "ip:10.0.0.7", "10.0.0.7", source="tr064")
    conn.execute("INSERT INTO device_ports (mac, port) VALUES ('ip:10.0.0.7', 443)")
    conn.execute("CREATE TRIGGER boom BEFORE UPDATE ON device_ports BEGIN SELECT RAISE(ABORT, 'kaputt'); END")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.dedupe.merge_placeholders(conn)
    conn.rollback()
    assert db.get_device(conn, "ip:10.0.0.7") is not None
    assert conn.execute("SELECT mac FROM device_ports WHERE mac = 'ip:10.0.0.7'").fetchone() is not None
    row = db.get_device(conn, "aa:aa:aa:aa:aa:01")
    assert row["source"] == "ping+arp"
    assert row["status"] == "online"
