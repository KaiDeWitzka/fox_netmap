"""Geraete-Einordnung (seit v1.6.0 mit Punktesystem).

Jedes Signal vergibt Punkte fuer eine Kategorie; die hoechste Summe gewinnt. Die staerksten Signale stehen oben:

  Gateway-IP (100) > Mesh-Rolle der FRITZ!Box (50) > mDNS-Modell (8) > Hostname (6) > mDNS-Dienst (4)
  > Hersteller laut OUI (3) > offene Ports (1-5) > zufaellige MAC im WLAN (1)

Die Begruendung wird als maschinenlesbarer Code zurueckgegeben (z. B. "host:iphone", "port:62078") und in der
Oberflaeche uebersetzt. Eine manuell gesetzte Kategorie (category_override) hat immer Vorrang (siehe db.py).
"""

import re

ROUTER = "Router"
REPEATER = "Repeater/AP"
SWITCH = "Switch"
SERVER = "Server/NAS"
CLIENT = "Client"
MOBILE = "Mobilgerät"
MEDIA = "Multimedia"
PRINTER = "Drucker"
IOT = "Smart-Home/IoT"
UNKNOWN = "Unbekannt"

CATEGORIES = [ROUTER, REPEATER, SWITCH, SERVER, CLIENT, MOBILE, MEDIA, PRINTER, IOT, UNKNOWN]


def _rx(*parts: str) -> re.Pattern:
    # Treffer nur am Wortanfang: "ring" passt auf "ring-tuer", nicht auf "string"
    return re.compile(r"(?:^|[^a-z0-9])(?:" + "|".join(parts) + ")")


# Reihenfolge = Vorrang bei gleicher Punktzahl (spezifische Muster zuerst, z. B. "nintendo switch")
HOSTNAME_RULES: list[tuple[str, re.Pattern]] = [
    (MEDIA, _rx(r"nintendo", r"playstation", r"ps[345](?![0-9])", r"xbox")),
    (PRINTER, _rx(r"drucker", r"printer", r"npi[0-9a-f]{6}", r"brw[0-9a-f]{12}", r"epson", r"canon", r"brother",
                  r"lexmark", r"officejet", r"laserjet", r"deskjet", r"envy", r"kyocera", r"mfc-")),
    (REPEATER, _rx(r"repeater", r"fritz-?repeater", r"fritz-?powerline", r"powerline", r"access-?point", r"ap[0-9]*(?![a-z])",
                   r"uap", r"extender", r"deco-")),
    (ROUTER, _rx(r"fritz[-.]?box", r"speedport", r"router", r"gateway", r"opnsense", r"pfsense", r"openwrt", r"mikrotik",
                 r"edgerouter", r"udm", r"usg")),
    (SWITCH, _rx(r"switch", r"tl-sg", r"gs1[0-9]{2}", r"gs3[0-9]{2}", r"sg[0-9]{3}", r"unmanaged")),
    (MOBILE, _rx(r"iphone", r"ipad", r"ipod", r"android", r"galaxy", r"pixel", r"oneplus", r"redmi", r"poco",
                 r"smartphone", r"handy", r"tablet", r"kindle", r"watch")),
    (MEDIA, _rx(r"tv", r"[a-z]*tv(?![a-z])", r"smarttv", r"webos", r"lgwebos", r"bravia", r"tizen", r"magentatv",
                r"apple-?tv", r"fire-?tv", r"chromecast", r"roku", r"sonos", r"homepod", r"kodi", r"libreelec", r"osmc",
                r"shield", r"receiver", r"denon", r"yamaha", r"marantz", r"soundbar", r"beamer", r"projector",
                r"teufel", r"bose", r"vu-?plus", r"dreambox", r"enigma")),
    (IOT, _rx(r"shelly", r"tasmota", r"esp[-_]?[0-9a-f]*", r"espressif", r"hue", r"philips-hue", r"yeelight", r"tradfri",
              r"homematic", r"ccu[0-9]", r"zigbee", r"deconz", r"conbee", r"tuya", r"smartlife", r"wemo", r"kasa",
              r"tapo", r"ring", r"nest", r"ecobee", r"netatmo", r"tado", r"miio", r"roborock", r"roomba", r"vacuum",
              r"plug", r"steckdose", r"bulb", r"lampe", r"thermostat", r"doorbell", r"ipcam", r"cam[0-9]", r"reolink",
              r"eufy", r"wled", r"sonoff", r"alexa", r"echo", r"wallbox", r"inverter", r"wechselrichter")),
    (SERVER, _rx(r"[a-z]*nas(?![a-z])", r"synology", r"diskstation", r"ds[0-9]{3}", r"qnap", r"truenas", r"unraid", r"server",
                 r"srv", r"proxmox", r"pve", r"esxi", r"pi-?hole", r"home-?assistant", r"hassio", r"docker",
                 r"nextcloud", r"plex", r"jellyfin", r"runtipi", r"raspberry(?:pi)?", r"homelab")),
    (CLIENT, _rx(r"macbook", r"imac", r"mac-?mini", r"mac-?pro", r"mac-?studio", r"mac(?![a-z])", r"[a-z]+mac(?![a-z])",
                 r"desktop", r"laptop", r"notebook", r"thinkpad", r"pc(?![a-z])", r"workstation", r"surface", r"win-",
                 r"ubuntu", r"fedora", r"debian")),
]

