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
    assert categorize.categorize(vendor="AVM GmbH") == "Router"
    assert categorize.categorize(ports=[{"port": 53}]) == "Router"
    assert categorize.categorize(ports=[{"port": 161}]) == "Switch"
    assert categorize.categorize(hostname="switch-keller") == "Switch"
    assert categorize.categorize(hostname="synology-nas") == "Server/NAS"
    assert categorize.categorize(ports=[{"port": 445}]) == "Server/NAS"
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


def test_port_list():
    assert ports.port_list(10) == list(range(1, 11))
    assert ports.port_list(0)[-1] == 65535
    assert ports.port_list(1000, "443,80,443") == [80, 443]
    assert 8080 in ports.port_list(2000)


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
