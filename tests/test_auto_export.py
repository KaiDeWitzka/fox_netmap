import os
import re

import pytest

from app import db, exporters
from app.config import Settings


def make(tmp_path, **kw):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    base = {"data_dir": str(tmp_path), "history_hours": 1}
    base.update(kw)
    return conn, Settings(**base)


def test_auto_export_writes_files_inside_data_dir(tmp_path):
    conn, settings = make(tmp_path, auto_export_dir="exports")
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
    data_real = os.path.realpath(str(tmp_path))
    for p in written:
        assert os.path.realpath(p).startswith(data_real + os.sep)
        assert re.fullmatch(r"netmap-.+\.(json|csv)", os.path.basename(p))
    assert any(p.endswith(".json") for p in written)
    assert any(p.endswith(".csv") for p in written)
    conn.close()


def test_auto_export_dir_cannot_escape_data_dir(tmp_path):
    conn, settings = make(tmp_path, auto_export_dir="../evil")
    with pytest.raises(ValueError):
        exporters.auto_export(settings, conn)
    assert not os.path.exists(tmp_path / "evil")
    conn.close()