# Hersteller laut OUI-Datenbank (Teilstring, klein). Mehrdeutige Hersteller (Apple, Samsung, TP-Link, HP) fehlen bewusst.
VENDOR_RULES: list[tuple[str, tuple[str, ...]]] = [
    (MEDIA, ("sonos", "sony interactive", "nintendo", "roku", "bose", "denon", "sound united", "vestel",
             "lg electronics", "hisense", "tcl", "sky uk", "humax", "technisat", "panasonic av")),
    (PRINTER, ("brother", "seiko epson", "canon", "lexmark", "kyocera", "xerox", "ricoh")),
    (IOT, ("espressif", "tuya", "shelly", "allterco", "signify", "philips lighting", "ikea", "dresden elektronik",
           "eq-3", "netatmo", "tado", "ecobee", "nest labs", "ring llc", "itead", "lumi united", "beijing xiaomi")),
    (SERVER, ("synology", "qnap", "raspberry pi", "western digital", "asustor", "terramaster")),
    (REPEATER, ("ubiquiti", "ruckus", "aruba", "lancom", "devolo")),
    (CLIENT, ("intel corporate", "micro-star", "giga-byte", "asrock", "dell", "lenovo", "microsoft")),
]

# Diensttyp (DNS-SD) -> Kategorie
SERVICE_RULES: dict[str, str] = {
    "_ipp._tcp": PRINTER, "_ipps._tcp": PRINTER, "_printer._tcp": PRINTER, "_pdl-datastream._tcp": PRINTER,
    "_uscan._tcp": PRINTER, "_scanner._tcp": PRINTER,
    "_googlecast._tcp": MEDIA, "_sonos._tcp": MEDIA, "_spotify-connect._tcp": MEDIA, "_amzn-wplay._tcp": MEDIA,
    "_roku-rcp._tcp": MEDIA, "_androidtvremote2._tcp": MEDIA, "_daap._tcp": MEDIA,
    "_hap._tcp": IOT, "_hap._udp": IOT, "_hue._tcp": IOT, "_matter._tcp": IOT, "_matterc._udp": IOT,
    "_shelly._tcp": IOT, "_esphomelib._tcp": IOT, "_miio._udp": IOT,
    "_home-assistant._tcp": SERVER, "_smb._tcp": SERVER, "_afpovertcp._tcp": SERVER, "_nfs._tcp": SERVER,
    "_adisk._tcp": SERVER,
}

# Modellkennung aus TXT-Daten (_device-info, AirPlay, Cast). Apple-Kennungen sind eindeutig.
MODEL_RULES: list[tuple[str, re.Pattern]] = [
    (MOBILE, re.compile(r"^(iphone|ipad|ipod|watch)", re.I)),
    (MEDIA, re.compile(r"^(appletv|audioaccessory|homepod|chromecast|google tv|shield)", re.I)),
    (CLIENT, re.compile(r"^(macbook|imac|macmini|macpro|mac\d|j\d{3}\w*ap)", re.I)),
]

# Port -> (Kategorie, Punkte). Nur Ports mit klarer Aussage; 53/67 allein machen kein Geraet zum Router mehr.
PORT_RULES: dict[int, tuple[str, int]] = {
    62078: (MOBILE, 5),  # iOS/iPadOS (lockdownd)
    8008: (MEDIA, 4), 8009: (MEDIA, 4),  # Google Cast
    1400: (MEDIA, 4),  # Sonos
    3689: (MEDIA, 2),  # DAAP
    9100: (PRINTER, 4), 631: (PRINTER, 4), 515: (PRINTER, 4),
    8006: (SERVER, 4),  # Proxmox
    2049: (SERVER, 3), 32400: (SERVER, 3), 8096: (SERVER, 3), 8123: (SERVER, 3),
    5001: (SERVER, 2), 53: (SERVER, 2), 1883: (SERVER, 2), 548: (SERVER, 1),
    3389: (CLIENT, 3),
    161: (SWITCH, 1),
    49000: (REPEATER, 2),  # TR-064 (AVM), nur wenn das Geraet nicht das Gateway ist
}

