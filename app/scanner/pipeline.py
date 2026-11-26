"""Scanner-Pipeline (W7/Q-3): reine Stufen - sammeln (discover/TR-064), zusammenfuehren
(merge_sources), anreichern (Ports/Namen/mDNS/SNMP/Mesh), finalisieren (Kategorie/Layout).
run.py haelt nur noch run_once/apply_scan/main und importiert von hier, damit bestehende
Imports und Monkeypatches auf app.scanner.run weitergreifen."""

import ipaddress
import logging
import os
import sqlite3
from typing import Any, TypedDict
from urllib.parse import urlparse

from .. import db, netutil
from ..config import Settings
from . import categorize, discover, mdns, names, oui, ports, snmp, topology, tr064

SEED_OUI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "oui_seed.txt")

log = logging.getLogger("fox_netmap")


def load_oui_table(settings: Settings) -> dict[str, str]:
    for path in (os.path.join(settings.data_dir, "oui.txt"), SEED_OUI):
        table = oui.load_oui(path)
        if table:
            return table
    return {}


def add_source(d: dict[str, Any], src: str) -> None:
    parts = [s for s in d.get("source", "").split(",") if s]
    if src not in parts:
        parts.append(src)
    d["source"] = ",".join(parts)


def known_mac(conn: sqlite3.Connection | None, ip: str) -> str | None:
    if conn is None or not ip:
        return None
    row = conn.execute(
        "SELECT mac FROM devices WHERE ip = ? AND mac NOT LIKE 'ip:%' ORDER BY last_seen DESC LIMIT 1",
        (ip,),
    ).fetchone()
    return row["mac"] if row else None


def _is_v6(ip: str) -> bool:
    return ":" in (ip or "")


def _merge_addr(target: dict[str, Any], ip: str) -> None:
    """C-4: IPv4 gewinnt fuer `ip`; eine reine IPv6-Adresse landet in `ip6` (Dual-Stack-Geraet
    mit v4+ping+arp und v6+ndp bleibt sonst nur die IPv6 stehen)."""
    if not ip:
        return
    cur = target.get("ip", "")
    if not cur:
        target["ip"] = ip
    elif _is_v6(cur) and not _is_v6(ip):
        target["ip6"] = cur
        target["ip"] = ip
    elif _is_v6(ip) and not _is_v6(cur):
        target["ip6"] = ip


def merge_sources(
    found: list[dict[str, Any]], tr064_hosts: dict[str, dict[str, Any]], conn: sqlite3.Connection | None = None
) -> list[dict[str, Any]]:
    by_mac: dict[str, dict[str, Any]] = {}
    for d in found:
        if not d.get("ip"):
            continue
        if not d.get("mac"):
            d["mac"] = known_mac(conn, d["ip"]) or f"ip:{d['ip']}"
        existing = by_mac.get(d["mac"])
        if existing is None:
            by_mac[d["mac"]] = d
        else:
            _merge_addr(existing, d["ip"])
            add_source(existing, d.get("source", ""))
    by_ip = {d["ip"]: d for d in by_mac.values() if d.get("ip")}
    for mac, h in tr064_hosts.items():
        dev: dict[str, Any] | None
        if mac in by_mac:
            dev = by_mac[mac]
        elif h.get("ip") in by_ip:
            dev = by_ip[h["ip"]]
            existing = dev.get("mac", "")
            if existing.startswith("ip:") or not existing:
                by_mac.pop(existing, None)
                dev["mac"] = mac
                by_mac[mac] = dev
            else:
                log.warning("MAC-Konflikt bei %s: ARP %s vs TR-064 %s -> ARP gewinnt", h.get("ip"), existing, mac)
                dev = by_mac[existing]
        else:
            dev = None
        if dev is not None:
            _merge_addr(dev, h.get("ip", ""))  # C-4: IPv4 aus TR-064 gewinnt gegen IPv6
            if h.get("hostname"):
                dev["hostname"] = h["hostname"]
            add_source(dev, "tr064")
            dev["tr064_type"] = h.get("type", "")
            dev["tr064_active"] = h.get("active", True)
            if topology.is_vpn_tr064(h.get("type", "")):
                dev["vpn"] = True
            if h.get("endpoint"):
                dev["tr064_endpoint"] = h["endpoint"]
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


