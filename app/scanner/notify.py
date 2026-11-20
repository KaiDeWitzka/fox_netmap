import httpx


def _norm_mac(mac: str) -> str:
    parts = mac.lower().replace("-", ":").split(":")
    if len(parts) == 6:
        try:
            return ":".join(f"{int(p, 16):02x}" for p in parts)
        except ValueError:
            return mac.lower()
    return mac.lower()


def is_whitelisted(settings, dev: dict) -> bool:
    raw = getattr(settings, "alarm_whitelist", "") or ""
    entries = [_norm_mac(e.strip()) for e in raw.split(",") if e.strip()]
    if not entries:
        return False
    mac = _norm_mac(dev.get("mac") or "")
    ip = (dev.get("ip") or "").strip()
    if mac and not mac.startswith("ip:") and mac in entries:
        return True
    if ip and ip in entries:
        return True
    return False


def notify_new_devices(settings, devices: list[dict]) -> None:
    if not devices:
        return
    summary = [{"mac": d.get("mac"), "ip": d.get("ip"), "hostname": d.get("hostname"), "vendor": d.get("vendor")} for d in devices]
    message = f"{len(devices)} neue(s) Geraet(e): " + ", ".join(f"{d.get('hostname') or d.get('ip')} ({d.get('mac')})" for d in devices)
    if settings.notify_webhook:
        try:
            httpx.post(settings.notify_webhook, json={"event": "new_devices", "devices": summary}, timeout=5)
        except Exception:
            pass
    if settings.notify_gotify and settings.notify_gotify_token:
        try:
            httpx.post(
                f"{settings.notify_gotify.rstrip('/')}/message?token={settings.notify_gotify_token}",
                json={"title": "fox_netmap: neues Geraet", "message": message, "priority": 5},
                timeout=5,
            )
        except Exception:
            pass
    if settings.notify_ntfy:
        headers = {"Title": "fox_netmap: neues Geraet"}
        if settings.notify_ntfy_token:
            headers["Authorization"] = f"Bearer {settings.notify_ntfy_token}"
        try:
            httpx.post(settings.notify_ntfy, content=message, headers=headers, timeout=5)
        except Exception:
            pass
