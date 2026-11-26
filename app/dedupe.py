"""Zusammenfuehrung von Geraete-Eintraegen (K-3/C-14/N-1, Entscheidung E-1 = B).

Nur `ip:<adresse>`-Platzhalter werden in eine echte MAC derselben IP eingemischt (Altlasten
aus der Zeit vor der MAC-Erkennung). Zwei echte MACs auf derselben IP werden NIEMALS
zusammengefuehrt - sonst wuerde ein Geraet samt Notiz, Raum, Layout und Verlauf geloescht,
sobald ein anderes Geraet seine IP uebernimmt. Stattdessen wird die alte IP des aelteren
Offline-Geraets geleert (blank_stale_ip).
"""

import sqlite3

# Tabellen, deren Zeilen beim Zusammenfuehren umgebucht werden
DEVICE_CHILD_TABLES = ("device_ports", "device_layout", "device_history", "device_events")


def merge_placeholders(conn: sqlite3.Connection) -> int:
    """Mischt jeden `ip:`-Platzhalter in die echte MAC derselben IP ein. Liefert die Anzahl."""
    rows = conn.execute(
        "SELECT mac, ip, source, status, last_seen FROM devices WHERE mac LIKE 'ip:%' AND ip != ''"
    ).fetchall()
    moved = 0
    for r in rows:
        real = conn.execute(
            "SELECT mac, source, status, last_seen FROM devices WHERE ip = ? AND mac NOT LIKE 'ip:%'"
            " ORDER BY last_seen DESC LIMIT 1",
            (r["ip"],),
        ).fetchone()
        if real is None:
            continue
        real_mac = real["mac"]
        for table in DEVICE_CHILD_TABLES:
            if (
                table == "device_layout"
                and conn.execute("SELECT 1 FROM device_layout WHERE mac = ?", (real_mac,)).fetchone()
            ):
                # echte MAC hat bereits ein Layout -> Platzhalter-Layout verwerfen
                conn.execute("DELETE FROM device_layout WHERE mac = ?", (r["mac"],))
            else:
                conn.execute(f"UPDATE {table} SET mac = ? WHERE mac = ?", (real_mac, r["mac"]))  # noqa: S608 - Tabellenname aus interner Konstante DEVICE_CHILD_TABLES
        # devices-Zeile der echten MAC aktualisieren: Quellen vereint, online gewinnt, juengster Stand
        sources = {s for s in (real["source"] or "").split(",") if s}
        sources |= {s for s in (r["source"] or "").split(",") if s}
        status = "online" if "online" in (real["status"], r["status"]) else "offline"
        last_seen = max(real["last_seen"] or "", r["last_seen"] or "")
        conn.execute(
            "UPDATE devices SET source = ?, status = ?, last_seen = ? WHERE mac = ?",
            (",".join(sorted(sources)), status, last_seen, real_mac),
        )
        conn.execute("DELETE FROM devices WHERE mac = ?", (r["mac"],))
        moved += 1
    return moved


def blank_stale_ip(conn: sqlite3.Connection, ip: str, keep_mac: str) -> int:
    """Leert die IP aller anderen Zeilen, sobald `keep_mac` diese IP meldet (N-1).

    Verhindert, dass ein Treffer ohne MAC (ARP-lose Funde) einem Offline-Geraet zugeordnet
    wird und dessen Zeile ueberschreibt.
    """
    if not ip:
        return 0
    cur = conn.execute("UPDATE devices SET ip = '' WHERE ip = ? AND mac != ?", (ip, keep_mac))
    return cur.rowcount
