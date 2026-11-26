# fox_netmap – Architektur

Stand: November 2026 · App-Version: `app/__init__.py` bzw. `/api/meta`

Überblick über Komponenten, Datenfluss, Modulstruktur und Sicherheitsgrenzen.
Bedrohungsmodell und Restrisiken: [Sicherheitskonzept §1 und §4](03-sicherheit.md). Betrieb
(Backup/Upgrade/Umgebungsvariablen): [05-betrieb.md](05-betrieb.md).

## 1. Komponenten

Ein Image, zwei Prozesse (plus Healthcheck):

- `python -m app web` — FastAPI-App (`app/web.py::create_app`), liefert UI (`app/static`) und REST-API
- `python -m app scanner` — Scan-Schleife (`app/scanner/run.py`), schreibt in dieselbe SQLite-DB
- `python -m app health` — Docker-HEALTHCHECK (`app/healthcheck.py`)

```text
Scanner (zyklisch/manuell)
  → Erkennung: ARP/NDP, ping, TCP-Probe, TR-064, SNMP, mDNS (app/scanner/discover.py, pipeline.py)
  → Aufbereitung: Merge, Dedupe (nicht-destruktiv), Kategorie, Topologie
  → SQLite (WAL, Transaktionen)  ←  manuelle Edits (Web/API)
  → Web/API (FastAPI)  →  REST + statische UI (Vanilla JS + Cytoscape.js)  →  Browser
```

## 2. Datenfluss pro Scan

`collect_devices` (`app/scanner/pipeline.py`) arbeitet stufenweise: Rohdaten sammeln → TR-064
(Hosts/WAN/Mesh) → Ports scannen → mDNS/DNS-Namen → SNMP → Merge/Dedupe → Kategorisierung →
Finalisieren → transaktional in die DB (`apply_scan`) → Verlauf/Ereignisse/Alarme
(Webhook/Gotify/Ntfy) → Auto-Export. Scanfehler landen in `scan_state` und im Healthcheck (SF-2).

## 3. Modulstruktur (seit W7)

- `app/web.py` — `create_app`, Middleware (Auth, CSRF-Origin, Security-Header), Seiten
- `app/routers/` — je Bereich ein Router: `common` (DB/Auth-Dependencies), `devices`, `scan`,
  `export`, `settings`, `tokens`, `meta`
- `app/services/` — fachliche Logik: `authz` (Token-Scope, S-1), `devices`
- `app/models.py` / `app/types.py` — Response-Models und TypedDicts (`mypy --strict app`)
- `app/validation.py` — reine Validierung (`validate_patch`), Quelle `app/settings_schema.py`
- `app/scanner/` — `run` (Schleife), `pipeline`, `discover`, `categorize`, `tr064`, `ports`,
  `snmp`, `mdns`, `names`, `oui`, `topology`, `notify`
- Infrastruktur: `app/db.py`, `app/auth.py`, `app/security.py`, `app/config.py`,
  `app/settings_schema.py`, `app/exporters.py`, `app/logsetup.py`, `app/healthcheck.py`,
  `app/dedupe.py`, `app/netutil.py`

## 4. Datenbank-Schema (High-Level)

`devices` (MAC als Schlüssel), `device_ports`, `device_history`, `device_events`,
`device_layout`, `settings`, `embed_tokens` (nur Hash, siehe Sicherheitskonzept 2.12), `users`
(PBKDF2), `scan_state`, `oui_cache`. Schema-Migrationen laufen idempotent in `db.init_db`.

## 5. Sicherheitsgrenzen

- Öffentlich ohne Anmeldung nur: `GET /api/health` (nur `{"status": "ok"}`), `POST /api/login`,
  `GET /api/categories`, `/embed` (mit gültigem Token), statische Dateien, `/login` (S-10).
- Token-Pfade (`/api/devices`, `/api/device/{mac}`, `/api/export/*`, `/api/meta`, `/api/sites`,
  `/api/scan/status`): Sitzung **oder** Embed-Token; der Token-Scope (Subnetz/Kategorie) gilt für
  Liste und Detail, außerhalb des Scopes Antwort 404 (S-1).
- `/docs` und `/openapi.json` sind abgeschaltet (D-3).
- CSRF: unsichere Methoden mit Session-Cookie brauchen passenden Origin/Referer (S-16);
  Security-Header auf allen Antworten; Tokens im Zugriffslog geschwärzt (S-12).

## 6. Teststrategie

- `scripts/gate.sh` (lokal und in CI, Python 3.12 + 3.13): ruff + format, mypy + `mypy --strict
app`, pytest mit Coverage, UI-DOM-Check (jsdom, `tests/ui/*`), eslint, pip-audit, prettier
  (Markdown)
- Charakterisierungstests pinnen das Verhalten vor Umbauten (W7), Mutationstests killen
  Regressionen (`scripts/mutants.sh`, W6), Doku-Regressionstests prüfen Doku gegen Code
  (`tests/test_docs.py`, W8)
- CI zusätzlich: Docker-Build + Trivy-Gate, SBOM (CycloneDX/SPDX) je Merge und Release
