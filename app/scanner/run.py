import ipaddress
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from .. import db
from ..config import Settings, get_settings
from ..exporters import auto_export, auto_export_due
from ..logsetup import get_logger
from . import categorize, discover, mdns, names, notify, oui, ports, snmp, topology, tr064

SEED_OUI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "oui_seed.txt")

log = logging.getLogger("fox_netmap")

OVERRIDABLE = {
    "scan_interval": int,
    "subnets": str,
    "port_top": int,
    "snmp_enabled": lambda v: str(v).lower() in ("1", "true", "yes"),
    "history_hours": int,
    "device_retention_days": int,
    "event_retention_days": int,
    "theme": str,
    "auto_export": lambda v: str(v).lower() in ("1", "true", "yes"),
    "auto_export_interval_hours": int,
    "mdns_enabled": lambda v: str(v).lower() in ("1", "true", "yes"),
    "oui_online_enabled": lambda v: str(v).lower() in ("1", "true", "yes"),
    "oui_online_max": int,
    "oui_online_url": str,
    "alarm_whitelist": str,
    "sites": str,
    "lang": str,
    "scan_timeout": float,
    "ports": str,
    "fritz_url": str,
    "fritz_urls": str,
    "fritz_user": str,
    "fritz_pass": str,
    "fritz_mesh": lambda v: str(v).lower() in ("1", "true", "yes"),
    "vpn_pool": str,
    "snmp_community": str,
    "notify_webhook": str,
    "notify_gotify": str,
    "notify_ntfy": str,
    "auto_export_dir": str,
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


def add_source(d: dict, src: str) -> None:
    parts = [s for s in d.get("source", "").split(",") if s]
    if src not in parts:
        parts.append(src)
    d["source"] = ",".join(parts)


def known_mac(conn, ip: str) -> str | None:
    if conn is None or not ip:
        return None
    row = conn.execute(
        "SELECT mac FROM devices WHERE ip = ? AND mac NOT LIKE 'ip:%' ORDER BY last_seen DESC LIMIT 1",
        (ip,),
    ).fetchone()
    return row["mac"] if row else None


def merge_sources(found: list[dict], tr064_hosts: dict[str, dict], conn=None) -> list[dict]:
    by_ip = {d["ip"]: d for d in found if d.get("ip")}
    by_mac: dict[str, dict] = {}
    for d in found:
        if not d.get("ip"):
            continue
        if not d.get("mac"):
            d["mac"] = known_mac(conn, d["ip"]) or f"ip:{d['ip']}"
        by_mac[d["mac"]] = d
    for mac, h in tr064_hosts.items():
        if mac in by_mac:
            d = by_mac[mac]
        elif h.get("ip") in by_ip:
            d = by_ip[h["ip"]]
            existing = d.get("mac", "")
            if existing.startswith("ip:") or not existing:
                by_mac.pop(existing, None)
                d["mac"] = mac
                by_mac[mac] = d
            else:
                log.warning(
                    "MAC-Konflikt bei %s: ARP %s vs TR-064 %s -> ARP gewinnt", h.get("ip"), existing, mac
                )
                d = by_mac[existing]
        else:
            d = None
        if d is not None:
            d["ip"] = d["ip"] or h["ip"]
            if h.get("hostname"):
                d["hostname"] = h["hostname"]
            add_source(d, "tr064")
            d["tr064_type"] = h.get("type", "")
            d["tr064_active"] = h.get("active", True)
            if topology.is_vpn_tr064(h.get("type", "")):
                d["vpn"] = True
            if h.get("endpoint"):
                d["tr064_endpoint"] = h["endpoint"]
        else:
            by_mac[mac] = {
                "ip": h["ip"],
                "mac": mac,
                "hostname": h.get("hostname", ""),
                "source": "tr064",
                "tr064_type": h.get("type", ""),
                "tr064_active": h.get("active", True),
                "vpn": topology.is_vpn_tr064(h.get("type", "")),
            }
    return list(by_mac.values())


def fetch_mesh_info(settings: Settings, endpoints: list[str]) -> dict | None:
    """Mesh-Topologie vom ersten erreichbaren FRITZ!-Endpunkt (in der Regel der Mesh-Master)."""
    if not (settings.fritz_mesh and settings.fritz_user and settings.fritz_pass):
        return None
    for ep in endpoints:
        try:
            info = tr064.parse_mesh(tr064.fetch_mesh(ep, settings.fritz_user, settings.fritz_pass))
        except tr064.TR064Error as exc:
            log.warning("Mesh-Topologie nicht abrufbar (%s): %s", urlparse(ep if "://" in ep else "http://" + ep).hostname, exc)
            continue
        repeaters = sum(1 for n in info["nodes"].values() if n["role"] == "slave")
        log.info("Mesh: %s Knoten, %s Repeater, %s Zuordnungen", len(info["nodes"]), repeaters, len(info["parents"]))
        return info
    return None


def mesh_role_map(mesh_info: dict | None) -> dict[str, str]:
    """{mac: "master" | "slave"} fuer alle Mesh-Knoten, auch unter ihren Schnittstellen-MACs."""
    out: dict[str, str] = {}
    for mac, node in ((mesh_info or {}).get("nodes") or {}).items():
        role = node.get("role", "")
        if role not in ("master", "slave"):
            continue
        for m in [mac, *node.get("macs", [])]:
            out.setdefault(oui.normalize_mac(m), role)
    return out


def mesh_parent_map(mesh_info: dict, devices: list[dict], gateway: str) -> dict[str, str]:
    """Bildet die Mesh-Eltern auf gescannte Geraete ab.

    Die Mesh-Liste fuehrt Geraete-MAC und Schnittstellen-MACs. Ist der Elternknoten unter keiner davon gescannt,
    wird der Mesh-Master auf die Gateway-IP abgebildet; andere unbekannte Eltern entfallen (Fallback greift).
    """
    known = {oui.normalize_mac(d["mac"]) for d in devices if d.get("mac")}
    nodes = mesh_info.get("nodes", {})
    out: dict[str, str] = {}
    for child, link in mesh_info.get("parents", {}).items():
        parent = link["parent"]
        target = next((m for m in nodes.get(parent, {}).get("macs", [parent]) if m in known), "")
        if not target and parent == mesh_info.get("master") and gateway:
            target = gateway
        if target and target != child:
            out[oui.normalize_mac(child)] = target
    return out


def effective_vpn_pool(settings, endpoints: list[str]) -> str:
    """Effektiver VPN-Pool: explizit konfigurierter Wert gewinnt. Bei 'off' und konfiguriertem
    TR-064 (FRITZ!Box mit User/Pass) greift die FRITZ!-Konvention 'auto' (letzte Oktett >= 201
    im Gateway-/24) — WireGuard-Peers tauchen naemlich nicht in TR-064 auf."""
    pool = (getattr(settings, "vpn_pool", "off") or "off").strip().lower()
    if pool == "off" and endpoints and getattr(settings, "fritz_user", "") and getattr(settings, "fritz_pass", ""):
        return "auto"
    return pool


def collect_devices(settings: Settings, conn) -> list[dict]:
    subnets = settings.subnet_list or discover.local_subnets()
    found = discover.discover(subnets, settings.scan_timeout) if subnets else []
    oui_table = load_oui_table(settings)
    v6_by_mac = discover.v6_by_mac(discover.neigh6_table())
    oui_budget = {"left": settings.oui_online_max}
    gateway = topology.gateway_ip()
    if gateway:
        db.set_setting(conn, "gateway", gateway)
    gateway6 = topology.gateway_ip6()
    if gateway6:
        db.set_setting(conn, "gateway6", gateway6)
    conn.commit()

    endpoints: list[str] = []
    if settings.fritz_url:
        endpoints.append(settings.fritz_url)
    elif gateway:
        endpoints.append(f"http://{gateway}:49000")
    endpoints += [u.strip() for u in settings.fritz_urls.split(",") if u.strip()]
    all_tr064: list[dict] = []
    wan_endpoints: set[str] = set()
    if endpoints and settings.fritz_user and settings.fritz_pass:
        for ep in endpoints:
            try:
                hosts = tr064.fetch_hosts_with_fallback(ep, settings.fritz_user, settings.fritz_pass)
                host_part = urlparse(ep if "://" in ep else "http://" + ep).hostname or ep
                for h in hosts:
                    h["endpoint"] = host_part
                all_tr064.extend(hosts)
                log.info("TR-064: %s Hosts von %s gelesen", len(hosts), ep)
                wan = tr064.fetch_wan(ep, settings.fritz_user, settings.fritz_pass)
                if wan:
                    log.info("TR-064 WAN %s (%s): externe IP %s, Status %s", host_part, wan["service"].split(":")[-2], wan["wan_ip"] or "-", wan["status"] or "-")
                    db.set_setting(conn, "wan_ip", wan["wan_ip"])
                    db.set_setting(conn, "wan_status", wan["status"])
                    # Router-Endpunkt merken: darueber wird der Internet-Knoten mit dem Router verbunden
                    wan_endpoints.add(host_part)
                    conn.commit()
            except tr064.TR064Error as exc:
                log.warning("TR-064 nicht erreichbar (%s): %s", ep, exc)
    if wan_endpoints:
        db.set_setting(conn, "wan_endpoint", ",".join(sorted(wan_endpoints)))
        conn.commit()
    vpn_pool_eff = effective_vpn_pool(settings, endpoints)
    if vpn_pool_eff != (getattr(settings, "vpn_pool", "off") or "off"):
        log.info("VPN-Pool: NETZ_VPN_POOL=off, aber TR-064 konfiguriert -> 'auto' (FRITZ!-Konvention: letzte Oktett >= 201 im Gateway-/24)")
    mesh_info = fetch_mesh_info(settings, endpoints)
    tr064_hosts = {h["mac"]: h for h in all_tr064 if h.get("mac")}
    tr064_parent: dict[str, str] = {}
    for h in all_tr064:
        if h.get("mac") and h.get("endpoint"):
            tr064_parent[h["mac"]] = h["endpoint"]

    devices = merge_sources(found, tr064_hosts, conn)
    # IPv6 bei grossen Netzen (/64): SLAAC/EUI-64-Kandidaten pro bekannter MAC per ping6 testen
    v6_by_mac = discover.v6_slaac_probe(subnets, {d.get("mac", "") for d in devices}, settings.scan_timeout, base=v6_by_mac)
    live = [d for d in devices if d.get("ip") and d.get("tr064_active", True)]
    port_plan = ports.port_list(settings.port_top, settings.ports)
    if not settings.ports.strip() and settings.port_top > 0:
        # Wenige zusaetzliche Ports, die die Einordnung entscheiden (z. B. 62078 iOS, 8009 Cast, 1400 Sonos)
        port_plan = sorted(set(port_plan) | set(categorize.FINGERPRINT_PORTS))
    for d in live:
        d["ports"] = ports.scan_ports(d["ip"], port_plan, settings.scan_timeout)
    hostnames = names.resolve_all([d["ip"] for d in live], use_mdns=settings.mdns_enabled)
    mdns_map = mdns.browse() if settings.mdns_enabled else {}
    if mdns_map:
        log.info("mDNS: %s Geräte mit Diensten", len(mdns_map))

    snmp_map: dict[str, str] = {}
    if settings.snmp_enabled and not settings.snmp_community.strip():
        log.info("SNMP übersprungen: keine Community gesetzt (NETZ_SNMP_COMMUNITY, seit v1.6.0 ohne Standardwert)")
    elif settings.snmp_enabled:
        custom = [s.strip() for s in settings.snmp_switches.split(",") if s.strip()]
        targets = custom or [d["ip"] for d in live if any(p["port"] == 161 for p in d.get("ports", []))]
        if targets:
            cam = snmp.cam_map(targets, settings.snmp_community)
            lldp = snmp.lldp_map(targets, settings.snmp_community)
            snmp_map = {**lldp, **cam}
            if lldp:
                log.info("LLDP-MIB: %s Nachbarn zusaetzlich erkannt", len(lldp))

    mesh_parents = mesh_parent_map(mesh_info, devices, gateway) if mesh_info else {}
    mesh_roles = mesh_role_map(mesh_info)
    fixed: set[str] = set()
    lan_ports: dict[str, tuple[str, str]] = {}
    for d in devices:
        if not d.get("mac"):
            continue
        d["mac"] = oui.normalize_mac(d["mac"])
        d["ip6"] = v6_by_mac.get(d["mac"], "")
        if not d["ip6"] and d.get("hostname"):
            # Fallback: DNS-AAAA des Hostnamens (z. B. FRITZ!Box-DNS), per ping6 verifizieren
            cand = names.resolve_aaaa(d["hostname"])
            if cand and any(discover.in_net(cand, ipaddress.ip_network(sn, strict=False)) for sn in subnets if ":" in sn):
                if discover.ping_host(cand, settings.scan_timeout):
                    d["ip6"] = cand
                    v6_by_mac[d["mac"]] = cand
        d["vendor"] = oui.lookup(d["mac"], oui_table)
        if not d["vendor"]:
            d["vendor"] = oui.lookup_online(d["mac"], settings, conn, oui_budget)
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
        # VPN-Client? Entweder TR-064 InterfaceType "VPN" (IPSec) oder IP im konfigurierten VPN-Pool
        # (Default "off" = keine Annahme; "auto" = FRITZ!-Konvention letzte Oktett >= 201 im Gateway-/24;
        # WireGuard-Peers erscheinen nicht in TR-064, daher ggf. Pool explizit setzen)
        if not d.get("vpn"):
            d["vpn"] = topology.is_vpn_ip(d.get("ip", ""), vpn_pool_eff, gateway)
        # TR-064 liefert "Ethernet", "802.11" oder "HomePlug" (vor v1.6.0 wurde nur "wlan"/"lan" erkannt)
        d["connection"] = topology.conn_type(d.get("tr064_type", ""))
        link = mesh_info["parents"].get(d["mac"]) if mesh_info else None
        d["category"], d["category_reason"] = categorize.classify(
            hostname=d.get("hostname", ""),
            vendor=d.get("vendor", ""),
            ports=d.get("ports", []),
            mac=d["mac"],
            is_gateway=bool(d.get("ip")) and d.get("ip") in (gateway, gateway6),
            mesh_role=mesh_roles.get(d["mac"], ""),
            mdns=mdns_map.get(d.get("ip", "")),
            connection=link["conn"] if link else d["connection"],
        )
        layout = db.get_layout(conn, d["mac"]) or {}
        manual = layout.get("connected_to") if layout.get("connected_manual") else None
        d["layout"] = {
            "connected_to": topology.resolve_connected_to(
                d["mac"],
                d.get("ip", ""),
                snmp_map=snmp_map,
                tr064_parent=tr064_parent,
                tr064_type=d.get("tr064_type", ""),
                mesh_parent=mesh_parents,
                gateway=topology.gateway_for(d.get("ip", ""), gateway, gateway6),
                gateway6=gateway6,
                manual=manual,
            )
        }
        if manual:
            fixed.add(d["mac"])
        elif d["mac"] in snmp_map:
            fixed.add(d["mac"])
        elif link:
            # Die Mesh-Verbindung ist die tatsaechliche Anbindung (auch fuer Geraete am Repeater)
            if link["conn"] in ("lan", "wlan"):
                d["connection"] = link["conn"]
            d["link_port"] = link["port"]
            if link["conn"] == "lan":
                lan_ports[d["mac"]] = (d["layout"]["connected_to"], link["port"])
    if lan_ports:
        moved = topology.assign_behind_switch(devices, lan_ports, fixed)
        if moved:
            log.info("Mesh: %s Geräte einem Switch am selben LAN-Port zugeordnet", moved)
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
    return {"seen": len(seen), "new": len(new_devices), "new_devices": new_devices, "new_online": new_online, "removed": removed}


def apply_retention(conn, settings: Settings, now: str) -> int:
    days = getattr(settings, "device_retention_days", 0)
    if days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute("SELECT mac FROM devices WHERE status = 'offline' AND last_seen < ?", (cutoff,)).fetchall()
    for r in rows:
        db.delete_device(conn, r["mac"])
    if rows:
        log.info("Retention: %s Geraete entfernt (offline seit > %s Tagen)", len(rows), days)
    return len(rows)


def run_once(settings: Settings, conn) -> dict:
    log.info("Scan gestartet (Subnetze: %s)", ", ".join(settings.subnet_list) or "auto")
    db.set_scan_state(conn, scanning=1)
    conn.commit()
    try:
        devices = collect_devices(settings, conn)
        n_ping = sum(1 for d in devices if "ping" in d.get("source", ""))
        n_tcp = sum(1 for d in devices if "tcp" in d.get("source", ""))
        n_arp = sum(1 for d in devices if "arp" in d.get("source", ""))
        n_tr = sum(1 for d in devices if "tr064" in d.get("source", ""))
        n_only_tr = sum(1 for d in devices if d.get("source") == "tr064")
        log.info(
            "Abgleich: %s Geraete gesamt (%s Ping, %s TCP-Probe, %s davon ARP, %s TR-064, %s nur TR-064/offline)",
            len(devices), n_ping, n_tcp, n_arp, n_tr, n_only_tr,
        )
        summary = apply_scan(conn, settings, devices)
        # VPN-Clients (z. B. .201/.202 der FRITZ!Box) kommen und gehen mit dem VPN-Tunnel -> kein Alarm
        for d in summary["new_online"]:
            if d.get("vpn"):
                log.info("neues VPN-Geraet (kein Alarm): %s %s %s", d.get("mac"), d.get("ip"), d.get("hostname") or "-")
        alarm_list = [d for d in summary["new_online"] if not d.get("vpn") and not notify.is_whitelisted(settings, d)]
        skipped = len(summary["new_online"]) - len(alarm_list)
        if skipped:
            log.info("Alarm unterdrueckt (Whitelist): %s Geraet(e)", skipped)
        notify.notify_new_devices(settings, alarm_list)
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
