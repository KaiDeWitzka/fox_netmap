import sqlite3
import threading

from app import db


def make_conn(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    db.init_db(conn)
    return conn


def test_scan_state_singleton(tmp_path):
    conn = make_conn(tmp_path)
    state = db.get_scan_state(conn)
    assert state["scanning"] == 0
    assert state["last_scan"] is None


def test_upsert_list_ports(tmp_path):
    conn = make_conn(tmp_path)
    now = db.utcnow()
    db.upsert_device(
        conn,
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "ip": "192.168.1.10",
            "hostname": "nas",
            "vendor": "Synology",
            "category": "Server/NAS",
            "status": "online",
            "subnet": "192.168.1.0/24",
            "source": "ping+arp",
        },
        now,
    )
    conn.commit()
    db.replace_ports(conn, "aa:bb:cc:dd:ee:ff", [{"port": 443, "service": "https"}, {"port": 80, "service": "http"}], now)
    conn.commit()
    rows = db.list_devices(conn)
    assert len(rows) == 1
    assert rows[0]["ports_str"] == "80;443"
    assert rows[0]["port_count"] == 2
    assert len(db.list_devices(conn, q="nas")) == 1
    assert len(db.list_devices(conn, q="synology")) == 1
    assert len(db.list_devices(conn, category="Server/NAS")) == 1
    assert db.list_devices(conn, category="Drucker") == []
    assert db.list_devices(conn, status="offline") == []
    dev = db.get_device(conn, "aa:bb:cc:dd:ee:ff")
    assert dev["ports"][0]["port"] == 80
    assert db.get_device(conn, "00:00:00:00:00:00") is None


def test_category_override_kept_on_rescan(tmp_path):
    conn = make_conn(tmp_path)
    now = db.utcnow()
    db.upsert_device(conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "10.0.0.2", "category": "Unbekannt", "status": "online"}, now)
    conn.execute("UPDATE devices SET category_override='Drucker', category='Drucker' WHERE mac='aa:bb:cc:dd:ee:ff'")
    conn.commit()
    db.upsert_device(conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "10.0.0.2", "category": "Client", "status": "online"}, now)
    conn.commit()
    assert db.list_devices(conn)[0]["category"] == "Drucker"


def test_layout_roundtrip(tmp_path):
    conn = make_conn(tmp_path)
    db.set_layout(conn, "aa:bb:cc:dd:ee:ff", x=10.0, y=20.0, connected_to="11:22:33:44:55:66", connected_manual=1)
    conn.commit()
    lay = db.get_layout(conn, "aa:bb:cc:dd:ee:ff")
    assert lay["x"] == 10.0 and lay["connected_to"] == "11:22:33:44:55:66" and lay["connected_manual"] == 1
    db.set_layout(conn, "aa:bb:cc:dd:ee:ff", x=99.0)
    conn.commit()
    lay = db.get_layout(conn, "aa:bb:cc:dd:ee:ff")
    assert lay["x"] == 99.0 and lay["y"] == 20.0 and lay["connected_to"] == "11:22:33:44:55:66"


def test_tokens(tmp_path):
    conn = make_conn(tmp_path)
    now = db.utcnow()
    db.create_token(conn, "tok1", "", "", "", now)
    db.create_token(conn, "tok2", "2000-01-01T00:00:00+00:00", "", "", now)
    conn.commit()
    assert db.get_valid_token(conn, "tok1") is not None
    assert db.get_valid_token(conn, "tok2") is None
    assert db.get_valid_token(conn, "nope") is None
    assert len(db.list_tokens(conn)) == 2
    db.delete_token(conn, "tok1")
    conn.commit()
    assert db.get_valid_token(conn, "tok1") is None


def test_trim_history(tmp_path):
    conn = make_conn(tmp_path)
    conn.execute("INSERT INTO device_history (mac, ts, status) VALUES ('m', '2000-01-01T00:00:00+00:00', 'online')")
    conn.execute("INSERT INTO device_history (mac, ts, status) VALUES ('m', ?, 'online')", (db.utcnow(),))
    conn.commit()
    db.trim_history(conn, 1, db.utcnow())
    assert len(conn.execute("SELECT ts FROM device_history").fetchall()) == 1


