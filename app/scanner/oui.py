import os
import re

LINE_RE = re.compile(r"^([0-9A-Fa-f]{2})[-:]([0-9A-Fa-f]{2})[-:]([0-9A-Fa-f]{2})\s+\(hex\)\s+(.+)$")


def normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").replace(".", ":").lower()


def oui_prefix(mac: str) -> str:
    return normalize_mac(mac).replace(":", "")[:6].upper()


def load_oui(path: str) -> dict[str, str]:
    table: dict[str, str] = {}
    if not path or not os.path.exists(path):
        return table
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = LINE_RE.match(line.strip())
            if m:
                table[(m.group(1) + m.group(2) + m.group(3)).upper()] = m.group(4).strip()
    return table


def lookup(mac: str, table: dict[str, str]) -> str:
    return table.get(oui_prefix(mac), "")
