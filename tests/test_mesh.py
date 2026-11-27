"""Mesh-Topologie der FRITZ!Box (TR-064 X_AVM-DE_GetMeshListPath), v1.6.0."""

import pytest

from app import db
from app.config import Settings
from app.scanner import run, topology, tr064

BOX = "3c:a6:2f:00:00:01"
BOX_LAN = "3c:a6:2f:00:00:02"  # Schnittstellen-MAC der Box (so taucht sie oft im ARP-Cache auf)
REP = "3c:a6:2f:00:00:20"
SWITCH = "02:00:00:00:00:01"
PC = "aa:00:00:00:00:01"
NAS = "aa:00:00:00:00:02"
PHONE = "aa:00:00:00:00:03"
TV = "aa:00:00:00:00:04"
PRINTER = "aa:00:00:00:00:05"
GONE = "aa:00:00:00:00:06"


def _iface(uid, node, name, typ, mac="", links=()):
    return {"uid": uid, "name": name, "type": typ, "mac_address": mac, "node_uid": node, "node_links": list(links)}


def _link(uid, typ, n1, i1, n2, i2, state="CONNECTED"):
    return {
        "uid": uid,
        "type": typ,
        "state": state,
        "node_1_uid": n1,
        "node_interface_1_uid": i1,
        "node_2_uid": n2,
        "node_interface_2_uid": i2,
    }


def _client(uid, mac, name, iface_uid, typ, link):
    return {
        "uid": uid,
        "device_name": name,
        "device_mac_address": mac,
        "is_meshed": False,
        "mesh_role": "unknown",
        "node_interfaces": [_iface(iface_uid, uid, "eth0" if typ == "LAN" else "wlan0", typ, mac, [link])],
    }


def mesh_json():
    """Box (Master) mit Repeater ueber 5 GHz und 2,4 GHz (Schleife), Switch + 2 Geraete an LAN:1."""
    l_rep5 = _link("nl-1", "WLAN", "n-box", "ni-box-5g", "n-rep", "ni-rep-up5")
    l_rep2 = _link("nl-2", "WLAN", "n-box", "ni-box-2g", "n-rep", "ni-rep-up2")
    l_sw = _link("nl-3", "LAN", "n-box", "ni-box-lan1", "n-sw", "ni-sw")
    l_pc = _link("nl-4", "LAN", "n-box", "ni-box-lan1", "n-pc", "ni-pc")
    l_nas = _link("nl-5", "LAN", "n-box", "ni-box-lan1", "n-nas", "ni-nas")
    l_phone = _link("nl-6", "WLAN", "n-box", "ni-box-5g", "n-phone", "ni-phone")
    l_tv = _link("nl-7", "WLAN", "n-rep", "ni-rep-ap2", "n-tv", "ni-tv")
    l_pr = _link("nl-8", "LAN", "n-rep", "ni-rep-lan1", "n-pr", "ni-pr")
    l_gone = _link("nl-9", "WLAN", "n-box", "ni-box-5g", "n-gone", "ni-gone", state="DISCONNECTED")
    box = {
        "uid": "n-box",
        "device_name": "fritz.box",
        "device_mac_address": BOX,
        "is_meshed": True,
        "mesh_role": "master",
        "node_interfaces": [
            _iface("ni-box-lan1", "n-box", "LAN:1", "LAN", BOX_LAN, [l_sw, l_pc, l_nas]),
            _iface("ni-box-5g", "n-box", "AP:5G:0", "WLAN", "3c:a6:2f:00:00:03", [l_rep5, l_phone, l_gone]),
            _iface("ni-box-2g", "n-box", "AP:2G:0", "WLAN", "3c:a6:2f:00:00:04", [l_rep2]),
            _iface("ni-box-lan2", "n-box", "LAN:2", "LAN", "00:00:00:00:00:00", []),
        ],
    }
    rep = {
        "uid": "n-rep",
        "device_name": "fritz-repeater",
        "device_mac_address": REP,
        "is_meshed": True,
        "mesh_role": "slave",
        "node_interfaces": [
            _iface("ni-rep-up5", "n-rep", "UPLINK:5G:0", "WLAN", "3c:a6:2f:00:00:21", [l_rep5]),
            _iface("ni-rep-up2", "n-rep", "UPLINK:2G:0", "WLAN", "3c:a6:2f:00:00:22", [l_rep2]),
            _iface("ni-rep-ap2", "n-rep", "AP:2G:0", "WLAN", "3c:a6:2f:00:00:23", [l_tv]),
            _iface("ni-rep-lan1", "n-rep", "LAN:1", "LAN", "3c:a6:2f:00:00:24", [l_pr]),
        ],
    }
    return {
        "schema_version": "8.7",
        "nodes": [
            box,
            rep,
            _client("n-sw", SWITCH, "TL-SG108E-GZ", "ni-sw", "LAN", l_sw),
            _client("n-pc", PC, "pc", "ni-pc", "LAN", l_pc),
            _client("n-nas", NAS, "nas", "ni-nas", "LAN", l_nas),
            _client("n-phone", PHONE, "iPhone", "ni-phone", "WLAN", l_phone),
            _client("n-tv", TV, "LGwebOSTV", "ni-tv", "WLAN", l_tv),
            _client("n-pr", PRINTER, "drucker", "ni-pr", "LAN", l_pr),
            _client("n-gone", GONE, "alt", "ni-gone", "WLAN", l_gone),
        ],
    }


