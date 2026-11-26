"""W2-C: S-11 (mDNS fremde Antworten ignorieren), S-14/N-5 (OUI-Online), S-15 (TR-064-Limits)."""

import struct

import pytest

from app.scanner import names, oui, tr064


def _mdns_packet(owner: str, ptr: str) -> bytes:
    header = struct.pack(">HHHHHH", 0x1234, 0x8400, 0, 1, 0, 0)
    rname = names._encode_name(ptr)
    oname = names._encode_name(owner)
    answer = oname + struct.pack(">HHIH", 12, 1, 120, len(rname)) + rname
    return header + answer


def test_mdns_ignores_foreign_owner_name(monkeypatch):
    # S-11: Antwort mit fremdem Eigentuemer wird verworfen
    pkt = _mdns_packet("fremd.local", "drucker.local")

    class FakeSock:
        def settimeout(self, t):
            pass

        def setsockopt(self, *a):
            pass

        def sendto(self, q, g):
            pass

        def recvfrom(self, n):
            import time

            if time.time() > getattr(self, "_deadline", 0):
                raise TimeoutError
            self._deadline = time.time() + 0.01
            return pkt, ("192.0.2.10", 5353)

        def close(self):
            pass

    monkeypatch.setattr(names.socket, "socket", lambda *a, **k: FakeSock())
    assert names.resolve_hostname_mdns("192.0.2.10", timeout=0.05) == ""


def test_mdns_sanitizes_name():
    assert names._sanitize_mdns_name('=HYPERLINK("x")\x07bad') == "HYPERLINKxbad"
    assert len(names._sanitize_mdns_name("a" * 200)) <= 63


def test_oui_online_url_rejects_loopback():
    with pytest.raises(ValueError):
        oui._check_online_url("http://127.0.0.1:631/")
    with pytest.raises(ValueError):
        oui._check_online_url("file:///etc/passwd")
    oui._check_online_url("https://api.macvendors.com")  # ok


def test_oui_parse_vendor_capped():
    assert len(oui.parse_vendor("x" * 5000)) <= 128
    assert oui.parse_vendor('{"vendor": "AVM"}') == "AVM"


def test_oui_online_http_exception_does_not_abort_scan(monkeypatch):
    # N-5: Protokollfehler (z. B. BadStatusLine) wird geloggt und liefert ""
    import http.client

    def boom(url, timeout=5.0):
        raise http.client.BadStatusLine("nope")

    monkeypatch.setattr(oui, "_http_get", boom)
    from app.config import Settings

    s = Settings(oui_online_enabled=True)
    assert oui.lookup_online("aa:bb:cc:dd:ee:ff", s, None, {"left": 5}) == ""


def test_tr064_host_count_capped(monkeypatch):
    calls = {"n": 0}

    def fake_call(base_url, path, service, action, args, user, password, **kw):
        calls["n"] += 1
        if action == "GetHostNumberOfEntries":
            return {"NewHostNumberOfEntries": "1000000000"}
        return {"NewMACAddress": "aa:bb:cc:dd:ee:ff", "NewIPAddress": "192.0.2.5", "NewHostName": "x", "NewActive": "1"}

    monkeypatch.setattr(tr064, "_soap_call", fake_call)
    hosts = tr064.fetch_hosts("http://192.0.2.1:49000", "u", "p")
    assert calls["n"] == 1 + 4096  # Count + gedeckelte 4096 Eintraege
    assert len(hosts) <= 4096


def test_tr064_non_numeric_count_raises_tr064error(monkeypatch):
    def fake_call(base_url, path, service, action, args, user, password, **kw):
        return {"NewHostNumberOfEntries": "lots"}

    monkeypatch.setattr(tr064, "_soap_call", fake_call)
    with pytest.raises(tr064.TR064Error):
        tr064.fetch_hosts("http://192.0.2.1:49000", "u", "p")
