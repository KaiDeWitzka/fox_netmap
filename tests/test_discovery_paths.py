import logging

import pytest

from app import logsetup
from app.scanner import discover, ports, snmp


def test_discover_uses_post_multicast_ndp(monkeypatch):
    tables = iter([{}, {"2001:db8::1": "aa:bb:cc:dd:ee:ff"}])
    monkeypatch.setattr(discover, "arp_table", lambda: {})
    monkeypatch.setattr(discover, "neigh6_table", lambda: next(tables))
    monkeypatch.setattr(discover, "ping6_all_nodes", lambda timeout=2.0: ["2001:db8::1"])
    monkeypatch.setattr(discover.topology, "gateway_ip6", lambda: "")
    monkeypatch.setattr(discover, "ping_host", lambda ip, timeout: False)
    devs = discover.discover(["2001:db8::/64"], 0.1)
    assert devs == [{"ip": "2001:db8::1", "mac": "aa:bb:cc:dd:ee:ff", "source": "ndp"}]


def _cam_line(mac, port):
    oid = ".".join(str(int(x, 16)) for x in mac.split(":"))
    return f"1.3.6.1.2.1.17.7.1.2.2.1.2.1.{oid} = INTEGER: {port}"


def test_cam_map_ignores_uplink_port(monkeypatch):
    gw = "00:11:22:33:44:55"
    output = "\n".join(
        [
            _cam_line("aa:bb:cc:dd:ee:ff", 2),
            _cam_line("11:22:33:44:55:66", 1),
            _cam_line("22:33:44:55:66:77", 1),
            _cam_line(gw, 1),
        ]
    )
    monkeypatch.setattr(snmp, "snmp_walk", lambda ip, community, oid, timeout=5: output)
    mapping = snmp.cam_map(["10.0.0.1"], "public", exclude_macs={gw})
    assert mapping == {"aa:bb:cc:dd:ee:ff": "10.0.0.1"}


def test_port_list_validates_range():
    with pytest.raises(ValueError):
        ports.port_list(100, "70000")
    with pytest.raises(ValueError):
        ports.port_list(100, "abc")
    assert ports.port_list(100, "1,443,65535") == [1, 443, 65535]
    assert ports.port_list(0) == list(range(1, 65536))
    assert len(ports.port_list(5000)) == ports.MAX_PORT_TOP == 1040


def test_missing_binaries_log_warning_once(monkeypatch, caplog):
    logsetup.reset_run_warnings()
    monkeypatch.setattr(discover.shutil, "which", lambda name: None)

    def boom(*a, **kw):
        raise OSError("kein Binary")

    monkeypatch.setattr(discover.subprocess, "run", boom)
    assert discover.binaries_available() is False
    with caplog.at_level(logging.WARNING, logger="fox_netmap"):
        discover.local_subnets()
        discover.local_subnets()
        assert discover.ping_host("10.0.0.1", 0.1) is False
        assert discover.ping_host("10.0.0.2", 0.1) is False
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert sum("ip-Kommando" in m for m in msgs) == 1
    assert sum("ping nicht ausfuehrbar" in m for m in msgs) == 1
