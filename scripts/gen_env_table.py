"""Generiert die Umgebungsvariablen-Referenz in docs/05-betrieb.md (W8/D-4).

Wahrheitsquelle: app/settings_schema.py (FIELDS) + Defaults aus app/config.py (Settings).
Env-only-Variablen ohne Schema-Eintrag (z. B. NETZ_SQLITE_JOURNAL) kommen aus .env.example.
Aufruf: uv run python scripts/gen_env_table.py [--check]  (--check: exit 1 bei Drift, fuer tests/test_docs.py)
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.config import Settings  # noqa: E402
from app.settings_schema import FIELDS  # noqa: E402

DOC = REPO / "docs" / "05-betrieb.md"
START = "<!-- GEN:ENV-TABLE:START -->"
END = "<!-- GEN:ENV-TABLE:END -->"

ALIAS_NOTES = {
    "subnet": "Alt-Alias von `NETZ_SUBNETS`; DB-Zeilen werden beim Start migriert (Q-16)",
    "fritz_url": "Alt-Alias von `NETZ_FRITZ_URLS`; DB-Zeilen werden beim Start migriert (Q-16)",
}
SPECIAL_NOTES = {
    "auth_enabled": "immer Umgebung (E-2/S-9), nie per PATCH/DB",
    "host": "Bind-Adresse im Container",
    "embed_ancestors": "CSP frame-ancestors fuer `/embed`",
    "oui_online_url": "nur bei aktiviertem Online-OUI (Datenschutz, Default aus)",
    "pve_enabled": "Token read-only anlegen (Rolle fox_netmap, VM.Audit+Sys.Audit) - Anleitung: Handbuch 02, Abschnitt 8 'Proxmox VE'",
    "pve_token_secret": "Secret des API-Tokens; wird nur einmal in PVE angezeigt - Anleitung: Handbuch 02, Abschnitt 8 'Proxmox VE'",
}
EXTRA_NOTES = {
    "NETZ_SQLITE_JOURNAL": "SQLite-Journal-Modus (`app/db.py`): `auto` = WAL per Schreibprobe, Fallback `delete` bei `disk I/O error`",
    "NETZ_FORWARDED_ALLOW_IPS": "uvicorn `forwarded_allow_ips` + `proxy_headers` (`app/__main__.py`); leer = `X-Forwarded-For` wird nicht ausgewertet (S-13)",
}


def _env(key: str) -> str:
    return "NETZ_" + key.upper()


def _default(key: str) -> str:
    field = Settings.model_fields.get(key)
    if field is None or field.default is None:
        return "(leer)"
    v = field.default
    if isinstance(v, bool):
        return "`true`" if v else "`false`"
    if isinstance(v, str):
        return f"`{v}`" if v else "(leer)"
    return str(v)


def _bereich(minimum: float | None, maximum: float | None) -> str:
    if minimum is None and maximum is None:
        return "-"
    lo = "" if minimum is None else str(minimum)
    hi = "beliebig" if maximum is None else str(maximum)
    return f"{lo}-{hi}"


def _flags(secret: bool, exposed: bool, patchable: bool, scanner: bool) -> str:
    out = []
    if secret:
        out.append("Secret (GET nur `configured`)")
    if not exposed:
        out.append("kein GET")
    if not patchable:
        out.append("kein PATCH")
    if not scanner:
        out.append("kein Scanner")
    return ", ".join(out) if out else "-"


def _extra_rows() -> list[tuple[str, str]]:
    rows = []
    for ln in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(NETZ_[A-Z0-9_]+)=(.*)$", ln.strip())
        if m and m.group(1)[5:].lower() not in FIELDS:
            default = f"`{m.group(2)}`" if m.group(2) else "(leer)"
            rows.append((m.group(1), default))
    return sorted(rows)


def render_table() -> str:
    lines = [
        "| Variable | Typ | Default | Bereich | Flags | Bemerkung |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for key, f in FIELDS.items():
        note = ALIAS_NOTES.get(key) or SPECIAL_NOTES.get(key) or ""
        lines.append(
            f"| `{_env(key)}` | {f.type} | {_default(key)} | {_bereich(f.minimum, f.maximum)}"
            f" | {_flags(f.secret, f.exposed, f.patchable, f.scanner)} | {note} |"
        )
    for name, default in _extra_rows():
        lines.append(
            f"| `{name}` | str | {default} | - | env-only (kein GET/PATCH/Scanner) | {EXTRA_NOTES.get(name, '')} |"
        )
    return "\n".join(lines) + "\n"


def render_block() -> str:
    # Leerzeile vor END: prettier trennt Tabelle und Kommentar ohnehin so (prettier-ignore schuetzt die Tabelle)
    return f"{START}\n<!-- prettier-ignore -->\n{render_table()}\n{END}\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="nur pruefen, nicht schreiben (exit 1 bei Drift)")
    args = ap.parse_args()
    text = DOC.read_text(encoding="utf-8")
    m = re.search(re.escape(START) + r".*?" + re.escape(END), text, re.S)
    if not m:
        print(f"{DOC}: Marker {START} ... {END} fehlt", file=sys.stderr)
        return 1
    block = render_block()
    if args.check:
        if m.group(0) == block.rstrip("\n"):
            print("env-tabelle aktuell")
            return 0
        print("env-tabelle veraltet - bitte ausfuehren: uv run python scripts/gen_env_table.py", file=sys.stderr)
        return 1
    DOC.write_text(text[: m.start()] + block.rstrip("\n") + text[m.end() :], encoding="utf-8")
    print(f"{DOC}: env-tabelle aktualisiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
