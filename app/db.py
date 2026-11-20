import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

log = logging.getLogger("fox_netmap")

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    mac TEXT PRIMARY KEY,
    ip TEXT NOT NULL DEFAULT '',
    hostname TEXT NOT NULL DEFAULT '',
    vendor TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'Unbekannt',
    category_override TEXT,
    status TEXT NOT NULL DEFAULT 'offline',
    subnet TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    first_seen TEXT NOT NULL DEFAULT '',
    last_seen TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS device_ports (
    mac TEXT NOT NULL,
    port INTEGER NOT NULL,
    proto TEXT NOT NULL DEFAULT 'tcp',
    service TEXT NOT NULL DEFAULT '',
    scan_ts TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (mac, port, proto)
);
CREATE TABLE IF NOT EXISTS device_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mac TEXT NOT NULL,
    ts TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS device_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mac TEXT NOT NULL,
    type TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS device_layout (
    mac TEXT PRIMARY KEY,
    x REAL,
    y REAL,
    connected_to TEXT,
    connected_manual INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS embed_tokens (
    token TEXT PRIMARY KEY,
    expires TEXT,
    subnets TEXT NOT NULL DEFAULT '',
    categories TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    pass_hash TEXT NOT NULL,
    created TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS scan_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_scan TEXT,
    next_scan TEXT,
    scanning INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_history_mac ON device_history(mac, ts);
CREATE INDEX IF NOT EXISTS idx_events_mac ON device_events(mac, ts);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path(data_dir: str) -> str:
    return os.path.join(data_dir, "netmap.db")


def connect(path: str) -> sqlite3.Connection:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO scan_state (id, last_scan, next_scan, scanning) VALUES (1, NULL, NULL, 0)"
    )
    removed = dedupe_devices_by_ip(conn)
    conn.commit()
    if removed:
        log.info("Identitaet: %s doppelte Geraete (gleiche IP) zusammengefuehrt", removed)


def dedupe_devices_by_ip(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT mac, ip, status, last_seen, source FROM devices WHERE ip != '' ORDER BY ip, last_seen DESC"
    ).fetchall()
    by_ip: dict[str, list[dict]] = {}
    for r in rows:
        by_ip.setdefault(r["ip"], []).append(dict(r))
    removed = 0
    for group in by_ip.values():
        if len(group) < 2:
            continue
        real = [g for g in group if not g["mac"].startswith("ip:")]
        keep = max(real or group, key=lambda g: g["last_seen"])
        keep_mac = keep["mac"]
        for g in group:
            if g["mac"] == keep_mac:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO device_ports (mac, port, proto, service, scan_ts) "
                "SELECT ?, port, proto, service, scan_ts FROM device_ports WHERE mac = ?",
                (keep_mac, g["mac"]),
            )
            conn.execute("DELETE FROM device_ports WHERE mac = ?", (g["mac"],))
            if conn.execute("SELECT 1 FROM device_layout WHERE mac = ?", (keep_mac,)).fetchone() is None:
                conn.execute("UPDATE device_layout SET mac = ? WHERE mac = ?", (keep_mac, g["mac"]))
            else:
                conn.execute("DELETE FROM device_layout WHERE mac = ?", (g["mac"],))
            conn.execute("UPDATE device_history SET mac = ? WHERE mac = ?", (keep_mac, g["mac"]))
            conn.execute("UPDATE device_events SET mac = ? WHERE mac = ?", (keep_mac, g["mac"]))
            conn.execute("DELETE FROM devices WHERE mac = ?", (g["mac"],))
            removed += 1
        sources = sorted({s for g in group for s in g["source"].split(",") if s})
        status = "online" if any(g["status"] == "online" for g in group) else "offline"
        last_seen = max(g["last_seen"] for g in group)
        conn.execute(
            "UPDATE devices SET source = ?, status = ?, last_seen = ? WHERE mac = ?",
            (",".join(sources), status, last_seen, keep_mac),
        )
    return removed


def upsert_device(conn: sqlite3.Connection, dev: dict, now: str) -> None:
    row = conn.execute(
        "SELECT first_seen, category_override FROM devices WHERE mac = ?", (dev["mac"],)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO devices (mac, ip, hostname, vendor, category, status, subnet, source, note, first_seen, last_seen)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                dev["mac"],
                dev.get("ip", ""),
                dev.get("hostname", ""),
                dev.get("vendor", ""),
                dev.get("category", "Unbekannt"),
                dev.get("status", "online"),
                dev.get("subnet", ""),
                dev.get("source", ""),
                "",
                now,
                now,
            ),
        )
    else:
        category = row["category_override"] or dev.get("category", "Unbekannt")
        conn.execute(
            "UPDATE devices SET ip=?, hostname=?, vendor=?, category=?, status=?, subnet=?, source=?, last_seen=? WHERE mac=?",
            (
                dev.get("ip", ""),
                dev.get("hostname", ""),
                dev.get("vendor", ""),
                category,
                dev.get("status", "online"),
                dev.get("subnet", ""),
                dev.get("source", ""),
                now,
                dev["mac"],
            ),
        )


def replace_ports(conn: sqlite3.Connection, mac: str, port_list: list[dict], now: str) -> tuple[set, set]:
    old = {r["port"] for r in conn.execute("SELECT port FROM device_ports WHERE mac = ?", (mac,))}
    conn.execute("DELETE FROM device_ports WHERE mac = ?", (mac,))
    for p in port_list:
        conn.execute(
            "INSERT OR REPLACE INTO device_ports (mac, port, proto, service, scan_ts) VALUES (?,?,?,?,?)",
            (mac, p["port"], p.get("proto", "tcp"), p.get("service", ""), now),
        )
    new = {p["port"] for p in port_list}
    return old, new