def test_dedupe_devices_by_ip(tmp_path):
    conn = make_conn(tmp_path)
    now = db.utcnow()
    conn.execute(
        "INSERT INTO devices (mac, ip, hostname, status, subnet, source, last_seen, first_seen) VALUES "
        "('b0:4a:39:01:78:3c', '192.168.178.33', 'kid-robot', 'online', '192.168.178.0/24', 'ping+arp', ?, ?)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO devices (mac, ip, hostname, status, subnet, source, last_seen, first_seen) VALUES "
        "('ip:192.168.178.33', '192.168.178.33', 'kid-robot', 'offline', '192.168.178.0/24', 'tr064', '2026-11-20T04:21:00+00:00', '2026-11-20T04:21:00+00:00')"
    )
    conn.execute("INSERT INTO device_ports (mac, port, scan_ts) VALUES ('b0:4a:39:01:78:3c', 80, ?)", (now,))
    conn.execute("INSERT INTO device_ports (mac, port, scan_ts) VALUES ('ip:192.168.178.33', 443, ?)", (now,))
    conn.execute("INSERT INTO device_layout (mac, x, y) VALUES ('ip:192.168.178.33', 5, 6)")
    conn.commit()
    removed = db.dedupe_devices_by_ip(conn)
    conn.commit()
    assert removed == 1
    rows = db.list_devices(conn)
    assert len(rows) == 1
    assert rows[0]["mac"] == "b0:4a:39:01:78:3c"
    assert rows[0]["status"] == "online"
    assert rows[0]["source"] == "ping+arp,tr064"
    assert rows[0]["ports_str"] == "80;443"
    assert rows[0]["x"] == 5


