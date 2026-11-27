# Startplan – Kampagne Produktionsreife fox_netmap

- **Stand:** 2026-11-26, `main` a2ee055 (v1.6.18), Branch `vibe/produktionsreife-2b2bb8`
- **Grundlage:** `docs/produktionsreife/UEBERGABE.md` – Abschnitt 5 (Entscheidungen), 7 (Befundkatalog), 8 (Wellen + Dateibesitz), 9 (Arbeitsprotokoll), 10 (Checkliste)
- **Auftrag:** 101 geprüfte Befunde in neun Wellen (W0–W8) abarbeiten, jede Welle endet mit Gate, Advisor und einem Commit. Zielbild/Abnahmekriterien: UEBERGABE Abschnitt 6.

## 0. Getroffene Entscheidungen (UEBERGABE Abschnitt 5)

| Nr | Thema | Kais Wahl |
| -- | ----- | --------- |
| E-1 | Geräte mit gleicher IP zusammenführen | B (Empfehlung): nur `ip:`-Platzhalter mergen |
| E-2 | Login per Oberfläche abschaltbar | B (Empfehlung): nur `NETZ_AUTH_ENABLED` |
| E-3 | TR-064 HTTPS→HTTP-Rückfall | **C (abweichend, eingetragen):** Fallback bleibt (seit #111, WARN je Lauf + Port-Hinweis); Restrisiko trägt, wer den Downgrade aktiv nutzt → Doku + `docs/03-sicherheit.md` §4. Kein Code-Eingriff in W2. |
| E-4 | Oberfläche in Module aufteilen | B: nur `api.js` auslagern, Rest nach v1.7 |
| E-5 | Strenge der Typprüfung | B: `mypy --strict app` bis W7 |
| E-6 | JavaScript-Prüfung | A: eslint 9 Flat Config im Gate |
| E-7 | Gerätekategorien als neutrale IDs | A: in dieser Kampagne nur dokumentieren (Q-13) |

## 1. Bootstrap vor Welle 0

1. Branch `vibe/produktionsreife-2b2bb8` von `main` anlegen (erledigt, HEAD a2ee055).
2. Befund-Orte gegen aktuellen Stand prüfen: Zeilennummern in UEBERGABE sind Stand `a63750f`; seit v1.6.18 gab es TR-064-Änderungen (#110, #111). Vor jedem Fix `grep -rn` auf die genannte Stelle.
3. `STAND.md` anlegen mit Entscheidungen (erledigt: E-3 = C). `ARCHIV.md` und `checkliste.html` entstehen in W0 (UEBERGABE §10).
4. Harte Grenzen aktiv (UEBERGABE §9.1): kein Push/Merge/Tag/Release, kein Scan echter Netze (nur `NETZ_SUBNETS=127.0.0.0/30`), keine externen Aufrufe aus dem App-Code (Tests mocken), keine Version erhöhen (`CHANGELOG.md` nur `[Unreleased]`), kein `git add -A` – Pfade einzeln stagen.

## 2. Welle 0 – Werkzeuge (Orchestrator allein, kein Verhaltens-Change)

**Ziel:** einheitliches Gate auf uv-Basis; danach misst jede Welle gegen dieselbe Latte.

- `pyproject.toml`: `[project] dependencies` aus `requirements.in`, `dependency-groups` dev (pytest, pytest-cov, ruff, mypy, hypothesis, pip-audit), hatchling mit `[tool.hatch.version] path = "app/__init__.py"` (Version nur noch in `app/__init__.py`, Q-5). `uv.lock` erzeugen und committen; `requirements*.in/.txt` löschen, sobald Dockerfile/CI umgestellt.
- `Dockerfile` zweistufig (build: uv per Digest aus `ghcr.io/astral-sh/uv`, `uv sync --frozen --no-dev`; runtime: nur venv + `app/`); `apt-get upgrade` entfernen (Q-7); Basis-Digest `python:3.12-slim` aktualisieren (D-6).
- CI (`.github/workflows/ci.yml`, `release.yml`, `main-scan.yml`): `astral-sh/setup-uv` per SHA, `uv sync --frozen`, Matrix 3.12+3.13, Gate-Schritte wie `scripts/gate.sh`, `uv export … | uvx pip-audit`. Release prüft Tag == `app.__version__`.
- `scripts/gate.sh`: `ruff check` (erweiterte Regeln: + B, UP, SIM, S, BLE, RUF, DTZ, ASYNC, C90 max 15; B008/S101-in-tests ignoriert), `ruff format --check`, `mypy`, `pytest -q --cov=app --cov-branch`, `npm ci && node tests/ui_dom_check.mjs`, `eslint`. Bricht beim ersten Fehler ab.
- Einmalig `ruff format` auf die 19 betroffenen Dateien (TL-6), danach `--check` im Gate. Sichere Autofixes nur mit gelesenem Diff, keine `--unsafe-fixes`.
- `eslint.config.mjs`: Flat Config, `sourceType: "script"`, gemeinsame Globals (`I18N`, `LANGS`, `iconUri`, `cytoscape`), `no-unused-vars` mit `caughtErrors: "none"`; `npm run lint` in CI (TL-7).
- Dependabot: pip→uv; „Manuell zu pflegen“-Tabelle (Cytoscape-vendor, gitleaks, Trivy-Pin) in `CONTRIBUTING.md` (D-7).
- README/README.en/CONTRIBUTING: Supply-chain- und Development-Abschnitte auf uv umschreiben.
- Artefakte W0: `scripts/gate.sh`, `STAND.md` (vorhanden), `ARCHIV.md`, `docs/produktionsreife/checkliste.html` (aus UEBERGABE §10, 101 Befund-Zeilen + ZK-1…ZK-13).
- **Abnahme W0:** `gate.sh` lokal und in CI grün (3.12+3.13); `grep -rn "1\.6\.18" app pyproject.toml` nur `app/__init__.py`; `uv run pytest --co -q` ≥ 230 Tests; `docker compose build` + CI-Job `docker` grün; checkliste.html/STAND.md/ARCHIV.md existieren.

## 3. Wellen W1–W8 (Übersicht; Details inkl. Writer/Dateibesitz in UEBERGABE Abschnitt 8)

| Welle | Thema | Kernbefunde | Highlight |
| ----- | ----- | ----------- | --------- |
| W1 | Bausteine: Settings-Schema, MAC-Normalisierung, Logging | Q-1, C-1, C-2, C-3, N-2, N-3, S-7, S-8, S-9, D-2, Q-8, Q-9, SF-4 | `app/settings_schema.py`, `effective_settings()` für beide Prozesse, `.env.example`, alle `NETZ_*` in Compose |
| W2 | Sicherheit | S-1, S-3, S-4, S-5, S-6, S-10, S-11, S-12, S-13, S-14, S-15, S-16, S-17, N-5, C-10, T-1 | **S-2 entfällt als Code-Fix (E-3=C): nur Doku/Restrisiko.** Token-Scope `token_allows()`, PDF-Bildgrenze + `mem_limit`, CSV-Formel-Prefix, Login-Race, `PUBLIC_PATHS` schrumpfen, Origin-Check, umask 077 |
| W3 | Datenbank + Nebenläufigkeit | K-1…K-12, C-6, N-1, T-10 | `app/dedupe.py` (nur Platzhalter mergen, E-1=B), Lock nur beim Schreiben, Rollback bei Scanfehler, SIGTERM, atomare Exporte, Scan-State-Spalten für W4 |
| W4 | Scanner + stille Fehler | C-4, C-5, C-8, C-9, C-13, SF-1, SF-2, SF-3, SF-5, SF-7, SF-8, N-4, T-2, T-3, T-6 | IPv4 gewinnt bei Dual-Stack, leere Erkennung löscht nichts (SF-1), Scanfehler in `scan_state` + Healthcheck, `run_once` testen (T-2) |
| W5 | Oberfläche (2 Runden) | F-1…F-16, Q-10, TL-4, D-5, C-3/C-10/S-8/SF-5-Frontend | Runde 1: `api.js` + Fehlerschicht + Zustand; Runde 2: Tastatur/A11y/i18n/Performance/Embed; gemeinsamer Wellen-Commit |
| W6 | Testlücken + Mutanten | T-4, T-7, T-8, T-9, T-11, T-12, T-13, T-14, T-15, T-16 | `scripts/mutants.sh`; Kill-Liste B2,B3,M11,R1,R2,R3,F4–F7,M10 muss sterben; hypothesis für LAN-Parser; E2E Scan→API |
| W7 | Struktur + Typen | Q-3, Q-4, Q-12, Q-14, Q-16, TL-5, Q-13(doku) | `app/scanner/pipeline.py`, Router/Services, `DeviceRow` TypedDict, `mypy --strict app` grün, Charakterisierungstests vorher |
| W8 | Doku | N-6, D-1, D-3, D-4, D-10 | 6 Handbücher synchron, README ohne feste Version, `docs/05-betrieb.md` + `docs/06-architektur.md`, **Restrisiko E-3/C in `docs/03-sicherheit.md` §4**, `tests/test_docs.py` |

## 4. Ablauf je Welle (UEBERGABE §9.2, verbindlich)

1. Plan lesen (Abschnitt 7/8), Dateilisten per `grep -rn` gegen aktuellen Stand prüfen.
2. Dateibesitz festlegen: jede Datei gehört genau einem Writer oder dem Orchestrator; Integrationsdateien (`web.py`, `api.py`-Registrierung, `pyproject.toml`, CI, `i18n.js`) trägt der Orchestrator beim Gate ein.
3. Writer parallel starten (eine Nachricht, mehrere Aufrufe); warten, nicht pollen.
4. Gate: `scripts/gate.sh` (ab W0) + Container-Prüfung in Wellen mit Dockerfile/entrypoint/compose/Deps (`NETZ_SUBNETS=127.0.0.0/30`). Rot ist rot.
5. Advisor (frischer Agent, Diff + Abnahmekriterien, lässt Gate selbst laufen) vor jedem verhaltensändernden Commit; APPROVED oder Nacharbeitsliste. Ausnahmen: reine Doku/Test/mechanische Wellen.
6. Ein Commit je Welle, nur Orchestrator, Pfade einzeln stagen, Conventional Commits deutsch (Umlaute im Betreff ae/oe/ue/ss), z. B. `fix(security): Embed-Token-Scope … (W2-S1)`.
7. `STAND.md` (nächste Welle, offene Fragen, Entscheidungen), `ARCHIV.md` (eine Zeile je abgeschlossene Welle mit Commit), `checkliste.html` (Status je Befund, `erledigt` nur mit Commit + Test) aktualisieren.

## 5. Lieferkette/CI-Anforderungen (aus Projektvorgaben, bei jedem Merge)

- PR-Template ausfüllen; Doku-Pflicht: sichtbare Änderungen in alle 6 Handbücher + README.md/README.en.md + `CHANGELOG.md [Unreleased]`.
- CI-Gates bleiben grün: ruff, pytest, UI-DOM, eslint, docker build + Härtung, Trivy (CRITICAL/HIGH mit Fix = fail), gitleaks, CodeQL.
- Release (nur Kai): Tag `vX.Y.Z` == `app.__version__`, dann SBOM (CycloneDX+SPDX) + Trivy-Bericht + Release Notes; Image multi-arch auf GHCR.
- Repos bleiben privat; Runtipi-Logik: Repo → `fox_tmp` (Test) → `foxhole` (Release), erst nach Freigabe durch Kai.
