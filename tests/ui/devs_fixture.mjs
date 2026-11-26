// Geraete-Fixture fuer den jsdom-DOM-Check (aus der echten API erzeugt und geprueft:
// tests/fixtures/api_devices_sample.json, Paritaets-Test tests/ui/fixture_parity.mjs).
export const DEVS = [
      {
        mac: "aa:bb:cc:dd:ee:ff", ip: "10.0.0.5", ip6: "2001:db8::10", hostname: "nas", vendor: "Synology",
        category: "Server/NAS", status: "online", subnet: "10.0.0.0/24", site: "Zuhause", source: "ping+arp,tr064", room: "Keller",
        ports_str: "80;443", connected_to: "10.0.0.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 2, x: null, y: null, connection: "lan",
      },
      {
        mac: "ip:192.168.179.20", ip: "192.168.179.20", hostname: "remote-plug", vendor: "",
        category: "Smart-Home/IoT", status: "offline", subnet: "192.168.179.0/24", site: "Remote", source: "tcp",
        ports_str: "", connected_to: "02:00:00:8e:ee:06", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 0, x: null, y: null, connection: "",
      },
      {
        mac: "02:00:00:8e:ee:06", ip: "192.168.178.10", hostname: "TL-SG108E-GZ", vendor: "TP-Link",
        category: "Switch", status: "online", subnet: "192.168.178.0/24", site: "Zuhause", source: "ping+arp",
        ports_str: "80", connected_to: "192.168.178.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 1, x: null, y: null, connection: "lan",
      },
      {
        mac: "aa:bb:cc:00:11:22", ip: "192.168.178.77", hostname: "wlan-tv", vendor: "",
        category: "Smart-Home/IoT", status: "online", subnet: "192.168.178.0/24", site: "Zuhause", source: "tr064", room: "EG-Wohnzimmer",
        ports_str: "", connected_to: "wlan:192.168.178.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 0, x: null, y: null, connection: "wlan", vpn: 1,
      },
      {
        mac: "76:84:18:83:f1:3c", ip: "", hostname: "PC-76-84-18-83-F1-3C", vendor: "",
        category: "Client", status: "online", subnet: "", site: "", source: "tr064",
        ports_str: "", connected_to: "192.168.178.1", note: "", last_seen: "2026-01-01T10:00:00+00:00",
        port_count: 0, x: null, y: null, connection: "",
      },
];
