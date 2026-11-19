CATEGORIES = ["Router", "Switch", "Server/NAS", "Client", "Drucker", "Smart-Home/IoT", "Unbekannt"]

KEYWORD_RULES = [
    ("Router", ("fritz", "speedport", "gateway", "router", "unifi", "mikrotik", "openwrt", "pfsense", "opnsense", "avm", "asus rt-", "netgear r")),
    ("Switch", ("switch", "tl-sg", "gs105", "gs108", "netgear gs", "unmanaged")),
    ("Server/NAS", ("nas", "synology", "qnap", "truenas", "server", "proxmox", "esxi", "pi-hole", "raspberry")),
    ("Drucker", ("drucker", "printer", "canon", "epson", "envy", "brother", "lexmark", "officejet")),
    ("Smart-Home/IoT", ("shelly", "tasmota", "hue", "yeelight", "xiaomi", "mi home", "ikea", "tradfri", "homematic", "homematic", "sonos", "ring", "nest", "alexa", "echo dot", "bulb", "plug", "wemo", "kasa", "smart tv", "chromecast", "fire tv", "apple tv")),
]


def categorize(hostname: str = "", vendor: str = "", ports=(), tr064_type: str = "") -> str:
    text = f"{hostname} {vendor} {tr064_type}".lower()
    for category, keywords in KEYWORD_RULES:
        if any(k in text for k in keywords):
            return category
    port_set = {p["port"] if isinstance(p, dict) else int(p) for p in ports}
    if 53 in port_set or 67 in port_set:
        return "Router"
    if 161 in port_set:
        return "Switch"
    if 9100 in port_set or 631 in port_set:
        return "Drucker"
    if 445 in port_set or {22, 80, 443} <= port_set:
        return "Server/NAS"
    return "Unbekannt"
