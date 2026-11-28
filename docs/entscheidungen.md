# Entscheidungsvermerke der Produktionsreife-Kampagne (W7/W8)

Vermerke zu Befunden, die bewusst **nicht** im Code umgesetzt werden (UEBERGABE Abschnitt 7.7,
Q-13/Q-12/Q-16). Verhalten aendert sich dadurch nicht.

## Q-13 – Benennung (Kategorien, Logger, Präfix) bleibt, wie sie ist

- **Fakt:** Kategorien (`Router`, `Drucker`, `Mobilgerät`, …) sind gespeicherte deutsche
  Anzeigetexte in `devices.category`; eine Umbenennung oder Umstellung auf sprachneutrale IDs
  verlangt eine Datenmigration plus Änderungen an API, UI und allen sechs Handbüchern.
  Logger heißen teils `fox_netmap.*`, teils `netmap.*`; das Env-Präfix ist `NETZ_`.
- **Entscheidung (W7):** In dieser Kampagne nur dokumentieren. Sprachneutrale Kategorie-IDs mit
  Übersetzungsetiketten sind eine eigene Kampagne (Datenmigration + UI + Doku), kein Nebenprodukt
  der Produktionsreife.
- **Konvention für neuen Code:** neue Module/Funktionen auf Englisch, neue Log-Namen unter
  `fox_netmap.*`, neue Env-Variablen mit `NETZ_`-Präfix.

## Q-12 – `/api/rooms` bleibt vorerst erhalten

- **Fakt:** Von 26 API-Routen hat nur `/api/rooms` keinen Bezug in `app/static` (das Frontend
  nutzt Räume nur als Filter-Query und PATCH-Feld). `/api/health` dient dem Docker-HEALTHCHECK.
- **Entscheidung (W7):** Route bleibt (API-Stabilität für externe Nutzer); sie ist in
  `tests/test_routes_inventory.py::test_no_unreferenced_routes` als bewusst gehalten
  (KEEP-Liste) dokumentiert. Ersatz durch eine Raumliste im Frontend bzw. Entfernung ist für
  eine kommende größere Version vorgesehen.

## Q-16 – Doppelpfade `subnet`/`subnets` und `fritz_url`/`fritz_urls`

- **Wahrheitsquelle (Dokumentation):** Umgebung ist der Startwert, die Datenbank ist die
  Laufzeitüberschreibung (`effective_settings` in `app/config.py`).
- **Umgesetzt in W7:** Datenbank-Altzeilen `subnet`/`fritz_url` werden beim Start automatisch
  auf die kanonischen `subnets`/`fritz_urls` migriert und gelöscht
  (`db._migrate_setting_aliases`, Test `test_settings_schema.py::test_legacy_alias_migrated`).
- **Noch offen (bewusst):** die Env-Aliase `NETZ_SUBNET` und `NETZ_FRITZ_URL` bleiben als
  deprecated kompatibel (`Settings.subnet`/`fritz_url` in `app/config.py`); sie werden in einer
  größeren Version zusammen mit der Datenmigration entfernt.

## D-3 – `/docs` und `/openapi.json` werden abgeschaltet (W8)

- **Fakt:** FastAPI registriert `/docs` und `/openapi.json` standardmäßig — hinter dem Login
  geschützt, aber bei `NETZ_AUTH_ENABLED=false` öffentlich erreichbar.
- **Entscheidung (W8):** `docs_url=None, openapi_url=None` in `app/web.py::create_app`. Die Doku
  liegt versioniert im Repo unter `docs/`; eine automatisch generierte API-Doku ohne Review ist
  kein Mehrwert. Nachweis: `tests/test_docs.py::test_docs_url_disabled`.

## E-8 – Containerlandschaft-Scan über die Docker Engine API, read-only (Backlog #112 #12)

- **Fakt:** Container sind ohne Engine-API nicht zuverlässig erkennbar: Port 2375/2376 zeigt nur
  den Docker-Host, nicht die Container. Bridge-Scans (172.16.0.0/12) finden Container-IPs nur im
  selben L2-Segment. Der Docker-Socket (`/var/run/docker.sock`) im Scanner-Container wäre
  root-äquivalent am Host und wird **nicht** gemountet.
- **Entscheidung:** Scan über die Engine-API (2376/TLS bevorzugt, 2375 fallback), ausschließlich
  read-only Endpunkte (`/version`, `/info`, `/containers/json?all=1`, `/networks`), optional
  `Authorization: Bearer` via `NETZ_DOCKER_TOKEN` (secret, nie geloggt). Hosts entweder explizit
  (`NETZ_DOCKER_HOSTS`) oder auto-detektiert über offene Ports 2375/2376 im Port-Scan.
  `NETZ_DOCKER_ENABLED` default **aus** (API ist root-äquivalent am Host; Doku-Warnung in
  `docs/03-sicherheit.md`). Container werden als Geräte mit synthetischer MAC `ip:<ip>`,
  Kategorie `Container`, „verbunden mit" = Docker-Host. Host-Network-Container werden übersprungen.
- **Später:** Proxmox VE über eigene API (Backlog #13), Kubernetes als eigener Punkt (Backlog #15).

## E-9 – Proxmox VE über die REST-API, read-only, API-Token statt Passwort (Backlog #112 #13)

- **Fakt:** VMs und Container (CTs) auf Proxmox VE sind per ARP/Port-Scan nicht zuverlässig von anderen Geräten
  unterscheidbar; die PVE-API liefert dagegen verlässliche Namen, VMIDs, MAC-Adressen und Typen. Ein PVE-API-Token
  kann admin-äquivalent sein; Passwörter sollen nicht gespeichert werden (Grundschutz/DSGVO: minimale Credentials,
  keine Klartext-Passwörter in der DB).
- **Entscheidung:** Anbindung über die PVE-REST-API (`https://host:8006/api2/json`), ausschließlich read-only GETs
  (`/nodes`, `/nodes/{node}/qemu`, `/nodes/{node}/lxc`), Authentifizierung per API-Token im `PVEAPIToken`-Header.
  Neue Einstellungen in einem eigenen Abschnitt "Proxmox VE": `NETZ_PVE_ENABLED` (default **aus**), `NETZ_PVE_URLS`
  (kommagetrennt, Default-Port 8006), `NETZ_PVE_USER` (`user@realm`), `NETZ_PVE_TOKEN_ID` (`user@realm!name`),
  `NETZ_PVE_TOKEN_SECRET` (Secret, nie geloggt, in der UI write-only), `NETZ_PVE_INSECURE_TLS` (WARN beim Scan,
  MITM-Risiko). Validierung in `app/validation.py::validate_patch` inkl. Querfeldprüfung gegen den Ist-Zustand
  (aktiv nur mit kompletter Konfiguration); URLs mit `user:pass@` werden abgelehnt (S-8). Doku:
  `docs/03-sicherheit.md` §2.19. Scanner-Stage (`app/scanner/pve.py`, Anreicherung der Geräte per MAC) folgt als
  eigener Schritt.
- **Später:** Kubernetes (Backlog #15), verschachtelte Container-Ansicht (#16), Docker-Bridge-Fallback (#17).
