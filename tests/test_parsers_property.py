"""T-11 (W6): Property-/Fuzz-Tests fuer Parser von LAN-Daten (hypothesis).
Pakete/Antworten aus dem Netz duerfen nie haengen und nur die vorgesehenen Fehler werfen."""

import xml.etree.ElementTree as ET

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from app import netutil
from app.scanner import mdns, names, tr064


@given(st.binary(min_size=0, max_size=9000))
@hsettings(max_examples=300, deadline=None)
def test_parse_packet_never_raises(data: bytes):
    services, model = mdns.parse_packet(data)
    assert isinstance(services, set) and isinstance(model, str)
    assert all(s.startswith("_") for s in services)
    assert len(model) <= mdns.MAX_VALUE_LEN


@given(st.binary(min_size=0, max_size=2000))
@hsettings(max_examples=200, deadline=None)
def test_parse_mdns_answers_never_raises(data: bytes):
    answers = names.parse_mdns_answers(data)
    assert isinstance(answers, list)
    assert all(isinstance(a, tuple) and len(a) == 2 for a in answers)


@given(st.binary(min_size=0, max_size=600), st.integers(min_value=0, max_value=700))
@hsettings(max_examples=200, deadline=None)
def test_decode_name_never_raises(data: bytes, offset: int):
    name, end = names._decode_name(data, offset)
    assert isinstance(name, str) and isinstance(end, int)


class _Resp:
    def __init__(self, data: bytes, status: int = 200):
        self.text = data.decode("utf-8", "replace")
        self.status_code = status
        self.headers = {}
        self.content = data


@given(st.binary(min_size=0, max_size=4000))
@hsettings(max_examples=200, deadline=None)
def test_soap_call_random_response_raises_only_tr064error(data: bytes):
    """Kaputte SOAP-Antwort aus dem LAN: nur TR064Error (S-15), nie eine andere Exception.
    (Kein monkeypatch: hypothesis verbietet function-scoped fixtures in @given.)"""
    real_post = tr064.httpx.post
    tr064.httpx.post = lambda *a, **kw: _Resp(data, 200)
    try:
        try:
            out = tr064._soap_call(
                "http://10.0.0.1:49000",
                "/upnp/control/hosts",
                tr064.HOSTS_SERVICE,
                "GetHostNumberOfEntries",
                {},
                "",
                "",
            )
            assert isinstance(out, dict)
        except tr064.TR064Error:
            pass  # erwartet bei kaputtem XML/HTTP-Fehler
    finally:
        tr064.httpx.post = real_post


def test_parse_fields_collects_only_new_fields():
    root = ET.fromstring("<r><NewA> 1 </NewA><Other>x</Other><NewB>y</NewB></r>")  # noqa: S314 - Test-Fixture, kein LAN-Input
    assert tr064._parse_fields(root) == {"NewA": "1", "NewB": "y"}


@given(st.text(min_size=0, max_size=40))
@hsettings(max_examples=300, deadline=None)
def test_normalize_mac_idempotent(value: str):
    once = netutil.normalize_mac(value)
    if once is None:
        assert netutil.normalize_mac(value) is None
    else:
        assert netutil.normalize_mac(once) == once
        assert netutil.is_mac(once)
        assert netutil.normalize_mac_key(once) == once


def test_token_parse_robust():
    # Vergleich gegen echte Beispiele aus der DB-Migration
    assert netutil.normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
    assert netutil.normalize_mac("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"
    assert netutil.normalize_mac("") is None
    assert netutil.normalize_mac("aa:bb:cc:dd:ee") is None
    assert netutil.normalize_mac_key("ip:10.0.0.5") == "ip:10.0.0.5"


@pytest.mark.parametrize("text", ["", "<", "<a>", "<?xml?>", "<r/>", "<r><NewX>1</NewX></r>"])
def test_parse_fields_on_tiny_xml(text: str):
    try:
        root = ET.fromstring(text)  # noqa: S314 - Test-Fixture, kein LAN-Input
    except ET.ParseError:
        return
    out = tr064._parse_fields(root)
    assert all(k.startswith("New") for k in out)
