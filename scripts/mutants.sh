#!/usr/bin/env bash
# Mutations-Kill-Liste (docs/produktionsreife/UEBERGABE.md Abschnitt 7.6, W6):
# Jeder Mutant wird einzeln auf eine Kopie des Repos angewendet und gegen die
# zugehoerigen Tests gejagt. Jeder Mutant muss mindestens einen Test rot werden
# lassen ("killed"); ein Ueberlebender ("SURVIVED") beendet den Lauf mit Exit 1.
#
# Nutzung: bash scripts/mutants.sh [Mutant ...]   (ohne Argumente: alle)
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 - "$REPO" "$@" <<'PY'
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
ONLY = set(sys.argv[2:])

# name -> (Datei, [(alt, neu), ...], pytest-Ziele, Timeout s)
MUTANTS = {
    "M10": (
        "app/auth.py",
        [("    return entry[1] > now", "    return True  # M10: Sitzungsablauf ignoriert")],
        ["tests/test_session_expiry.py"],
        120,
    ),
    "B2": (
        "app/routers/devices.py",
        [("    body: BulkConnect, request: Request, conn: sqlite3.Connection = Depends(get_conn), _: None = Depends(require_auth)",
          "    body: BulkConnect, request: Request, conn: sqlite3.Connection = Depends(get_conn)  # B2: require_auth entfernt")],
        # Middleware allein genuegt nicht als Nachweis -> Struktur-Test in test_public_surface.py
        ["tests/test_public_surface.py"],
        120,
    ),
    "B3": (
        "app/routers/devices.py",
        [("    conn: sqlite3.Connection = Depends(get_conn),\n    _: None = Depends(require_auth),\n) -> DeviceDetail:",
          "    conn: sqlite3.Connection = Depends(get_conn),\n) -> DeviceDetail:  # B3: require_auth entfernt")],
        ["tests/test_public_surface.py"],
        120,
    ),
    "M11": (
        "app/services/authz.py",
        [('    if subs and dev.get("subnet", "") not in subs:',
          '    if False and subs and dev.get("subnet", "") not in subs:  # M11: Subnetz-Scope des Tokens ignoriert')],
        ["tests/test_token_scope.py"],
        120,
    ),
    "R1": (
        "app/scanner/run.py",
        [("\"SELECT mac FROM devices WHERE status = 'offline' AND COALESCE(NULLIF(last_seen, ''), first_seen) < ?\"",
          "\"SELECT mac FROM devices WHERE COALESCE(NULLIF(last_seen, ''), first_seen) < ?\"  # R1: Statusfilter weg")],
        ["tests/test_retention.py"],
        120,
    ),
    "R2": (
        "app/scanner/run.py",
        [("timedelta(days=days)", "timedelta(hours=days)  # R2: Stunden statt Tage")],
        ["tests/test_retention.py"],
        120,
    ),
    "R3": (
        "app/exporters.py",
        [("def auto_export(settings: Settings, conn: sqlite3.Connection) -> list[str]:",
          "def auto_export(settings: Settings, conn: sqlite3.Connection) -> list[str]:\n    return []  # R3: schreibt nichts")],
        ["tests/test_auto_export.py"],
        120,
    ),
    "F4": (
        "app/scanner/run.py",
        [("        notify_ok = notify.notify_new_devices(settings, alarm_list)",
          "        notify_ok = True  # F4: Notify wird nie aufgerufen")],
        ["tests/test_scanner_loop.py"],
        120,
    ),
    # F5: scanning=0 an ALLEN drei Stellen in run_once weg - einzeln ist jede Stelle redundant
    "F5": (
        "app/scanner/run.py",
        [
            ("    db.set_scan_state(conn, last_scan=now, scanning=0)",
             "    db.set_scan_state(conn, last_scan=now)  # F5"),
            ("                conn,\n                scanning=0,\n                last_error=str(exc)[:500],",
             "                conn,\n                last_error=str(exc)[:500],  # F5"),
            ("        db.set_scan_state(conn, scanning=0, next_scan=next_scan)",
             "        db.set_scan_state(conn, next_scan=next_scan)  # F5"),
        ],
        ["tests/test_scan_state.py", "tests/test_e2e_scan_api.py"],
        120,
    ),
    "F6": (
        "app/scanner/run.py",
        [('alarm_list = [d for d in summary["new_online"] if not d.get("vpn") and not notify.is_whitelisted(settings, d)]',
          'alarm_list = [d for d in summary["new_online"] if not notify.is_whitelisted(settings, d)]  # F6: VPN loest Alarm aus')],
        ["tests/test_scanner_loop.py"],
        120,
    ),
    "F7": (
        "app/scanner/run.py",
        [("            summary = run_once(eff, conn)",
          '            summary = {"seen": 0, "new": 0, "new_devices": [], "new_online": [], "removed": 0}  # F7: run_once nie aufgerufen')],
        ["tests/test_scanner_loop.py"],
        240,  # der SIGTERM-Test haengt ohne run_once -> Timeout zaehlt als Kill
    ),
}

IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".hypothesis",
    ".ruff_cache", ".mypy_cache", "htmlcov", ".coverage", ".coverage.*",
)


def main() -> int:
    names = [n for n in MUTANTS if not ONLY or n in ONLY]
    if ONLY:
        missing = ONLY - set(MUTANTS)
        if missing:
            print(f"unbekannte Mutanten: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    print(f"Mutationslauf ueber {len(names)} Mutanten (Repo: {REPO})\n")
    survived = []
    with tempfile.TemporaryDirectory(prefix="fox-mutants-") as tmp:
        for name in names:
            rel, edits, targets, timeout = MUTANTS[name]
            dst = Path(tmp) / name
            shutil.copytree(REPO, dst, symlinks=True, ignore=IGNORE)
            f = dst / rel
            text = f.read_text(encoding="utf-8")
            ok = True
            for old, new in edits:
                count = text.count(old)
                if count != 1:
                    print(f"{name:5s} PATCH-FEHLER: '{old[:60]}...' kommt {count}x in {rel} vor")
                    ok = False
                    break
                text = text.replace(old, new)
            if not ok:
                survived.append(name)
                continue
            f.write_text(text, encoding="utf-8")
            py = dst / ".venv" / "bin" / "python"
            cmd = [str(py) if py.exists() else sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets]
            try:
                proc = subprocess.run(cmd, cwd=dst, capture_output=True, text=True, timeout=timeout)
                rc, tail = proc.returncode, proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
            except subprocess.TimeoutExpired:
                rc, tail = -9, f"Timeout nach {timeout}s (haengt -> Kill)"
            status = "killed" if rc != 0 else "SURVIVED"
            if rc == 0:
                survived.append(name)
            print(f"{name:5s} {rel:22s} {' '.join(targets):40s} {status:9s} {tail}")
    print()
    if survived:
        print(f"UEBERLEBENDE: {', '.join(survived)}")
        return 1
    print(f"ALLE {len(names)} MUTANTEN GETOETET")
    return 0


sys.exit(main())
PY
