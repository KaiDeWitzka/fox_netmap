"""Reine Prueffunktionen fuer Einstellungs-Texte (Q-2).

Jede Funktion wirft ValueError mit der bisherigen deutschen Meldung, damit die
Fehlertexte von PATCH /api/settings woertlich gleich bleiben."""

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from .netutil import looks_like_endpoint
from .settings_schema import SettingField

RANGE_MESSAGES = {
    "scan_interval": "scan_interval muss zwischen 30 und 86400 Sekunden liegen",
    "port_top": "port_top muss zwischen 0 (alle Ports) und 65535 liegen",
    "history_hours": "history_hours muss zwischen 1 und 87600 liegen",
    "device_retention_days": "device_retention_days muss zwischen 0 (nie löschen) und 3650 liegen",
    "event_retention_days": "event_retention_days muss zwischen 0 (nie löschen) und 3650 liegen",
    "scan_timeout": "scan_timeout muss zwischen 0.2 und 10 Sekunden liegen",
    "auto_export_interval_hours": "auto_export_interval_hours muss zwischen 0 (jeder Scan) und 720 liegen",
    "oui_online_max": "oui_online_max muss zwischen 0 und 200 liegen",
}

ENUM_MESSAGES = {
    "theme": "theme muss 'dark' oder 'light' sein",
    "lang": "lang muss de, en, fr, es, it oder pt sein",
}


def check_range(key: str, value: Any, field: SettingField) -> str | None:
    if key in RANGE_MESSAGES and (
        (field.minimum is not None and value < field.minimum) or (field.maximum is not None and value > field.maximum)
    ):
        return RANGE_MESSAGES[key]
    if key in ENUM_MESSAGES:
        allowed = {"theme": ("dark", "light"), "lang": ("de", "en", "fr", "es", "it", "pt")}[key]
        if value not in allowed:
            return ENUM_MESSAGES[key]
    return None


def parse_subnets(text: str) -> list[str]:
    out = []
    for sn in text.split(","):
        sn = sn.strip()
        if not sn:
            continue
        try:
            out.append(str(ipaddress.ip_network(sn, strict=False)))
        except ValueError:
            raise ValueError(f"ungültiges Subnetz: {sn!r} (CIDR erwartet, z. B. 192.168.178.0/24)") from None
    return out


def parse_sites(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"ungültiger Standort-Eintrag: {part!r} (Format: Name:Subnetz[,Subnetz]; ...)")
        name, _, subs = part.partition(":")
        if not name.strip():
            raise ValueError(f"Standort ohne Namen: {part!r}")
        for sn in subs.split(","):
            sn = sn.strip()
            if not sn:
                continue
            try:
                ipaddress.ip_network(sn, strict=False)
            except ValueError:
                raise ValueError(f"ungültiges Subnetz im Standort {name.strip()!r}: {sn!r}") from None
            out[sn] = name.strip()
    return out


def parse_endpoint(text: str) -> str:
    """URL oder host:port. S-8: Zugangsdaten (user:pass@host) in URLs werden abgelehnt."""
    t = text.strip()
    if t.startswith(("http://", "https://")):
        if "@" in urlparse(t).netloc:
            raise ValueError(f"URL darf keine Zugangsdaten (user:pass@) enthalten: {t!r}")
        return t
    if re.match(r"^[a-zA-Z0-9.\-]+(:\d+)?$", t):
        return t
    raise ValueError(f"{t!r} (URL oder host:port erwartet)")


PVE_FIELDS = ("pve_enabled", "pve_urls", "pve_user", "pve_token_id", "pve_token_secret", "pve_insecure_tls")


def parse_pve_url(text: str) -> str:
    """Proxmox-VE-API-Basis-URL: https?://host(:port)?(/api2/json)? - Default-Port 8006.

    S-8: Zugangsdaten (user:pass@host) in URLs werden abgelehnt; nur Basis-URL ohne Pfad.
    """
    t = text.strip()
    if t.endswith("/api2/json"):
        t = t[: -len("/api2/json")]
    t = t.rstrip("/")
    p = urlparse(t)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError(f"{text!r} (https://host:8006 erwartet)")
    if p.username or p.password:
        raise ValueError(f"URL darf keine Zugangsdaten (user:pass@) enthalten: {text!r}")
    if p.path not in ("", "/"):
        raise ValueError(f"nur Basis-URL ohne Pfad angeben (ausser /api2/json): {text!r}")
    try:
        port = p.port
    except ValueError as exc:
        raise ValueError(f"ungueltiger Port in Proxmox-URL: {text!r}") from exc
    if port is not None and not (1 <= port <= 65535):
        raise ValueError(f"Port ausserhalb 1-65535 in Proxmox-URL: {text!r}")
    return t


