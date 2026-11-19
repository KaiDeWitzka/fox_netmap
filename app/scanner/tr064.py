import xml.etree.ElementTree as ET

import httpx

HOSTS_SERVICE = "urn:dslforum-org:service:Hosts:1"
WANIP_SERVICE = "urn:dslforum-org:service:WANIPConnection:1"


def _soap_call(base_url: str, control_path: str, service: str, action: str, args: dict, user: str, password: str, timeout: float = 10.0) -> ET.Element:
    url = f"{base_url.rstrip('/')}{control_path}"
    body = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body>"
        f'<u:{action} xmlns:u="{service}">'
        + "".join(f"<{k}>{v}</{k}>" for k, v in args.items())
        + f"</u:{action}></s:Body></s:Envelope>"
    )
    headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{service}#{action}"'}
    auth = httpx.DigestAuth(user, password) if user else None
    response = httpx.post(url, content=body, headers=headers, auth=auth, timeout=timeout)
    response.raise_for_status()
    return ET.fromstring(response.text)


def _text(root: ET.Element, tag: str) -> str:
    el = root.find(f".//{{*}}{tag}")
    return el.text.strip() if el is not None and el.text else ""


def fetch_hosts(base_url: str, user: str, password: str) -> list[dict]:
    root = _soap_call(base_url, "/upnp/control/hosts", HOSTS_SERVICE, "GetHostList", {}, user, password)
    host_list = _text(root, "NewHostList")
    hosts = []
    macs = [m.strip().lower() for m in host_list.split(",") if m.strip()]
    for index, _mac in enumerate(macs):
        try:
            entry = _soap_call(
                base_url, "/upnp/control/hosts", HOSTS_SERVICE, "GetHostEntry", {"NewHostIndex": str(index)}, user, password
            )
        except Exception:
            continue
        hosts.append(
            {
                "mac": _text(entry, "NewMACAddress").lower() or _mac,
                "ip": _text(entry, "NewIPAddress"),
                "hostname": _text(entry, "NewHostName"),
                "active": _text(entry, "NewActive") == "1",
                "type": _text(entry, "NewX_AVM-DE_ConnectionType") or _text(entry, "NewInterfaceType"),
                "source": "tr064",
            }
        )
    return hosts


def fetch_wan_ip(base_url: str, user: str, password: str) -> str:
    try:
        root = _soap_call(base_url, "/upnp/control/wanipconn", WANIP_SERVICE, "GetExternalIPAddress", {}, user, password)
        return _text(root, "NewExternalIPAddress")
    except Exception:
        return ""
