# fox_netmap – Betrieb (Runbook)

Stand: November 2026 · App-Version: `app/__init__.py` bzw. `/api/meta`

Runbook für Backup, Upgrade, Rollback, Monitoring und die vollständige Referenz aller
Umgebungsvariablen. Verwandte Doku: [Sicherheitskonzept](03-sicherheit.md) (inkl.
Bedrohungsmodell und Restrisiken), [Architektur](06-architektur.md),
[Datenschutzhinweis](04-datenschutz.md), [Benutzerhandbuch](02-benutzerhandbuch.md).

## 1. Dienste und Daten

- Zwei Compose-Services aus einem Image: `netmap` (Web/API, Port 8399, Bridge-Netz) und
  `netmap-scanner` (`network_mode: host`, nur Cap `NET_RAW`), beide als UID/GID 10001.
- Alle Daten liegen im Volume `./data` (Container `/data`): `netmap.db` (SQLite, WAL),
  `netmap.log` (rotierend, 1 MB × 3), `exports/`, ggf. `initial-admin-password.txt`.
- Dateirechte: `umask 0o077` (S-17) — neue Dateien sind `0600`, Besitzer UID 10001. Secrets
  (`fritz_pass`, `snmp_community`, `notify_*_token`) liegen im Klartext in `netmap.db`,
  geschützt durch die Dateirechte; die API liefert sie nie aus (S-8).

## 2. Backup (WAL-sicher)

Ohne laufenden Schreibzugriff (Scanner gestoppt) reicht ein Datei-Copy des ganzen Verzeichnisses:

```bash
docker compose stop netmap-scanner
cp -a data "data-backup-$(date +%F-%H%M)" # auf dem Host; Rechte bleiben erhalten (0600)
docker compose start netmap-scanner
```

Online-Backup ohne Downtime (SQLite-Backup-API, konsistent auch mit WAL):

```bash
docker compose exec netmap python -c "import sqlite3; s=sqlite3.connect('/data/netmap.db'); d=sqlite3.connect('/data/netmap-backup.db'); s.backup(d); d.close(); s.close()"
docker compose cp netmap:/data/netmap-backup.db ./netmap-backup.db
docker compose exec netmap rm /data/netmap-backup.db
```

Prüfen:
`python3 -c "import sqlite3; print(sqlite3.connect('netmap-backup.db').execute('PRAGMA integrity_check').fetchone())"`
→ `('ok',)`.

- Backups enthalten MACs, Hostnamen und Anwesenheitsprofile (personenbeziehbar, siehe
  [Datenschutzhinweis §3](04-datenschutz.md)) — dieselbe Vertraulichkeit wie das Original,
  Rechte `0600`.
- Restore-Test: Backup in ein leeres Datenverzeichnis legen, `docker compose up -d`, Health
  prüfen (`docker compose ps`, `GET /api/health`).

## 3. Upgrade

1. Fertiges Image: `docker compose pull && docker compose up -d`; lokaler Build:
   `docker compose up -d --build`.
2. Compose-Änderungen (Env, Ports, Command) brauchen immer ein Recreate: `docker compose up -d`
   (ein `restart` allein reicht nicht).
3. Migrationen laufen automatisch beim Start (`db.init_db`): Schema idempotent, Alias-Migration
   `subnet`→`subnets` / `fritz_url`→`fritz_urls` (Q-16), Token-Hashing idempotent (2.12),
   Dedupe nicht-destruktiv (nur `ip:`-Platzhalter, K-3).
4. Danach prüfen: `docker compose ps` (healthy?), `curl -s http://localhost:8399/api/health`,
   Log: `docker compose logs netmap | tail -50`.
5. Daten in `./data` bleiben erhalten — **`docker compose down -v` löscht sie!**

## 4. Rollback

1. Vorheriges Image pinnen: `image: ghcr.io/kaidewitzka/fox_netmap:<alter-Tag>` in der Compose,
   dann `docker compose up -d`.
2. Hat die neue Version das DB-Schema erweitert, vor dem Downgrade das letzte Backup der
   `netmap.db` zurückspielen (Abschnitt 2).
