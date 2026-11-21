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


def build_pdf(settings, rows: list[dict], conn, image_bytes: bytes | None = None, title: str = "") -> bytes:
    """Serverseitiges PDF: Kopf (Version/Zeit/Statistik) + optional Karten-Snapshot (PNG/JPEG) + Geräte-Tabelle."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=title or "fox_netmap Export",
    )
    styles = getSampleStyleSheet()
    online = sum(1 for r in rows if r.get("status") == "online")
    story = [Paragraph(f"fox_netmap — {title or 'Netzwerk-Export'}", styles["Title"])]
    meta = (
        f"Version {settings.app_version} · erstellt {db.utcnow()} · "
        f"Geräte: {len(rows)} (online {online}, offline {len(rows) - online})"
    )
    story.append(Paragraph(meta, styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    max_w = A4[0] - 28 * mm
    if image_bytes:
        img = Image(io.BytesIO(image_bytes))
        ratio = img.imageHeight / float(img.imageWidth or 1)
        img.drawWidth = max_w
        img.drawHeight = max_w * ratio
        max_h = A4[1] - 70 * mm
        if img.drawHeight > max_h:
            img.drawHeight = max_h
            img.drawWidth = max_h / ratio
        story.append(img)
        story.append(Spacer(1, 6 * mm))

    header = ["Hostname", "IP", "MAC", "Hersteller", "Kategorie", "Status", "Subnetz", "Verbunden mit", "Ports"]
    data = [header]
    for r in rows:
        data.append([
            r.get("hostname") or "",
            r.get("ip") or "",
            r.get("mac") or "",
            r.get("vendor") or "",
            r.get("category") or "",
            r.get("status") or "",
            r.get("subnet") or "",
            r.get("connected_to") or "",
            r.get("ports_str") or "",
        ])
    widths = [32 * mm, 24 * mm, 30 * mm, 22 * mm, 20 * mm, 15 * mm, 26 * mm, 24 * mm, max_w - 193 * mm]
    t = Table(data, repeatRows=1, colWidths=widths)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#075985")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(t)
    doc.build(story)
    return buf.getvalue()
