import ipaddress
import logging
import os
import time
from datetime import datetime, timezone

from .. import db
from ..config import Settings, get_settings
from ..exporters import auto_export
from ..logsetup import get_logger
from . import categorize, discover, names, notify, oui, ports, snmp, topology, tr064

SEED_OUI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "oui_seed.txt")

log = logging.getLogger("fox_netmap")

OVERRIDABLE = {
    "scan_interval": int,
    "subnets": str,
    "port_top": int,
    "snmp_enabled": lambda v: str(v).lower() in ("1", "true", "yes"),
    "history_hours": int,
    "theme": str,
    "auto_export": lambda v: str(v).lower() in ("1", "true", "yes"),
}


def effective_settings(conn, base: Settings) -> Settings:
    data = base.model_dump()
    for key, cast in OVERRIDABLE.items():
        stored = db.get_setting(conn, key)
        if stored not in (None, ""):
            try:
                data[key] = cast(stored)
            except (ValueError, TypeError):
                pass
    return base.model_copy(update=data)


def load_oui_table(settings: Settings) -> dict[str, str]:
    for path in (os.path.join(settings.data_dir, "oui.txt"), SEED_OUI):
        table = oui.load_oui(path)
        if table:
            return table
    return {}


def collect_devices(settings: Settings, conn) -> list[dict]:
    subnets = settings.subnet_list or discover.local_subnets()
    found = discover.discover(subnets, settings.scan_timeout) if subnets else []
    oui_table = load_oui_table(settings)
    gateway = topology.gateway_ip()

    tr064_hosts: dict[str, dict] = {}
    base = settings.fritz_url or (f"http://{gateway}:49000" if gateway else "")
    if base and settings.fritz_user and settings.fritz_pass:
        try:
            hosts = tr064.fetch_hosts_with_fallback(base, settings.fritz_user, settings.fritz_pass)
            tr064_hosts = {h["mac"]: h for h in hosts if h.get("mac")}
            log.info("TR-064: %s Hosts von %s gelesen", len(tr064_hosts), base)
            wan = tr064.fetch_wan(base, settings.fritz_user, settings.fritz_pass)
            if wan:
                log.info("TR-064 WAN (%s): externe IP %s, Status %s", wan["service"].split(":")[-2], wan["wan_ip"] or "-", wan["status"] or "-")
        except tr064.TR064Error as exc:
            log.warning("TR-064 nicht erreichbar (%s): %s", base, exc)

    by_mac: dict[str, dict] = {}
    for d in found:
        if d.get("mac"):
            by_mac[d["mac"]] = d
    for mac, h in tr064_hosts.items():
        if mac in by_mac:
            d = by_mac[mac]
            d["ip"] = d["ip"] or h["ip"]
            if h.get("hostname"):
                d["hostname"] = h["hostname"]
            d["source"] = "tr064+" + d["source"] if d["source"] else "tr064"
            d["tr064_type"] = h.get("type", "")
            d["tr064_active"] = h.get("active", True)
        else:
            by_mac[mac] = {
                "ip": h["ip"],
                "mac": mac,
                "hostname": h.get("hostname", ""),
                "source": "tr064",
                "tr064_type": h.get("type", ""),
                "tr064_active": h.get("active", True),
            }

    devices = list(by_mac.values())
    live = [d for d in devices if d.get("ip")]
    for d in live:
        d["ports"] = ports.scan_ports(d["ip"], ports.port_list(settings.port_top, settings.ports), settings.scan_timeout)
    hostnames = names.resolve_all([d["ip"] for d in live])

    snmp_map: dict[str, str] = {}
    if settings.snmp_enabled:
        custom = [s.strip() for s in settings.snmp_switches.split(",") if s.strip()]
        targets = custom or [d["ip"] for d in live if any(p["port"] == 161 for p in d.get("ports", []))]
        if targets:
            snmp_map = snmp.cam_map(targets, settings.snmp_community)

    tr064_map = {mac: gateway for mac in tr064_hosts if gateway}

    for d in devices:
        if not d.get("mac"):
            continue
        d["mac"] = oui.normalize_mac(d["mac"])
        d["vendor"] = oui.lookup(d["mac"], oui_table)
        if not d.get("hostname") and d.get("ip"):
            d["hostname"] = hostnames.get(d["ip"], "")
        if "tr064_active" in d:
            d["status"] = "online" if d["tr064_active"] else "offline"
        else:
            d["status"] = "online"
        d["subnet"] = ""
        if d.get("ip"):
            try:
                addr = ipaddress.ip_address(d["ip"])
                d["subnet"] = next((sn for sn in subnets if addr in ipaddress.ip_network(sn, strict=False)), "")
            except ValueError:
                pass
        d["category"] = categorize.categorize(
            hostname=d.get("hostname", ""),
            vendor=d.get("vendor", ""),
            ports=d.get("ports", []),
            tr064_type=d.get("tr064_type", ""),
        )
        layout = db.get_layout(conn, d["mac"]) or {}
        manual = layout.get("connected_to") if layout.get("connected_manual") else None
        d["layout"] = {
            "connected_to": topology.resolve_connected_to(
                d["mac"], d.get("ip", ""), snmp_map=snmp_map, tr064_map=tr064_map, gateway=gateway, manual=manual
            )
        }
    return devices


