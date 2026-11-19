# fox_netmap
scan am visualize a network as a map

- [Anforderungen & Zielarchitektur](docs/01-anforderungen.md)

## Quickstart (standalone Docker)

```bash
docker compose up -d --build
# Web-UI: http://localhost:8399  (Login: NETZ_AUTH_USER / NETZ_AUTH_PASS, Default-Benutzer "admin")
```

Konfiguration über Umgebungsvariablen (`NETZ_*`, siehe `docker-compose.yml`):
`NETZ_SUBNETS` (kommagetrennt, leer = lokales Subnetz), `NETZ_SCAN_INTERVAL` (Sekunden, Default 900),
`NETZ_PORT_TOP` (Top-N-Ports, 0 = alle), `NETZ_FRITZ_URL/USER/PASS` (TR-064),
`NETZ_SNMP_ENABLED/COMMUNITY/SWITCHES`, `NETZ_AUTH_ENABLED/USER/PASS`, `NETZ_NOTIFY_*`, `NETZ_HISTORY_HOURS`, `NETZ_THEME`.

Der Scanner-Container läuft im Host-Netzwerkmodus (`network_mode: host`), damit MAC-Adressen per ARP aufgelöst werden können. Daten liegen in `./data` (SQLite + Exporte).

OUI-Datenbank aktualisieren: `python scripts/update_oui.py ./data` (lädt die IEEE-OUI-Datei nach `data/oui.txt`).

## Entwicklung

```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
python -m app web       # Web/API lokal (NETZ_DATA_DIR=./data)
python -m app scanner   # Scanner lokal
```
