import sqlite3

import pytest

from app import db

OLD_SCHEMA = """
CREATE TABLE devices (
    mac TEXT PRIMARY KEY, ip TEXT NOT NULL DEFAULT '', hostname TEXT NOT NULL DEFAULT '',
    vendor TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Unbekannt', category_override TEXT,
    status TEXT NOT NULL DEFAULT 'offline', subnet TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL DEFAULT '', last_seen TEXT NOT NULL DEFAULT ''
);
CREATE TABLE embed_tokens (
    token TEXT PRIMARY KEY, expires TEXT, subnets TEXT NOT NULL DEFAULT '',
    categories TEXT NOT NULL DEFAULT '', created TEXT NOT NULL DEFAULT ''
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '');
CREATE TABLE scan_state (
    id INTEGER PRIMARY KEY CHECK (id = 1), last_scan TEXT, next_scan TEXT, scanning INTEGER NOT NULL DEFAULT 0
);
"""


def test_v10_db_upgrade_keeps_rows_and_tokens(tmp_path):
    path = str(tmp_path / "v10.db")
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.execute(
        "INSERT INTO devices (mac, ip, hostname, status, source, note, first_seen, last_seen) VALUES "
        "('aa:bb:cc:dd:ee:ff', '10.0.0.9', 'alt-pc', 'online', 'ping+arp', 'wichtig',"
        " '2025-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO embed_tokens (token, expires, created) VALUES "
        "('geheimertoken123', '2030-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00')"
    )
    conn.execute("INSERT INTO settings (key, value) VALUES ('theme', 'dark')")
    conn.commit()
    conn.close()

    conn = db.connect(path)
    db.init_db(conn)
    row = conn.execute("SELECT * FROM devices WHERE mac = 'aa:bb:cc:dd:ee:ff'").fetchone()
    assert row["hostname"] == "alt-pc"
    assert row["note"] == "wichtig"
    assert row["status"] == "online"
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)")}
    assert {"connection", "ip6", "link_port", "category_reason", "vpn", "room"} <= cols
    tok = conn.execute("SELECT token, hint, expires FROM embed_tokens").fetchone()
    assert tok["token"] == db.token_key("geheimertoken123")
    assert tok["token"].startswith("sha256:")
    assert tok["hint"] == "geheim"
    assert tok["expires"] == "2030-01-01T00:00:00+00:00"
    ss_cols = {r["name"] for r in conn.execute("PRAGMA table_info(scan_state)")}
    assert {"last_error", "last_error_at", "consecutive_failures", "scan_started_at"} <= ss_cols
    assert db.get_setting(conn, "theme") == "dark"
    assert db.get_scan_state(conn)["id"] == 1
    conn.close()


def test_migrate_ignores_duplicate_column(monkeypatch, tmp_path):
    conn = db.connect(str(tmp_path / "m.db"))
    db.init_db(conn)

    def boom(c):
        raise sqlite3.OperationalError("duplicate column name: devices.room")

    monkeypatch.setattr(db, "_migrate_inner", boom)
    db._migrate(conn)
    conn.close()


def test_migrate_reraises_other_errors(monkeypatch, tmp_path):
    conn = db.connect(str(tmp_path / "m.db"))
    db.init_db(conn)

    def boom(c):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "_migrate_inner", boom)
    with pytest.raises(sqlite3.OperationalError):
        db._migrate(conn)
    conn.close()
