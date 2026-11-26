"""Geraete-Einordnung v1.6.0: Punktesystem, Hostnamen aus echten Netzen, mDNS, Ports."""

import struct

import pytest

from app.scanner import categorize as c
from app.scanner import mdns, names


@pytest.mark.parametrize(
    "host,exp",
    [
        ("iPhone", c.MOBILE),
        ("Kais-iPad", c.MOBILE),
        ("Galaxy-S23", c.MOBILE),
        ("android-3f2a", c.MOBILE),
        ("PS5-642", c.MEDIA),
        ("LGwebOSTV", c.MEDIA),
        ("MagentaTV-One-2-Generation", c.MEDIA),
        ("Nintendo-Switch", c.MEDIA),
        ("Apple-TV-Wohnzimmer", c.MEDIA),
        ("sonos-kueche", c.MEDIA),
        ("Mac", c.CLIENT),
        ("iMac", c.CLIENT),
        ("NettiMac", c.CLIENT),
        ("Kais-Mac-mini", c.CLIENT),
        ("MacBook-Pro", c.CLIENT),
        ("DESKTOP-4KQ7T1B", c.CLIENT),
        ("NPI077254", c.PRINTER),
        ("BRW0080927AFBCE", c.PRINTER),
        ("drucker-buero", c.PRINTER),
        ("HueBridge", c.IOT),
        ("shelly-wohnzimmer", c.IOT),
        ("steckdose-1", c.IOT),
        ("ring-tuer", c.IOT),
        ("PupsNAS", c.SERVER),
        ("pups-nas", c.SERVER),
        ("pve", c.SERVER),
        ("pi-hole", c.SERVER),
        ("TL-SG108E-GZ", c.SWITCH),
        ("fritz.box", c.ROUTER),
        ("fritz-repeater", c.REPEATER),
    ],
)
def test_hostnamen(host, exp):
    assert c.categorize(hostname=host) == exp


@pytest.mark.parametrize("host", ["string-test", "honest", "machine", "cheap", "native"])
def test_keine_falschen_treffer_im_wort(host):
    assert c.categorize(hostname=host) == c.UNKNOWN


def test_gateway_schlaegt_alles():
    assert c.classify("homeserver", ports=[{"port": 445}, {"port": 22}], is_gateway=True) == (c.ROUTER, "gateway")


def test_mesh_rollen():
    assert c.classify("fritz.box", vendor="AVM GmbH", mesh_role="slave") == (c.REPEATER, "mesh:slave")
    assert c.classify("", mesh_role="master")[0] == c.ROUTER


def test_port_53_kein_router_mehr():
    assert c.classify(ports=[53, 80]) == (c.SERVER, "port:53")


def test_ios_port_und_cast():
    assert c.classify(ports=[62078]) == (c.MOBILE, "port:62078")
    assert c.classify(ports=[8008, 8009])[0] == c.MEDIA


def test_mdns_modell_schlaegt_hostname():
    # Hostname "server" waere Server/NAS, das Modell sagt eindeutig iPhone
    assert c.classify("server", mdns={"model": "iPhone14,2", "services": set()}) == (c.MOBILE, "mdns:iPhone14,2")
    assert c.classify("", mdns={"model": "MacBookPro18,3", "services": {"_airplay._tcp"}})[0] == c.CLIENT
    assert c.classify("", mdns={"model": "AppleTV11,1", "services": {"_airplay._tcp"}})[0] == c.MEDIA


def test_mdns_dienste():
    assert c.classify("", mdns={"services": {"_ipp._tcp"}, "model": ""}) == (c.PRINTER, "svc:_ipp._tcp")
    assert c.classify("", mdns={"services": {"_googlecast._tcp"}, "model": ""})[0] == c.MEDIA
    assert c.classify("", mdns={"services": {"_hap._tcp"}, "model": ""})[0] == c.IOT


def test_hersteller():
    assert c.classify(vendor="Sonos, Inc.") == (c.MEDIA, "vendor:Sonos, Inc.")
    assert c.classify(vendor="Espressif Inc.")[0] == c.IOT
    assert c.classify(vendor="Apple, Inc.")[0] == c.UNKNOWN  # mehrdeutig, bewusst keine Regel