def tr064_401_hint(exc: Exception) -> str:
    """HTTP 401 = Authentifizierung/Berechtigung fehlgeschlagen: Der TR-064-Benutzer braucht in der
    FRITZ!Box Admin-Rechte bzw. alle Berechtigungen sowie 'Zugriff fuer Anwendungen zulassen' und
    'Statusinformationen ueber UPnP uebermitteln' (Heimnetz > Netzwerk > Netzwerkeinstellungen).
    Manche Modelle lehnen einzelne Actions trotz korrekter Zugangsdaten mit 401 ab."""
    if "HTTP 401" in str(exc):
        return " — HTTP 401: TR-064-Benutzer in der FRITZ!Box pruefen (laut AVM braucht er die Berechtigung 'App' oder 'Phone', am einfachsten Admin-Rechte; zusaetzlich 'Zugriff fuer Anwendungen zulassen' + 'Statusinformationen ueber UPnP uebermitteln' in Heimnetz > Netzwerk > Netzwerkeinstellungen; manche Modelle lehnen einzelne Actions trotz korrekter Zugangsdaten mit 401 ab; nach mehreren Fehlversuchen sperrt die FRITZ!Box den Benutzer kurzzeitig (Brute-Force-Schutz) - einmal erfolgreich als TR-064-Benutzer im Web-UI anmelden (hebt die Sperre auf) oder einige Minuten warten; System > Ereignisse zeigt die Fehlversuche; danach erneut scannen)"
    return ""


def tr064_tls_hint(exc: Exception, endpoint: str = "") -> str:
    """TLS-/Port-Hinweis: https auf Klartext-Port 49000 -> SSL WRONG_VERSION_NUMBER;
    der HTTPS-Port der FRITZ!Box ist 49443. Fallback auf http wurde versucht."""
    msg = str(exc).lower()
    norm = endpoint if "://" in endpoint else ("http://" + endpoint if endpoint else "")
    https_49000 = norm.startswith("https://") and urlparse(norm).netloc.endswith(":49000")
    if "wrong_version_number" in msg or "wrong version number" in msg or https_49000:
        return (
            " \u2014 TLS/Port: HTTPS laeuft auf Port 49443, nicht 49000 (https://\u2026:49000 -> SSL WRONG_VERSION_NUMBER); "
            "URL auf https://\u2026:49443 aendern oder http://\u2026:49000 verwenden; http-Fallback wurde versucht"
        )
    return ""


def fetch_mesh_info(settings: Settings, endpoints: list[str]) -> dict[str, Any] | None:
    """Mesh-Topologie vom ersten erreichbaren FRITZ!-Endpunkt (in der Regel der Mesh-Master)."""
    if not (settings.fritz_mesh and settings.fritz_user and settings.fritz_pass):
        return None
    for ep in endpoints:
        try:
            info = tr064.parse_mesh(
                tr064.fetch_mesh_with_fallback(
                    ep,
                    settings.fritz_user,
                    settings.fritz_pass,
                    verify=not getattr(settings, "tr064_insecure_tls", False),
                )
            )
        except tr064.TR064Error as exc:
            log.warning(
                "Mesh-Topologie nicht abrufbar (%s): %s%s%s",
                urlparse(ep if "://" in ep else "http://" + ep).hostname,
                exc,
                tr064_401_hint(exc),
                tr064_tls_hint(exc, ep),
            )
            continue
        repeaters = sum(1 for n in info["nodes"].values() if n["role"] == "slave")
        log.info("Mesh: %s Knoten, %s Repeater, %s Zuordnungen", len(info["nodes"]), repeaters, len(info["parents"]))
        return info
    return None


def mesh_role_map(mesh_info: dict[str, Any] | None) -> dict[str, str]:
    """{mac: "master" | "slave"} fuer alle Mesh-Knoten, auch unter ihren Schnittstellen-MACs."""
    out: dict[str, str] = {}
    for mac, node in ((mesh_info or {}).get("nodes") or {}).items():
        role = node.get("role", "")
        if role not in ("master", "slave"):
            continue
        for m in [mac, *node.get("macs", [])]:
            out.setdefault(netutil.normalize_mac_key(m), role)
    return out


