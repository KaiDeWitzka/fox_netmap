# Archiv – abgeschlossene Wellen der Produktionsreife-Kampagne

Je Welle eine Zeile: Ergebnis + Commit. Details stehen in den Commit-Messages und in `STAND.md`.

| Welle | Ergebnis | Commit |
| ----- | -------- | ------ |
| W4 | erledigt: Dual-Stack IPv4 (C-4), SF-1 leere Erkennung sperrt nichts, SF-2 scan_state-Fehler + Healthcheck (SF-3/K-9 read-only, haengende Scans), C-5 last_seen nur online, C-8 NDP nach Multicast, C-9 SNMP-Uplink, C-13 Ports validiert, SF-8/TL-1 warn_once, SF-5 Notify>=300 + Status, N-4 PDF 500+Log, SF-7 Entrypoint-WARN, T-2/T-3/T-6 Tests; 346 Tests, gate grün | `ed7efa3` |
| W3 | erledigt: Dedupe ohne Datenverlust (K-3/C-14), connect ohne Schreib-Lock (K-1), sofortiges OUI-Commit (K-2), Scan-Rollback (K-5/K-10), SIGTERM + atomarer Export (K-8/K-11), Migrationen (K-4/K-12), Upsert COALESCE + stale-IP (C-6/N-1), Layout-UPSERT (K-6), scan_state-Fehlerfelder, T-10; 316 Tests, gate grün | `88f99df` |
| W1 | erledigt: Schema+effective_settings, Secrets maskiert, auth env-only, compose vollstaendig, netutil, Logger; 257 Tests grün, gate grün | `974b211` |
| W2 | erledigt: Sicherheit - Token-Scope, Public Surface, PDF/CSV, Login, Log, Proxy-Header, Scanner-Eingaenge, CSRF, Dateirechte; 301 Tests, gate grün; S-2 -> W8 Doku (E-3=C) | `bed6eed` |
| W0 | erledigt: uv + gate.sh grün lokal, zweistufiges Dockerfile, CI 3.12/3.13 + eslint, 234 Tests grün, mypy app 0 Fehler, cov 85% (fail_under=84); docker-Job lokal nicht prüfbar (kein Daemon) | `8079aab` |
