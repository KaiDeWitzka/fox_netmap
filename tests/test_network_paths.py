"""T-9/T-16 (W6): echte Netzpfade - TCP-Sonden gegen einen lokalen Socket auf 127.0.0.1
(e885216) und aufgezeichnete Ausgaben von ip/arp/ping/snmpwalk als Fixtures (tests/fixtures/net/)."""

import builtins
import socket
import subprocess
import threading
from pathlib import Path

import pytest

from app.scanner import discover, ports, snmp

FIXTURES = Path(__file__).parent / "fixtures" / "net"


class LocalListener:
    """Echter TCP-Listener auf 127.0.0.1: akzeptiert Verbindungen und schliesst sie sofort."""

    def __init__(self, sock: socket.socket, port: int):
        self._sock = sock
        self.port = port
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        self._sock.settimeout(0.2)
        while not self._stop:
            try:
                conn, _ = self._sock.accept()
                conn.close()
            except TimeoutError:
                continue
            except OSError:
                break

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop = True
        self._sock.close()
        self._thread.join(2)


def _listener_on_free_port() -> LocalListener:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    return LocalListener(sock, sock.getsockname()[1])


def _bind_probe_port():
    """Echten Socket an einem der PROBE_PORTS binden (tcp_probe_sweep nutzt die feste Liste)."""
    for p in discover.PROBE_PORTS:
        sock = socket.socket()
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", p))
            sock.listen(8)
            return sock, p
        except OSError:
            sock.close()
    return None, None


def _free_closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _fake_run(mapping: dict):
    """subprocess.run-Ersatz: Kommandozeilen-Schluessel -> (returncode, stdout) aus Fixtures."""
    real_run = subprocess.run

    def fake_run(args, **kw):
        key = " ".join(str(a) for a in args)
        for needle, (rc, out) in mapping.items():
            if needle in key:
                return subprocess.CompletedProcess(args, rc, stdout=out, stderr="")
        return real_run(args, **kw)

    return fake_run


# --- echte Sockets ---------------------------------------------------------------------------------


def test_check_port_open_and_closed():
    with _listener_on_free_port() as listener:
        assert ports.check_port("127.0.0.1", listener.port, 1.0) == listener.port
        assert ports.check_port("127.0.0.1", _free_closed_port(), 0.5) is None


def test_scan_ports_finds_local_listener():
    with _listener_on_free_port() as listener:
        found = ports.scan_ports("127.0.0.1", [listener.port, _free_closed_port()], timeout=0.5)
    assert [p["port"] for p in found] == [listener.port]
    assert all(p["proto"] == "tcp" for p in found)


def test_tcp_probe_against_local_socket():
    with _listener_on_free_port() as listener:
        assert discover.tcp_probe("127.0.0.1", timeout=0.5, ports=[listener.port]) is True
        assert discover.tcp_probe("127.0.0.1", timeout=0.3, ports=[_free_closed_port()]) is False


def test_tcp_probe_sweep_against_local_socket():
    sock, port = _bind_probe_port()
    if sock is None:
        pytest.skip("keiner der PROBE_PORTS ist auf 127.0.0.1 bindbar")
    with LocalListener(sock, port):
        found = discover.tcp_probe_sweep("127.0.0.0/30", set(), timeout=0.5)
        assert "127.0.0.1" in found  # e885216: TCP-Probe findet den lokalen Listener
        skipped = discover.tcp_probe_sweep("127.0.0.0/30", {"127.0.0.1"}, timeout=0.3)
        assert "127.0.0.1" not in skipped
    assert discover.tcp_probe_sweep("kaputt", set()) == set()


# --- aufgezeichnete Systemausgaben ------------------------------------------------------------------


