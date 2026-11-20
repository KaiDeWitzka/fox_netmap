import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone

from . import db

CSV_FIELDS = [
    "mac",
    "ip",
    "hostname",
    "vendor",
    "category",
    "status",
    "subnet",
    "site",
    "connected_to",
    "ports",
    "note",
    "first_seen",
    "last_seen",
]


def devices_payload(settings, rows: list[dict], conn) -> dict:
    devices = []
    for r in rows:
        port_rows = conn.execute(
            "SELECT port FROM device_ports WHERE mac = ? ORDER BY port", (r["mac"],)
        ).fetchall()
        devices.append(
            {
                "mac": r["mac"],
                "ip": r["ip"],
                "hostname": r["hostname"],
                "vendor": r["vendor"],
                "category": r["category"],
                "status": r["status"],
                "subnet": r["subnet"],
                "site": (settings.site_map.get(r["subnet"], "") if r.get("subnet") else ""),
                "source": r["source"],
                "connection": r.get("connection", ""),
                "connected_to": r.get("connected_to") or "",
                "ports": [p["port"] for p in port_rows],
                "note": r["note"],
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
            }
        )
    return {
        "app": "fox_netmap",
        "version": settings.app_version,
        "exported_at": db.utcnow(),
        "device_count": len(devices),
        "devices": devices,
    }


def to_csv(rows: list[dict], delimiter: str = ";") -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
    writer.writerow(CSV_FIELDS)
    for r in rows:
        writer.writerow(
            [
                r["mac"],
                r["ip"],
                r["hostname"],
                r["vendor"],
                r["category"],
                r["status"],
                r["subnet"],
                r.get("site", ""),
                r.get("connected_to") or "",
                r.get("ports_str") or "",
                r["note"],
                r["first_seen"],
                r["last_seen"],
            ]
        )
    return buf.getvalue()


def auto_export_due(last: str | None, interval_hours: int, now=None) -> bool:
    if interval_hours <= 0:
        return True
    if not last:
        return True
    now = now or datetime.now(timezone.utc)
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    return (now - last_dt) >= timedelta(hours=interval_hours)


def auto_export(settings, conn) -> list[str]:
    out_dir = os.path.join(settings.data_dir, settings.auto_export_dir)
    os.makedirs(out_dir, exist_ok=True)
    rows = db.list_devices(conn)
    for r in rows:
        r["site"] = settings.site_map.get(r["subnet"], "") if r.get("subnet") else ""
    stamp = db.utcnow().replace(":", "-")
    written = []
    json_path = os.path.join(out_dir, f"netmap-{stamp}.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(devices_payload(settings, rows, conn), fh, ensure_ascii=False, indent=2)
    written.append(json_path)
    csv_path = os.path.join(out_dir, f"netmap-{stamp}.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(to_csv(rows, ";"))
    written.append(csv_path)
    return written