def test_parse_mesh_eltern_und_verbindungsart():
    m = tr064.parse_mesh(mesh_json())
    p = m["parents"]
    assert m["master"] == BOX
    assert p[REP]["parent"] == BOX and p[REP]["conn"] == "wlan"
    assert p[REP]["band"] in ("5 GHz", "2,4 GHz")
    assert p[PHONE] == {"parent": BOX, "conn": "wlan", "port": "AP:5G:0", "band": "5 GHz", "role": "master"}
    assert p[TV]["parent"] == REP and p[TV]["band"] == "2,4 GHz"
    assert p[PRINTER]["parent"] == REP and p[PRINTER]["conn"] == "lan" and p[PRINTER]["port"] == "LAN:1"
    for mac in (SWITCH, PC, NAS):
        assert p[mac]["parent"] == BOX and p[mac]["port"] == "LAN:1"


def test_parse_mesh_ignoriert_getrennte_links_und_null_macs():
    m = tr064.parse_mesh(mesh_json())
    assert GONE not in m["parents"]
    assert "00:00:00:00:00:00" not in m["nodes"][BOX]["macs"]
    assert BOX_LAN in m["nodes"][BOX]["macs"]
    # Repeater ist auch unter seinen Schnittstellen-MACs zugeordnet
    assert m["parents"]["3c:a6:2f:00:00:21"]["parent"] == BOX


def test_parse_mesh_robust_gegen_schleifen_und_muell():
    data = mesh_json()
    data["nodes"].append({"uid": "x"})
    data["nodes"].append("kein dict")
    data["nodes"][0]["node_interfaces"].append(
        {"uid": "kaputt", "node_links": [{"state": "CONNECTED", "node_1_uid": "n-box", "node_2_uid": "fehlt"}]}
    )
    m = tr064.parse_mesh(data)
    assert m["parents"][TV]["parent"] == REP
    assert tr064.parse_mesh({"nodes": []}) == {"parents": {}, "nodes": {}, "master": ""}


def test_parse_mesh_ohne_master_nimmt_knoten_mit_meisten_links():
    data = mesh_json()
    data["nodes"][0]["mesh_role"] = "unknown"
    m = tr064.parse_mesh(data)
    assert m["master"] == BOX and m["parents"][PC]["parent"] == BOX


@pytest.mark.parametrize("path", ["http://evil.example/x", "//evil.example/x", "meshlist.lua", "", "/a\\b"])
def test_mesh_url_nur_relative_pfade(path):
    with pytest.raises(tr064.TR064Error):
        tr064._mesh_url("http://192.168.178.1:49000", path)


def test_mesh_url_relativ_ok():
    assert (
        tr064._mesh_url("http://192.168.178.1:49000/", "/meshlist.lua?sid=abc")
        == "http://192.168.178.1:49000/meshlist.lua?sid=abc"
    )


class _Resp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


SOAP_PATH = (
    '<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
    '<u:X_AVM-DE_GetMeshListPathResponse xmlns:u="urn:dslforum-org:service:Hosts:1">'
    "<NewX_AVM-DE_MeshListPath>/meshlist.lua?sid=0123456789abcdef</NewX_AVM-DE_MeshListPath>"
    "</u:X_AVM-DE_GetMeshListPathResponse></s:Body></s:Envelope>"
)


class _Stream:
    def __init__(self, body: bytes, status=200, chunk=65536):
        self.body, self.status_code, self.chunk = body, status, chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_bytes(self):
        for i in range(0, len(self.body), self.chunk):
            yield self.body[i : i + self.chunk]


