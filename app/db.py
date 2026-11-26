import hashlib
import logging
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from . import dedupe

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
    created TEXT NOT NULL DEFAULT '',
    hint TEXT NOT NULL DEFAULT ''
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
    scanning INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_error_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    scan_started_at TEXT
);
CREATE TABLE IF NOT EXISTS oui_cache (
    prefix TEXT PRIMARY KEY,
    vendor TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_mac ON device_history(mac, ts);
CREATE INDEX IF NOT EXISTS idx_events_mac ON device_events(mac, ts);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def db_path(data_dir: str) -> str:
    return os.path.join(data_dir, "netmap.db")


def _write_probe(conn: sqlite3.Connection) -> None:
    """Echte Schreibprobe: BEGIN IMMEDIATE erzwingt Journal-Datei + Lock und schlaegt auf
    ungeeigneten Dateisystemen (virtiofs, NAS, read-only Mount) sofort mit I/O-Fehler fehl."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS fox_probe (x INTEGER)")
        conn.execute("INSERT INTO fox_probe (x) VALUES (1)")
    finally:
        conn.execute("ROLLBACK")


def _set_journal_mode(conn: sqlite3.Connection, path: str) -> None:
    """Journal-Modus waehlen: WAL bevorzugt (Web + Scanner schreiben nebenlaeufig).

    Auf manchen Bind-Mounts (Docker Desktop/virtiofs, NAS, manche Overlay-FS) schlaegt WAL
    mit sqlite3.OperationalError: disk I/O error fehl. Dann Fallback auf Rollback-Journal
    (DELETE). Erzwingen via NETZ_SQLITE_JOURNAL=wal|delete|auto (Default auto).
    """
    forced = os.getenv("NETZ_SQLITE_JOURNAL", "auto").strip().lower()
    if forced == "delete":
        conn.execute("PRAGMA journal_mode=DELETE")
        _write_probe(conn)
        return
    if forced == "wal":
        conn.execute("PRAGMA journal_mode=WAL")
        _write_probe(conn)
        return
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if str(mode).lower() != "wal":
            raise sqlite3.OperationalError(f"journal_mode nicht wal (ist: {mode})")
        _write_probe(conn)
        return
    except (sqlite3.OperationalError, OSError) as exc:
        log.warning("WAL nicht nutzbar fuer %s (%s) - Fallback journal_mode=DELETE", path, exc)
        with suppress(sqlite3.Error):
            conn.execute("ROLLBACK")
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        _write_probe(conn)
    except (sqlite3.OperationalError, OSError) as exc:
        directory = os.path.dirname(path) or "."
        raise RuntimeError(
            f"Datenbank-Verzeichnis nicht beschreibbar: {directory} ({exc}). "
            "Bitte Volume-Mount von /data pruefen (read-write, nicht ro) und freien Speicherplatz (df -h)."
        ) from exc


def connect(path: str) -> sqlite3.Connection:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # check_same_thread=False: FastAPI/anyio fuehrt synchrone Generator-Depends
    # (z. B. get_conn in api.py) mit Enter und Exit in unterschiedlichen Worker-Threads
    # aus - die Connection wird also in einem anderen Thread erzeugt als benutzt/
    # geschlossen. Pro Request gibt es genau eine Connection, die nur sequentiell
    # genutzt wird; konkurrierende Zugriffe (Web-Requests + Scanner-Prozess) regelt
    # SQLite ueber Datei-Locking + busy timeout (timeout=30). Daher ist das sicher.
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    _harden_file(path)  # S-17: 0600
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    # K-1: teure Schreibprobe (Journal-Modus + BEGIN IMMEDIATE) nur einmal je Prozess und Pfad,
    # nicht bei jedem connect() - sonst skaliert die Verbindungszeit mit jedem Healthcheck/Read
    if path not in _journal_probed:
        _set_journal_mode(conn, path)
        _journal_probed.add(path)
    return conn


_journal_probed: set[str] = set()


def connect_readonly(path: str) -> sqlite3.Connection:
    """Nur lesende Verbindung (z. B. Healthcheck): ohne Journal-Probe, nimmt keinen Schreib-Lock."""
    conn = sqlite3.connect(f"file:{quote(path)}?mode=ro", uri=True, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    # K-4: Web und Scanner koennen beim ersten Start dieselbe Migration fahren - "duplicate column
    # name" ist dann harmlos (der andere Prozess war schneller)
    try:
        _migrate_inner(conn)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc):
            log.info("Migration uebersprungen (anderer Prozess war schneller): %s", exc)
        else:
            raise


def _migrate_inner(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(devices)")}
    if "connection" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN connection TEXT NOT NULL DEFAULT ''")
        log.info("Migration: Spalte devices.connection ergaenzt")
    if "ip6" not in cols:
        conn.execute("ALTER TABLE devices ADD COLUMN ip6 TEXT NOT NULL DEFAULT ''")
        log.info("Migration: Spalte devices.ip6 ergaenzt")
    if "link_port" not in cols:
        # v1.6.0: Anschluss laut FRITZ!Box-Mesh, z. B. "LAN:1" oder "AP:5G:0"
        conn.execute("ALTER TABLE devices ADD COLUMN link_port TEXT NOT NULL DEFAULT ''")
        log.info("Migration: Spalte devices.link_port ergaenzt")
    _migrate_tokens(conn)
    if "category_reason" not in cols:
        # v1.6.0: Begruendung der automatischen Einordnung, z. B. "host:iphone" oder "port:62078"
        conn.execute("ALTER TABLE devices ADD COLUMN category_reason TEXT NOT NULL DEFAULT ''")
        log.info("Migration: Spalte devices.category_reason ergaenzt")
    if "vpn" not in cols:
        # VPN-Client (z. B. FRITZ!Box IPSec/WireGuard .201+): Kennzeichen, kein "neues Geraet"-Alarm
        conn.execute("ALTER TABLE devices ADD COLUMN vpn INTEGER NOT NULL DEFAULT 0")
        log.info("Migration: Spalte devices.vpn ergaenzt")
    if "room" not in cols:
        # v1.6.14: Raum/Ebene (frei vergebbar, z. B. "EG Wohnzimmer") fuer Karten-Gruppierung, Filter, Exporte
        conn.execute("ALTER TABLE devices ADD COLUMN room TEXT NOT NULL DEFAULT ''")
        log.info("Migration: Spalte devices.room ergaenzt")
    # W3: Scanzustand um Fehler-Spalten erweitert (SF-2, W4 nutzt sie)
    ss_cols = {r["name"] for r in conn.execute("PRAGMA table_info(scan_state)")}
    for col, decl in (
        ("last_error", "TEXT"),
        ("last_error_at", "TEXT"),
        ("consecutive_failures", "INTEGER NOT NULL DEFAULT 0"),
        ("scan_started_at", "TEXT"),
    ):
        if col not in ss_cols:
            conn.execute(f"ALTER TABLE scan_state ADD COLUMN {col} {decl}")
            log.info("Migration: Spalte scan_state.%s ergaenzt", col)


TOKEN_PREFIX = "sha256:"  # noqa: S105 - Konstantenpraefix, kein Passwort


def token_key(token: str) -> str:
    """Embed-Tokens werden nur als SHA-256 gespeichert (seit v1.6.0). Ein Salt ist bei 192 Bit Zufall nicht noetig."""
    return TOKEN_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _migrate_tokens(conn: sqlite3.Connection) -> None:
    tcols = {r["name"] for r in conn.execute("PRAGMA table_info(embed_tokens)")}
    if not tcols:
        return
    if "hint" not in tcols:
        conn.execute("ALTER TABLE embed_tokens ADD COLUMN hint TEXT NOT NULL DEFAULT ''")
    rows = conn.execute("SELECT token FROM embed_tokens WHERE token NOT LIKE 'sha256:%'").fetchall()
    for r in rows:
        conn.execute(
            "UPDATE embed_tokens SET token = ?, hint = ? WHERE token = ?",
            (token_key(r["token"]), r["token"][:6], r["token"]),
        )
    if rows:
        conn.commit()
        log.info("Migration: %s Embed-Tokens auf SHA-256 umgestellt", len(rows))


# Q-16: Alt-Aliase aus frueheren Versionen -> kanonische Schluessel (subnets, fritz_urls).
# Die env-Felder NETZ_SUBNET/NETZ_FRITZ_URL bleiben als deprecated kompatibel.
LEGACY_SETTING_ALIASES = (("subnet", "subnets"), ("fritz_url", "fritz_urls"))


def _migrate_setting_aliases(conn: sqlite3.Connection) -> None:
    for old, new in LEGACY_SETTING_ALIASES:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (old,)).fetchone()
        if row is None:
            continue
        if row["value"] == "":
            conn.execute("DELETE FROM settings WHERE key = ?", (old,))
            continue
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (new,)).fetchone()
        cur_val = cur["value"] if cur else ""
        # fritz_url wurde bisher zuerst angefragt; bei subnets gewinnt der kanonische Wert
        merged = row["value"] + "," + cur_val if new == "fritz_urls" and cur_val else cur_val or row["value"]
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (new, merged),
        )
        conn.execute("DELETE FROM settings WHERE key = ?", (old,))


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    _migrate_setting_aliases(conn)  # Q-16
    # C-2: leere Altzeilen loeschen (app.js sendete frueher jedes Feld; leer darf nicht die Umgebung ueberschreiben)
    conn.execute("DELETE FROM settings WHERE value = ''")
    conn.execute("INSERT OR IGNORE INTO scan_state (id, last_scan, next_scan, scanning) VALUES (1, NULL, NULL, 0)")
    # Schema/Migration/scan_state dauerhaft sichern, bevor die Dedupe fehlschlagen darf (K-12)
    conn.commit()
    try:
        removed = dedupe.merge_placeholders(conn)
    except sqlite3.OperationalError as exc:
        # Cleanup darf den Start nicht toeten (z. B. I/O-Fehler auf ungeeignetem Mount)
        log.error("Dedupe fehlgeschlagen (%s) - wird uebersprungen", exc)
        conn.rollback()  # K-12: keine halbe Zusammenfuehrung committen
        removed = 0
    conn.commit()
    if removed:
        log.info("Identitaet: %s doppelte Geraete (gleiche IP) zusammengefuehrt", removed)


def upsert_device(conn: sqlite3.Connection, dev: dict[str, Any], now: str) -> None:
    row = conn.execute("SELECT first_seen, category_override FROM devices WHERE mac = ?", (dev["mac"],)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO devices (mac, ip, ip6, vpn, hostname, vendor, category, status, subnet, source, connection, link_port, category_reason, note, first_seen, last_seen)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                dev["mac"],
                dev.get("ip", ""),
                dev.get("ip6", ""),
                1 if dev.get("vpn") else 0,
                dev.get("hostname", ""),
                dev.get("vendor", ""),
                dev.get("category", "Unbekannt"),
                dev.get("status", "online"),
                dev.get("subnet", ""),
                dev.get("source", ""),
                dev.get("connection", ""),
                dev.get("link_port", ""),
                dev.get("category_reason", ""),
                "",
                now,
                # C-5: last_seen nur setzen, wenn das Geraet online ist (sonst greift die Aufbewahrung nie)
                now if dev.get("status", "online") == "online" else "",
            ),
        )
    else:
        category = row["category_override"] or dev.get("category", "Unbekannt")
        # C-6: unvollstaendige Erkennung (leere Felder) darf Hostname/Hersteller/IPv6/IP nicht
        # loeschen - COALESCE behaelt den letzten bekannten Wert; ip erst recht (N-1)
        conn.execute(
            "UPDATE devices SET ip=COALESCE(NULLIF(?, ''), ip), ip6=COALESCE(NULLIF(?, ''), ip6), vpn=?, "
            "hostname=COALESCE(NULLIF(?, ''), hostname), vendor=COALESCE(NULLIF(?, ''), vendor), category=?, status=?, "
            "subnet=?, source=?, connection=?, link_port=?, category_reason=?, "
            # C-5: last_seen nur bei online aktualisieren, sonst Aufbewahrungsfrist nie erreicht
            "last_seen=CASE WHEN ? = 'online' THEN ? ELSE last_seen END WHERE mac=?",
            (
                dev.get("ip", ""),
                dev.get("ip6", ""),
                1 if dev.get("vpn") else 0,
                dev.get("hostname", ""),
                dev.get("vendor", ""),
                category,
                dev.get("status", "online"),
                dev.get("subnet", ""),
                dev.get("source", ""),
                dev.get("connection", ""),
                dev.get("link_port", ""),
                dev.get("category_reason", ""),
                dev.get("status", "online"),
                now,
                dev["mac"],
            ),
        )
    # N-1: sobald diese MAC eine IP meldet, wird die IP anderer (stale) Zeilen geleert
    dedupe.blank_stale_ip(conn, dev.get("ip", ""), dev["mac"])


def replace_ports(
    conn: sqlite3.Connection, mac: str, port_list: list[dict[str, Any]], now: str
) -> tuple[set[int], set[int]]:
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
    conn.execute("INSERT INTO device_events (ts, mac, type, detail) VALUES (?,?,?,?)", (now, mac, type_, detail))


def list_devices(
    conn: sqlite3.Connection,
    q: str = "",
    category: str = "",
    status: str = "",
    subnet: str = "",
    subnets: list[str] | None = None,
    categories: list[str] | None = None,
) -> list[dict[str, Any]]:
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
    if categories is not None:
        conds.append(f"d.category IN ({','.join('?' * len(categories))})" if categories else "1=0")
        params += categories
    elif category:
        conds.append("d.category = ?")
        params.append(category)
    if status:
        conds.append("d.status = ?")
        params.append(status)
    if subnets is not None:
        conds.append(f"d.subnet IN ({','.join('?' * len(subnets))})" if subnets else "1=0")
        params += subnets
    elif subnet:
        conds.append("d.subnet = ?")
        params.append(subnet)
    if conds:
        sql += " AND " + " AND ".join(conds)
    sql += " ORDER BY d.hostname COLLATE NOCASE, d.ip"
    return [dict(r) for r in conn.execute(sql, params)]


def get_device(conn: sqlite3.Connection, mac: str) -> dict[str, Any] | None:
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
    lay = conn.execute(
        "SELECT x, y, connected_to, connected_manual FROM device_layout WHERE mac = ?", (mac,)
    ).fetchone()
    out["layout"] = dict(lay) if lay else {}
    out["history"] = [
        dict(r)
        for r in conn.execute("SELECT ts, status FROM device_history WHERE mac = ? ORDER BY ts DESC LIMIT 100", (mac,))
    ]
    out["events"] = [
        dict(r)
        for r in conn.execute(
            "SELECT ts, type, detail FROM device_events WHERE mac = ? ORDER BY ts DESC LIMIT 50", (mac,)
        )
    ]
    return out


DEVICE_TABLES = ("device_ports", "device_layout", "device_history", "device_events", "devices")


def delete_device(conn: sqlite3.Connection, mac: str) -> None:
    """Löscht ein Gerät mit allen zugehörigen Daten (Ports, Layout, Verlauf, Ereignisse) - Art. 17 DSGVO.
    Manuelle Zuordnungen anderer Geräte zu diesem Gerät werden gelöst."""
    for table in DEVICE_TABLES:
        conn.execute(f"DELETE FROM {table} WHERE mac = ?", (mac,))  # noqa: S608 - Tabellenname aus interner Konstante
    conn.execute("UPDATE device_layout SET connected_to = NULL, connected_manual = 0 WHERE connected_to = ?", (mac,))


# --- HTTP-nahe Helfer (W7/Q-4): SQL gehoert nicht in die Router --------------------------------


def device_exists(conn: sqlite3.Connection, mac: str) -> bool:
    return conn.execute("SELECT 1 FROM devices WHERE mac = ?", (mac,)).fetchone() is not None


def list_rooms(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT room FROM devices WHERE room != '' ORDER BY room").fetchall()
    return [r["room"] for r in rows]


def update_device(
    conn: sqlite3.Connection,
    mac: str,
    *,
    category: str | None = None,
    note: str | None = None,
    room: str | None = None,
    connected_to: str | None = None,
    x: float | None = None,
    y: float | None = None,
) -> None:
    """Schreibt die per PATCH aenderbaren Felder spaltenweise (C-6: unberuehrte Spalten bleiben)."""
    if category is not None:
        conn.execute(
            "UPDATE devices SET category_override = ?, category = ? WHERE mac = ?",
            (category, category, mac),
        )
    if note is not None:
        conn.execute("UPDATE devices SET note = ? WHERE mac = ?", (note, mac))
    if room is not None:
        conn.execute("UPDATE devices SET room = ? WHERE mac = ?", (room.strip(), mac))
    if connected_to is not None:
        if connected_to == "":
            conn.execute("UPDATE device_layout SET connected_to = NULL, connected_manual = 0 WHERE mac = ?", (mac,))
        else:
            set_layout(conn, mac, connected_to=connected_to, connected_manual=1)
    if x is not None or y is not None:
        set_layout(conn, mac, x=x, y=y)


def reset_layout(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE device_layout SET x = NULL, y = NULL")


def parent_chain(conn: sqlite3.Connection, start: str, limit: int = 10000) -> list[str]:
    """Kette der connected_to-Verweise ab `start` (MACs; IPs werden ueber devices aufgeloest).
    Zyklussicher durch `seen` + Limit - Basis der Pruefung in services/devices.check_parent."""
    chain: list[str] = []
    seen: set[str] = set()
    cur: str | None = start
    while cur and cur not in seen and len(seen) < limit:
        seen.add(cur)
        chain.append(cur)
        row = conn.execute("SELECT connected_to FROM device_layout WHERE mac = ?", (cur,)).fetchone()
        nxt = row["connected_to"] if row else None
        if nxt and not device_exists(conn, nxt):
            by_ip = conn.execute("SELECT mac FROM devices WHERE ip = ?", (nxt,)).fetchone()
            nxt = by_ip["mac"] if by_ip else None
        cur = nxt
    return chain


def get_layout(conn: sqlite3.Connection, mac: str) -> dict[str, Any] | None:
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
    # K-6: spaltengenauer UPSERT - nur die uebergebenen Felder werden geschrieben, ein
    # konkurrierender Schreibzugriff auf eine andere Spalte kann nicht verloren gehen
    fields = {"x": x, "y": y, "connected_to": connected_to, "connected_manual": connected_manual}
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return
    cols = ", ".join(fields)
    marks = ", ".join("?" * len(fields))
    sets = ", ".join(f"{k}=excluded.{k}" for k in fields)
    conn.execute(
        f"INSERT INTO device_layout (mac, {cols}) VALUES (?, {marks}) "  # noqa: S608 - Spaltennamen aus internen fields-Schluesseln, Werte per Parameter
        f"ON CONFLICT(mac) DO UPDATE SET {sets}",
        (mac, *fields.values()),
    )


@contextmanager
def read_snapshot(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """K-10/K-11: gemeinsamer konsistenter Schnappschuss fuer mehrteilige Lesezugriffe
    (Exporte, Detailansicht) - Daten mischen nicht vor und nach einem Scan-Commit."""
    conn.execute("BEGIN")
    try:
        yield conn
    finally:
        with suppress(sqlite3.Error):
            conn.rollback()


def get_scan_state(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM scan_state WHERE id = 1").fetchone()
    return dict(row) if row else {"last_scan": None, "next_scan": None, "scanning": 0}


def set_scan_state(conn: sqlite3.Connection, **fields: Any) -> None:
    keys = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE scan_state SET {keys} WHERE id = 1", tuple(fields.values()))  # noqa: S608 - Spalten aus internen **fields-Schluesseln, Werte per Parameter


def get_oui_cache(conn: sqlite3.Connection, prefix: str) -> str | None:
    r = conn.execute("SELECT vendor FROM oui_cache WHERE prefix = ?", (prefix,)).fetchone()
    return r["vendor"] if r else None


def set_oui_cache(conn: sqlite3.Connection, prefix: str, vendor: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO oui_cache (prefix, vendor, fetched_at) VALUES (?, ?, ?)",
        (prefix, vendor, utcnow()),
    )
    conn.commit()  # K-2: Transaktion sofort beenden, nicht bis apply_scan offen halten


def _harden_file(path: str) -> None:
    """S-17: DB und Log nur fuer den Besitzer lesbar (Bestandsschutz beim Start)."""
    with suppress(OSError):
        os.chmod(path, 0o600)


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def delete_setting(conn: sqlite3.Connection, key: str) -> None:
    """S-8: explizites Loeschen eines gespeicherten Werts (Zeile entfernen, nicht leeren String -
    C-2: ein gespeicherter leerer String wuerde die Umgebung ueberschreiben)."""
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))


def get_user(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
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
        "INSERT INTO embed_tokens (token, expires, subnets, categories, created, hint) VALUES (?,?,?,?,?,?)",
        (token_key(token), expires, subnets, categories, now, token[:6]),
    )


def get_valid_token(conn: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    if not token:
        return None
    row = conn.execute("SELECT * FROM embed_tokens WHERE token = ?", (token_key(token),)).fetchone()
    if row is None:
        return None
    if row["expires"]:
        try:
            if datetime.fromisoformat(row["expires"]) < datetime.now(UTC):
                return None
        except ValueError:
            return None
    return dict(row)


def list_tokens(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Ohne Token im Klartext: `id` ist der Hash (zum Loeschen), `hint` die ersten 6 Zeichen zur Wiedererkennung."""
    rows = conn.execute(
        "SELECT token, hint, expires, subnets, categories, created FROM embed_tokens ORDER BY created DESC"
    )
    return [
        {
            "id": r["token"][len(TOKEN_PREFIX) :],
            "hint": r["hint"],
            "expires": r["expires"],
            "subnets": r["subnets"],
            "categories": r["categories"],
            "created": r["created"],
        }
        for r in rows
    ]


def delete_token(conn: sqlite3.Connection, ident: str) -> None:
    """Loeschen ueber die Listen-ID (Hash) oder, fuer bestehende Skripte, ueber das Token selbst."""
    conn.execute("DELETE FROM embed_tokens WHERE token IN (?, ?)", (TOKEN_PREFIX + ident, token_key(ident)))


def trim_events(conn: sqlite3.Connection, days: int) -> int:
    """Ereignisse aelter als `days` Tage loeschen (0 = nie). Gilt auch fuer aktive Geraete (seit v1.6.0)."""
    if days <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
    cur = conn.execute("DELETE FROM device_events WHERE ts < ?", (cutoff,))
    conn.commit()
    return cur.rowcount or 0


def trim_history(conn: sqlite3.Connection, hours: int, now: str) -> None:
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM device_history WHERE ts < ?", (cutoff,))
    conn.commit()