def add_history(conn: sqlite3.Connection, mac: str, status: str, now: str) -> None:
    conn.execute("INSERT INTO device_history (mac, ts, status) VALUES (?,?,?)", (mac, now, status))


def add_event(conn: sqlite3.Connection, mac: str, type_: str, detail: str, now: str) -> None:
    conn.execute(
        "INSERT INTO device_events (ts, mac, type, detail) VALUES (?,?,?,?)", (now, mac, type_, detail)
    )


def list_devices(
    conn: sqlite3.Connection,
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
) -> list[dict]:
    sql = (
        "SELECT d.*, "
        "(SELECT COUNT(*) FROM device_ports p WHERE p.mac = d.mac) AS port_count, "
        "(SELECT GROUP_CONCAT(port, ';') FROM (SELECT port FROM device_ports p WHERE p.mac = d.mac ORDER BY port)) AS ports_str, "
        "lo.x, lo.y, lo.connected_to "
        "FROM devices d LEFT JOIN device_layout lo ON lo.mac = d.mac WHERE 1=1"
    )
    conds, params = [], []
    if q:
        conds.append("(d.ip LIKE ? OR d.hostname LIKE ? OR d.mac LIKE ? OR d.vendor LIKE ? OR d.note LIKE ?)")
        like = f"%{q}%"
        params += [like] * 5
    if category:
        conds.append("d.category = ?")
        params.append(category)
    if status:
        conds.append("d.status = ?")
        params.append(status)
    if subnet:
        conds.append("d.subnet = ?")
        params.append(subnet)
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY d.hostname COLLATE NOCASE, d.ip"
    return [dict(r) for r in conn.execute(sql, params)]


def get_device(conn: sqlite3.Connection, mac: str) -> dict | None:
    row = conn.execute("SELECT * FROM devices WHERE mac = ?", (mac,)).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["ports"] = [
        dict(r)
        for r in conn.execute(
            "SELECT port, proto, service, scan_ts FROM device_ports WHERE mac = ? ORDER BY port", (mac,)
        )
    ]
    lay = conn.execute("SELECT x, y, connected_to, connected_manual FROM device_layout WHERE mac = ?", (mac,)).fetchone()
    out["layout"] = dict(lay) if lay else {}
    out["history"] = [
        dict(r)
        for r in conn.execute(
            "SELECT ts, status FROM device_history WHERE mac = ? ORDER BY ts DESC LIMIT 100", (mac,)
        )
    ]
    out["events"] = [
        dict(r)
        for r in conn.execute(
            "SELECT ts, type, detail FROM device_events WHERE mac = ? ORDER BY ts DESC LIMIT 50", (mac,)
        )
    ]
    return out


def get_layout(conn: sqlite3.Connection, mac: str) -> dict | None:
    row = conn.execute("SELECT * FROM device_layout WHERE mac = ?", (mac,)).fetchone()
    return dict(row) if row else None


def set_layout(
    conn: sqlite3.Connection,
    mac: str,
    x: float | None = None,
    y: float | None = None,
    connected_to: str | None = None,
    connected_manual: int | None = None,
) -> None:
    row = get_layout(conn, mac)
    x = x if x is not None else (row["x"] if row else None)
    y = y if y is not None else (row["y"] if row else None)
    ct = connected_to if connected_to is not None else (row["connected_to"] if row else None)
    cm = connected_manual if connected_manual is not None else (row["connected_manual"] if row else 0)
    conn.execute(
        "INSERT INTO device_layout (mac, x, y, connected_to, connected_manual) VALUES (?,?,?,?,?) "
        "ON CONFLICT(mac) DO UPDATE SET x=excluded.x, y=excluded.y, connected_to=excluded.connected_to, connected_manual=excluded.connected_manual",
        (mac, x, y, ct, cm),
    )


def get_scan_state(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM scan_state WHERE id = 1").fetchone()
    return dict(row) if row else {"last_scan": None, "next_scan": None, "scanning": 0}


def set_scan_state(conn: sqlite3.Connection, **fields) -> None:
    keys = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE scan_state SET {keys} WHERE id = 1", tuple(fields.values()))


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_user(conn: sqlite3.Connection, username: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def ensure_user(conn: sqlite3.Connection, username: str, pass_hash: str, now: str) -> None:
    conn.execute(
        "INSERT INTO users (username, pass_hash, created) VALUES (?,?,?) "
        "ON CONFLICT(username) DO UPDATE SET pass_hash=excluded.pass_hash",
        (username, pass_hash, now),
    )


def create_token(conn: sqlite3.Connection, token: str, expires: str, subnets: str, categories: str, now: str) -> None:
    conn.execute(
        "INSERT INTO embed_tokens (token, expires, subnets, categories, created) VALUES (?,?,?,?,?)",
        (token, expires, subnets, categories, now),
    )


def get_valid_token(conn: sqlite3.Connection, token: str) -> dict | None:
    row = conn.execute("SELECT * FROM embed_tokens WHERE token = ?", (token,)).fetchone()
    if row is None:
        return None
    if row["expires"]:
        try:
            if datetime.fromisoformat(row["expires"]) < datetime.now(timezone.utc):
                return None
        except ValueError:
            return None
    return dict(row)


def list_tokens(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT token, expires, subnets, categories, created FROM embed_tokens ORDER BY created DESC")]


def delete_token(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM embed_tokens WHERE token = ?", (token,))


def trim_history(conn: sqlite3.Connection, hours: int, now: str) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM device_history WHERE ts < ?", (cutoff,))
    conn.commit()