def test_migration_adds_room_column(tmp_path):
    conn = db.connect(str(tmp_path / "old.db"))
    conn.execute(
        "CREATE TABLE devices (mac TEXT PRIMARY KEY, ip TEXT NOT NULL DEFAULT '', hostname TEXT NOT NULL DEFAULT '',"
        " vendor TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Unbekannt', category_override TEXT,"
        " status TEXT NOT NULL DEFAULT 'offline', subnet TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',"
        " note TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL DEFAULT '', last_seen TEXT NOT NULL DEFAULT '')"
    )
    conn.commit()
    db.init_db(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)")}
    assert "room" in cols
    # Scanner-Upsert ueberschreibt room nicht
    db.upsert_device(conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.10", "hostname": "nas", "subnet": "192.168.1.0/24", "source": "ping"}, db.utcnow())
    conn.execute("UPDATE devices SET room = 'EG' WHERE mac = 'aa:bb:cc:dd:ee:ff'")
    conn.commit()
    db.upsert_device(conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.10", "hostname": "nas2", "subnet": "192.168.1.0/24", "source": "ping"}, db.utcnow())
    conn.commit()
    row = db.get_device(conn, "aa:bb:cc:dd:ee:ff")
    assert row["room"] == "EG"
    assert row["hostname"] == "nas2"
    conn.close()


def test_migration_adds_connection_column(tmp_path):
    conn = db.connect(str(tmp_path / "old.db"))
    conn.execute(
        "CREATE TABLE devices (mac TEXT PRIMARY KEY, ip TEXT NOT NULL DEFAULT '', hostname TEXT NOT NULL DEFAULT '',"
        " vendor TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Unbekannt', category_override TEXT,"
        " status TEXT NOT NULL DEFAULT 'offline', subnet TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',"
        " note TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL DEFAULT '', last_seen TEXT NOT NULL DEFAULT '')"
    )
    conn.commit()
    db.init_db(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)")}
    assert "connection" in cols
    conn.close()


def test_settings_kv(tmp_path):
    conn = make_conn(tmp_path)
    assert db.get_setting(conn, "scan_interval") is None
    db.set_setting(conn, "scan_interval", "300")
    conn.commit()
    assert db.get_setting(conn, "scan_interval") == "300"


def test_migration_adds_vpn_column(tmp_path):
    conn = db.connect(str(tmp_path / "old.db"))
    conn.execute(
        "CREATE TABLE devices (mac TEXT PRIMARY KEY, ip TEXT NOT NULL DEFAULT '', hostname TEXT NOT NULL DEFAULT '',"
        " vendor TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Unbekannt', category_override TEXT,"
        " status TEXT NOT NULL DEFAULT 'offline', subnet TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',"
        " note TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL DEFAULT '', last_seen TEXT NOT NULL DEFAULT '')"
    )
    conn.commit()
    db.init_db(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)")}
    assert "vpn" in cols
    conn.close()


def test_upsert_vpn_flag(tmp_path):
    conn = make_conn(tmp_path)
    now = db.utcnow()
    db.upsert_device(conn, {"mac": "00:7a:a4:9b:d9:68", "ip": "192.168.178.201", "vpn": True, "status": "online"}, now)
    conn.commit()
    assert db.get_device(conn, "00:7a:a4:9b:d9:68")["vpn"] == 1
    assert db.list_devices(conn)[0]["vpn"] == 1
    db.upsert_device(conn, {"mac": "00:7a:a4:9b:d9:68", "ip": "192.168.178.201", "vpn": False, "status": "offline"}, now)
    conn.commit()
    assert db.get_device(conn, "00:7a:a4:9b:d9:68")["vpn"] == 0




class _Row:
    def __init__(self, v):
        self.v = v

    def fetchone(self):
        return (self.v,)


class _FakeConn:
    """Duck-Typing fuer _set_journal_mode. probe_failures = Anzahl Schreibproben, die fehlschlagen."""

    def __init__(self, wal_ok=True, probe_failures=0):
        self.wal_ok = wal_ok
        self.probe_failures = probe_failures
        self.probe_calls = 0
        self.calls: list[str] = []

    def execute(self, sql, *args):
        self.calls.append(sql)
        if "journal_mode=WAL" in sql:
            if not self.wal_ok:
                raise sqlite3.OperationalError("disk I/O error")
            return _Row("wal")
        if "journal_mode=DELETE" in sql:
            return _Row("delete")
        if sql.startswith("BEGIN") or "fox_probe" in sql:
            self.probe_calls += 1
            if self.probe_calls <= self.probe_failures:
                raise sqlite3.OperationalError("disk I/O error")
            return _Row(None)
        return _Row(None)


def test_journal_mode_default_wal(tmp_path):
    conn = db.connect(str(tmp_path / "netmap.db"))
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    conn.close()


def test_journal_mode_fallback_delete_when_wal_probe_fails(monkeypatch, tmp_path):
    # WAL-Pragma ok, aber erste Schreibprobe (WAL) schlaegt fehl -> DELETE-Probe gelingt
    monkeypatch.delenv("NETZ_SQLITE_JOURNAL", raising=False)
    fake = _FakeConn(wal_ok=True, probe_failures=1)
    db._set_journal_mode(fake, str(tmp_path / "netmap.db"))
    assert any("journal_mode=DELETE" in c for c in fake.calls)


def test_journal_mode_clear_error_if_dir_unwritable(monkeypatch, tmp_path):
    # WAL- und DELETE-Probe schlagen beide fehl -> RuntimeError mit klarer Meldung
    monkeypatch.delenv("NETZ_SQLITE_JOURNAL", raising=False)
    fake = _FakeConn(wal_ok=True, probe_failures=99)
    try:
        db._set_journal_mode(fake, str(tmp_path / "netmap.db"))
        raise AssertionError("sollte RuntimeError werfen")
    except RuntimeError as exc:
        assert "nicht beschreibbar" in str(exc) and "Volume-Mount" in str(exc)


def test_journal_mode_forced_delete(monkeypatch, tmp_path):
    monkeypatch.setenv("NETZ_SQLITE_JOURNAL", "delete")
    fake = _FakeConn(wal_ok=True)
    db._set_journal_mode(fake, str(tmp_path / "netmap.db"))
    assert not any("journal_mode=WAL" in c for c in fake.calls)
    assert any("journal_mode=DELETE" in c for c in fake.calls)


def test_journal_mode_forced_wal_keeps_wal(monkeypatch, tmp_path):
    monkeypatch.setenv("NETZ_SQLITE_JOURNAL", "wal")
    fake = _FakeConn(wal_ok=True)
    db._set_journal_mode(fake, str(tmp_path / "netmap.db"))
    assert any("journal_mode=WAL" in c for c in fake.calls)
    assert not any("journal_mode=DELETE" in c for c in fake.calls)


def test_init_db_survives_dedupe_io_error(monkeypatch, tmp_path):
    conn = db.connect(str(tmp_path / "netmap.db"))

    def boom(c):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "dedupe_devices_by_ip", boom)
    db.init_db(conn)  # darf nicht crashen
    assert db.get_scan_state(conn)["id"] == 1
    conn.close()


def test_connect_usable_across_threads(tmp_path):
    # FastAPI/anyio fuehrt synchrone Generator-Depends (get_conn in api.py) mit
    # Enter und Exit in unterschiedlichen Worker-Threads aus. Ohne
    # check_same_thread=False wirft sqlite3 hier ProgrammingError.
    conn = db.connect(str(tmp_path / "netmap.db"))
    db.init_db(conn)
    errors = []

    def worker():
        try:
            db.set_scan_state(conn, scanning=1)
            conn.commit()
            assert db.get_scan_state(conn)["scanning"] == 1
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            conn.close()

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=10)
    assert not t.is_alive()
    assert errors == []
