import logging
import os
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from .. import db
from ..config import Settings, effective_settings, get_settings
from ..exporters import auto_export, auto_export_due
from ..logsetup import get_logger
from . import categorize, discover, docker, mdns, names, notify, oui, ports, snmp, topology, tr064  # noqa: F401 - Anker fuer monkeypatch(run.<modul>) in Tests
from .pipeline import (  # noqa: F401 - Re-Exporte: bestehende Imports/Patches auf app.scanner.run bleiben gueltig
    add_source,
    collect_devices,
    effective_vpn_pool,
    fetch_mesh_info,
    known_mac,
    load_oui_table,
    merge_sources,
    mesh_parent_map,
    mesh_role_map,
    tr064_401_hint,
    tr064_tls_hint,
)

log = logging.getLogger("fox_netmap")


def apply_scan(
    conn: sqlite3.Connection,
    settings: Settings,
    devices: list[dict[str, Any]],
    now: str | None = None,
    *,
    skip_offline: bool = False,
) -> dict[str, Any]:
    now = now or db.utcnow()
    # K-10: Schreib-Lock sofort nehmen - Lesen und erstes Schreiben laufen sonst ohne
    # gemeinsamen Schnappschuss (Exporte mischen Daten vor/nach dem Scan)
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        return _apply_scan_body(conn, settings, devices, now, skip_offline=skip_offline)
    except Exception:
        # K-5: ein Fehler mitten im Scan verwirft den GANZEN Scan (kein halber Stand),
        # das finally in run_once schreibt danach nur noch den Scanstatus
        conn.rollback()
        raise


def _apply_scan_body(
    conn: sqlite3.Connection, settings: Settings, devices: list[dict[str, Any]], now: str, *, skip_offline: bool = False
) -> dict[str, Any]:
    existing = {r["mac"]: dict(r) for r in conn.execute("SELECT mac, status FROM devices")}
    seen: set[str] = set()
    new_devices: list[dict[str, Any]] = []
    for dev in devices:
        mac = dev["mac"]
        seen.add(mac)
        prev = existing.get(mac)
        db.upsert_device(conn, dev, now)
        old_ports, new_ports = db.replace_ports(conn, mac, dev.get("ports", []), now)
        status = dev.get("status", "online")
        db.add_history(conn, mac, status, now)
        if prev is None:
            db.add_event(conn, mac, "new", f"neues Geraet {dev.get('ip', '')}", now)
            new_devices.append(dev)
        else:
            if prev["status"] != status:
                db.add_event(conn, mac, status, "", now)
            if old_ports != new_ports:
                db.add_event(conn, mac, "ports_changed", f"{sorted(old_ports)} -> {sorted(new_ports)}", now)
        layout = dev.get("layout") or {}
        if layout.get("connected_to"):
            current = db.get_layout(conn, mac) or {}
            if not current.get("connected_manual"):
                db.set_layout(conn, mac, connected_to=layout["connected_to"])
    # SF-1: bei gesperrtem Lauf (leere Erkennung trotz online Bestand) weder offline setzen noch loeschen
    if skip_offline:
        removed = 0
    else:
        for mac, row in existing.items():
            if mac not in seen and row["status"] == "online":
                conn.execute("UPDATE devices SET status = 'offline' WHERE mac = ?", (mac,))
                db.add_history(conn, mac, "offline", now)
                db.add_event(conn, mac, "offline", "", now)
        removed = apply_retention(conn, settings, now)
    db.set_scan_state(conn, last_scan=now, scanning=0)
    conn.commit()
    db.trim_history(conn, settings.history_hours, now)
    trimmed = db.trim_events(conn, getattr(settings, "event_retention_days", 0))
    if trimmed:
        log.info("Retention: %s Ereignisse entfernt (älter als %s Tage)", trimmed, settings.event_retention_days)
    new_online = [d for d in new_devices if d.get("status") == "online"]
    return {
        "seen": len(seen),
        "new": len(new_devices),
        "new_devices": new_devices,
        "new_online": new_online,
        "removed": removed,
    }


def apply_retention(conn: sqlite3.Connection, settings: Settings, now: str) -> int:
    days = getattr(settings, "device_retention_days", 0)
    if days <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
    # C-5: last_seen wird nur bei online gesetzt; leer -> first_seen als Massstab
    rows = conn.execute(
        "SELECT mac FROM devices WHERE status = 'offline' AND COALESCE(NULLIF(last_seen, ''), first_seen) < ?",
        (cutoff,),
    ).fetchall()
    for r in rows:
        db.delete_device(conn, r["mac"])
    if rows:
        log.info("Retention: %s Geraete entfernt (offline seit > %s Tagen)", len(rows), days)
    return len(rows)


