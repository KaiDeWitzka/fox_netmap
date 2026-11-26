from app.scanner.run import merge_sources

MAC = "aa:bb:cc:dd:ee:ff"


def test_dual_stack_prefers_ipv4_for_ip():
    found = [
        {"ip": "192.168.178.20", "mac": MAC, "source": "ping+arp"},
        {"ip": "2001:db8::20", "mac": MAC, "source": "ndp"},
    ]
    out = merge_sources(found, {})
    assert len(out) == 1
    assert out[0]["ip"] == "192.168.178.20"
    assert out[0]["ip6"] == "2001:db8::20"
    assert set(out[0]["source"].split(",")) == {"ping+arp", "ndp"}


def test_dual_stack_reversed_order_still_prefers_ipv4():
    found = [
        {"ip": "2001:db8::20", "mac": MAC, "source": "ndp"},
        {"ip": "192.168.178.20", "mac": MAC, "source": "ping+arp"},
    ]
    out = merge_sources(found, {})
    assert len(out) == 1
    assert out[0]["ip"] == "192.168.178.20"
    assert out[0]["ip6"] == "2001:db8::20"


def test_ipv6_only_host_keeps_ipv6_as_ip():
    found = [{"ip": "2001:db8::20", "mac": MAC, "source": "ndp"}]
    out = merge_sources(found, {})
    assert len(out) == 1
    assert out[0]["ip"] == "2001:db8::20"
    assert not out[0].get("ip6")


def test_tr064_ipv4_wins_over_discovered_ipv6():
    found = [{"ip": "2001:db8::20", "mac": MAC, "source": "ndp"}]
    tr064 = {MAC: {"mac": MAC, "ip": "192.168.178.20", "hostname": "pc", "active": True, "type": "Ethernet"}}
    out = merge_sources(found, tr064)
    assert len(out) == 1
    assert out[0]["ip"] == "192.168.178.20"
    assert out[0]["ip6"] == "2001:db8::20"
    assert out[0]["hostname"] == "pc"
    assert "tr064" in out[0]["source"]