def mesh_parent_map(mesh_info: dict[str, Any], devices: list[dict[str, Any]], gateway: str) -> dict[str, str]:
    """Bildet die Mesh-Eltern auf gescannte Geraete ab.

    Die Mesh-Liste fuehrt Geraete-MAC und Schnittstellen-MACs. Ist der Elternknoten unter keiner davon gescannt,
    wird der Mesh-Master auf die Gateway-IP abgebildet; andere unbekannte Eltern entfallen (Fallback greift).
    """
    known = {netutil.normalize_mac_key(d["mac"]) for d in devices if d.get("mac")}
    nodes = mesh_info.get("nodes", {})
    out: dict[str, str] = {}
    for child, link in mesh_info.get("parents", {}).items():
        parent = link["parent"]
        target = next((m for m in nodes.get(parent, {}).get("macs", [parent]) if m in known), "")
        if not target and parent == mesh_info.get("master") and gateway:
            target = gateway
        if target and target != child:
            out[netutil.normalize_mac_key(child)] = target
    return out


def effective_vpn_pool(settings: Settings, endpoints: list[str]) -> str:
    """Effektiver VPN-Pool: explizit konfigurierter Wert gewinnt. Bei 'off' und konfiguriertem
    TR-064 (FRITZ!Box mit User/Pass) greift die FRITZ!-Konvention 'auto' (letzte Oktett >= 201
    im Gateway-/24) — WireGuard-Peers tauchen naemlich nicht in TR-064 auf."""
    pool = (getattr(settings, "vpn_pool", "off") or "off").strip().lower()
    if pool == "off" and endpoints and getattr(settings, "fritz_user", "") and getattr(settings, "fritz_pass", ""):
        return "auto"
    return pool


class Ctx(TypedDict):
    """Kontext der Finalisierungsstufe - alles, was der alte Monolith collect_devices lokal hielt."""

    settings: Settings
    conn: Any
    subnets: list[str]
    v6_by_mac: dict[str, str]
    oui_table: dict[str, str]
    oui_budget: dict[str, int]
    gateway: str
    gateway6: str
    vpn_pool_eff: str
    mesh_info: dict[str, Any] | None
    tr064_parent: dict[str, str]
    hostnames: dict[str, str]
    mdns_map: dict[str, Any]
    snmp_map: dict[str, str]


def _persist_gateways(conn: sqlite3.Connection, gateway: str, gateway6: str) -> None:
    if gateway:
        db.set_setting(conn, "gateway", gateway)
    if gateway6:
        db.set_setting(conn, "gateway6", gateway6)
    conn.commit()


def gather_raw(
    settings: Settings, conn: sqlite3.Connection
) -> tuple[list[str], list[dict[str, Any]], dict[str, str], dict[str, str], str, str]:
    """Stufe 1: Subnetze, Erkennung, OUI-Tabelle, NDP-Tabelle, Gateways (persistiert gateway/gateway6)."""
    subnets = settings.subnet_list or discover.local_subnets()
    found = discover.discover(subnets, settings.scan_timeout) if subnets else []
    oui_table = load_oui_table(settings)
    v6_by_mac = discover.v6_by_mac(discover.neigh6_table())
    gateway = topology.gateway_ip()
    gateway6 = topology.gateway_ip6()
    _persist_gateways(conn, gateway, gateway6)
    return subnets, found, oui_table, v6_by_mac, gateway, gateway6


def endpoints_for(settings: Settings, gateway: str) -> list[str]:
    endpoints: list[str] = []
    if settings.fritz_url:
        endpoints.append(settings.fritz_url)
    elif gateway:
        endpoints.append(f"http://{gateway}:49000")
    endpoints += [u.strip() for u in settings.fritz_urls.split(",") if u.strip()]
    for ep in endpoints:
        norm = ep if "://" in ep else "http://" + ep
        if norm.startswith("https://") and urlparse(norm).netloc.endswith(":49000"):
            log.warning(
                "TR-064: %s nutzt https auf Port 49000 \u2014 der HTTPS-Port der FRITZ!Box ist 49443; bitte URL auf https://\u2026:49443 aendern (http://\u2026:49000 geht auch)",
                ep,
            )
    return endpoints


