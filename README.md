# fox_netmap
scan am visualize a network as a map

- [Anforderungen & Zielarchitektur](docs/01-anforderungen.md)

## Lizenz

[MIT License](LICENSE) — Copyright (c) 2026 KaiDeWitzka.

fox_netmap darf frei genutzt, verändert und weitergegeben werden (auch kommerziell). Einzige Bedingung: Der Copyright- und Lizenzhinweis muss in allen Kopien/wesentlichen Teilen erhalten bleiben — wer den Code verwendet, soll das also kenntlich machen.

## Dokumentation

- [Benutzerhandbuch](docs/02-benutzerhandbuch.md) — in 6 Sprachen: [de](docs/02-benutzerhandbuch.md) · [en](docs/02-benutzerhandbuch.en.md) · [fr](docs/02-benutzerhandbuch.fr.md) · [es](docs/02-benutzerhandbuch.es.md) · [it](docs/02-benutzerhandbuch.it.md) · [pt](docs/02-benutzerhandbuch.pt.md) (Schnellstart, Bedienung, Screenshots, Settings, Embed, Exporte, Troubleshooting, API)
- [Anforderungen & Architektur](docs/01-anforderungen.md)
## Quickstart (standalone Docker)

```bash
docker compose up -d --build
# Web-UI: http://localhost:8399  (Login: NETZ_AUTH_USER / NETZ_AUTH_PASS, Default-Benutzer "admin")
# Exporte im Header: JSON, CSV, PDF (serverseitig via POST /api/export/pdf: Karten-Snapshot + Geraetetabelle), Druckansicht
```

**Änderungen an `docker-compose.yml` / `.env` anwenden:** Laufende Container übernehmen Compose-Änderungen nie automatisch. Nach dem Editieren `docker compose up -d` ausführen — Compose erstellt geänderte Services neu (Recreate). `docker compose restart` allein reicht nicht: Env-Variablen, Ports und Command bleiben dabei alt. Nach Code-Änderungen am Image: `docker compose up -d --build`. Die Daten liegen im Volume `./data` (SQLite, Log, Exporte) und überleben jedes Recreate; `docker compose down -v` löscht sie dagegen. Effektive Config prüfen: `docker compose config`.

Konfiguration über Umgebungsvariablen (`NETZ_*`, siehe `docker-compose.yml`) — Defaults für frische Installationen. Zur Laufzeit änderbar ohne Neustart sind in den **Einstellungen**: Subnetze (inkl. IPv6-CIDR), Scan-Intervall/-Timeout, Ports (Top-N/eigene Liste), TR-064 (URL/URLs/Benutzer), SNMP (aktiv/Switches/Community), Alarm-URLs (Webhook/Gotify/Ntfy), Historie, Retention, Auto-Export (an/Intervall/Ordner), mDNS, Whitelist, Standorte, Theme, Sprache, Login an/aus. **Secrets** (`NETZ_AUTH_PASS`, `NETZ_NOTIFY_*_TOKEN`) und Deployment-Variablen (`NETZ_DATA_DIR`, Port, `TZ`) bleiben bewusst env-only in der Compose. `NETZ_FRITZ_PASS` ist zusätzlich in den Einstellungen änderbar (write-only: wird nie von `GET /api/settings` ausgeliefert; leer = Env-Default). Ursprünglich:
`NETZ_SUBNETS` (kommagetrennt, IPv4 + IPv6 CIDRs, leer = lokales Subnetz; IPv6-Fund bei großen Netzen via NDP + Gateway, bei kleinen zusätzlich Sweep), `NETZ_SITES` (Standorte als `Name:Subnetz[,Subnetz]; Name2:Subnetz2` — Anzeige/Filter/Export, z. B. `Zuhause:192.168.178.0/24; Remote:192.168.179.0/24`), `NETZ_SCAN_INTERVAL` (Sekunden, Default 900),
`NETZ_PORT_TOP` (Top-N-Ports, 0 = alle), `NETZ_FRITZ_URL/USER/PASS` (TR-064, Hauptgeraet), `NETZ_FRITZ_URLS` (weitere TR-064-Endpunkte kommagetrennt, z. B. Repeater — deren WLAN-Clients werden dem jeweiligen Geraet zugeordnet),
`NETZ_SNMP_ENABLED/COMMUNITY/SWITCHES`, `NETZ_AUTH_ENABLED/USER/PASS`, `NETZ_NOTIFY_*`, `NETZ_HISTORY_HOURS`, `NETZ_DEVICE_RETENTION_DAYS` (Geräte offline löschen nach N Tagen, Default 30, 0 = nie), `NETZ_THEME`, `NETZ_LANG` (UI-Sprache: de/en/fr/es/it/pt, Default de; im Header umschaltbar, in Settings speicherbar, Embed via `?lang=`), `NETZ_AUTO_EXPORT`/`NETZ_AUTO_EXPORT_DIR`/`NETZ_AUTO_EXPORT_INTERVAL_HOURS` (Auto-Export, Default alle 24 h, 0 = nach jedem Scan), `NETZ_MDNS_ENABLED` (mDNS-Namensauflösung als DNS-Fallback, Default an), `NETZ_OUI_ONLINE_ENABLED/MAX/URL` (Online-OUI-Fallback: Hersteller unbekannter MACs online nachschlagen, Default an, max 10 Lookups/Scan, gecacht in `oui_cache`), `NETZ_ALARM_WHITELIST` (MACs/IPs kommagetrennt, für die kein „neues Gerät“-Alarm ausgelöst wird).

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