# Ports, die zusaetzlich zur normalen Liste geprueft werden, weil sie die Einordnung entscheiden
FINGERPRINT_PORTS = sorted(p for p in PORT_RULES if p > 1000)

WEIGHT_GATEWAY = 100
WEIGHT_MESH = 50
WEIGHT_MODEL = 8
WEIGHT_HOST = 6
WEIGHT_SERVICE = 4
WEIGHT_VENDOR = 3
WEIGHT_RANDOM_MAC = 1


def _port_set(ports) -> set[int]:
    out = set()
    for p in ports or ():
        try:
            out.add(int(p["port"] if isinstance(p, dict) else p))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def is_random_mac(mac: str) -> bool:
    """Lokal verwaltete MAC (zweites Bit im ersten Byte), z. B. private WLAN-Adresse von iOS/Android."""
    try:
        return bool(int(mac.split(":")[0], 16) & 0x02)
    except (ValueError, IndexError):
        return False


def classify(
    hostname: str = "",
    vendor: str = "",
    ports=(),
    *,
    mac: str = "",
    is_gateway: bool = False,
    mesh_role: str = "",
    mdns: dict | None = None,
    connection: str = "",
) -> tuple[str, str]:
    """Liefert (Kategorie, Begruendung). Begruendung: "<signal>:<wert>", "" bei Unbekannt."""
    scores: dict[str, int] = {}
    reasons: dict[str, tuple[int, str]] = {}

    def add(cat: str, pts: int, why: str) -> None:
        scores[cat] = scores.get(cat, 0) + pts
        if pts > reasons.get(cat, (0, ""))[0]:
            reasons[cat] = (pts, why)

    if is_gateway:
        add(ROUTER, WEIGHT_GATEWAY, "gateway")
    if mesh_role == "master":
        add(ROUTER, WEIGHT_MESH, "mesh:master")
    elif mesh_role == "slave":
        add(REPEATER, WEIGHT_MESH, "mesh:slave")

    info = mdns or {}
    model = str(info.get("model") or "")
    if model:
        for cat, rx in MODEL_RULES:
            if rx.search(model):
                add(cat, WEIGHT_MODEL, "mdns:" + model)
                break
    for svc in sorted(info.get("services") or ()):
        cat = SERVICE_RULES.get(svc)
        if cat:
            add(cat, WEIGHT_SERVICE, "svc:" + svc)

    host = (hostname or "").lower()
    if host:
        for cat, rx in HOSTNAME_RULES:
            m = rx.search(host)
            if m:
                add(cat, WEIGHT_HOST, "host:" + m.group(0).strip("-_. "))
                break

    ven = (vendor or "").lower()
    if ven:
        for cat, keys in VENDOR_RULES:
            k = next((k for k in keys if k in ven), None)
            if k:
                add(cat, WEIGHT_VENDOR, "vendor:" + vendor)
                break
        if "avm" in ven and not is_gateway and not mesh_role:
            add(REPEATER, WEIGHT_VENDOR, "vendor:" + vendor)

    port_set = _port_set(ports)
    for port in sorted(port_set):
        rule = PORT_RULES.get(port)
        if not rule or (port == 49000 and is_gateway):
            continue
        add(rule[0], rule[1], f"port:{port}")
    if {22, 80, 443} <= port_set:
        add(SERVER, 2, "port:22+80+443")
    if 445 in port_set:
        # SMB bieten Windows-PCs und Macs genauso an wie NAS; zusammen mit SSH eher ein Server
        add(SERVER if 22 in port_set else CLIENT, 1, "port:445")

    if mac and connection == "wlan" and is_random_mac(mac) and not scores:
        add(MOBILE, WEIGHT_RANDOM_MAC, "mac:random")

    if not scores:
        return UNKNOWN, ""
    order = {c: i for i, c in enumerate(CATEGORIES)}
    best = max(scores, key=lambda c: (scores[c], -order[c]))
    return best, reasons[best][1]


def categorize(hostname: str = "", vendor: str = "", ports=(), tr064_type: str = "", **kw) -> str:
    """Kompatibel zur alten Schnittstelle: nur die Kategorie."""
    return classify(hostname, vendor, ports, **kw)[0]