3. `docker compose down` (ohne `-v`!) — Daten bleiben liegen.

## 5. Monitoring und Healthcheck

- `GET /api/health` → `{"status": "ok"}` — öffentlich, ohne Metadaten (S-10); Version und
  Metadaten erst mit Login in `GET /api/meta`.
- Docker-HEALTHCHECK: Web prüft `/api/health`, Scanner prüft die Scan-Schleife; `docker compose
ps` zeigt `healthy`/`unhealthy`. Ab 3 aufeinanderfolgenden Scanfehlern meldet der Healthcheck
  `unhealthy` (SF-2).
- `GET /api/scan/status` (Login/Token): letzter/nächster Scan, `last_error`,
  `consecutive_failures`.
- Log: `docker compose logs -f netmap-scanner`, UI-Tab **Log** bzw. `GET /api/logs`.

## 6. Netzwerk und Ports

- Der Container hört auf `0.0.0.0:8399` (`NETZ_HOST`/`NETZ_PORT`); Host-Port per `NETMAP_PORT`.
- Empfehlung: Reverse Proxy mit HTTPS davor (z. B. nginx/Caddy/Traefik). Nur wenn der Proxy
  vertrauenswürdig ist: `NETZ_FORWARDED_ALLOW_IPS=<Proxy-IPs>` setzen — dann wertet uvicorn
  `X-Forwarded-For` aus (S-13); sonst sieht fox_netmap nur die Proxy-IP und die Login-Sperre
  greift faktisch global (siehe [Sicherheitskonzept §2.3](03-sicherheit.md)).
- `/docs` und `/openapi.json` sind abgeschaltet (D-3) — die Doku liegt in `docs/`.

## 7. Umgebungsvariablen

Vollständige Referenz, generiert aus `app/settings_schema.py` (Defaults aus `app/config.py`,
env-only-Variablen aus `.env.example`). Nach Schema-Änderungen neu generieren:

```bash
uv run python scripts/gen_env_table.py          # schreibt die Tabelle unten neu
uv run python scripts/gen_env_table.py --check  # prueft die Aktualitaet (Gate/Test)
```

