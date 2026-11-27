import json
import os

from app import db, exporters
from app.config import Settings


def make(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    settings = Settings(data_dir=str(tmp_path), history_hours=1)
    return conn, settings


def test_write_atomic_uses_tmp_and_replace(tmp_path, monkeypatch):
    calls = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((src, dst))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    target = str(tmp_path / "out.csv")
    exporters._write_atomic(target, "version-1\n")
    exporters._write_atomic(target, "version-2\n")
    assert calls == [(target + ".tmp", target), (target + ".tmp", target)]
    with open(target, encoding="utf-8") as fh:
        assert fh.read() == "version-2\n"
    assert not os.path.exists(target + ".tmp")


def test_auto_export_writes_valid_files_without_tmp_leftovers(tmp_path):
    conn, settings = make(tmp_path)
    now = db.utcnow()
    db.upsert_device(
        conn,
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "ip": "10.0.0.2",
            "hostname": "nas",
            "status": "online",
            "subnet": "10.0.0.0/24",
            "source": "ping+arp",
        },
        now,
    )
    conn.commit()
    written = exporters.auto_export(settings, conn)
    assert len(written) == 2
    for path in written:
        assert os.path.exists(path)
        assert not os.path.exists(path + ".tmp")
    json_path = next(p for p in written if p.endswith(".json"))
    csv_path = next(p for p in written if p.endswith(".csv"))
    with open(json_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["device_count"] == 1
    assert payload["devices"][0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert payload["devices"][0]["hostname"] == "nas"
    with open(csv_path, encoding="utf-8") as fh:
        assert "nas" in fh.read()
    conn.close()
