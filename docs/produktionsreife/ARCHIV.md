# Archiv – abgeschlossene Wellen der Produktionsreife-Kampagne

Je Welle eine Zeile: Ergebnis + Commit. Details stehen in den Commit-Messages und in `STAND.md`.

| Welle | Ergebnis | Commit |
| ----- | -------- | ------ |
| W1 | erledigt: Schema+effective_settings, Secrets maskiert, auth env-only, compose vollstaendig, netutil, Logger; 257 Tests grün, gate grün | `974b211` |
| W2 | erledigt: Sicherheit - Token-Scope, Public Surface, PDF/CSV, Login, Log, Proxy-Header, Scanner-Eingaenge, CSRF, Dateirechte; 301 Tests, gate grün; S-2 -> W8 Doku (E-3=C) | `bed6eed` |
| W0 | erledigt: uv + gate.sh grün lokal, zweistufiges Dockerfile, CI 3.12/3.13 + eslint, 234 Tests grün, mypy app 0 Fehler, cov 85% (fail_under=84); docker-Job lokal nicht prüfbar (kein Daemon) | `8079aab` |
