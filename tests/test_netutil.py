"""W1-B: gemeinsame MAC-Normalisierung (Q-9), Platzhalter ip:<ip> unveraendert (N-3)."""

from app.netutil import is_mac, normalize_mac, normalize_mac_key, oui_prefix


def test_normalize_mac_strict():
    assert normalize_mac("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac("aa-bb-cc-dd-ee-ff") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac("a:b:c:d:e:f") is None  # nicht aufgefuellt
    assert normalize_mac("aa:bb:cc:dd:ee") is None
    assert normalize_mac("zz:bb:cc:dd:ee:ff") is None
    assert normalize_mac("") is None


def test_normalize_mac_key_keeps_ip_placeholder():
    # N-3: ip:-Platzhalter duerfen nicht zu ip:192:0:2:5 verstuemmelt werden
    assert normalize_mac_key("ip:192.0.2.5") == "ip:192.0.2.5"
    assert normalize_mac_key("ip:2001:db8::1") == "ip:2001:db8::1"
    assert normalize_mac_key("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac_key("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"


def test_is_mac_and_oui_prefix():
    assert is_mac("aa:bb:cc:dd:ee:ff")
    assert not is_mac("ip:192.0.2.5")
    assert oui_prefix("AA:BB:CC:DD:EE:FF") == "AABBCC"
    assert oui_prefix("kaputt") == ""


def test_device_path_case_insensitive(auth_client, app):
    # C-15: /api/device/{mac} ist case-insensitive
    from app import db

    conn = db.connect(app.state.db_path)
    db.upsert_device(
        conn, {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.0.2.10", "hostname": "drucker", "source": "test"}, db.utcnow()
    )
    conn.commit()
    conn.close()
    assert auth_client.get("/api/device/AA:BB:CC:DD:EE:FF").status_code == 200
    assert auth_client.get("/api/device/aa:bb:cc:dd:ee:ff").status_code == 200


def test_placeholder_key_not_mangled_in_collect():
    # N-3: collect_devices speichert ip:-Platzhalter unveraendert
    from app.scanner import run

    found = [{"ip": "192.0.2.99", "mac": "", "source": "arp"}]
    merged = run.merge_sources(found, {}, conn=None)
    assert merged[0]["mac"] == "ip:192.0.2.99"
