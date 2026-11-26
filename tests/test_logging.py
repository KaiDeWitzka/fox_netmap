"""W1-B: Logger-Hierarchie (Q-8) - fox_netmap.notify/-mdns landen in netmap.log und im Log-Reiter."""

import logging
import os

from app.logsetup import get_logger


def test_notify_and_mdns_warnings_reach_log_file(tmp_path):
    root = logging.getLogger("fox_netmap")
    old_handlers = root.handlers[:]
    root.handlers = []
    try:
        log = get_logger(data_dir=str(tmp_path))
        logging.getLogger("fox_netmap.notify").warning("test-notify-warn")
        logging.getLogger("fox_netmap.mdns").warning("test-mdns-warn")
        for h in log.handlers:
            h.flush()
        with open(os.path.join(str(tmp_path), "netmap.log"), encoding="utf-8") as fh:
            text = fh.read()
        assert "test-notify-warn" in text
        assert "test-mdns-warn" in text
        assert "fox_netmap.notify" in text
    finally:
        root.handlers = old_handlers


def test_no_orphan_netmap_loggers():
    # Q-8: keine Logger mehr ausserhalb des fox_netmap-Baums
    import subprocess

    out = subprocess.run(["grep", "-rn", 'getLogger("netmap', "app/"], capture_output=True, text=True).stdout
    assert out == ""