def run_once(settings: Settings, conn: sqlite3.Connection) -> dict[str, Any]:
    log.info("Scan gestartet (Subnetze: %s)", ", ".join(settings.subnet_list) or "auto")
    db.set_scan_state(conn, scanning=1, scan_started_at=db.utcnow())  # SF-3: Startzeit fuer Haenger-Erkennung
    conn.commit()
    try:
        devices = collect_devices(settings, conn)
        # SF-1: leere Erkennung darf bei online Bestand nichts offline setzen oder loeschen.
        # Die Sperre greift nur, wenn keine Subnetze bekannt oder die Sonden-Binaerdateien fehlen -
        # sonst wuerde ein wirklich leeres Netz nie offline anzeigen.
        skip_offline = False
        if not devices:
            online_before = conn.execute("SELECT COUNT(*) AS c FROM devices WHERE status = 'online'").fetchone()["c"]
            if online_before:
                subnets = settings.subnet_list or discover.local_subnets()
                if not subnets or not discover.binaries_available():
                    log.error(
                        "Erkennung lieferte 0 Geraete, obwohl %s Geraete online waren (keine Subnetze oder fehlende "
                        "Sonden-Binaerdateien) - Offline-Uebergang und Aufbewahrung werden uebersprungen",
                        online_before,
                    )
                    skip_offline = True
                else:
                    log.warning(
                        "Erkennung lieferte 0 Geraete, obwohl %s Geraete online waren - Netz wirkt leer, "
                        "Offline-Uebergang wird durchgefuehrt",
                        online_before,
                    )
        n_ping = sum(1 for d in devices if "ping" in d.get("source", ""))
        n_tcp = sum(1 for d in devices if "tcp" in d.get("source", ""))
        n_arp = sum(1 for d in devices if "arp" in d.get("source", ""))
        n_tr = sum(1 for d in devices if "tr064" in d.get("source", ""))
        n_only_tr = sum(1 for d in devices if d.get("source") == "tr064")
        log.info(
            "Abgleich: %s Geraete gesamt (%s Ping, %s TCP-Probe, %s davon ARP, %s TR-064, %s nur TR-064/offline)",
            len(devices),
            n_ping,
            n_tcp,
            n_arp,
            n_tr,
            n_only_tr,
        )
        summary = apply_scan(conn, settings, devices, skip_offline=skip_offline)
        # VPN-Clients (z. B. .201/.202 der FRITZ!Box) kommen und gehen mit dem VPN-Tunnel -> kein Alarm
        for d in summary["new_online"]:
            if d.get("vpn"):
                log.info("neues VPN-Geraet (kein Alarm): %s %s %s", d.get("mac"), d.get("ip"), d.get("hostname") or "-")
        alarm_list = [d for d in summary["new_online"] if not d.get("vpn") and not notify.is_whitelisted(settings, d)]
        skipped = len(summary["new_online"]) - len(alarm_list)
        if skipped:
            log.info("Alarm unterdrueckt (Whitelist): %s Geraet(e)", skipped)
        notify_ok = notify.notify_new_devices(settings, alarm_list)
        if alarm_list:
            # SF-5: Zustellstatus persistent speichern (Anzeige in der Oberflaeche folgt in W5)
            db.set_setting(conn, "last_notify_status", "ok" if notify_ok else "fehlgeschlagen")
            db.set_setting(conn, "last_notify_at", db.utcnow())
            conn.commit()
        if settings.auto_export:
            last_export = db.get_setting(conn, "last_auto_export")
            interval = getattr(settings, "auto_export_interval_hours", 24)
            if auto_export_due(last_export, interval):
                written = auto_export(settings, conn)
                db.set_setting(conn, "last_auto_export", db.utcnow())
                conn.commit()
                log.info("Auto-Export geschrieben: %s", ", ".join(os.path.basename(p) for p in written))
            else:
                log.info("Auto-Export uebersprungen (Intervall %sh, letzter Export: %s)", interval, last_export)
        # SF-2: Erfolg -> Fehlerzustand zuruecksetzen
        db.set_scan_state(conn, last_error=None, last_error_at=None, consecutive_failures=0)
        conn.commit()
        return summary
    except Exception as exc:
        # SF-2: Scanfehler im Scanzustand sichtbar machen (Healthcheck wertet ab 3 Fehlern aus)
        try:
            state = db.get_scan_state(conn)
            fails = int(state.get("consecutive_failures") or 0) + 1
            db.set_scan_state(
                conn,
                scanning=0,
                last_error=str(exc)[:500],
                last_error_at=db.utcnow(),
                consecutive_failures=fails,
            )
            conn.commit()
        except Exception:
            log.debug("Scan-Fehler konnte nicht in scan_state geschrieben werden", exc_info=True)
        raise
    finally:
        next_scan = db.utcnow()
        db.set_scan_state(conn, scanning=0, next_scan=next_scan)
        conn.commit()


def main() -> None:
    import signal

    settings = get_settings()
    os.makedirs(settings.data_dir, exist_ok=True)
    conn = db.connect(db.db_path(settings.data_dir))
    db.init_db(conn)
    log = get_logger(data_dir=settings.data_dir)
    log.info("Scanner startet: Intervall %ss, Daten: %s", settings.scan_interval, settings.data_dir)
    stop = {"flag": False}

    def _on_sigterm(signum: int, frame: Any) -> None:
        stop["flag"] = True  # K-8: docker stop -> sauberes Ende statt SIGKILL nach 10 s

    signal.signal(signal.SIGTERM, _on_sigterm)
    signal.signal(signal.SIGINT, _on_sigterm)
    while not stop["flag"]:
        eff = effective_settings(conn, settings)
        if db.get_setting(conn, "scan_requested"):
            db.set_setting(conn, "scan_requested", "")
            conn.commit()
            log.info("manueller Scan angefordert")
        started = time.perf_counter()
        try:
            summary = run_once(eff, conn)
            log.info(
                "Scan fertig in %.1fs: %s Geraete gesehen, %s neu",
                time.perf_counter() - started,
                summary["seen"],
                summary["new"],
            )
            for d in summary["new_devices"]:
                log.info(
                    "neues Geraet: %s %s %s %s",
                    d.get("mac"),
                    d.get("ip"),
                    d.get("hostname") or "-",
                    d.get("vendor") or "-",
                )
        except Exception:
            log.exception("Scan-Fehler")
        deadline = time.time() + eff.scan_interval
        db.set_scan_state(conn, next_scan=datetime.fromtimestamp(deadline, UTC).isoformat(timespec="seconds"))
        conn.commit()
        while time.time() < deadline and not stop["flag"]:
            if db.get_setting(conn, "scan_requested"):
                break
            time.sleep(0.5)
    log.info("Scanner beendet (SIGTERM/SIGINT)")
