# Kampagnenstand – Produktionsreife fox_netmap

- **Stand:** 2026-11-26, `main` a2ee055 (v1.6.18), Arbeitsbranch `vibe/produktionsreife-2b2bb8`
- **Nächste Welle:** W5 (Oberfläche, 2 Runden: F-1…F-16, Q-10/Q-11, SF-6, TL-4, D-5, Frontend-Teile C-3/S-8/C-10/SF-5 Zustellstatus+Fehleranzeige) – Details in UEBERGABE Abschnitt 8
- **Grundlage:** `docs/produktionsreife/UEBERGABE.md` (Befunde Stand a63750f, vor jedem Fix gegen aktuellen Stand prüfen)

## Getroffene Entscheidungen (UEBERGABE Abschnitt 5)

- **E-3 (TR-064 HTTPS→HTTP-Rückfall): Kais Wahl = C, abweichend von Empfehlung B.** In UEBERGABE.md Abschnitt 5 eingetragen. Fallback bleibt (seit #111 für Hosts/WAN/Mesh, mit WARN je Lauf + Port-Hinweis 49443). Das Restrisiko trägt, wer den Downgrade aktiv nutzt (z. B. Port 49000 statt 49443). Umsetzung: **keine** Code-Änderung am Fallback in W2; S-2 wird als Doku-Korrektur (Handbuch:393) + Restrisiko in `docs/03-sicherheit.md` Abschnitt 4 (W8) behandelt.
- **E-1, E-2, E-4, E-5, E-6, E-7:** Spalte „Kais Wahl“ leer = Empfehlung gilt (B, B, B, B, A, A).

## Offene Fragen

- Push/PR: **Kampagne bleibt lokal** (Kai, 2026-11-26). UEBERGABE §9.1 gilt: Agent pusht/merged/taggt nicht; Push, PR und Release macht Kai. Commits landen lokal auf `vibe/produktionsreife-2b2bb8`.

## Fortsetzungsschritte

1. `STARTPLAN.md` Abschnitt 1 (Bootstrap) ausführen, dann Welle 0.
2. Nach jeder Welle: Gate → Advisor → ein Commit → STAND.md/ARCHIV.md/checkliste.html aktualisieren (UEBERGABE §9.8).

## Erledigte Wellen

- **W0 (2026-11-26, Commit `8079aab`):** uv statt pip-tools (`pyproject.toml` + `uv.lock`, requirements*.txt gelöscht), `scripts/gate.sh` lokal grün (ruff check/format, mypy app, 234 pytest + cov fail_under=84, UI-DOM, eslint 0 errors, pip-audit clean), zweistufiges Dockerfile (uv-Image + python:3.12-slim je per Digest, kein `apt-get upgrade`), CI-Matrix 3.12/3.13 + setup-uv v10.4.0 per SHA, eslint 9 Flat Config, ruff-Regeln erweitert (B/UP/SIM/S/BLE/RUF/DTZ/ASYNC/C90), Version nur noch in `app/__init__.py` (config.py liest `app.__version__`), Dependabot pip→uv + docker cooldown, README/CONTRIBUTING auf uv, checkliste.html (114 Punkte) + ARCHIV.md angelegt. **Lokal nicht nachfahrbar:** CI-Job `docker` (kein Docker-Daemon in dieser Umgebung) – ZK-8 bleibt CI-seitig zu prüfen.

- **W1 (2026-11-26, Commit `974b211`):** erledigt. settings_schema.py (FIELDS, eine Quelle), effective_settings in config.py (Web+Scanner, C-1), C-2/SF-4, S-7/S-8/S-9 (E-2), D-2 (compose + .env.example, 43 NETZ_* + NETZ_SQLITE_JOURNAL), Q-2 (validation.py, Meldungen wörtlich gleich), Q-8, Q-9/C-15/N-3 (netutil.py), N-2. Gate grün: ruff/format/mypy/257 pytest/UI/eslint/pip-audit. **Vorher-rot-Nachweis:** neue Tests brauchen das Schema (ImportError gegen altem Code). **Offen aus W1:** UI-Teil C-3/S-8 (Secret-Felder in app.js) und auth_enabled-Schalter entfernen → W5. Doku-Pflicht Handbücher (6 Sprachen) zu Settings-Änderungen → W8.

- **W2 (2026-11-26, Commit `bed6eed`):** erledigt. S-1/C-7/T-5 Token-Scope (404 out-of-scope, Multi-Subnetz, nie erweitern), S-10 PUBLIC_PATHS minimiert + health nur status, T-1 Schreibrouten-Tests (dabei echter Fund: POST /api/export/pdf ohne require_auth), S-6 PDF 16MP + Token-kein-Bild + mem_limit, S-3 CSV-Formel-Praefix, S-4/S-5 Login pending+Sperre-hebt-sich, S-12 Accesslog-Redaction, S-13 proxy_headers default aus, S-11 mDNS, S-14/N-5 OUI, S-15 TR-064 caps, S-16 CSRF-Origin, S-17 umask 0600, C-10. Gate grün: 301 Tests. **S-2 offen bis W8** (E-3=C: nur Doku + Restrisiko in sicherheit.md §4). Doku-Pflicht Handbücher (S-5/S-10/S-13-Verhalten) -> W8.

- **W3 (2026-11-26, Commit `88f99df`):** erledigt. K-3/C-14 Dedupe ohne Datenverlust (`app/dedupe.py`: nur `ip:`-Platzhalter werden in die echte MAC derselben IP eingemischt, zwei echte MACs nie verschmolzen), K-12 init_db sichert Schema/scan_state vor der Dedupe und rollt bei Fehler nur die Dedupe zurueck, K-1 connect()-Journalprobe nur einmal je Prozess/Pfad (kein Schreib-Lock bei Lesen/Healthcheck), K-2 set_oui_cache committet sofort, K-4 Migrationen tolerieren "duplicate column name", K-10/K-5 apply_scan per BEGIN IMMEDIATE + kompletter Rollback bei Fehler, K-8 SIGTERM/SIGINT sauber (`init: true` in Compose) + atomarer Auto-Export (tmp + os.replace), K-11 read_snapshot fuer Exporte, C-6 Upsert per COALESCE (leere Felder loeschen nicht mehr), N-1 blank_stale_ip bei gemeldeter IP, K-6 set_layout spaltengenauer UPSERT, scan_state um last_error/last_error_at/consecutive_failures/scan_started_at erweitert (Basis SF-2 in W4), T-10 v1.0-Fixture-Migrationstest. Neue Tests: test_dedupe.py, test_db_concurrency.py, test_migrations.py, test_export_atomic.py, test_scanner_loop.py. Gate grün: 316 Tests.

- **W4 (2026-11-26, Commit `ed7efa3`):** erledigt. C-4 IPv4 gewinnt bei Dual-Stack (ip6-Spalte), SF-1 leere Erkennung sperrt Offline+Retention nur bei fehlenden Subnetzen/Binaerdateien (sonst WARNING + normaler Uebergang), SF-2 Scanfehler in scan_state + /api/scan/status + Healthcheck unhealthy ab 3 Fehlern (read-only Verbindung), SF-3/K-9 haengende Scans unhealthy + stale_scanning, C-5 last_seen nur bei online (Retention faellt auf first_seen zurueck), C-8 post-multicast-NDP im Ergebnis, C-9 SNMP ignoriert Uplink-Ports/Switch-MACs/Gateway, C-13 Portliste 1-65535 validiert + port_top-Cap 1040 dokumentiert, SF-8/TL-1 warn_once je Lauf fuer fehlende Binaerdateien + DEBUG fuer erwartbare Sondenfehler, WAN-Werte bei TR-064-Ausfall geleert, SF-5 Notify ab HTTP 300 + last_notify_status/-at persistent (UI-Anzeige -> W5), N-4 PDF nur Bildfehler als 422, sonst 500 + log.exception (pillow als direkte Dependency), SF-7 Entrypoint meldet chown-Probe-Fehler als WARN, T-6 Auto-Export per realpath im Datenverzeichnis. Neue Tests: test_merge_sources, test_scan_state, test_discovery_paths, test_health_status, test_notify, test_pdf_errors, test_retention, test_auto_export + Erweiterungen test_scanner_loop (T-2) und test_hardening (SF-7). Gate grün: 346 Tests. **SF-1-Auslegung:** Sperre greift nur bei leerer Subnetzliste ODER fehlenden Sonden-Binaerdateien (so zeigt ein wirklich leeres Netz weiter offline); Test siehe test_scan_state.py.
