"""Zentrales Einstellungs-Schema (Befund Q-1).

Eine Tabelle `FIELDS` beschreibt jedes `NETZ_*`-Feld: Typ, Grenzen, Geheimhaltung,
Sichtbarkeit in `GET /api/settings`, Aenderbarkeit per `PATCH /api/settings` und ob der
Scanner den DB-Wert zur Laufzeit uebernimmt. Daraus werden `SettingsPatch`, die GET-Ausgabe
und `effective_settings` abgeleitet - eine neue Einstellung steht an genau einer Stelle.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def cast_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class SettingField:
    type: str  # "str" | "int" | "float" | "bool"
    cast: Callable[[str], Any]
    minimum: float | None = None
    maximum: float | None = None
    secret: bool = False  # nie im Klartext ausliefern (GET zeigt nur "configured")
    exposed: bool = True  # in GET /api/settings sichtbar
    patchable: bool = True  # per PATCH /api/settings aenderbar
    scanner: bool = True  # Scanner uebernimmt den DB-Wert zur Laufzeit


_STR = ("str", str)
_INT = ("int", int)
_FLOAT = ("float", float)
_BOOL = ("bool", cast_bool)

FIELDS: dict[str, SettingField] = {
    # Deployment-/Env-only (nie patchbar, nie im GET)
    "data_dir": SettingField(*_STR, exposed=False, patchable=False, scanner=False),
    "host": SettingField(*_STR, exposed=False, patchable=False, scanner=False),
    "port": SettingField(*_INT, exposed=False, patchable=False, scanner=False),
    "subnet": SettingField(*_STR, exposed=False, patchable=False, scanner=False),  # Alt-Alias von subnets (Q-16)
    "embed_ancestors": SettingField(*_STR, exposed=False, patchable=False, scanner=False),
    "cookie_secure": SettingField(*_STR, exposed=False, patchable=False, scanner=False),
    # Auth: auth_enabled bewusst nur per Umgebung (E-2/S-9), auth_pass nur Env
    "auth_enabled": SettingField(*_BOOL, patchable=False, scanner=False),
    "auth_user": SettingField(*_STR, patchable=False, scanner=False),
    "auth_pass": SettingField(*_STR, secret=True, exposed=False, patchable=False, scanner=False),
    # Secrets: nie im Klartext in GET /api/settings (S-8)
    "fritz_pass": SettingField(*_STR, secret=True),
    "snmp_community": SettingField(*_STR, secret=True),
    "notify_gotify_token": SettingField(*_STR, secret=True),
    "notify_ntfy_token": SettingField(*_STR, secret=True),
    # Scan
    "subnets": SettingField(*_STR),
    "sites": SettingField(*_STR),
    "scan_interval": SettingField(*_INT, minimum=30, maximum=86400),
    "scan_timeout": SettingField(*_FLOAT, minimum=0.2, maximum=10),
    "port_top": SettingField(*_INT, minimum=0, maximum=65535),
    "ports": SettingField(*_STR),
    # TR-064 / FRITZ!Box
    "fritz_url": SettingField(*_STR),
    "fritz_urls": SettingField(*_STR),
    "fritz_user": SettingField(*_STR),
    "fritz_mesh": SettingField(*_BOOL),
    "tr064_insecure_tls": SettingField(*_BOOL),
    "vpn_pool": SettingField(*_STR),
    # SNMP
    "snmp_enabled": SettingField(*_BOOL),
    "snmp_switches": SettingField(*_STR),
    # Docker Engine API (Containerlandschaft-Scan, read-only, E-8)
    "docker_enabled": SettingField(*_BOOL),
    "docker_hosts": SettingField(*_STR),
    "docker_insecure_tls": SettingField(*_BOOL),
    "docker_token": SettingField(*_STR, secret=True),
    # Alarm
    "notify_webhook": SettingField(*_STR),
    "notify_gotify": SettingField(*_STR),
    "notify_ntfy": SettingField(*_STR),
    "alarm_whitelist": SettingField(*_STR),
    # Historie/Retention
    "history_hours": SettingField(*_INT, minimum=1, maximum=87600),
    "device_retention_days": SettingField(*_INT, minimum=0, maximum=3650),
    "event_retention_days": SettingField(*_INT, minimum=0, maximum=3650),
    # UI
    "theme": SettingField(*_STR),
    "lang": SettingField(*_STR),
    # Auto-Export
    "auto_export": SettingField(*_BOOL),
    "auto_export_dir": SettingField(*_STR),
    "auto_export_interval_hours": SettingField(*_INT, minimum=0, maximum=720),
    # Erkennung
    "mdns_enabled": SettingField(*_BOOL),
    "oui_online_enabled": SettingField(*_BOOL),
    "oui_online_max": SettingField(*_INT, minimum=0, maximum=200),
    "oui_online_url": SettingField(*_STR),
}


def patchable_fields() -> list[str]:
    return sorted(k for k, f in FIELDS.items() if f.patchable)


def exposed_fields() -> list[str]:
    return sorted(k for k, f in FIELDS.items() if f.exposed)


def scanner_fields() -> list[str]:
    return sorted(k for k, f in FIELDS.items() if f.scanner)