def _patch(monkeypatch, body: bytes, status=200, calls=None):
    import json as _json  # noqa: F401

    monkeypatch.setattr(tr064.httpx, "post", lambda *a, **k: _Resp(SOAP_PATH))

    def fake_stream(method, url, timeout=None, follow_redirects=None, verify=None):
        if calls is not None:
            calls.append((method, url, follow_redirects))
        return _Stream(body, status)

    monkeypatch.setattr(tr064.httpx, "stream", fake_stream)


def test_fetch_mesh_ok_ohne_redirects(monkeypatch):
    import json

    calls = []
    _patch(monkeypatch, json.dumps(mesh_json()).encode(), calls=calls)
    data = tr064.fetch_mesh("192.168.178.1:49000", "u", "p")
    assert len(data["nodes"]) == 9
    assert calls == [("GET", "http://192.168.178.1:49000/meshlist.lua?sid=0123456789abcdef", False)]


def test_fetch_mesh_fehler_ohne_session_id(monkeypatch):
    _patch(monkeypatch, b"", status=403)
    with pytest.raises(tr064.TR064Error) as exc:
        tr064.fetch_mesh("192.168.178.1:49000", "u", "p")
    assert "403" in str(exc.value) and "0123456789abcdef" not in str(exc.value)


def test_fetch_mesh_groessenlimit_und_json(monkeypatch):
    _patch(monkeypatch, b"x" * (tr064.MESH_MAX_BYTES + 10))
    with pytest.raises(tr064.TR064Error, match="zu groß"):
        tr064.fetch_mesh("192.168.178.1:49000", "u", "p")
    _patch(monkeypatch, b"{kein json")
    with pytest.raises(tr064.TR064Error, match="JSON"):
        tr064.fetch_mesh("192.168.178.1:49000", "u", "p")
    _patch(monkeypatch, b'{"nodes": 5}')
    with pytest.raises(tr064.TR064Error, match="Knotenliste"):
        tr064.fetch_mesh("192.168.178.1:49000", "u", "p")


def test_resolve_prioritaet_snmp_vor_mesh_vor_tr064():
    gw = "192.168.178.1"
    kw = {"tr064_parent": {"m": "192.168.178.20"}, "mesh_parent": {"m": REP}, "gateway": gw}
    assert topology.resolve_connected_to("m", "192.168.178.50", snmp_map={"m": SWITCH}, **kw) == SWITCH
    assert topology.resolve_connected_to("m", "192.168.178.50", **kw) == REP
    assert topology.resolve_connected_to("m", "192.168.178.50", manual="x", **kw) == "x"
    assert topology.resolve_connected_to("other", "192.168.178.50", **kw) == gw


def test_mesh_parent_map_alias_und_master_fallback():
    info = tr064.parse_mesh(mesh_json())
    devs = [{"mac": BOX_LAN}, {"mac": REP}, {"mac": PC}, {"mac": TV}]
    out = run.mesh_parent_map(info, devs, "192.168.178.1")
    assert out[PC] == BOX_LAN  # Box nur unter Schnittstellen-MAC gescannt
    assert out[TV] == REP
    out2 = run.mesh_parent_map(info, [{"mac": PC}], "192.168.178.1")
    assert out2[PC] == "192.168.178.1"  # Master nicht gescannt -> Gateway-IP
    assert TV not in out2  # Repeater nicht gescannt -> kein Eintrag, Fallback greift


def _d(mac, cat, parent):
    return {"mac": mac, "category": cat, "layout": {"connected_to": parent}}


def test_assign_behind_switch():
    devs = [_d(SWITCH, "Switch", BOX), _d(PC, "Client", BOX), _d(NAS, "Server/NAS", BOX), _d(PHONE, "Client", BOX)]
    ports = {SWITCH: (BOX, "LAN:1"), PC: (BOX, "LAN:1"), NAS: (BOX, "LAN:1"), PHONE: (BOX, "LAN:2")}
    assert topology.assign_behind_switch(devs, ports, fixed={NAS}) == 1
    by = {d["mac"]: d["layout"]["connected_to"] for d in devs}
    assert by == {SWITCH: BOX, PC: SWITCH, NAS: BOX, PHONE: BOX}


def test_assign_behind_switch_mehrdeutig_bleibt():
    devs = [_d(SWITCH, "Switch", BOX), _d("02:00:00:00:00:02", "Switch", BOX), _d(PC, "Client", BOX)]
    ports = {d["mac"]: (BOX, "LAN:1") for d in devs}
    assert topology.assign_behind_switch(devs, ports, fixed=set()) == 0


