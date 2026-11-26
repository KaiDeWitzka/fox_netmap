"""Gemeinsame Netz-/MAC-Hilfen (Q-9): eine Normalisierung statt vieler Kopien."""

import re

_HEX = set("0123456789abcdef")


def normalize_mac(value: str) -> str | None:
    """Streng: genau 6 aufgefuellte Oktette, kleingeschrieben, ':'-getrennt; sonst None."""
    v = (value or "").strip().lower().replace("-", ":")
    parts = v.split(":")
    if len(parts) != 6 or not all(len(p) == 2 and set(p) <= _HEX for p in parts):
        return None
    return v


def normalize_mac_key(value: str) -> str:
    """Schluessel fuer API-Pfade/DB: echte MAC normalisiert, `ip:<adresse>`-Platzhalter
    (N-3) und IPv6-Platzhalter bleiben unveraendert, sonst Fallback auf lower()."""
    if value.startswith("ip:"):
        return value
    return normalize_mac(value) or value.strip().lower()


def is_mac(value: str) -> bool:
    return normalize_mac(value) is not None


def oui_prefix(mac: str) -> str:
    m = normalize_mac(mac)
    return m.replace(":", "")[:6].upper() if m else ""


_ENDPOINT_RE = re.compile(r"^[a-zA-Z0-9.\-]+(:\d+)?$")


def looks_like_endpoint(text: str) -> bool:
    t = text.strip()
    return t.startswith(("http://", "https://")) or bool(_ENDPOINT_RE.match(t))
