import json
import xml.etree.ElementTree as ET
from contextlib import suppress

import httpx

HOSTS_SERVICE = "urn:dslforum-org:service:Hosts:1"
HOSTS_PATH = "/upnp/control/hosts"
WAN_SERVICES = (
    ("urn:dslforum-org:service:WANIPConnection:1", "/upnp/control/wanipconn"),
    ("urn:dslforum-org:service:WANPPPConnection:1", "/upnp/control/wanpppconn1"),
)


class TR064Error(Exception):
    pass


def _soap_body(service: str, action: str, args: dict) -> str:
    return (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body>"
        f'<u:{action} xmlns:u="{service}">'
        + "".join(f"<{k}>{v}</{k}>" for k, v in args.items())
        + f"</u:{action}></s:Body></s:Envelope>"
    )


def _soap_fault_root(root: ET.Element) -> str:
    desc, code, faultstring = "", "", ""
    for el in root.iter():
        if el.text is None:
            continue
        tag = el.tag.split("}")[-1]
        if tag in ("UPnPErrorDescription", "errorDescription") and not desc:
            desc = el.text.strip()
        elif tag in ("UPnPErrorCode", "errorCode") and not code:
            code = el.text.strip()
        elif tag == "faultstring" and not faultstring:
            faultstring = el.text.strip()
    return " ".join(p for p in (faultstring, code, desc) if p)


def _parse_fields(root: ET.Element) -> dict:
    out = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag.startswith("New") and el.text is not None:
            out[tag] = el.text.strip()
    return out