def test_collect_devices_mit_mesh(tmp_path, monkeypatch):
    """Ende-zu-Ende: Scan + TR-064-Hosts + Mesh ergibt Baum statt Stern."""
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    settings = Settings(
        data_dir=str(tmp_path),
        subnets="192.168.178.0/24",
        fritz_user="u",
        fritz_pass="p",
        snmp_enabled=False,
        mdns_enabled=False,
    )
    ips = {
        BOX: "192.168.178.1",
        REP: "192.168.178.20",
        SWITCH: "192.168.178.10",
        PC: "192.168.178.100",
        NAS: "192.168.178.101",
        PHONE: "192.168.178.102",
        TV: "192.168.178.103",
        PRINTER: "192.168.178.104",
    }
    names_ = {
        BOX: "fritz.box",
        REP: "fritz-repeater",
        SWITCH: "TL-SG108E-GZ",
        PC: "pc",
        NAS: "nas",
        PHONE: "iPhone",
        TV: "LGwebOSTV",
        PRINTER: "drucker",
    }
    monkeypatch.setattr(
        run.discover,
        "discover",
        lambda subnets, timeout: [{"ip": ip, "mac": mac, "source": "ping+arp"} for mac, ip in ips.items()],
    )
    monkeypatch.setattr(run.ports, "scan_ports", lambda *a, **k: [])
    monkeypatch.setattr(run.names, "resolve_all", lambda ips_, use_mdns=False: {})
    monkeypatch.setattr(run.topology, "gateway_ip", lambda: "192.168.178.1")
    monkeypatch.setattr(run.topology, "gateway_ip6", lambda: "")
    monkeypatch.setattr(run.oui, "lookup_online", lambda *a, **k: "")
    hosts = [
        {"mac": m, "ip": ips[m], "hostname": names_[m], "active": True, "type": "LAN", "source": "tr064"}
        for m in ips
        if m != BOX
    ]
    monkeypatch.setattr(run.tr064, "fetch_hosts_with_fallback", lambda *a, **k: [dict(h) for h in hosts])
    monkeypatch.setattr(run.tr064, "fetch_wan", lambda *a, **k: None)
    monkeypatch.setattr(run.tr064, "fetch_mesh", lambda *a, **k: mesh_json())
    devices = run.collect_devices(settings, conn)
    ct = {d["mac"]: d["layout"]["connected_to"] for d in devices}
    assert ct[REP] == BOX
    assert ct[SWITCH] == BOX
    assert ct[PC] == SWITCH and ct[NAS] == SWITCH  # hinter dem Switch am selben LAN-Port
    assert ct[PHONE] == BOX
    assert ct[TV] == REP and ct[PRINTER] == REP
    conn_type = {d["mac"]: d["connection"] for d in devices}
    assert conn_type[REP] == "wlan" and conn_type[PHONE] == "wlan"
    assert conn_type[TV] == "wlan"  # Mesh schlaegt den TR-064-Host-Typ (Hosts melden hier "LAN")
    assert conn_type[PRINTER] == "lan"
    cat = {d["mac"]: d["category"] for d in devices}
    assert cat[BOX] == "Router" and cat[REP] == "Repeater/AP" and cat[SWITCH] == "Switch"
    assert cat[PHONE] == "Mobilgerät" and cat[TV] == "Multimedia" and cat[PRINTER] == "Drucker"
    assert cat[NAS] == "Server/NAS" and cat[PC] == "Client"
    reason = {d["mac"]: d["category_reason"] for d in devices}
    assert reason[BOX] == "gateway" and reason[REP] == "mesh:slave"

    # Abschaltbar: ohne Mesh wieder Stern am Gateway
    settings2 = settings.model_copy(update={"fritz_mesh": False})
    devices2 = run.collect_devices(settings2, conn)
    assert {d["layout"]["connected_to"] for d in devices2 if d["mac"] != BOX} <= {
        "192.168.178.1",
        "192.168.178.1:49000",
        "wlan:192.168.178.1",
    }


@pytest.mark.parametrize(
    "raw,exp",
    [("Ethernet", "lan"), ("802.11", "wlan"), ("HomePlug", "plc"), ("", ""), ("WLAN", "wlan"), ("LAN", "lan")],
)
def test_conn_type_avm_werte(raw, exp):
    assert topology.conn_type(raw) == exp


def test_resolve_wlan_bei_80211():
    assert (
        topology.resolve_connected_to("m", "192.168.178.5", tr064_type="802.11", gateway="192.168.178.1")
        == "wlan:192.168.178.1"
    )
