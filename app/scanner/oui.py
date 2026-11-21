import json
import os
import re
import urllib.error
import urllib.request

from .. import db as _db

LINE_RE = re.compile(r"^([0-9A-Fa-f]{2})[-:]([0-9A-Fa-f]{2})[-:]([0-9A-Fa-f]{2})\s+\(hex\)\s+(.+)$")


def normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").replace(".", ":").lower()


def oui_prefix(mac: str) -> str:
    return normalize_mac(mac).replace(":", "")[:6].upper()


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


def _http_get(url: str, timeout: float = 5.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "fox_netmap (OUI lookup)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def parse_vendor(body: str) -> str:
    """macvendors.com liefert Klartext, manche APIs JSON {\"vendor\": ...} — beides bedienen."""
    body = (body or "").strip()
    if not body:
        return ""
    if body.startswith("{"):
        try:
            obj = json.loads(body)
            return str(obj.get("vendor") or obj.get("company") or "").strip()
        except ValueError:
            return ""
    return body.splitlines()[0].strip()


def lookup_online(mac: str, settings, conn, budget: dict) -> str:
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
    except (urllib.error.URLError, OSError, ValueError):
        return ""
    if vendor and conn is not None:
        _db.set_oui_cache(conn, prefix, vendor)
    return vendor