def _soap_call(
    base_url: str,
    path: str,
    service: str,
    action: str,
    args: dict,
    user: str,
    password: str,
    timeout: float = 8.0,
    verify: bool = True,
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": f'"{service}#{action}"'}
    auth = httpx.DigestAuth(user, password) if user else None
    try:
        response = httpx.post(
            url, content=_soap_body(service, action, args), headers=headers, auth=auth, timeout=timeout, verify=verify
        )
    except httpx.HTTPError as exc:
        raise TR064Error(f"{action} -> {url}: Verbindungsfehler: {exc}") from exc
    if response.status_code >= 400:
        try:
            fault = _soap_fault_root(ET.fromstring(response.text))  # noqa: S314 - SOAP-Antwort aus dem LAN; Groessen-/Host-Limit in W2 (S-15)
        except ET.ParseError:
            fault = ""
        raise TR064Error(f"{action} -> HTTP {response.status_code}" + (f" ({fault})" if fault else ""))
    try:
        root = ET.fromstring(response.text)  # noqa: S314 - SOAP-Antwort aus dem LAN; Groessen-/Host-Limit in W2 (S-15)
    except ET.ParseError as exc:
        raise TR064Error(f"{action} -> {url}: ungültige XML-Antwort") from exc
    fault = _soap_fault_root(root)
    if fault:
        raise TR064Error(f"{action} -> SOAP Fault: {fault}")
    return _parse_fields(root)


def _normalize_base(base_url: str) -> str:
    if "://" not in base_url:
        base_url = "http://" + base_url
    return base_url.rstrip("/")


def fetch_hosts(base_url: str, user: str, password: str, verify: bool = True) -> list[dict]:
    base_url = _normalize_base(base_url)
    count = _soap_call(base_url, HOSTS_PATH, HOSTS_SERVICE, "GetHostNumberOfEntries", {}, user, password, verify=verify)
    n = int(count.get("NewHostNumberOfEntries", "0") or 0)
    hosts = []
    for i in range(n):
        h = _soap_call(
            base_url,
            HOSTS_PATH,
            HOSTS_SERVICE,
            "GetGenericHostEntry",
            {"NewIndex": str(i)},
            user,
            password,
            verify=verify,
        )
        mac = h.get("NewMACAddress", "").lower()
        if mac or h.get("NewIPAddress"):
            hosts.append(
                {
                    "mac": mac,
                    "ip": h.get("NewIPAddress", ""),
                    "hostname": h.get("NewHostName", ""),
                    "active": h.get("NewActive", "0") == "1",
                    "type": h.get("NewInterfaceType", "") or h.get("NewX_AVM-DE_ConnectionType", ""),
                    "source": "tr064",
                }
            )
    return hosts


def _http_fallback_url(base_url: str) -> str | None:
    """https://… -> http://… (gleicher Host/Port), sonst None."""
    if base_url.startswith("https://"):
        return "http://" + base_url[len("https://") :]
    return None


def fetch_hosts_with_fallback(base_url: str, user: str, password: str, verify: bool = True) -> list[dict]:
    base_url = _normalize_base(base_url)
    try:
        return fetch_hosts(base_url, user, password, verify=verify)
    except TR064Error:
        fb = _http_fallback_url(base_url)
        if fb:
            return fetch_hosts(fb, user, password, verify=verify)
        raise


def fetch_wan_with_fallback(base_url: str, user: str, password: str, verify: bool = True) -> dict | None:
    base_url = _normalize_base(base_url)
    try:
        wan = fetch_wan(base_url, user, password, verify=verify)
        if wan is not None:
            return wan
        raise TR064Error("kein WAN-Service erreichbar")
    except TR064Error:
        fb = _http_fallback_url(base_url)
        if fb:
            return fetch_wan(fb, user, password, verify=verify)
        raise


def fetch_mesh_with_fallback(
    base_url: str, user: str, password: str, timeout: float = 10.0, verify: bool = True
) -> dict:
    base_url = _normalize_base(base_url)
    try:
        return fetch_mesh(base_url, user, password, timeout=timeout, verify=verify)
    except TR064Error:
        fb = _http_fallback_url(base_url)
        if fb:
            return fetch_mesh(fb, user, password, timeout=timeout, verify=verify)
        raise


def fetch_wan(base_url: str, user: str, password: str, verify: bool = True) -> dict | None:
    base_url = _normalize_base(base_url)
    for service, path in WAN_SERVICES:
        try:
            status = _soap_call(base_url, path, service, "GetStatusInfo", {}, user, password, verify=verify)
        except TR064Error:
            try:
                status = _soap_call(base_url, path, service, "GetInfo", {}, user, password, verify=verify)
            except TR064Error:
                continue
        wan_ip = ""
        with suppress(TR064Error):
            wan_ip = _soap_call(base_url, path, service, "GetExternalIPAddress", {}, user, password, verify=verify).get(
                "NewExternalIPAddress", ""
            )
        return {
            "wan_ip": wan_ip,
            "status": status.get("NewStatus", ""),
            "error": status.get("NewLastConnectionError", ""),
            "uptime": status.get("NewUptime", ""),
            "service": service,
        }
    return None


# --- Mesh-Topologie (X_AVM-DE_GetMeshListPath) ------------------------------------------------------------
# AVM liefert ueber TR-064 einen Pfad (mit Session-ID) zu einem JSON-Dokument mit Knoten, Schnittstellen und
# Verbindungen. Schema: https://fritz.support/resources/Mesh-Topology.pdf (je FRITZ!OS-Version ein JSON-Schema).
# Laut AVM kann die Topologie Schleifen enthalten (Powerline, WLAN-DBDC); die Eltern werden deshalb per
# Breitensuche ab dem Mesh-Master bestimmt.

MESH_MAX_BYTES = 5 * 1024 * 1024
_ZERO_MAC = "00:00:00:00:00:00"
_LINK_PRIO = {"LAN": 0, "WLAN": 1, "PLC": 2}


def _mesh_url(base_url: str, path: str) -> str:
    """Baut die Abruf-URL. Nur relative Pfade auf derselben Box, keine fremden Hosts (SSRF-Schutz)."""
    path = (path or "").strip()
    if not path.startswith("/") or path.startswith("//") or "://" in path or "\\" in path:
        raise TR064Error("Mesh: ungültiger Pfad in der Antwort")
    return base_url.rstrip("/") + path


def fetch_mesh(base_url: str, user: str, password: str, timeout: float = 10.0, verify: bool = True) -> dict:
    base_url = _normalize_base(base_url)
    res = _soap_call(base_url, HOSTS_PATH, HOSTS_SERVICE, "X_AVM-DE_GetMeshListPath", {}, user, password, verify=verify)
    url = _mesh_url(base_url, res.get("NewX_AVM-DE_MeshListPath", ""))
    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=False, verify=verify) as response:
            if response.status_code >= 400:
                # Die URL enthaelt eine Session-ID; sie wird nicht protokolliert.
                raise TR064Error(f"Mesh: HTTP {response.status_code}")
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MESH_MAX_BYTES:
                    raise TR064Error("Mesh: Antwort zu groß")
    except httpx.HTTPError as exc:
        raise TR064Error(f"Mesh: Verbindungsfehler ({type(exc).__name__})") from exc
    try:
        data = json.loads(bytes(body).decode("utf-8", "replace"))
    except ValueError as exc:
        raise TR064Error("Mesh: ungültiges JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise TR064Error("Mesh: keine Knotenliste im JSON")
    return data


def _mac(v) -> str:
    v = (v or "").strip().lower() if isinstance(v, str) else ""
    return "" if v in ("", _ZERO_MAC) else v


def _band(iface_name: str) -> str:
    n = (iface_name or "").upper()
    for tag, band in (("2G", "2,4 GHz"), ("5G", "5 GHz"), ("6G", "6 GHz")):
        if f":{tag}" in n:
            return band
    return ""


def parse_mesh(data: dict) -> dict:  # noqa: C901 - Zerlegung in W7 (Q-14)
    """Wertet das Mesh-JSON aus.

    Rueckgabe:
      parents: {mac: {"parent": mac, "conn": "lan"|"wlan"|"plc", "port": Schnittstelle am Elternknoten,
                      "band": "5 GHz"|..., "role": Rolle des Elternknotens}}
      nodes:   {mac: {"name", "role", "meshed", "macs"}}  (alle Knoten, macs = Geraete- und Schnittstellen-MACs)
      master:  MAC des Mesh-Masters oder ""
    """
    nodes = [n for n in data.get("nodes", []) if isinstance(n, dict) and n.get("uid")]
    iface = {}
    node_mac = {}
    node_macs = {}
    for n in nodes:
        macs = []
        dm = _mac(n.get("device_mac_address"))
        if dm:
            macs.append(dm)
        for i in n.get("node_interfaces") or []:
            if not isinstance(i, dict) or not i.get("uid"):
                continue
            iface[i["uid"]] = {"node": n["uid"], "name": i.get("name") or "", "type": (i.get("type") or "").upper()}
            im = _mac(i.get("mac_address"))
            if im and im not in macs:
                macs.append(im)
        if macs:
            node_mac[n["uid"]] = macs[0]
            node_macs[n["uid"]] = macs

    adj: dict[str, list] = {n["uid"]: [] for n in nodes}
    seen_links = set()
    for n in nodes:
        for i in n.get("node_interfaces") or []:
            for link in (i.get("node_links") or []) if isinstance(i, dict) else []:
                if not isinstance(link, dict) or link.get("state") != "CONNECTED":
                    continue
                uid = link.get("uid")
                if uid in seen_links:
                    continue
                seen_links.add(uid)
                a, b = link.get("node_1_uid"), link.get("node_2_uid")
                if a not in adj or b not in adj or a == b:
                    continue
                ltype = (link.get("type") or "").upper()
                ia, ib = link.get("node_interface_1_uid"), link.get("node_interface_2_uid")
                adj[a].append((b, ltype, ia))
                adj[b].append((a, ltype, ib))

    role = {n["uid"]: (n.get("mesh_role") or "unknown") for n in nodes}
    masters = [n["uid"] for n in nodes if role[n["uid"]] == "master"]
    root = masters[0] if masters else (max(adj, key=lambda u: len(adj[u])) if adj else "")

    parents = {}
    if root:
        from collections import deque

        visited = {root}
        queue = deque([root])
        while queue:
            cur = queue.popleft()
            # Mesh-Knoten (Repeater) zuerst, damit Clients nicht ueber einen Nachbar-Client "verbunden" werden
            for other, ltype, own_iface in sorted(
                adj[cur], key=lambda x: (role.get(x[0]) == "unknown", _LINK_PRIO.get(x[1], 9))
            ):
                if other in visited:
                    continue
                visited.add(other)
                queue.append(other)
                child_mac, parent_mac = node_mac.get(other), node_mac.get(cur)
                if not child_mac or not parent_mac:
                    continue
                port = iface.get(own_iface, {}).get("name", "")
                info = {
                    "parent": parent_mac,
                    "conn": ltype.lower() if ltype in _LINK_PRIO else "",
                    "port": port,
                    "band": _band(port) if ltype == "WLAN" else "",
                    "role": role.get(cur, "unknown"),
                }
                for m in node_macs.get(other, [child_mac]):
                    parents[m] = info

    out_nodes = {}
    for n in nodes:
        mac = node_mac.get(n["uid"])
        if mac:
            out_nodes[mac] = {
                "name": n.get("device_name") or "",
                "role": role[n["uid"]],
                "meshed": bool(n.get("is_meshed")),
                "macs": node_macs[n["uid"]],
            }
    return {"parents": parents, "nodes": out_nodes, "master": node_mac.get(root, "") if root else ""}
