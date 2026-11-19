import httpx


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
