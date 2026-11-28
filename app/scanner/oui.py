import ipaddress
import json
import logging
import os
import re
import socket
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .. import db as _db
from ..config import Settings
from ..logsetup import warn_once
from ..netutil import normalize_mac as _norm_mac
from ..netutil import oui_prefix as _oui_prefix

log = logging.getLogger("fox_netmap.oui")

LINE_RE = re.compile(r"^([0-9A-Fa-f]{2})[-:]([0-9A-Fa-f]{2})[-:]([0-9A-Fa-f]{2})\s+\(hex\)\s+(.+)$")


def normalize_mac(mac: str) -> str:
    # duenn: Q-9, strenger Parser in app/netutil.py; unbekannte Werte bleiben als lower()-String
    return _norm_mac(mac) or mac.replace("-", ":").replace(".", ":").lower()


def oui_prefix(mac: str) -> str:
    return _oui_prefix(mac)


def load_oui(path: str) -> dict[str, str]:
    table: dict[str, str] = {}
    if not path or not os.path.exists(path):
        return table
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = LINE_RE.match(line.strip())
            if m:
                table[(m.group(1) + m.group(2) + m.group(3)).upper()] = m.group(4).strip()
    return table


def lookup(mac: str, table: dict[str, str]) -> str:
    return table.get(oui_prefix(mac), "")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: Any, msg: Any, headers: Any, newurl: Any) -> Any:
        return None  # S-14: keine Weiterleitungen folgen


def _check_online_url(url: str) -> None:
    # S-14: nur http(s), kein Loopback/Link-Local - der Scanner darf keine lokalen Dienste abrufen
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError(f"oui_online_url muss eine http(s)-URL sein: {url!r}")
    host = (p.hostname or "").strip("[]")
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_loopback or addr.is_link_local:
            raise ValueError(f"oui_online_url darf nicht auf Loopback/Link-Local zeigen: {url!r}")
    except ValueError as exc:
        if "darf nicht" in str(exc):
            raise
        # Hostname: aufloesen und pruefen
        try:
            for ai in socket.getaddrinfo(host, None):
                a = ai[4][0]
                if ipaddress.ip_address(a).is_loopback or ipaddress.ip_address(a).is_link_local:
                    raise ValueError(f"oui_online_url loest auf Loopback/Link-Local auf: {url!r}")
        except OSError:
            raise ValueError(f"oui_online_url-Host nicht aufloesbar: {host!r}") from None


def _http_get(url: str, timeout: float = 5.0) -> str:
    _check_online_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "fox_netmap (OUI lookup)"})  # noqa: S310 - URL per _check_online_url geprueft (http(s), kein Loopback)
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(4096)  # S-14: Lese-Cap 4 KB
        text: str = raw.decode("utf-8", "ignore")
        return text


_PRINTABLE_RE = re.compile(r"[^\x20-\x7e]")


def parse_vendor(body: str) -> str:
    """macvendors.com liefert Klartext, manche APIs JSON {\"vendor\": ...} — beides bedienen."""
    body = (body or "").strip()
    if not body:
        return ""
    if body.startswith("{"):
        try:
            obj = json.loads(body)
            vendor = str(obj.get("vendor") or obj.get("company") or "").strip()
        except ValueError:
            return ""
    else:
        vendor = body.splitlines()[0].strip()
    # S-14: nur druckbare ASCII-Zeichen, auf 128 begrenzt - die Antwort landet in UI und DB
    return _PRINTABLE_RE.sub("", vendor)[:128]


def lookup_online(mac: str, settings: Settings, conn: sqlite3.Connection, budget: dict[str, Any]) -> str:
    """Online-OUI-Fallback: nur bei leerem lokalem Treffer, gecacht in oui_cache, mit Budget pro Scan."""
    if not getattr(settings, "oui_online_enabled", False):
        return ""
    if budget.get("left", 0) <= 0:
        return ""
    prefix = oui_prefix(mac)
    if not prefix or len(prefix) < 6:
        return ""
    if conn is not None:
        cached = _db.get_oui_cache(conn, prefix)
        if cached:
            return cached
    url = settings.oui_online_url.rstrip("/") + "/" + prefix
    budget["left"] = budget.get("left", 0) - 1
    try:
        vendor = parse_vendor(_http_get(url))
    except urllib.error.HTTPError as exc:
        if exc.code == 429 or exc.code >= 500:
            # Rate-Limit/Serverfehler: Online-Lookups fuer den Rest dieses Scans pausieren,
            # statt jede MAC erneut zu fragen (Log-Spam, weiterer 429)
            budget["left"] = 0
            warn_once(
                f"oui:http{exc.code}",
                "OUI-Online-Lookup HTTP %s - Online-Lookups fuer diesen Scan pausiert (%s)",
                exc.code,
                url,
            )
        else:
            warn_once(
                f"oui:http{exc.code}:{prefix}",
                "OUI-Online-Lookup fehlgeschlagen (HTTP %s) fuer %s",
                exc.code,
                url,
            )
        return ""
    except Exception as exc:  # noqa: BLE001  # N-5: ein Protokollfehler darf den ganzen Scan nicht abbrechen
        # kein exc_info: sonst landet pro MAC ein voller Traceback im Log (Log-Spam bei Ausfall)
        warn_once(
            f"oui:{type(exc).__name__}:{prefix}",
            "OUI-Online-Lookup fehlgeschlagen (%s) fuer %s",
            type(exc).__name__,
            url,
        )
        return ""
    if vendor and conn is not None:
        _db.set_oui_cache(conn, prefix, vendor)
    return vendor
