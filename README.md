# fox_netmap
scan am visualize a network as a map

- [Anforderungen & Zielarchitektur](docs/01-anforderungen.md)

## Quickstart (standalone Docker)

```bash
docker compose up -d --build
# Web-UI: http://localhost:8399  (Login: NETZ_AUTH_USER / NETZ_AUTH_PASS, Default-Benutzer "admin")
```

**Änderungen an `docker-compose.yml` / `.env` anwenden:** Laufende Container übernehmen Compose-Änderungen nie automatisch. Nach dem Editieren `docker compose up -d` ausführen — Compose erstellt geänderte Services neu (Recreate). `docker compose restart` allein reicht nicht: Env-Variablen, Ports und Command bleiben dabei alt. Nach Code-Änderungen am Image: `docker compose up -d --build`. Die Daten liegen im Volume `./data` (SQLite, Log, Exporte) und überleben jedes Recreate; `docker compose down -v` löscht sie dagegen. Effektive Config prüfen: `docker compose config`.

Konfiguration über Umgebungsvariablen (`NETZ_*`, siehe `docker-compose.yml`):
`NETZ_SUBNETS` (kommagetrennt, leer = lokales Subnetz), `NETZ_SCAN_INTERVAL` (Sekunden, Default 900),
`NETZ_PORT_TOP` (Top-N-Ports, 0 = alle), `NETZ_FRITZ_URL/USER/PASS` (TR-064, Hauptgeraet), `NETZ_FRITZ_URLS` (weitere TR-064-Endpunkte kommagetrennt, z. B. Repeater — deren WLAN-Clients werden dem jeweiligen Geraet zugeordnet),
`NETZ_SNMP_ENABLED/COMMUNITY/SWITCHES`, `NETZ_AUTH_ENABLED/USER/PASS`, `NETZ_NOTIFY_*`, `NETZ_HISTORY_HOURS`, `NETZ_DEVICE_RETENTION_DAYS` (Geräte offline löschen nach N Tagen, Default 30, 0 = nie), `NETZ_THEME`.

Der Scanner-Container läuft im Host-Netzwerkmodus (`network_mode: host`), damit MAC-Adressen per ARP aufgelöst werden können. Daten liegen in `./data` (SQLite + Exporte).

**Topologie („Verbunden mit“), Priorität:** manuelles Mapping in der Karte (Detail-Panel → „Verbunden mit“) > SNMP CAM-Tabelle + LLDP-MIB verwalteter Switche > TR-064-Endpunkt (z. B. Repeater, an dem der Client hängt) > TR-064 WLAN/LAN (WLAN-Geräte hängen an einem virtuellen WLAN-Knoten) > Gateway. Unmanaged Switche (z. B. TL-SG108E ohne SNMP) sind nicht automatisch sichtbar — dort manuell zuordnen.

OUI-Datenbank aktualisieren: `python scripts/update_oui.py ./data` (lädt die IEEE-OUI-Datei nach `data/oui.txt`).

## Releases

- Version steht in `app/__init__.py` (`__version__`), `pyproject.toml` und `app/config.py` (`app_version`). Aktuell: **v1.0.0**
- SemVer ab v1.0.0: Releases tragen Tags im Format `vMAJOR.MINOR.PATCH` (z. B. `v1.0.0`, `v1.1.0`, `v2.0.0`) auf `main`
- Tag pushen (`git tag v1.1.0 && git push origin v1.1.0`) → Workflow `release.yml` testet (ruff + pytest + UI-DOM) und erstellt automatisch ein GitHub-Release

## Entwicklung

```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest -q
python -m app web       # Web/API lokal (NETZ_DATA_DIR=./data)
python -m app scanner   # Scanner lokal
```
