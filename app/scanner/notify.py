import logging

import httpx

log = logging.getLogger("fox_netmap.notify")


def _norm_mac(mac: str) -> str:
    # Q-9: eine Normalisierung in app/netutil.py; ip:-Platzhalter bleiben unveraendert
    from ..netutil import normalize_mac_key

    return normalize_mac_key(mac)


def is_whitelisted(settings, dev: dict) -> bool:
    raw = getattr(settings, "alarm_whitelist", "") or ""
    entries = [_norm_mac(e.strip()) for e in raw.split(",") if e.strip()]
    if not entries:
        return False
    mac = _norm_mac(dev.get("mac") or "")
    ip = (dev.get("ip") or "").strip()
    if mac and not mac.startswith("ip:") and mac in entries:
        return True
    return bool(ip and ip in entries)


def notify_new_devices(settings, devices: list[dict]) -> bool:
    """Liefert True, wenn alle konfigurierten Kanaele zustellten. SF-5: HTTP ab 300 (auch Redirects,
    follow_redirects=False) und Verbindungsfehler gelten als Fehlschlag."""
    if not devices:
        return True
    summary = [
        {"mac": d.get("mac"), "ip": d.get("ip"), "hostname": d.get("hostname"), "vendor": d.get("vendor")}
        for d in devices
    ]
    message = f"{len(devices)} neue(s) Geraet(e): " + ", ".join(
        f"{d.get('hostname') or d.get('ip')} ({d.get('mac')})" for d in devices
    )
    results = []
    if settings.notify_webhook:
        results.append(_post("Webhook", settings.notify_webhook, json={"event": "new_devices", "devices": summary}))
    if settings.notify_gotify and settings.notify_gotify_token:
        # Token im Header X-Gotify-Key statt als ?token= in der URL (v1.6.0): taucht so nicht in Proxy-,
        # Zugriffs- oder Fehlerprotokollen auf
        results.append(
            _post(
                "Gotify",
                f"{settings.notify_gotify.rstrip('/')}/message",
                json={"title": "fox_netmap: neues Geraet", "message": message, "priority": 5},
                headers={"X-Gotify-Key": settings.notify_gotify_token},
            )
        )
    if settings.notify_ntfy:
        headers = {"Title": "fox_netmap: neues Geraet"}
        if settings.notify_ntfy_token:
            headers["Authorization"] = f"Bearer {settings.notify_ntfy_token}"
        results.append(_post("ntfy", settings.notify_ntfy, content=message, headers=headers))
    return all(results) if results else True


def _post(name: str, url: str, **kw) -> bool:
    """Fehler nur mit Dienstname und Statuscode bzw. Fehlertyp protokollieren, nie mit URL oder Token.
    SF-5: Status ab 300 ist ein Fehler (Redirects werden nicht verfolgt)."""
    try:
        r = httpx.post(url, timeout=5, follow_redirects=False, **kw)
    except Exception as exc:  # noqa: BLE001 - Benachrichtigung darf den Scan nie abbrechen
        log.warning("%s-Benachrichtigung fehlgeschlagen: %s", name, type(exc).__name__)
        return False
    if r.status_code >= 300:
        log.warning("%s-Benachrichtigung abgelehnt: HTTP %s", name, r.status_code)
        return False
    return True
