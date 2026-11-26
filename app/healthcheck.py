"""Container-Healthcheck (`python -m app health`), genutzt vom HEALTHCHECK im Dockerfile.

Erkennt die Rolle am Hauptprozess (PID 1) bzw. an NETZ_ROLE:
- web:     GET http://127.0.0.1:<port>/api/health muss 200 liefern.
- scanner: Die Scan-Schleife darf nicht hängen. Ist kein Scan aktiv und der geplante nächste Scan
           länger als GRACE Sekunden überfällig, gilt der Container als ungesund.
Exit-Code 0 = gesund, 1 = ungesund.
"""

import os
import sys
import urllib.request
from datetime import UTC, datetime

GRACE = 300


def detect_role() -> str:
    role = os.environ.get("NETZ_ROLE", "").strip().lower()
    if role in ("web", "scanner"):
        return role
    try:
        with open("/proc/1/cmdline", "rb") as fh:
            args = fh.read().split(b"\0")
        return "scanner" if b"scanner" in args else "web"
    except OSError:
        return "web"


def check_web(port: int) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=4) as r:
            return r.status == 200, f"HTTP {r.status}"
    except Exception as exc:  # noqa: BLE001
        return False, f"web nicht erreichbar: {exc}"


def check_scanner(data_dir: str, now: datetime | None = None) -> tuple[bool, str]:
    from . import db

    path = db.db_path(data_dir)
    if not os.path.exists(path):
        return True, "Datenbank noch nicht angelegt (Start)"
    conn = db.connect(path)
    try:
        state = db.get_scan_state(conn)
    finally:
        conn.close()
    if state.get("scanning"):
        return True, "Scan laeuft"
    nxt = state.get("next_scan")
    if not nxt:
        return True, "noch kein Scan geplant"
    now = now or datetime.now(UTC)
    overdue = (now - datetime.fromisoformat(nxt)).total_seconds()
    if overdue > GRACE:
        return False, f"Scan-Schleife haengt: naechster Scan seit {int(overdue)} s ueberfaellig"
    return True, "ok"


def drop_root() -> None:
    """Docker führt HEALTHCHECK als root aus. Vor dem DB-Zugriff auf den App-Benutzer wechseln,
    damit SQLite keine root-eigenen -wal/-shm-Dateien anlegt, die die App dann nicht öffnen kann."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        os.setgid(int(os.environ.get("APP_GID", "10001")))
        os.setuid(int(os.environ.get("APP_UID", "10001")))


def main() -> int:
    from .config import get_settings

    drop_root()
    settings = get_settings()
    role = detect_role()
    ok, msg = check_scanner(settings.data_dir) if role == "scanner" else check_web(settings.port)
    print(f"{role}: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