def parse_whitelist(text: str) -> list[str]:
    out = []
    for entry in text.split(","):
        e = entry.strip()
        if not e:
            continue
        try:
            ipaddress.ip_address(e)
            out.append(e)
            continue
        except ValueError:
            pass
        parts = e.replace("-", ":").split(":")
        is_mac = len(parts) == 6 and all(
            len(p) in (1, 2) and all(c in "0123456789abcdefABCDEF" for c in p) for p in parts
        )
        if not is_mac:
            raise ValueError(f"ungültiger Whitelist-Eintrag: {e!r} (MAC oder IP erwartet)")
        out.append(e)
    return out


def parse_ports(text: str) -> list[int]:
    out = []
    for p in text.split(","):
        p = p.strip()
        if not p:
            continue
        if not p.isdigit() or not 1 <= int(p) <= 65535:
            raise ValueError(f"ungültiger Port in eigener Portliste: {p!r}")
        out.append(int(p))
    return out


def parse_snmp_switches(text: str) -> list[str]:
    out = []
    for ip in text.split(","):
        ip = ip.strip()
        if not ip:
            continue
        try:
            out.append(str(ipaddress.ip_address(ip)))
        except ValueError:
            raise ValueError(f"ungültige IP für SNMP-Switch: {ip!r}") from None
    return out


def parse_notify_url(key: str, value: str) -> str:
    v = value.strip()
    if not v.startswith(("http://", "https://")):
        raise ValueError(f"{key} muss eine http(s)-URL sein: {v!r}")
    if "@" in urlparse(v).netloc:
        raise ValueError(f"{key} darf keine Zugangsdaten (user:pass@) in der URL enthalten: {v!r}")
    return v


def parse_auto_export_dir(value: str) -> str:
    d = value.strip()
    if not d or d.startswith("/") or ".." in d.split("/"):
        raise ValueError("auto_export_dir muss ein relativer Ordnername innerhalb des Daten-Volumes sein")
    return d


def looks_like_url_or_endpoint(value: str) -> bool:
    return looks_like_endpoint(value)


# --- PATCH /api/settings als reine Funktion (W7/Q-2): validate_patch(data) -> Fehlermeldung | None ---

from .settings_schema import FIELDS  # noqa: E402 - unten, nahe der Verwendung


def _check_ranges(data: dict[str, Any]) -> str | None:
    for key, value in data.items():
        err = check_range(key, value, FIELDS[key])
        if err:
            return err
    return None


def _check_ports(data: dict[str, Any]) -> str | None:
    if str(data.get("ports", "")).strip():
        try:
            parse_ports(data["ports"])
        except ValueError as exc:
            return str(exc)
    return None


def _check_fritz(data: dict[str, Any]) -> str | None:
    if str(data.get("fritz_url", "")).strip():
        try:
            parse_endpoint(data["fritz_url"])
        except ValueError as exc:
            return f"ungueltiges TR-064-Hauptgeraet: {exc}"
    if str(data.get("fritz_urls", "")).strip():
        for u in data["fritz_urls"].split(","):
            u = u.strip()
            if u:
                try:
                    parse_endpoint(u)
                except ValueError as exc:
                    return f"ungueltiger weiterer TR-064-Endpunkt: {exc}"
    if data.get("fritz_pass") is not None and len(data["fritz_pass"]) > 256:
        return "fritz_pass darf hoechstens 256 Zeichen haben"
    return None


def _check_notify(data: dict[str, Any]) -> str | None:
    for key in ("notify_webhook", "notify_gotify", "notify_ntfy"):
        val = data.get(key)
        if val is not None and str(val).strip():
            try:
                parse_notify_url(key, val)
            except ValueError as exc:
                return str(exc)
    if str(data.get("oui_online_url", "")).strip():
        try:
            parse_notify_url("oui_online_url", data["oui_online_url"])
        except ValueError as exc:
            return str(exc)
    return None


