import csv
import io
import json
import os
from datetime import UTC, datetime, timedelta

from . import db

CSV_FIELDS = [
    "mac",
    "ip",
    "ip6",
    "vpn",
    "hostname",
    "vendor",
    "category",
    "status",
    "subnet",
    "site",
    "connected_to",
    "link_port",
    "ports",
    "note",
    "room",
    "first_seen",
    "last_seen",
]


def devices_payload(settings, rows: list[dict], conn) -> dict:
    devices = []
    for r in rows:
        port_rows = conn.execute("SELECT port FROM device_ports WHERE mac = ? ORDER BY port", (r["mac"],)).fetchall()
        devices.append(
            {
                "mac": r["mac"],
                "ip": r["ip"],
                "ip6": r.get("ip6", ""),
                "vpn": bool(r.get("vpn")),
                "hostname": r["hostname"],
                "vendor": r["vendor"],
                "category": r["category"],
                "status": r["status"],
                "subnet": r["subnet"],
                "site": (settings.site_map.get(r["subnet"], "") if r.get("subnet") else ""),
                "source": r["source"],
                "connection": r.get("connection", ""),
                "connected_to": r.get("connected_to") or "",
                "link_port": r.get("link_port", ""),
                "ports": [p["port"] for p in port_rows],
                "note": r["note"],
                "room": r.get("room", ""),
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


def _csv_cell(value, formula: bool = False) -> str:
    # S-3: Freitextfelder mit fuehrendem =,+,-,@,Tab,CR werden in Tabellenkalkulationen als Formel
    # ausgewertet - ein ' wird vorangestellt. Gilt nicht fuer MAC/IP/Ports/Zeitstempel und nicht fuer JSON.
    s = "" if value is None else str(value)
    if formula and s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def to_csv(rows: list[dict], delimiter: str = ";") -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
    writer.writerow(CSV_FIELDS)
    for r in rows:
        writer.writerow(
            [
                r["mac"],
                r["ip"],
                r.get("ip6", ""),
                "ja" if r.get("vpn") else "nein",
                _csv_cell(r["hostname"], formula=True),
                _csv_cell(r["vendor"], formula=True),
                r["category"],
                r["status"],
                r["subnet"],
                _csv_cell(r.get("site", ""), formula=True),
                _csv_cell(r.get("connected_to") or "", formula=True),
                _csv_cell(r.get("link_port") or "", formula=True),
                r.get("ports_str") or "",
                _csv_cell(r["note"], formula=True),
                _csv_cell(r.get("room", ""), formula=True),
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
    now = now or datetime.now(UTC)
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=UTC)
    return bool((now - last_dt) >= timedelta(hours=interval_hours))


def _write_atomic(path: str, data: str) -> None:
    # K-8: atomar schreiben (tmp + os.replace) - ein Abbruch hinterlaesst keine abgeschnittene Datei
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(data)
    os.replace(tmp, path)


def auto_export(settings, conn) -> list[str]:
    out_dir = os.path.join(settings.data_dir, settings.auto_export_dir)
    os.makedirs(out_dir, exist_ok=True)
    with db.read_snapshot(conn):  # K-11: konsistenter Schnappschuss statt Daten vor/nach Scan
        rows = db.list_devices(conn)
        for r in rows:
            r["site"] = settings.site_map.get(r["subnet"], "") if r.get("subnet") else ""
        payload = devices_payload(settings, rows, conn)
        csv_text = to_csv(rows, ";")
    stamp = db.utcnow().replace(":", "-")
    written = []
    json_path = os.path.join(out_dir, f"netmap-{stamp}.json")
    _write_atomic(json_path, json.dumps(payload, ensure_ascii=False, indent=2))
    written.append(json_path)
    csv_path = os.path.join(out_dir, f"netmap-{stamp}.csv")
    _write_atomic(csv_path, csv_text)
    written.append(csv_path)
    return written


def build_pdf(
    settings,
    rows: list[dict],
    conn,
    image_bytes: bytes | None = None,
    title: str = "",
    orientation: str = "portrait",
) -> bytes:
    """Serverseitiges PDF: Kopf (Version/Zeit/Statistik) + optional Karten-Snapshot + Geräte-Tabelle.

    orientation: "portrait" (A4 hoch) oder "landscape" (A4 quer).
    Zellen sind Paragraphs -> langer Text wird umgebrochen statt zu überlappen.
    """
    from html import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    page = landscape(A4) if orientation == "landscape" else A4
    margin = 14 * mm
    usable_w = page[0] - 2 * margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=title or "fox_netmap Export",
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=8.5)
    head_style = ParagraphStyle("head", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)
    online = sum(1 for r in rows if r.get("status") == "online")
    story = [Paragraph(escape(f"fox_netmap — {title or 'Netzwerk-Export'}"), styles["Title"])]
    meta = (
        f"Version {escape(str(settings.app_version))} · erstellt {db.utcnow()} · "
        f"Ausrichtung: {'quer' if orientation == 'landscape' else 'hoch'} · "
        f"Geräte: {len(rows)} (online {online}, offline {len(rows) - online})"
    )
    story.append(Paragraph(meta, styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    if image_bytes:
        # S-6: Pixelzahl vor reportlab pruefen - ein 9000x9000-Bild belegt sonst >1 GB RAM
        from reportlab.lib.utils import ImageReader

        _w, _h = ImageReader(io.BytesIO(image_bytes)).getSize()
        if _w * _h > 16_000_000:
            raise ValueError("image zu gross (max 16 Megapixel)")
        img = Image(io.BytesIO(image_bytes))
        ratio = img.imageHeight / float(img.imageWidth or 1)
        img.drawWidth = usable_w
        img.drawHeight = usable_w * ratio
        max_h = page[1] - 70 * mm
        if img.drawHeight > max_h:
            img.drawHeight = max_h
            img.drawWidth = max_h / ratio
        story.append(img)
        story.append(Spacer(1, 6 * mm))

    header = ["Hostname", "IP", "MAC", "Hersteller", "Kategorie", "Status", "Subnetz", "Verbunden mit", "Ports"]
    fracs = [0.15, 0.11, 0.14, 0.13, 0.10, 0.07, 0.12, 0.10, 0.08]
    data = [[Paragraph(escape(h), head_style) for h in header]]
    for r in rows:
        data.append(
            [
                Paragraph(escape(str(r.get(k) or "")), cell_style)
                for k in (
                    "hostname",
                    "ip",
                    "mac",
                    "vendor",
                    "category",
                    "status",
                    "subnet",
                    "connected_to",
                    "ports_str",
                )
            ]
        )
    t = Table(data, repeatRows=1, colWidths=[f * usable_w for f in fracs])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#075985")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(t)
    doc.build(story)
    return buf.getvalue()
