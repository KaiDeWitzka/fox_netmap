# Kampagnenstand – Produktionsreife fox_netmap

- **Stand:** 2026-11-26, `main` a2ee055 (v1.6.18), Arbeitsbranch `vibe/produktionsreife-2b2bb8`
- **Nächste Welle:** W0 (Werkzeuge: uv + `scripts/gate.sh`, zweistufiges Dockerfile, CI-Matrix 3.12/3.13, eslint) – Details in `STARTPLAN.md` Abschnitt 2 und UEBERGABE Abschnitt 8 „Welle 0 im Detail“
- **Grundlage:** `docs/produktionsreife/UEBERGABE.md` (Befunde Stand a63750f, vor jedem Fix gegen aktuellen Stand prüfen)

## Getroffene Entscheidungen (UEBERGABE Abschnitt 5)

- **E-3 (TR-064 HTTPS→HTTP-Rückfall): Kais Wahl = C, abweichend von Empfehlung B.** In UEBERGABE.md Abschnitt 5 eingetragen. Fallback bleibt (seit #111 für Hosts/WAN/Mesh, mit WARN je Lauf + Port-Hinweis 49443). Das Restrisiko trägt, wer den Downgrade aktiv nutzt (z. B. Port 49000 statt 49443). Umsetzung: **keine** Code-Änderung am Fallback in W2; S-2 wird als Doku-Korrektur (Handbuch:393) + Restrisiko in `docs/03-sicherheit.md` Abschnitt 4 (W8) behandelt.
- **E-1, E-2, E-4, E-5, E-6, E-7:** Spalte „Kais Wahl“ leer = Empfehlung gilt (B, B, B, B, A, A).

## Offene Fragen

- Push/PR: UEBERGABE §9.1 verbietet dem Agenten Push/Merge/Tag – Kampagne endet mit lokalen Commits auf `vibe/produktionsreife-2b2bb8`. Push/PR/Release macht Kai.

## Fortsetzungsschritte

1. `STARTPLAN.md` Abschnitt 1 (Bootstrap) ausführen, dann Welle 0.
2. Nach jeder Welle: Gate → Advisor → ein Commit → STAND.md/ARCHIV.md/checkliste.html aktualisieren (UEBERGABE §9.8).
