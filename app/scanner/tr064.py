import xml.etree.ElementTree as ET

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


def _soap_call(base_url: str, path: str, service: str, action: str, args: dict, user: str, password: str, timeout: float = 8.0) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": f'"{service}#{action}"'}
    auth = httpx.DigestAuth(user, password) if user else None
    try:
        response = httpx.post(url, content=_soap_body(service, action, args), headers=headers, auth=auth, timeout=timeout)
    except httpx.HTTPError as exc:
        raise TR064Error(f"{action} -> {url}: Verbindungsfehler: {exc}") from exc
    if response.status_code >= 400:
        try:
            fault = _soap_fault_root(ET.fromstring(response.text))
        except ET.ParseError:
            fault = ""
        raise TR064Error(f"{action} -> HTTP {response.status_code}" + (f" ({fault})" if fault else ""))
    try:
        root = ET.fromstring(response.text)
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


def fetch_hosts(base_url: str, user: str, password: str) -> list[dict]:
    base_url = _normalize_base(base_url)
    count = _soap_call(base_url, HOSTS_PATH, HOSTS_SERVICE, "GetHostNumberOfEntries", {}, user, password)
    n = int(count.get("NewHostNumberOfEntries", "0") or 0)
    hosts = []
    for i in range(n):
        h = _soap_call(base_url, HOSTS_PATH, HOSTS_SERVICE, "GetGenericHostEntry", {"NewIndex": str(i)}, user, password)
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


def fetch_hosts_with_fallback(base_url: str, user: str, password: str) -> list[dict]:
    base_url = _normalize_base(base_url)
    try:
        return fetch_hosts(base_url, user, password)
    except TR064Error:
        if base_url.startswith("https://"):
            return fetch_hosts("http://" + base_url[len("https://"):], user, password)
        raise


def fetch_wan(base_url: str, user: str, password: str) -> dict | None:
    base_url = _normalize_base(base_url)
    for service, path in WAN_SERVICES:
        try:
            status = _soap_call(base_url, path, service, "GetStatusInfo", {}, user, password)
        except TR064Error:
            try:
                status = _soap_call(base_url, path, service, "GetInfo", {}, user, password)
            except TR064Error:
                continue
        wan_ip = ""
        try:
            wan_ip = _soap_call(base_url, path, service, "GetExternalIPAddress", {}, user, password).get("NewExternalIPAddress", "")
        except TR064Error:
            pass
        return {
            "wan_ip": wan_ip,
            "status": status.get("NewStatus", ""),
            "error": status.get("NewLastConnectionError", ""),
            "uptime": status.get("NewUptime", ""),
            "service": service,
        }
    return None
