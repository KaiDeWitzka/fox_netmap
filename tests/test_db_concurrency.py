import pytest

from app import db


def test_connect_does_not_take_write_lock(tmp_path, monkeypatch):
    path = str(tmp_path / "a.db")
    probes = []
    orig = db._set_journal_mode

    def counting(conn, p):
        probes.append(p)
        return orig(conn, p)

    monkeypatch.setattr(db, "_set_journal_mode", counting)
    c1 = db.connect(path)
    assert c1.in_transaction is False
    c2 = db.connect(path)
    assert probes == [path]
    c2.execute("BEGIN IMMEDIATE")
    c2.execute("CREATE TABLE IF NOT EXISTS lock_probe (x INTEGER)")
    c2.commit()
    assert c1.in_transaction is False
    c1.close()
    c2.close()


def test_set_oui_cache_commits_immediately(tmp_path):
    path = str(tmp_path / "t.db")
    conn = db.connect(path)
    db.init_db(conn)
    other = db.connect(path)
    db.set_oui_cache(conn, "aa:bb:cc", "Acme GmbH")
    assert not conn.in_transaction
    assert db.get_oui_cache(other, "aa:bb:cc") == "Acme GmbH"
    other.close()
    conn.close()


def test_set_layout_updates_only_given_columns(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    mac = "aa:bb:cc:dd:ee:ff"
    db.set_layout(conn, mac, x=1.0, y=2.0, connected_to="bb:bb:bb:bb:bb:bb", connected_manual=1)
    conn.commit()
    db.set_layout(conn, mac, x=9.0)
    conn.commit()
    lay = db.get_layout(conn, mac)
    assert lay["x"] == 9.0
    assert lay["y"] == 2.0
    assert lay["connected_to"] == "bb:bb:bb:bb:bb:bb"
    assert lay["connected_manual"] == 1
    db.set_layout(conn, "cc:cc:cc:cc:cc:cc")
    assert db.get_layout(conn, "cc:cc:cc:cc:cc:cc") is None
    conn.close()


def test_read_snapshot_consistent_during_commit(tmp_path):
    path = str(tmp_path / "t.db")
    conn = db.connect(path)
    db.init_db(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if str(mode).lower() != "wal":
        pytest.skip("konsistenter Lese-Schnappschuss setzt WAL voraus")
    now = db.utcnow()
    db.upsert_device(conn, {"mac": "aa:aa:aa:aa:aa:01", "ip": "10.0.0.2", "hostname": "alt", "status": "online"}, now)
    conn.commit()
    other = db.connect(path)
    with db.read_snapshot(conn):
        before = db.list_devices(conn)
        db.upsert_device(
            other, {"mac": "bb:bb:bb:bb:bb:02", "ip": "10.0.0.3", "hostname": "neu", "status": "online"}, now
        )
        other.commit()
        during = db.list_devices(conn)
        assert [r["mac"] for r in before] == ["aa:aa:aa:aa:aa:01"]
        assert [r["mac"] for r in during] == ["aa:aa:aa:aa:aa:01"]
    after = db.list_devices(conn)
    assert {r["mac"] for r in after} == {"aa:aa:aa:aa:aa:01", "bb:bb:bb:bb:bb:02"}
    other.close()
    conn.close()