def fetch_tr064_stage(
    settings: Settings, endpoints: list[str], conn: sqlite3.Connection
) -> tuple[list[dict[str, Any]], set[str]]:
    """Stufe 2: TR-064-Hosts + WAN je Endpunkt lesen; WAN-Werte landen in den Settings."""
    all_tr064: list[dict[str, Any]] = []
    wan_endpoints: set[str] = set()
    if endpoints and settings.fritz_user and settings.fritz_pass:
        tr064_verify = not getattr(settings, "tr064_insecure_tls", False)
        if not tr064_verify:
            log.warning(
                "TR-064: NETZ_TR064_INSECURE_TLS=1 - TLS-Zertifikatspruefung deaktiviert (selbstsigniertes FRITZ!Box-Zertifikat); nur im eigenen LAN verwenden (MITM-Risiko)"
            )
        for ep in endpoints:
            try:
                hosts = tr064.fetch_hosts_with_fallback(
                    ep, settings.fritz_user, settings.fritz_pass, verify=tr064_verify
                )
                host_part = urlparse(ep if "://" in ep else "http://" + ep).hostname or ep
                for h in hosts:
                    h["endpoint"] = host_part
                all_tr064.extend(hosts)
                log.info("TR-064: %s Hosts von %s gelesen", len(hosts), ep)
                wan = tr064.fetch_wan_with_fallback(ep, settings.fritz_user, settings.fritz_pass, verify=tr064_verify)
                if wan:
                    log.info(
                        "TR-064 WAN %s (%s): externe IP %s, Status %s",
                        host_part,
                        wan["service"].split(":")[-2],
                        wan["wan_ip"] or "-",
                        wan["status"] or "-",
                    )
                    db.set_setting(conn, "wan_ip", wan["wan_ip"])
                    db.set_setting(conn, "wan_status", wan["status"])
                    # Router-Endpunkt merken: darueber wird der Internet-Knoten mit dem Router verbunden
                    wan_endpoints.add(host_part)
                    conn.commit()
            except tr064.TR064Error as exc:
                log.warning(
                    "TR-064 nicht erreichbar (%s): %s%s%s", ep, exc, tr064_401_hint(exc), tr064_tls_hint(exc, ep)
                )
    if wan_endpoints:
        db.set_setting(conn, "wan_endpoint", ",".join(sorted(wan_endpoints)))
        conn.commit()
    elif endpoints and settings.fritz_user and settings.fritz_pass:
        # SF-8: WAN-Abruf fehlgeschlagen -> Werte vom letzten Lauf nicht stehenlassen
        db.set_setting(conn, "wan_ip", "")
        db.set_setting(conn, "wan_status", "")
        db.set_setting(conn, "wan_endpoint", "")
        conn.commit()
    return all_tr064, wan_endpoints


def port_plan_for(settings: Settings) -> list[int]:
    port_plan = ports.port_list(settings.port_top, settings.ports)
    if not settings.ports.strip() and settings.port_top > 0:
        # Wenige zusaetzliche Ports, die die Einordnung entscheiden (z. B. 62078 iOS, 8009 Cast, 1400 Sonos)
        port_plan = sorted(set(port_plan) | set(categorize.FINGERPRINT_PORTS))
    return port_plan


def scan_ports_stage(settings: Settings, live: list[dict[str, Any]], port_plan: list[int]) -> None:
    """Stufe 3: offene Ports der gefundenen Geraete."""
    for d in live:
        d["ports"] = ports.scan_ports(d["ip"], port_plan, settings.scan_timeout)


def names_mdns_stage(settings: Settings, live: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, Any]]:
    """Stufe 4: Hostnamen (DNS/mDNS-PTR) und mDNS-Dienstsuche."""
    hostnames = names.resolve_all([d["ip"] for d in live], use_mdns=settings.mdns_enabled)
    mdns_map = mdns.browse() if settings.mdns_enabled else {}
    if mdns_map:
        log.info("mDNS: %s Geräte mit Diensten", len(mdns_map))
    return hostnames, mdns_map