def test_smb_allein_ist_client():
    assert c.classify(ports=[445])[0] == c.CLIENT
    assert c.classify(ports=[445, 22])[0] == c.SERVER


def test_zufaellige_mac_nur_im_wlan_und_als_letztes_signal():
    assert c.classify(mac="da:a1:19:00:00:01", connection="wlan") == (c.MOBILE, "mac:random")
    assert c.classify(mac="da:a1:19:00:00:01", connection="lan")[0] == c.UNKNOWN
    assert c.classify(mac="00:11:32:00:00:01", connection="wlan")[0] == c.UNKNOWN
    assert c.classify("pc", mac="da:a1:19:00:00:01", connection="wlan")[0] == c.CLIENT


def test_fingerprint_ports_klein_und_hoch():
    assert 62078 in c.FINGERPRINT_PORTS and 8009 in c.FINGERPRINT_PORTS
    assert all(p > 1000 for p in c.FINGERPRINT_PORTS) and len(c.FINGERPRINT_PORTS) < 20


def test_kategorien_api_entspricht_scanner():
    from app import api

    assert api.CATEGORIES == c.CATEGORIES


# ---- mDNS ----


def _name(n: str) -> bytes:
    return names._encode_name(n)


def _rr(name: str, rtype: int, rdata: bytes) -> bytes:
    return _name(name) + struct.pack(">HHIH", rtype, 1, 120, len(rdata)) + rdata


def _txt(*items: str) -> bytes:
    return b"".join(bytes([len(i)]) + i.encode() for i in items)


def test_mdns_paket_dienste_und_modell():
    pkt = struct.pack(">HHHHHH", 0, 0x8400, 0, 2, 0, 1)
    pkt += _rr("_services._dns-sd._udp.local", 12, _name("_airplay._tcp.local"))
    pkt += _rr("_airplay._tcp.local", 12, _name("Wohnzimmer._airplay._tcp.local"))
    pkt += _rr("Wohnzimmer._airplay._tcp.local", 16, _txt("deviceid=AA:BB", "model=AppleTV11,1"))
    services, model = mdns.parse_packet(pkt)
    assert services == {"_airplay._tcp"} and model == "AppleTV11,1"


def test_mdns_meta_name_ist_kein_dienst():
    assert mdns._service_type("_services._dns-sd._udp.local") == ""
    assert mdns._service_type("kai-iphone.local") == ""


def test_mdns_kaputte_pakete():
    assert mdns.parse_packet(b"") == (set(), "")
    assert mdns.parse_packet(b"\x00" * 12 + b"\xff\xff") == (set(), "")
    # Laengenangabe groesser als das Paket
    pkt = struct.pack(">HHHHHH", 0, 0x8400, 0, 1, 0, 0) + _name("a.local") + struct.pack(">HHIH", 16, 1, 1, 500)
    assert mdns.parse_packet(pkt) == (set(), "")


def test_mdns_txt_wert_begrenzt():
    pkt = struct.pack(">HHHHHH", 0, 0x8400, 0, 1, 0, 0) + _rr("x._ipp._tcp.local", 16, _txt("ty=" + "A" * 200))
    assert len(mdns.parse_packet(pkt)[1]) == mdns.MAX_VALUE_LEN


def test_dns_zeigerschleife_endet():
    # Zeiger auf sich selbst (Offset 12) darf keine Endlosschleife ausloesen
    pkt = b"\x00" * 12 + b"\xc0\x0c"
    name, _ = names._decode_name(pkt, 12)
    assert name == ""


def test_mdns_abfrage_aufbau():
    q = mdns.build_query()
    assert struct.unpack(">HHHHHH", q[:12])[2] == len(mdns.QUERY_TYPES)


def test_browse_ohne_netz(monkeypatch):
    class Dead:
        def __init__(self, *a, **k):
            raise OSError("kein Netz")

    monkeypatch.setattr(mdns.socket, "socket", Dead)
    assert mdns.browse(0.1) == {}
