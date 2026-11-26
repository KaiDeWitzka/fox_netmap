"""mDNS/DNS-SD-Dienstsuche fuer die Geraete-Einordnung (seit v1.6.0).

Eine einzige Anfrage an 224.0.0.251:5353 von einem zufaelligen Quellport ("Legacy Unicast", RFC 6762 Abschnitt 6.7):
Geraete antworten per Unicast direkt an den Scanner. Ausgewertet werden nur Diensttypen (PTR) und wenige
TXT-Schluessel mit der Modellbezeichnung. Es verlassen keine Daten das lokale Netz; es wird nichts gespeichert
ausser der abgeleiteten Kategorie und ihrer Begruendung.
"""

import logging
import socket
import struct
import time
from typing import Any

from .names import MDNS_V4, _decode_name, _encode_name

log = logging.getLogger("fox_netmap.mdns")

# Meta-Abfrage liefert alle Diensttypen; die konkreten Typen sorgen dafuer, dass TXT-Daten mitkommen
QUERY_TYPES = (
    "_services._dns-sd._udp.local",
    "_device-info._tcp.local",
    "_airplay._tcp.local",
    "_raop._tcp.local",
    "_googlecast._tcp.local",
    "_companion-link._tcp.local",
    "_ipp._tcp.local",
    "_hap._tcp.local",
    "_sonos._tcp.local",
)
MODEL_KEYS = ("model", "md", "am", "ty", "usb_mdl")
MAX_PACKETS = 2000
MAX_PACKET_BYTES = 9000
MAX_VALUE_LEN = 64


def build_query(types: tuple[str, ...] = QUERY_TYPES) -> bytes:
    header = struct.pack(">HHHHHH", 0, 0, len(types), 0, 0, 0)
    return header + b"".join(_encode_name(t) + struct.pack(">HH", 12, 1) for t in types)


def _txt_pairs(rdata: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    i = 0
    while i < len(rdata):
        n = rdata[i]
        chunk = rdata[i + 1 : i + 1 + n].decode("utf-8", "ignore")
        i += 1 + n
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            out[k.strip().lower()] = v.strip()[:MAX_VALUE_LEN]
    return out


def parse_packet(data: bytes) -> tuple[set[str], str]:
    """Liefert (Diensttypen wie "_airplay._tcp", Modell) aus allen Abschnitten eines Antwortpakets."""
    services: set[str] = set()
    model = ""
    if len(data) < 12:
        return services, model
    _, _, qd, an, ns, ar = struct.unpack(">HHHHHH", data[:12])
    offset = 12
    for _ in range(qd):
        _, offset = _decode_name(data, offset)
        offset += 4
    for _ in range(min(an + ns + ar, 512)):
        if offset + 10 > len(data):
            break
        name, offset = _decode_name(data, offset)
        rtype, _rclass, _ttl, rdlen = struct.unpack(">HHIH", data[offset : offset + 10])
        offset += 10
        if offset + rdlen > len(data):
            break
        rdata = data[offset : offset + rdlen]
        if rtype == 12:
            target, _ = _decode_name(data, offset)
            for cand in (target, name):
                svc = _service_type(cand)
                if svc:
                    services.add(svc)
        elif rtype == 16:
            svc = _service_type(name)
            if svc:
                services.add(svc)
            pairs = _txt_pairs(rdata)
            for k in MODEL_KEYS:
                if pairs.get(k) and not model:
                    model = pairs[k]
        offset += rdlen
    return services, model


def _service_type(name: str) -> str:
    """ "Wohnzimmer._airplay._tcp.local" -> "_airplay._tcp"; Meta-Name und Hostnamen -> ""."""
    labels = [x for x in name.lower().rstrip(".").split(".") if x]
    for i in range(len(labels) - 1):
        if labels[i].startswith("_") and labels[i + 1] in ("_tcp", "_udp"):
            svc = labels[i] + "." + labels[i + 1]
            return "" if svc == "_dns-sd._udp" else svc
    return ""


def browse(timeout: float = 2.0) -> dict[str, dict[str, Any]]:
    """{ip: {"services": set[str], "model": str}} fuer alle Geraete, die antworten. Fehler ergeben {}."""
    result: dict[str, dict[str, Any]] = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        log.debug("mDNS-Socket nicht verfuegbar - Dienstsuche uebersprungen", exc_info=True)
        return result
    try:
        sock.settimeout(0.3)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        sock.sendto(build_query(), MDNS_V4)
        deadline = time.monotonic() + timeout
        packets = 0
        while time.monotonic() < deadline and packets < MAX_PACKETS:
            try:
                data, (ip, _port) = sock.recvfrom(MAX_PACKET_BYTES)
            except TimeoutError:
                continue
            except OSError:
                break
            packets += 1
            services, model = parse_packet(data)
            if not services and not model:
                continue
            entry = result.setdefault(ip, {"services": set(), "model": ""})
            entry["services"] |= services
            if model and not entry["model"]:
                entry["model"] = model
    except OSError as exc:
        log.warning("mDNS-Dienstsuche fehlgeschlagen: %s", exc)
    finally:
        sock.close()
    return result