def snmp_stage(settings: Settings, live: list[dict[str, Any]], gateway: str) -> dict[str, str]:
    """Stufe 5: SNMP-CAM/LLDP der Switches -> MAC-zu-Switch."""
    snmp_map: dict[str, str] = {}
    if settings.snmp_enabled and not settings.snmp_community.strip():
        log.info("SNMP übersprungen: keine Community gesetzt (NETZ_SNMP_COMMUNITY, seit v1.6.0 ohne Standardwert)")
    elif settings.snmp_enabled:
        custom = [s.strip() for s in settings.snmp_switches.split(",") if s.strip()]
        targets = custom or [d["ip"] for d in live if any(p["port"] == 161 for p in d.get("ports", []))]
        if targets:
            # C-9: MACs der Switches selbst und des Gateways duerfen nicht als "am Switch haengend" gelten
            arp_now = discover.arp_table()
            exclude = {arp_now.get(t, "") for t in targets}
            if gateway:
                exclude.add(arp_now.get(gateway, ""))
            exclude.discard("")
            cam = snmp.cam_map(targets, settings.snmp_community, exclude_macs=exclude)
            lldp = snmp.lldp_map(targets, settings.snmp_community)
            snmp_map = {**lldp, **cam}
            if lldp:
                log.info("LLDP-MIB: %s Nachbarn zusaetzlich erkannt", len(lldp))
    return snmp_map


def _finalize_device(
    d: dict[str, Any],
    ctx: Ctx,
    mesh_parents: dict[str, Any],
    mesh_roles: dict[str, str],
    fixed: set[str],
    lan_ports: dict[str, tuple[str, str]],
) -> None:
    """Pro Geraet: MAC normalisieren, IPv6/Hersteller/Hostname/Status/VPN/Kategorie/Layout setzen."""
    if not d.get("mac"):
        return
    d["mac"] = netutil.normalize_mac_key(d["mac"])
    d["ip6"] = ctx["v6_by_mac"].get(d["mac"], "")
    if not d["ip6"] and d.get("hostname"):
        # Fallback: DNS-AAAA des Hostnamens (z. B. FRITZ!Box-DNS), per ping6 verifizieren
        cand = names.resolve_aaaa(d["hostname"])
        if (
            cand
            and any(discover.in_net(cand, ipaddress.ip_network(sn, strict=False)) for sn in ctx["subnets"] if ":" in sn)
            and discover.ping_host(cand, ctx["settings"].scan_timeout)
        ):
            d["ip6"] = cand
            ctx["v6_by_mac"][d["mac"]] = cand
    d["vendor"] = oui.lookup(d["mac"], ctx["oui_table"])
    if not d["vendor"]:
        d["vendor"] = oui.lookup_online(d["mac"], ctx["settings"], ctx["conn"], ctx["oui_budget"])
    if not d.get("hostname") and d.get("ip"):
        d["hostname"] = ctx["hostnames"].get(d["ip"], "")
    if "tr064_active" in d:
        d["status"] = "online" if d["tr064_active"] else "offline"
    else:
        d["status"] = "online"
    d["subnet"] = ""
    if d.get("ip"):
        try:
            addr = ipaddress.ip_address(d["ip"])
            d["subnet"] = next((sn for sn in ctx["subnets"] if addr in ipaddress.ip_network(sn, strict=False)), "")
        except ValueError:
            pass
    # VPN-Client? Entweder TR-064 InterfaceType "VPN" (IPSec) oder IP im konfigurierten VPN-Pool
    # (Default "off" = keine Annahme; "auto" = FRITZ!-Konvention letzte Oktett >= 201 im Gateway-/24;
    # WireGuard-Peers erscheinen nicht in TR-064, daher ggf. Pool explizit setzen)
    if not d.get("vpn"):
        d["vpn"] = topology.is_vpn_ip(d.get("ip", ""), ctx["vpn_pool_eff"], ctx["gateway"])
    # TR-064 liefert "Ethernet", "802.11" oder "HomePlug" (vor v1.6.0 wurde nur "wlan"/"lan" erkannt)
    d["connection"] = topology.conn_type(d.get("tr064_type", ""))
    link = ctx["mesh_info"]["parents"].get(d["mac"]) if ctx["mesh_info"] else None
    d["category"], d["category_reason"] = categorize.classify(
        hostname=d.get("hostname", ""),
        vendor=d.get("vendor", ""),
        ports=d.get("ports", []),
        mac=d["mac"],
        is_gateway=bool(d.get("ip")) and d.get("ip") in (ctx["gateway"], ctx["gateway6"]),
        mesh_role=mesh_roles.get(d["mac"], ""),
        mdns=ctx["mdns_map"].get(d.get("ip", "")),
        connection=link["conn"] if link else d["connection"],
    )
    layout = db.get_layout(ctx["conn"], d["mac"]) or {}
    manual = layout.get("connected_to") if layout.get("connected_manual") else None
    d["layout"] = {
        "connected_to": topology.resolve_connected_to(
            d["mac"],
            d.get("ip", ""),
            snmp_map=ctx["snmp_map"],
            tr064_parent=ctx["tr064_parent"],
            tr064_type=d.get("tr064_type", ""),
            mesh_parent=mesh_parents,
            gateway=topology.gateway_for(d.get("ip", ""), ctx["gateway"], ctx["gateway6"]),
            gateway6=ctx["gateway6"],
            manual=manual,
        )
    }
    if manual or d["mac"] in ctx["snmp_map"]:
        fixed.add(d["mac"])
    elif link:
        # Die Mesh-Verbindung ist die tatsaechliche Anbindung (auch fuer Geraete am Repeater)
        if link["conn"] in ("lan", "wlan"):
            d["connection"] = link["conn"]
        d["link_port"] = link["port"]
        if link["conn"] == "lan":
            lan_ports[d["mac"]] = (d["layout"]["connected_to"], link["port"])


