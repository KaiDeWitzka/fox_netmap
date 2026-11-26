# Kampagnenstand – Produktionsreife fox_netmap

- **Stand:** 2026-11-26, `main` a2ee055 (v1.6.18), Arbeitsbranch `vibe/produktionsreife-2b2bb8`
- **Nächste Welle:** W1 (Bausteine: Settings-Schema, MAC-Normalisierung, Logging) – Details in UEBERGABE Abschnitt 8
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
