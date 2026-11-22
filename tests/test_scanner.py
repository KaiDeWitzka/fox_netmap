import os

from app import db
from app.config import Settings
from app.scanner import categorize, discover, oui, ports, snmp, tr064
from app.scanner.run import apply_scan, effective_settings

SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "data", "oui_seed.txt")


def make(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    db.init_db(conn)
    settings = Settings(data_dir=str(tmp_path), history_hours=1)
    return conn, settings


def dev(mac, ip, **kw):
    base = {"mac": mac, "ip": ip, "hostname": "", "vendor": "", "category": "Unbekannt", "status": "online", "subnet": "10.0.0.0/24", "source": "ping+arp", "ports": [], "layout": {}}
    base.update(kw)
    return base


def test_apply_scan_new_offline_events(tmp_path):
    conn, settings = make(tmp_path)
    d1 = dev("aa:aa:aa:aa:aa:01", "10.0.0.2", hostname="pc", category="Client", ports=[{"port": 80}], layout={"connected_to": "10.0.0.1"})
    summary = apply_scan(conn, settings, [d1])
    assert summary["new"] == 1 and summary["seen"] == 1
    assert len(summary["new_online"]) == 1
    stored = db.get_device(conn, d1["mac"])
    assert stored["status"] == "online"
    assert stored["layout"]["connected_to"] == "10.0.0.1"
    assert any(e["type"] == "new" for e in stored["events"])
    assert len(stored["history"]) == 1

    summary2 = apply_scan(conn, settings, [])
    assert summary2["seen"] == 0
    stored2 = db.get_device(conn, d1["mac"])
    assert stored2["status"] == "offline"
    assert any(e["type"] == "offline" for e in stored2["events"])


def test_apply_scan_tr064_only_offline_kein_alarm(tmp_path):
    conn, settings = make(tmp_path)
    stale = dev("aa:aa:aa:aa:aa:09", "10.0.0.99", category="Unbekannt", status="offline", source="tr064")
    summary = apply_scan(conn, settings, [stale])
    assert summary["new"] == 1
    assert summary["new_online"] == []
    assert db.get_device(conn, stale["mac"])["status"] == "offline"


def test_apply_scan_ports_changed_and_manual_layout_kept(tmp_path):
    conn, settings = make(tmp_path)
    mac = "aa:aa:aa:aa:aa:02"
    apply_scan(conn, settings, [dev(mac, "10.0.0.3", ports=[{"port": 80}])])
    db.set_layout(conn, mac, connected_to="manual-parent", connected_manual=1)
    conn.commit()
    apply_scan(conn, settings, [dev(mac, "10.0.0.3", ports=[{"port": 80}, {"port": 443}], layout={"connected_to": "auto-parent"})])
    stored = db.get_device(conn, mac)
    assert any(e["type"] == "ports_changed" for e in stored["events"])
    assert stored["layout"]["connected_to"] == "manual-parent"


def test_retention_removes_old_offline(tmp_path):
    conn, settings = make(tmp_path)
    settings = settings.model_copy(update={"device_retention_days": 30})
    d = dev("aa:aa:aa:aa:aa:10", "10.0.0.10")
    apply_scan(conn, settings, [d])
    conn.execute("UPDATE devices SET status='offline', last_seen='2020-01-01T00:00:00+00:00' WHERE mac=?", (d["mac"],))
    conn.commit()
    summary = apply_scan(conn, settings, [])
    assert summary["removed"] == 1
    assert db.get_device(conn, d["mac"]) is None


def test_retention_disabled_keeps(tmp_path):
    conn, settings = make(tmp_path)
    settings = settings.model_copy(update={"device_retention_days": 0})
    d = dev("aa:aa:aa:aa:aa:11", "10.0.0.11")
    apply_scan(conn, settings, [d])
    conn.execute("UPDATE devices SET status='offline', last_seen='2020-01-01T00:00:00+00:00' WHERE mac=?", (d["mac"],))
    conn.commit()
    summary = apply_scan(conn, settings, [])
    assert summary["removed"] == 0
    assert db.get_device(conn, d["mac"]) is not None


def test_offline_does_not_bump_last_seen(tmp_path):
    conn, settings = make(tmp_path)
    d = dev("aa:aa:aa:aa:aa:12", "10.0.0.12")
    apply_scan(conn, settings, [d])
    before = db.get_device(conn, d["mac"])["last_seen"]
    apply_scan(conn, settings, [])
    after = db.get_device(conn, d["mac"])
    assert after["status"] == "offline"
    assert after["last_seen"] == before


def test_effective_settings_override(tmp_path):
    conn, settings = make(tmp_path)
    db.set_setting(conn, "scan_interval", "300")
    db.set_setting(conn, "theme", "light")
    conn.commit()
    eff = effective_settings(conn, settings)
    assert eff.scan_interval == 300
    assert eff.theme == "light"
    assert eff.port_top == settings.port_top


def test_categorize():
    assert categorize.categorize(hostname="fritz.box") == "Router"
    # v1.6.0: AVM ohne Gateway-Rolle ist eher Repeater; Port 53 allein macht kein Geraet zum Router
    assert categorize.categorize(vendor="AVM GmbH") == "Repeater/AP"
    assert categorize.categorize(vendor="AVM GmbH", is_gateway=True) == "Router"
    assert categorize.categorize(ports=[{"port": 53}]) == "Server/NAS"
    assert categorize.categorize(ports=[{"port": 161}]) == "Switch"
    assert categorize.categorize(hostname="switch-keller") == "Switch"
    assert categorize.categorize(hostname="synology-nas") == "Server/NAS"
    assert categorize.categorize(ports=[{"port": 445}]) == "Client"
    assert categorize.categorize(ports=[{"port": 445}, {"port": 22}]) == "Server/NAS"
    assert categorize.categorize(ports=[{"port": 9100}]) == "Drucker"
    assert categorize.categorize(hostname="drucker-buero") == "Drucker"
    assert categorize.categorize(hostname="shelly-wohnzimmer") == "Smart-Home/IoT"
    assert categorize.categorize() == "Unbekannt"


def test_oui_seed():
    table = oui.load_oui(SEED)
    assert oui.lookup("00:04:0E:11:22:33", table) == "AVM GmbH"
    assert oui.lookup("b8:27:eb:aa:bb:cc", table) == "Raspberry Pi Foundation"
    assert oui.lookup("ff:ff:ff:00:00:00", table) == ""
    assert oui.oui_prefix("B8-27-EB-AA-BB-CC") == "B827EB"


def test_discover_parsers():
    ip_sample = (
        "1: lo    inet 127.0.0.1/8 scope host lo\n"
        "2: eth0    inet 192.168.178.20/24 brd 192.168.178.255 scope global eth0\n"
    )
    assert discover.parse_ip_addr(ip_sample) == ["192.168.178.0/24"]
    arp_sample = (
        "IP address       HW type     Flags       HW address            Mask     Device\n"
        "192.168.178.1    0x1         0x2         3C:37:86:AB:CD:EF     *        eth0\n"
        "192.168.178.30   0x1         0x0         00:00:00:00:00:00     *        eth0\n"
    )
    assert discover.parse_arp(arp_sample) == {"192.168.178.1": "3c:37:86:ab:cd:ef"}


def test_discover_loggt_pro_subnetz(monkeypatch, caplog):
    import logging

    monkeypatch.setattr(
        discover,
        "ping_sweep",
        lambda subnet, timeout=1.0: {"192.168.178.0/24": {"192.168.178.1"}, "192.168.179.0/24": set()}[subnet],
    )
    monkeypatch.setattr(discover, "tcp_probe_sweep", lambda subnet, skip, timeout=0.8: set())
    monkeypatch.setattr(discover, "arp_table", lambda: {"192.168.178.1": "aa:bb:cc:dd:ee:ff"})
    with caplog.at_level(logging.INFO, logger="fox_netmap"):
        devices = discover.discover(["192.168.178.0/24", "192.168.179.0/24"])
    assert len(devices) == 1
    messages = [r.getMessage() for r in caplog.records]
    assert any("192.168.178.0/24: 1 Hosts" in m for m in messages)
    assert any("192.168.179.0/24: 0 Hosts" in m for m in messages)


def test_discover_tcp_fallback(monkeypatch, caplog):
    import logging

    monkeypatch.setattr(discover, "ping_sweep", lambda subnet, timeout=1.0: set())
    monkeypatch.setattr(
        discover,
        "tcp_probe_sweep",
        lambda subnet, skip, timeout=0.8: {"192.168.179.20"} if subnet == "192.168.179.0/24" else set(),
    )
    monkeypatch.setattr(discover, "arp_table", lambda: {})
    with caplog.at_level(logging.INFO, logger="fox_netmap"):
        devices = discover.discover(["192.168.178.0/24", "192.168.179.0/24"])
    assert {d["ip"]: d["source"] for d in devices} == {"192.168.179.20": "tcp"}
    assert any("nur per TCP" in r.getMessage() for r in caplog.records)


def test_merge_sources_by_ip():
    from app.scanner.run import merge_sources

    found = [{"ip": "192.168.179.20", "mac": None, "source": "tcp"}]
    tr = {"aa:bb:cc:dd:ee:01": {"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.179.20", "hostname": "iot-plug", "active": True, "type": "WLAN"}}
    out = merge_sources(found, tr)
    assert len(out) == 1
    assert out[0]["mac"] == "aa:bb:cc:dd:ee:01"
    assert out[0]["source"] == "tcp,tr064"
    assert out[0]["hostname"] == "iot-plug"


def test_merge_sources_mac_konflikt_arp_gewinnt():
    from app.scanner.run import merge_sources

    found = [{"ip": "192.168.178.33", "mac": "b0:4a:39:01:78:3c", "source": "ping+arp"}]
    tr = {
        "bc:24:11:67:14:23": {"mac": "bc:24:11:67:14:23", "ip": "192.168.178.33", "hostname": "kid-robot", "active": False, "type": "LAN"},
        "bc:24:11:67:14:24": {"mac": "bc:24:11:67:14:24", "ip": "192.168.178.33", "hostname": "kid-robot", "active": False, "type": "LAN"},
    }
    out = merge_sources(found, tr)
    assert len(out) == 1
    assert out[0]["mac"] == "b0:4a:39:01:78:3c"
    assert out[0]["source"] == "ping+arp,tr064"
    assert out[0]["hostname"] == "kid-robot"


def test_merge_sources_adoptiert_bekannte_mac_per_ip(tmp_path):
    from app.scanner.run import merge_sources

    conn, _settings = make(tmp_path)
    conn.execute(
        "INSERT INTO devices (mac, ip, hostname, status, last_seen) VALUES ('a4:d5:78:0d:bc:c9', '192.168.178.59', 'sz', 'offline', '2026-11-20T04:21:00+00:00')"
    )
    conn.commit()
    out = merge_sources([{"ip": "192.168.178.59", "mac": None, "source": "ping"}], {}, conn)
    assert out[0]["mac"] == "a4:d5:78:0d:bc:c9"
    assert out[0]["source"] == "ping"
    conn.close()


def test_merge_sources_macless_bekommt_ip_key():
    from app.scanner.run import merge_sources

    out = merge_sources([{"ip": "192.168.179.20", "mac": None, "source": "tcp"}], {})
    assert out[0]["mac"] == "ip:192.168.179.20"
    tr = {"aa:bb:cc:dd:ee:02": {"mac": "aa:bb:cc:dd:ee:02", "ip": "192.168.179.20", "hostname": "remote", "active": True, "type": "LAN"}}
    out2 = merge_sources([{"ip": "192.168.179.20", "mac": None, "source": "tcp"}], tr)
    assert len(out2) == 1
    assert out2[0]["mac"] == "aa:bb:cc:dd:ee:02"


def test_port_list():
    assert ports.port_list(10) == list(range(1, 11))
    assert ports.port_list(0)[-1] == 65535
    assert ports.port_list(1000, "443,80,443") == [80, 443]
    assert 8080 in ports.port_list(2000)


def test_resolve_connected_to_prioritaet():
    from app.scanner import topology

    gw = "192.168.178.1"
    assert topology.resolve_connected_to("m", "10.0.0.5", manual="man") == "man"
    assert topology.resolve_connected_to("m", "10.0.0.5", snmp_map={"m": "192.168.178.10"}, tr064_parent={"m": "192.168.178.14"}, gateway=gw) == "192.168.178.10"
    assert topology.resolve_connected_to("m", "10.0.0.5", tr064_parent={"m": "192.168.178.14"}, gateway=gw) == "192.168.178.14"
    assert topology.resolve_connected_to("m", "10.0.0.5", tr064_type="WLAN", gateway=gw) == "wlan:" + gw
    assert topology.resolve_connected_to("m", "10.0.0.5", tr064_type="LAN", gateway=gw) == gw
    assert topology.resolve_connected_to("m", "10.0.0.5", gateway=gw) == gw


def test_snmp_parse_lldp():
    sample = (
        ".1.0.8802.1.1.2.1.4.1.1.6.0.5.1 = Hex-STRING: B0 4A 39 01 78 3C\n"
        ".1.0.8802.1.1.2.1.4.1.1.6.0.5.2 = Hex-STRING: A4 D5 78 0D BC C9\n"
    )
    assert snmp.parse_lldp(sample) == {"b0:4a:39:01:78:3c", "a4:d5:78:0d:bc:c9"}


def test_snmp_parse_cam():
    sample = (
        ".1.3.6.1.2.1.17.4.3.1.2.60.55.134.171.205.239 = INTEGER: 3\n"
        ".1.3.6.1.2.1.17.7.1.2.2.1.2.1.184.62.213.170.1.2 = INTEGER: 7\n"
    )
    parsed = snmp.parse_cam(sample)
    assert parsed == {"3c:37:86:ab:cd:ef": 3, "b8:3e:d5:aa:01:02": 7}


ENVELOPE = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>%s</s:Body></s:Envelope>'

HOSTS_COUNT = ENVELOPE % (
    '<u:GetHostNumberOfEntriesResponse xmlns:u="urn:dslforum-org:service:Hosts:1">'
    "<NewHostNumberOfEntries>1</NewHostNumberOfEntries></u:GetHostNumberOfEntriesResponse>"
)
HOST_ENTRY = ENVELOPE % (
    '<u:GetGenericHostEntryResponse xmlns:u="urn:dslforum-org:service:Hosts:1">'
    "<NewMACAddress>AA:BB:CC:DD:EE:FF</NewMACAddress>"
    "<NewIPAddress>192.168.178.30</NewIPAddress>"
    "<NewHostName>wohnzimmer-tv</NewHostName>"
    "<NewActive>1</NewActive>"
    "<NewInterfaceType>LAN</NewInterfaceType>"
    "</u:GetGenericHostEntryResponse>"
)
SOAP_FAULT = ENVELOPE % (
    "<s:Fault><faultcode>s:Client</faultcode><faultstring>UPnPError</faultstring>"
    '<detail><UPnPError xmlns="urn:schemas-upnp-org:control-1-0">'
    "<errorCode>402</errorCode><errorDescription>Invalid Action</errorDescription>"
    "</UPnPError></detail></s:Fault>"
)


class _FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


def _body_str(content):
    if isinstance(content, str):
        return content
    return (content or b"").decode()


def _fake_post_factory(mapping):
    def fake_post(url, content=None, headers=None, auth=None, timeout=None):
        body = _body_str(content)
        for key, resp in mapping.items():
            if key in body:
                return resp if isinstance(resp, _FakeResponse) else _FakeResponse(resp)
        return _FakeResponse("", 404)
    return fake_post


def test_tr064_fetch_hosts(monkeypatch):
    monkeypatch.setattr(
        tr064.httpx,
        "post",
        _fake_post_factory({"GetHostNumberOfEntries": HOSTS_COUNT, "GetGenericHostEntry": HOST_ENTRY}),
    )
    hosts = tr064.fetch_hosts("192.168.178.1:49000", "user", "pass")
    assert len(hosts) == 1
    assert hosts[0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert hosts[0]["ip"] == "192.168.178.30"
    assert hosts[0]["hostname"] == "wohnzimmer-tv"
    assert hosts[0]["active"] is True
    assert hosts[0]["type"] == "LAN"


def test_tr064_soap_fault_wird_gelesen(monkeypatch):
    import pytest

    monkeypatch.setattr(tr064.httpx, "post", _fake_post_factory({"GetHostNumberOfEntries": _FakeResponse(SOAP_FAULT, 500)}))
    with pytest.raises(tr064.TR064Error) as excinfo:
        tr064.fetch_hosts("http://192.168.178.1:49000", "user", "pass")
    assert "HTTP 500" in str(excinfo.value)
    assert "Invalid Action" in str(excinfo.value)


def test_tr064_https_fallback_auf_http(monkeypatch):
    urls = []

    def fake_post(url, content=None, headers=None, auth=None, timeout=None):
        urls.append(url)
        body = _body_str(content)
        if url.startswith("https://"):
            raise tr064.httpx.ConnectError("tls broken")
        if "GetHostNumberOfEntries" in body:
            return _FakeResponse(HOSTS_COUNT)
        return _FakeResponse(HOST_ENTRY)

    monkeypatch.setattr(tr064.httpx, "post", fake_post)
    hosts = tr064.fetch_hosts_with_fallback("https://192.168.178.1:49000", "user", "pass")
    assert len(hosts) == 1
    assert urls[0].startswith("https://") and urls[1].startswith("http://")


def test_notify_whitelist():
    from app.scanner import notify

    class S:
        alarm_whitelist = "aa:bb:cc:dd:ee:ff, 192.168.178.50"

    assert notify.is_whitelisted(S(), {"mac": "AA-BB-CC-DD-EE-FF", "ip": "10.0.0.1"})
    assert notify.is_whitelisted(S(), {"mac": "ip:192.168.178.50", "ip": "192.168.178.50"})
    assert not notify.is_whitelisted(S(), {"mac": "11:22:33:44:55:66", "ip": "10.0.0.9"})

    class Empty:
        alarm_whitelist = ""

    assert not notify.is_whitelisted(Empty(), {"mac": "aa:bb:cc:dd:ee:ff", "ip": "1.2.3.4"})


def test_auto_export_due():
    from datetime import datetime, timedelta, timezone

    from app.exporters import auto_export_due

    now = datetime.now(timezone.utc)
    assert auto_export_due(None, 24, now)
    assert auto_export_due("", 24, now)
    assert auto_export_due("kaputt", 24, now)
    assert auto_export_due((now - timedelta(hours=25)).isoformat(timespec="seconds"), 24, now)
    assert not auto_export_due((now - timedelta(hours=1)).isoformat(timespec="seconds"), 24, now)
    assert auto_export_due((now - timedelta(minutes=1)).isoformat(timespec="seconds"), 0, now)


def test_names_ptr_name():
    from app.scanner import names

    assert names.ptr_name("192.168.178.20") == "20.178.168.192.in-addr.arpa"
    p6 = names.ptr_name("2003::1")
    assert p6.endswith(".ip6.arpa") and p6.startswith("1.0.0.0.") and p6.endswith("3.0.0.2.ip6.arpa")
    assert names.ptr_name("keine-ip") is None


def test_names_parse_mdns_answers():
    import struct

    from app.scanner import names

    qname = "20.178.168.192.in-addr.arpa"
    header = struct.pack(">HHHHHH", 0x1234, 0x8400, 1, 1, 0, 0)
    question = names._encode_name(qname) + struct.pack(">HH", 12, 1)
    rname = names._encode_name("drucker.local")
    answer = b"\xc0\x0c" + struct.pack(">HHIH", 12, 1, 120, len(rname)) + rname
    packet = header + question + answer
    assert names.parse_mdns_answers(packet) == ["drucker.local"]
    assert names.parse_mdns_answers(b"\x00" * 5) == []


def test_resolve_all_mdns_fallback(monkeypatch):
    from app.scanner import names

    monkeypatch.setattr(names, "resolve_hostname", lambda ip: "")
    monkeypatch.setattr(names, "resolve_hostname_mdns", lambda ip, timeout=1.0: "tv" if ip == "192.168.178.77" else "")
    out = names.resolve_all(["192.168.178.77", "10.0.0.5"], use_mdns=True)
    assert out["192.168.178.77"] == "tv"
    assert out["10.0.0.5"] == ""
    out2 = names.resolve_all(["192.168.178.77"], use_mdns=False)
    assert out2["192.168.178.77"] == ""


def test_discover_ipv6_parser():
    sample6 = (
        "1: lo    inet6 ::1/128 scope host lo\n"
        "2: eth0    inet6 2003:db8:1::4/64 scope global eth0\n"
    )
    assert discover.parse_ip_addr(sample6, 6) == ["2003:db8:1::/64"]
    neigh_sample = (
        "2003:db8:1::1 dev eth0 lladdr 3C:37:86:AB:CD:EF REACHABLE\n"
        "2003:db8:1::5 dev eth0 lladdr 00:00:00:00:00:00 STALE\n"
        "2003:db8:1::9 dev eth0 FAILED\n"
        "fe80::1 dev eth0 lladdr aa:bb:cc:dd:ee:ff router STALE\n"
    )
    assert discover.parse_neigh6(neigh_sample) == {"2003:db8:1::1": "3c:37:86:ab:cd:ef", "fe80::1": "aa:bb:cc:dd:ee:ff"}


def test_ping_host_verwendet_version_flag(monkeypatch):
    calls = []

    class R:
        returncode = 0

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return R()

    monkeypatch.setattr(discover.subprocess, "run", fake_run)
    assert discover.ping_host("2003:db8::5", 1.0)
    assert discover.ping_host("192.168.178.1", 1.0)
    assert "-6" in calls[0] and "2003:db8::5" in calls[0]
    assert "-4" in calls[1] and "192.168.178.1" in calls[1]
    assert discover.ping_host("kaputt", 1.0) is False


def test_sweep_hosts_guard_grosse_netze():
    import ipaddress

    assert discover.sweep_hosts(ipaddress.ip_network("2003:db8::/64", strict=False)) == []
    assert discover.sweep_hosts(ipaddress.ip_network("2003:db8::/126", strict=False)) == ["2003:db8::1", "2003:db8::2", "2003:db8::3"]


def test_discover_v6_ndp_ohne_sweep(monkeypatch):
    monkeypatch.setattr(discover, "arp_table", lambda: {})
    monkeypatch.setattr(discover, "neigh6_table", lambda: {"2003:db8:1::10": "aa:bb:cc:dd:ee:ff", "2003:db8:9::1": "11:22:33:44:55:66"})
    monkeypatch.setattr(discover.topology, "gateway_ip6", lambda: "2003:db8:1::1")
    monkeypatch.setattr(discover, "ping_host", lambda ip, timeout: ip == "2003:db8:1::1")

    def sweep_raise(subnet, timeout=1.0, max_hosts=1024):
        raise AssertionError("Sweep darf bei /64 nicht laufen")

    monkeypatch.setattr(discover, "ping_sweep", sweep_raise)
    monkeypatch.setattr(discover, "tcp_probe_sweep", sweep_raise)
    devices = discover.discover(["2003:db8:1::/64"])
    by_ip = {d["ip"]: d for d in devices}
    assert by_ip["2003:db8:1::10"]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert by_ip["2003:db8:1::10"]["source"] == "ndp"
    assert by_ip["2003:db8:1::1"]["source"] == "ping"
    assert "2003:db8:9::1" not in by_ip


def test_topology_gateway6_und_v6_wahl(monkeypatch):
    from app.scanner import topology

    class R:
        def __init__(self, out):
            self.stdout = out

    monkeypatch.setattr(
        topology.subprocess,
        "run",
        lambda cmd, **kw: R("default via 2003:db8::1 dev eth0\n") if "-6" in cmd else R("default via 192.168.178.1 dev eth0\n"),
    )
    assert topology.gateway_ip6() == "2003:db8::1"
    assert topology.gateway_ip() == "192.168.178.1"
    assert topology.gateway_for("2003:db8::5", "192.168.178.1", "2003:db8::1") == "2003:db8::1"
    assert topology.gateway_for("192.168.178.5", "192.168.178.1", "2003:db8::1") == "192.168.178.1"
    assert topology.resolve_connected_to("aa:bb:cc:00:00:01", "2003:db8::5", gateway="192.168.178.1", gateway6="2003:db8::1") == "2003:db8::1"


def test_effective_settings_neue_compose_keys(tmp_path):
    conn, settings = make(tmp_path)
    db.set_setting(conn, "fritz_url", "http://192.168.178.1:49000")
    db.set_setting(conn, "scan_timeout", "3.5")
    db.set_setting(conn, "ports", "80,443")
    db.set_setting(conn, "notify_webhook", "https://hook.example/x")
    db.set_setting(conn, "fritz_pass", "geheim123")
    conn.commit()
    eff = effective_settings(conn, settings)
    assert eff.fritz_url == "http://192.168.178.1:49000"
    assert eff.scan_timeout == 3.5
    assert eff.ports == "80,443"
    assert eff.notify_webhook == "https://hook.example/x"
    assert eff.fritz_pass == "geheim123"
    conn.close()


def test_parse_vendor():
    assert oui.parse_vendor("ExampleVendor Inc.") == "ExampleVendor Inc."
    assert oui.parse_vendor('{"vendor": "JsonVendor"}') == "JsonVendor"
    assert oui.parse_vendor('{"company": "OtherVendor"}') == "OtherVendor"
    assert oui.parse_vendor("") == ""
    assert oui.parse_vendor("{kaputt") == ""


def test_oui_online_fallback(tmp_path, monkeypatch):
    conn, settings = make(tmp_path)
    settings = settings.model_copy(update={"oui_online_enabled": True, "oui_online_max": 5, "oui_online_url": "https://oui.example"})
    calls = []

    def fake_get(url, timeout=5.0):
        calls.append(url)
        return "ExampleVendor Inc."

    monkeypatch.setattr(oui, "_http_get", fake_get)
    budget = {"left": 5}
    v = oui.lookup_online("AA:BB:CC:11:22:33", settings, conn, budget)
    assert v == "ExampleVendor Inc."
    assert budget["left"] == 4
    assert calls == ["https://oui.example/AABBCC"]
    assert db.get_oui_cache(conn, "AABBCC") == "ExampleVendor Inc."
    # Cache-Treffer: kein HTTP, kein Budgetverbrauch
    v2 = oui.lookup_online("aa:bb:cc:99:88:77", settings, conn, budget)
    assert v2 == "ExampleVendor Inc." and len(calls) == 1 and budget["left"] == 4
    # Budget 0 -> kein HTTP
    assert oui.lookup_online("11:22:33:44:55:66", settings, conn, {"left": 0}) == "" and len(calls) == 1
    # deaktiviert -> kein HTTP
    s_off = settings.model_copy(update={"oui_online_enabled": False})
    assert oui.lookup_online("11:22:33:44:55:66", s_off, conn, {"left": 5}) == "" and len(calls) == 1
    # HTTP-Fehler -> "" und nicht gecacht
    def boom(url, timeout=5.0):
        raise OSError("down")

    monkeypatch.setattr(oui, "_http_get", boom)
    assert oui.lookup_online("DE:AD:BE:EF:00:01", settings, conn, {"left": 5}) == ""
    assert db.get_oui_cache(conn, "DEADBE") is None
    # JSON-Antwort parsen + cachen
    monkeypatch.setattr(oui, "_http_get", lambda url, timeout=5.0: '{"vendor": "JsonVendor"}')
    assert oui.lookup_online("DE:AD:BE:EF:00:02", settings, conn, {"left": 5}) == "JsonVendor"
    assert db.get_oui_cache(conn, "DEADBE") == "JsonVendor"
    conn.close()
def test_discover_mixed_v4_v6_sort(monkeypatch):
    """Regression: gemischte v4/v6-Live-Mengen duerfen sorted() nicht crashen (TypeError: not of the same version)."""
    import ipaddress

    monkeypatch.setattr(discover, "arp_table", lambda: {"192.168.178.34": "aa:bb:cc:00:00:01"})
    monkeypatch.setattr(discover, "neigh6_table", lambda: {"fdf1:3afe:ed39:0:27a:a4ff:fe9b:d968": "aa:bb:cc:00:00:02"})
    monkeypatch.setattr(discover, "ping_sweep", lambda subnet, timeout=1.0, max_hosts=0: {"192.168.178.34"})
    monkeypatch.setattr(discover, "tcp_probe_sweep", lambda subnet, skip, timeout=0.8, max_hosts=0: set())
    monkeypatch.setattr(discover, "ping_host", lambda ip, timeout: True)
    monkeypatch.setattr(discover.topology, "gateway_ip6", lambda: "fdf1:3afe:ed39::1")
    devs = discover.discover(["192.168.178.0/24", "fdf1:3afe:ed39::/64"], timeout=0.1)
    ips = [d["ip"] for d in devs]
    assert "192.168.178.34" in ips
    assert any(i.startswith("fdf1:") for i in ips)
    assert ips == sorted(ips, key=lambda s: (ipaddress.ip_address(s).version, int(ipaddress.ip_address(s))))
    assert discover.ip_sort_key("10.0.0.2") < discover.ip_sort_key("fdf1::1")


def test_v6_by_mac():
    neigh6 = {
        "fdf1:3afe:ed39::10": "AA:BB:CC:DD:EE:FF",
        "fe80::1": "aa:bb:cc:dd:ee:ff",  # Link-Local -> ignorieren
        "fdf1:3afe:ed39::20": "",  # ohne MAC -> ignorieren
    }
    m = discover.v6_by_mac(neigh6)
    assert m == {"aa:bb:cc:dd:ee:ff": "fdf1:3afe:ed39::10"}
    assert discover.v6_by_mac({}) == {}


def test_vpn_pool_heuristik():
    import pytest

    from app.scanner.topology import is_vpn_ip, is_vpn_tr064, vpn_pool_rules

    # auto: nur Gateway-/24, letzte Oktett >= 201 (FRITZ!-Default: DHCP endet bei .200)
    assert is_vpn_ip("192.168.178.201", "auto", "192.168.178.1") is True
    assert is_vpn_ip("192.168.178.254", "auto", "192.168.178.1") is True
    assert is_vpn_ip("192.168.178.200", "auto", "192.168.178.1") is False
    assert is_vpn_ip("192.168.179.201", "auto", "192.168.178.1") is False  # fremdes Subnetz unberuehrt
    assert is_vpn_ip("fdf1:3afe:ed39::201", "auto", "192.168.178.1") is False  # IPv6 nie per Pool
    assert is_vpn_ip("192.168.178.201", "off", "192.168.178.1") is False
    assert is_vpn_ip("192.168.178.201", "", "192.168.178.1") is False  # Default leer = aus, keine Annahme
    assert is_vpn_ip("", "auto", "192.168.178.1") is False
    # explizite CIDRs und Bereiche
    assert is_vpn_ip("10.8.0.5", "10.8.0.0/24", "") is True
    assert is_vpn_ip("192.168.178.203", "192.168.178.201-192.168.178.210", "") is True
    assert is_vpn_ip("192.168.178.211", "192.168.178.201-192.168.178.210", "") is False
    assert is_vpn_ip("10.8.0.9", "auto, 10.8.0.0/24", "192.168.178.1") is True
    with pytest.raises(ValueError):
        vpn_pool_rules("keine-ip", "")
    with pytest.raises(ValueError):
        vpn_pool_rules("192.168.178.210-192.168.178.201", "")
    # TR-064 InterfaceType
    assert is_vpn_tr064("VPN") is True
    assert is_vpn_tr064("Ethernet") is False


def test_merge_sources_tr064_vpn_flag():
    from app.scanner.run import merge_sources

    found = [{"ip": "192.168.178.201", "mac": "00:7a:a4:9b:d9:68", "source": "ping+arp"}]
    tr = {"00:7a:a4:9b:d9:68": {"mac": "00:7a:a4:9b:d9:68", "ip": "192.168.178.201", "hostname": "fritz.box", "active": True, "type": "VPN"}}
    out = merge_sources(found, tr)
    assert out[0]["vpn"] is True
    out2 = merge_sources([], {"00:7a:a4:9b:d9:69": {"mac": "00:7a:a4:9b:d9:69", "ip": "192.168.178.202", "hostname": "", "active": True, "type": "VPN"}})
    assert out2[0]["vpn"] is True
    out3 = merge_sources([], {"aa:bb:cc:dd:ee:ff": {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.178.50", "hostname": "nas", "active": True, "type": "Ethernet"}})
    assert not out3[0].get("vpn")


def test_apply_scan_speichert_vpn_flag(tmp_path):
    conn, settings = make(tmp_path)
    d1 = dev("00:7a:a4:9b:d9:68", "192.168.178.201", vpn=True, category="Unbekannt", layout={"connected_to": "192.168.178.1"})
    apply_scan(conn, settings, [d1])
    assert db.get_device(conn, d1["mac"])["vpn"] == 1
    # naechster Scan ohne VPN-Flag setzt es zurueck
    d2 = dev("00:7a:a4:9b:d9:68", "192.168.178.201", vpn=False, status="offline", layout={"connected_to": "192.168.178.1"})
    apply_scan(conn, settings, [d2])
    assert db.get_device(conn, d1["mac"])["vpn"] == 0