def _check_misc(data: dict[str, Any]) -> str | None:
    if str(data.get("snmp_community", "")).strip() and re.search(r"\s", data["snmp_community"].strip()):
        return "snmp_community darf keine Leerzeichen enthalten"
    if "vpn_pool" in data:
        from .scanner.topology import vpn_pool_rules

        try:
            vpn_pool_rules(data["vpn_pool"], "")
        except ValueError as exc:
            return f"ungueltiger vpn_pool-Eintrag: {exc}"
    if str(data.get("subnets", "")).strip():
        try:
            parse_subnets(data["subnets"])
        except ValueError as exc:
            return str(exc)
    if str(data.get("snmp_switches", "")).strip():
        try:
            parse_snmp_switches(data["snmp_switches"])
        except ValueError as exc:
            return str(exc)
    if "auto_export_dir" in data:
        try:
            parse_auto_export_dir(data["auto_export_dir"])
        except ValueError as exc:
            return str(exc)
    if str(data.get("alarm_whitelist", "")).strip():
        try:
            parse_whitelist(data["alarm_whitelist"])
        except ValueError as exc:
            return str(exc)
    if str(data.get("sites", "")).strip():
        try:
            parse_sites(data["sites"])
        except ValueError as exc:
            return str(exc)
    return None


def _check_pve(data: dict[str, Any], current: Any = None) -> str | None:
    # E-9: Proxmox VE. Querfeldpruefung gegen den Ist-Zustand (current = Settings), damit ein
    # gespeichertes Token-Secret beim Re-Aktivieren nicht erneut eingegeben werden muss.
    eff: dict[str, Any] = {k: getattr(current, k, "") for k in PVE_FIELDS} if current is not None else {}
    # S-8: leeres Secret im PATCH heisst "unveraendert" -> Ist-Zustand gilt weiter
    eff.update(
        {
            k: v
            for k, v in data.items()
            if k in PVE_FIELDS and v is not None and not (k == "pve_token_secret" and v == "")
        }
    )
    urls = str(eff.get("pve_urls") or "")
    if urls.strip():
        for u in urls.split(","):
            u = u.strip()
            if u:
                try:
                    parse_pve_url(u)
                except ValueError as exc:
                    return f"ungueltige Proxmox-VE-URL: {exc}"
    user = str(eff.get("pve_user") or "").strip()
    if user and not re.match(r"^[^\s@]+@[^\s@]+$", user):
        return f"ungueltiger Proxmox-Benutzer (user@realm erwartet, z. B. root@pam): {user}"
    token_id = str(eff.get("pve_token_id") or "").strip()
    if token_id and not re.match(r"^[^\s@]+@[^\s@]+![^\s]+$", token_id):
        return f"ungueltige Proxmox-Token-ID (user@realm!name erwartet, z. B. root@pam!fox_netmap): {token_id}"
    if data.get("pve_token_secret") is not None and len(str(data["pve_token_secret"])) > 256:
        return "pve_token_secret darf hoechstens 256 Zeichen haben"
    if eff.get("pve_enabled"):
        for key, label in (
            ("pve_urls", "PVE-URL(s)"),
            ("pve_user", "Benutzer (user@realm)"),
            ("pve_token_id", "Token-ID (user@realm!name)"),
            ("pve_token_secret", "Token-Secret"),
        ):
            if not str(eff.get(key) or "").strip():
                return f"Proxmox VE ist aktiv, aber {label} fehlt (NETZ_PVE_*)"
    return None


def validate_patch(data: dict[str, Any], current: Any = None) -> str | None:
    """Prueft ein settings-PATCH (nur gesetzte Felder). None = ok, sonst Fehlermeldung (woertlich wie frueher).

    current: optionales Settings-Objekt fuer Querfeldpruefungen gegen den Ist-Zustand (E-9/PVE).
    """
    for check in (_check_ranges, _check_ports, _check_fritz, _check_notify, _check_misc):
        err = check(data)
        if err:
            return err
    return _check_pve(data, current)