<!-- GEN:ENV-TABLE:START -->
<!-- prettier-ignore -->
| Variable | Typ | Default | Bereich | Flags | Bemerkung |
| --- | --- | --- | --- | --- | --- |
| `NETZ_DATA_DIR` | str | `/data` | - | kein GET, kein PATCH, kein Scanner |  |
| `NETZ_HOST` | str | `0.0.0.0` | - | kein GET, kein PATCH, kein Scanner | Bind-Adresse im Container |
| `NETZ_PORT` | int | 8399 | - | kein GET, kein PATCH, kein Scanner |  |
| `NETZ_SUBNET` | str | (leer) | - | kein GET, kein PATCH, kein Scanner | Alt-Alias von `NETZ_SUBNETS`; DB-Zeilen werden beim Start migriert (Q-16) |
| `NETZ_EMBED_ANCESTORS` | str | `*` | - | kein GET, kein PATCH, kein Scanner | CSP frame-ancestors fuer `/embed` |
| `NETZ_COOKIE_SECURE` | str | `auto` | - | kein GET, kein PATCH, kein Scanner |  |
| `NETZ_AUTH_ENABLED` | bool | `true` | - | kein PATCH, kein Scanner | immer Umgebung (E-2/S-9), nie per PATCH/DB |
| `NETZ_AUTH_USER` | str | `admin` | - | kein PATCH, kein Scanner |  |
| `NETZ_AUTH_PASS` | str | (leer) | - | Secret (GET nur `configured`), kein GET, kein PATCH, kein Scanner |  |
| `NETZ_FRITZ_PASS` | str | (leer) | - | Secret (GET nur `configured`) |  |
| `NETZ_SNMP_COMMUNITY` | str | (leer) | - | Secret (GET nur `configured`) |  |
| `NETZ_NOTIFY_GOTIFY_TOKEN` | str | (leer) | - | Secret (GET nur `configured`) |  |
| `NETZ_NOTIFY_NTFY_TOKEN` | str | (leer) | - | Secret (GET nur `configured`) |  |
| `NETZ_SUBNETS` | str | (leer) | - | - |  |
| `NETZ_SITES` | str | (leer) | - | - |  |
| `NETZ_SCAN_INTERVAL` | int | 900 | 30-86400 | - |  |
| `NETZ_SCAN_TIMEOUT` | float | 1.0 | 0.2-10 | - |  |
| `NETZ_PORT_TOP` | int | 1000 | 0-65535 | - |  |
| `NETZ_PORTS` | str | (leer) | - | - |  |
| `NETZ_FRITZ_URL` | str | (leer) | - | - | Alt-Alias von `NETZ_FRITZ_URLS`; DB-Zeilen werden beim Start migriert (Q-16) |
| `NETZ_FRITZ_URLS` | str | (leer) | - | - |  |
| `NETZ_FRITZ_USER` | str | (leer) | - | - |  |
| `NETZ_FRITZ_MESH` | bool | `true` | - | - |  |
| `NETZ_TR064_INSECURE_TLS` | bool | `false` | - | - |  |
| `NETZ_VPN_POOL` | str | `off` | - | - |  |
| `NETZ_SNMP_ENABLED` | bool | `true` | - | - |  |
| `NETZ_SNMP_SWITCHES` | str | (leer) | - | - |  |
| `NETZ_DOCKER_ENABLED` | bool | `false` | - | - |  |
| `NETZ_DOCKER_HOSTS` | str | (leer) | - | - |  |
| `NETZ_DOCKER_INSECURE_TLS` | bool | `false` | - | - |  |
| `NETZ_DOCKER_TOKEN` | str | (leer) | - | Secret (GET nur `configured`) |  |
| `NETZ_PVE_ENABLED` | bool | `false` | - | - |  |
| `NETZ_PVE_URLS` | str | (leer) | - | - |  |
| `NETZ_PVE_USER` | str | (leer) | - | - |  |
| `NETZ_PVE_TOKEN_ID` | str | (leer) | - | - |  |
| `NETZ_PVE_TOKEN_SECRET` | str | (leer) | - | Secret (GET nur `configured`) |  |
| `NETZ_PVE_INSECURE_TLS` | bool | `false` | - | - |  |
| `NETZ_NOTIFY_WEBHOOK` | str | (leer) | - | - |  |
| `NETZ_NOTIFY_GOTIFY` | str | (leer) | - | - |  |
| `NETZ_NOTIFY_NTFY` | str | (leer) | - | - |  |
| `NETZ_ALARM_WHITELIST` | str | (leer) | - | - |  |
| `NETZ_HISTORY_HOURS` | int | 720 | 1-87600 | - |  |
| `NETZ_DEVICE_RETENTION_DAYS` | int | 30 | 0-3650 | - |  |
| `NETZ_EVENT_RETENTION_DAYS` | int | 90 | 0-3650 | - |  |
| `NETZ_THEME` | str | `dark` | - | - |  |
| `NETZ_LANG` | str | `de` | - | - |  |
| `NETZ_AUTO_EXPORT` | bool | `false` | - | - |  |
| `NETZ_AUTO_EXPORT_DIR` | str | `exports` | - | - |  |
| `NETZ_AUTO_EXPORT_INTERVAL_HOURS` | int | 24 | 0-720 | - |  |
| `NETZ_MDNS_ENABLED` | bool | `true` | - | - |  |
| `NETZ_OUI_ONLINE_ENABLED` | bool | `false` | - | - |  |
| `NETZ_OUI_ONLINE_MAX` | int | 10 | 0-200 | - |  |
| `NETZ_OUI_ONLINE_URL` | str | `https://api.macvendors.com` | - | - | nur bei aktiviertem Online-OUI (Datenschutz, Default aus) |
| `NETZ_SQLITE_JOURNAL` | str | `auto` | - | env-only (kein GET/PATCH/Scanner) | SQLite-Journal-Modus (`app/db.py`): `auto` = WAL per Schreibprobe, Fallback `delete` bei `disk I/O error` |

<!-- GEN:ENV-TABLE:END -->