def apply_scan(conn, settings: Settings, devices: list[dict], now: str | None = None) -> dict:
    now = now or db.utcnow()
    existing = {r["mac"]: dict(r) for r in conn.execute("SELECT mac, status FROM devices")}
    seen: set[str] = set()
    new_devices: list[dict] = []
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
    for mac, row in existing.items():
        if mac not in seen and row["status"] == "online":
            conn.execute("UPDATE devices SET status = 'offline', last_seen = ? WHERE mac = ?", (now, mac))
            db.add_history(conn, mac, "offline", now)
            db.add_event(conn, mac, "offline", "", now)
    db.set_scan_state(conn, last_scan=now, scanning=0)
    conn.commit()
    db.trim_history(conn, settings.history_hours, now)
    return {"seen": len(seen), "new": len(new_devices), "new_devices": new_devices}


def run_once(settings: Settings, conn) -> dict:
    log.info("Scan gestartet (Subnetze: %s)", ", ".join(settings.subnet_list) or "auto")
    db.set_scan_state(conn, scanning=1)
    conn.commit()
    try:
        devices = collect_devices(settings, conn)
        summary = apply_scan(conn, settings, devices)
        notify.notify_new_devices(settings, summary["new_devices"])
        if settings.auto_export:
            auto_export(settings, conn)
        return summary
    finally:
        next_scan = db.utcnow()
        db.set_scan_state(conn, scanning=0, next_scan=next_scan)
        conn.commit()


def main() -> None:
    settings = get_settings()
    os.makedirs(settings.data_dir, exist_ok=True)
    conn = db.connect(db.db_path(settings.data_dir))
    db.init_db(conn)
    log = get_logger(data_dir=settings.data_dir)
    log.info("Scanner startet: Intervall %ss, Daten: %s", settings.scan_interval, settings.data_dir)
    while True:
        eff = effective_settings(conn, settings)
        if db.get_setting(conn, "scan_requested"):
            db.set_setting(conn, "scan_requested", "")
            conn.commit()
            log.info("manueller Scan angefordert")
        started = time.perf_counter()
        try:
            summary = run_once(eff, conn)
            log.info("Scan fertig in %.1fs: %s Geraete gesehen, %s neu", time.perf_counter() - started, summary["seen"], summary["new"])
            for d in summary["new_devices"]:
                log.info("neues Geraet: %s %s %s %s", d.get("mac"), d.get("ip"), d.get("hostname") or "-", d.get("vendor") or "-")
        except Exception:
            log.exception("Scan-Fehler")
        deadline = time.time() + eff.scan_interval
        db.set_scan_state(conn, next_scan=datetime.fromtimestamp(deadline, timezone.utc).isoformat(timespec="seconds"))
        conn.commit()
        while time.time() < deadline:
            if db.get_setting(conn, "scan_requested"):
                break
            time.sleep(1)