def test_local_subnets_from_recorded_ip_addr(monkeypatch):
    text = (FIXTURES / "ip_addr_show.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(discover.subprocess, "run", _fake_run({"addr show scope global": (0, text)}))
    # lo ("scope host") faellt heraus, v4 und v6 liefern dieselbe Fixture -> nur v4-Treffer
    assert discover.local_subnets() == ["192.168.178.0/24", "10.0.0.0/24"]


def test_neigh6_table_from_recorded_ip_neigh(monkeypatch):
    text = (FIXTURES / "ip_neigh6.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(discover.subprocess, "run", _fake_run({"neigh show": (0, text)}))
    table = discover.neigh6_table()
    assert table == {"2001:db8::1": "aa:bb:cc:00:11:22", "fe80::202:1": "02:00:00:8e:ee:06"}
    # FAILED/INCOMPLETE und die Null-MAC fehlen; v6_by_mac laesst Link-Local (fe80::) draussen
    assert discover.v6_by_mac(table) == {"aa:bb:cc:00:11:22": "2001:db8::1"}


def test_ping_host_from_recorded_output(monkeypatch):
    ok = (FIXTURES / "ping_ok.txt").read_text(encoding="utf-8")
    fail = (FIXTURES / "ping_fail.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(discover.subprocess, "run", _fake_run({"ping": (0, ok)}))
    assert discover.ping_host("10.0.0.1", 0.5) is True
    monkeypatch.setattr(discover.subprocess, "run", _fake_run({"ping": (1, fail)}))
    assert discover.ping_host("10.0.0.99", 0.5) is False

    def boom(args, **kw):
        raise OSError("ping nicht installiert")

    monkeypatch.setattr(discover.subprocess, "run", boom)
    assert discover.ping_host("10.0.0.1", 0.5) is False  # SF-8: fehlendes Binaer -> False + WARN einmal
    assert discover.ping_host("kaputt", 0.5) is False  # ungueltige IP vor dem Aufruf


def test_arp_table_from_recorded_proc_net_arp(monkeypatch):
    real_open = builtins.open

    def fake_open(file, *a, **kw):
        if str(file) == "/proc/net/arp":
            return real_open(FIXTURES / "arp_proc.txt", *a, **kw)
        return real_open(file, *a, **kw)

    monkeypatch.setattr(builtins, "open", fake_open)
    assert discover.arp_table() == {"192.168.178.1": "aa:bb:cc:00:11:22", "192.168.178.10": "02:00:00:8e:ee:06"}


# --- SNMP mit aufgezeichnetem snmpwalk ---------------------------------------------------------------


def test_snmp_walk_with_recorded_subprocess(monkeypatch):
    text = (FIXTURES / "snmpwalk_qbridge.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(snmp.subprocess, "run", _fake_run({"snmpwalk": (0, text)}))
    out = snmp.snmp_walk("10.0.0.2", "public", snmp.QBRIDGE_FDB)
    assert "170.187.204.221.238.255" in out
    monkeypatch.setattr(snmp.subprocess, "run", _fake_run({"snmpwalk": (1, "")}))
    assert snmp.snmp_walk("10.0.0.2", "public", snmp.QBRIDGE_FDB) == ""  # returncode != 0 -> leer

    def boom(args, **kw):
        raise OSError("snmpwalk nicht installiert")

    monkeypatch.setattr(snmp.subprocess, "run", boom)
    assert snmp.snmp_walk("10.0.0.2", "public", snmp.QBRIDGE_FDB) == ""  # warn_once + leer


def test_cam_map_from_recorded_snmpwalk(monkeypatch):
    qb = (FIXTURES / "snmpwalk_qbridge.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(snmp, "snmp_walk", lambda ip, community, oid, timeout=5: qb if oid == snmp.QBRIDGE_FDB else "")
    # C-9: Port 1 traegt zwei MACs (Uplink) -> beide fallen heraus; exclude_macs greift zusaetzlich
    mapping = snmp.cam_map(["10.0.0.2"], "public", exclude_macs={"22:33:44:55:66:77"})
    assert mapping == {"aa:bb:cc:dd:ee:ff": "10.0.0.2"}


def test_cam_map_falls_back_to_bridge_fdb(monkeypatch):
    bridge = (FIXTURES / "snmpwalk_bridge.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(
        snmp, "snmp_walk", lambda ip, community, oid, timeout=5: "" if oid == snmp.QBRIDGE_FDB else bridge
    )
    assert snmp.cam_map(["10.0.0.2"], "public") == {"3c:37:86:ab:cd:ef": "10.0.0.2"}


def test_lldp_map_from_recorded_snmpwalk(monkeypatch):
    text = (FIXTURES / "snmpwalk_lldp.txt").read_text(encoding="utf-8")
    monkeypatch.setattr(snmp, "snmp_walk", lambda ip, community, oid, timeout=5: text)
    assert snmp.lldp_map(["10.0.0.2"], "public") == {"b0:4a:39:01:78:3c": "10.0.0.2", "a4:d5:78:0d:bc:c9": "10.0.0.2"}