def finalize(devices: list[dict[str, Any]], ctx: Ctx) -> list[dict[str, Any]]:
    """Stufe 6: alle Geraete finalisieren, dann Geraete hinter gemeinsamem Switch-Port umhaengen."""
    mesh_parents = mesh_parent_map(ctx["mesh_info"], devices, ctx["gateway"]) if ctx["mesh_info"] else {}
    mesh_roles = mesh_role_map(ctx["mesh_info"])
    fixed: set[str] = set()
    lan_ports: dict[str, tuple[str, str]] = {}
    for d in devices:
        _finalize_device(d, ctx, mesh_parents, mesh_roles, fixed, lan_ports)
    if lan_ports:
        moved = topology.assign_behind_switch(devices, lan_ports, fixed)
        if moved:
            log.info("Mesh: %s Geraete einem Switch am selben LAN-Port zugeordnet", moved)
    return devices


def collect_devices(settings: Settings, conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Pipeline: sammeln -> zusammenfuehren -> anreichern -> finalisieren (Q-3)."""
    subnets, found, oui_table, v6_by_mac, gateway, gateway6 = gather_raw(settings, conn)
    endpoints = endpoints_for(settings, gateway)
    all_tr064, _wan_endpoints = fetch_tr064_stage(settings, endpoints, conn)
    vpn_pool_eff = effective_vpn_pool(settings, endpoints)
    if vpn_pool_eff != (getattr(settings, "vpn_pool", "off") or "off"):
        log.info(
            "VPN-Pool: NETZ_VPN_POOL=off, aber TR-064 konfiguriert -> 'auto' (FRITZ!-Konvention: letzte Oktett >= 201 im Gateway-/24)"
        )
    mesh_info = fetch_mesh_info(settings, endpoints)
    tr064_hosts = {h["mac"]: h for h in all_tr064 if h.get("mac")}
    tr064_parent: dict[str, str] = {}
    for h in all_tr064:
        if h.get("mac") and h.get("endpoint"):
            tr064_parent[h["mac"]] = h["endpoint"]

    devices = merge_sources(found, tr064_hosts, conn)
    # IPv6 bei grossen Netzen (/64): SLAAC/EUI-64-Kandidaten pro bekannter MAC per ping6 testen
    v6_by_mac = discover.v6_slaac_probe(
        subnets, {d.get("mac", "") for d in devices}, settings.scan_timeout, base=v6_by_mac
    )
    live = [d for d in devices if d.get("ip") and d.get("tr064_active", True)]
    scan_ports_stage(settings, live, port_plan_for(settings))
    hostnames, mdns_map = names_mdns_stage(settings, live)
    snmp_map = snmp_stage(settings, live, gateway)
    ctx: Ctx = {
        "settings": settings,
        "conn": conn,
        "subnets": subnets,
        "v6_by_mac": v6_by_mac,
        "oui_table": oui_table,
        "oui_budget": {"left": settings.oui_online_max},
        "gateway": gateway,
        "gateway6": gateway6,
        "vpn_pool_eff": vpn_pool_eff,
        "mesh_info": mesh_info,
        "tr064_parent": tr064_parent,
        "hostnames": hostnames,
        "mdns_map": mdns_map,
        "snmp_map": snmp_map,
    }
    return finalize(devices, ctx)
