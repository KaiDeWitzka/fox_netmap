# Changelog

Alle relevanten Änderungen an fox_netmap. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/). Frühere Versionen siehe
[GitHub-Releases](https://github.com/KaiDeWitzka/fox_netmap/releases).

## [1.5.2] – 2026-11-21

### Barrierefreiheit
- **`prefers-reduced-motion`:** Bei aktivierter Betriebssystem-Einstellung „Bewegung reduzieren“ keine Animationen
  und Übergänge mehr (WCAG 2.3.3). Der laufende Scan bleibt als ruhiger Punkt plus Text erkennbar.
- **Scan-Animation begrenzt:** Der Punkt pulsiert nicht mehr endlos, sondern dreimal (4,8 s) und bleibt dann stehen
  (WCAG 2.2.2 Pausieren, Beenden, Ausblenden).
- **Live-Region:** Der Scan-Status wird nur noch bei echter Änderung neu geschrieben; Screenreader lesen ihn nicht
  mehr alle 5 Sekunden vor.

### Datenschutz
- **Neuer [Datenschutzhinweis](docs/04-datenschutz.md):** erhobene Daten, Speicherort, Löschfristen, Datenflüsse
  nach außen, Hinweise für den Einsatz in Organisationen (DSGVO, Mitbestimmung), datensparsame Konfiguration.
- **Gerät löschen** (Recht auf Löschung, Art. 17 DSGVO): Knopf im Detail-Panel und `DELETE /api/device/{mac}`;
  entfernt Ports, Layout, Verlauf und Ereignisse und löst manuelle Zuordnungen anderer Geräte. Nur mit Login,
  nicht über Embed-Tokens.

### Design
- Druck-Feedback für Knöpfe (`scale(0.97)`, 160 ms, ease-out) – nur ohne „Bewegung reduzieren“.
- Tabellarische Ziffern (`tabular-nums`) in Gerätetabelle und Scan-Status, damit Zahlen beim Aktualisieren nicht springen.

### Dokumentation
- Handbuch (6 Sprachen): Bewegung reduzieren, Datenschutz, Gerät löschen, API-Tabelle; veraltete Angabe
  `NET_ADMIN` für den Scanner entfernt (seit v1.5.0 nur `NET_RAW`).

## [1.5.1] – 2026-11-21

### Lieferkette (Supply Chain)
- **Container-Image in GHCR:** Release-Tags veröffentlichen `ghcr.io/kaidewitzka/fox_netmap` für `linux/amd64` und
  `linux/arm64` (Tags `X.Y.Z`, `X.Y`, `X`, `latest`, `sha-…`) mit SBOM- und Provenance-Attestierung.
- **Trivy-Gate** in CI und Release: Abbruch bei fixbaren `CRITICAL`/`HIGH`-Schwachstellen im Image sowie bei
  Fehlkonfigurationen und Secrets im Repository. Trivy läuft aus einem per Digest gepinnten Image
  (`scripts/trivy.sh`), nicht über `trivy-action` (Kompromittierung März 2026).
- **SBOM** (CycloneDX und SPDX) als CI-Artefakt und als Anhang jedes GitHub-Releases, zusammen mit dem Trivy-Bericht.
- **Wöchentlicher Nachscan** des veröffentlichten Images (`image-scan.yml`).
- **Dependabot** für pip, npm, Docker und GitHub Actions (wöchentlich, gruppiert, 7 Tage Cooldown).
- **Reproduzierbarer Build:** Python-Abhängigkeiten mit SHA-256-Hashes (`pip-compile`, `--require-hashes`),
  Basis-Image per Digest, alle Actions per Commit-SHA gepinnt, `npm ci` statt `npm install`, `apt-get upgrade` im Image.
- OCI-Labels im Image (Quelle, Lizenz, Version); Release prüft, dass Tag und `app.__version__` übereinstimmen.

### Geändert
- `requirements.txt` ist jetzt eine generierte Lock-Datei; Versionsbereiche stehen in `requirements.in`.
- `release.yml` macht zusätzlich einen Probelauf (ohne Push) in Pull Requests, die Build-Dateien ändern.

## [1.5.0] – 2026-11-21

### Sicherheit
- **Container ohne root:** Web-Oberfläche und Scanner laufen als UID/GID 10001. Der Entrypoint übernimmt
  Bestandsdaten in `./data` automatisch, entfernt alle Capabilities (Scanner: nur `NET_RAW`) und startet per `setpriv`.
  Web zusätzlich mit `no-new-privileges`; beide mit schreibgeschütztem Root-Dateisystem. `NET_ADMIN` entfällt.
- **Docker-Healthcheck** (`python -m app health`): Web prüft `/api/health`, Scanner prüft, ob die Scan-Schleife läuft.
- **Passwort-Hash** PBKDF2-SHA256 mit 600.000 statt 100.000 Iterationen; alte Hashes werden beim Login umgestellt.
  Dummy-Prüfung für unbekannte Benutzer gegen User-Enumeration.
- **Sessions** werden aufgeräumt (abgelaufen, max. 200); Cookie mit `Secure` bei HTTPS (`NETZ_COOKIE_SECURE`).
- **Startpasswort** ohne `NETZ_AUTH_PASS` nur beim ersten Start, in `data/initial-admin-password.txt` (0600) statt im Log.

### Datenschutz
- Online-Herstellerabfrage (`NETZ_OUI_ONLINE_ENABLED`) standardmäßig **aus** (Privacy by Default).

### Geändert (bitte beachten)
- Dateien in `./data` gehören nach dem Update UID 10001; auf dem Host ggf. `sudo` zum Lesen nutzen.
- Ohne `NETZ_AUTH_PASS` bleibt das Passwort jetzt über Neustarts gleich (vorher bei jedem Start neu).

### CI
- Neuer Job `docker`: baut das Image, simuliert ein Upgrade mit root-eigenen Daten und prüft im laufenden
  Stack UID, Capabilities, `NoNewPrivs`, Schreibschutz, ping, Healthcheck und Login.

### Dokumentation
- Sicherheitskonzept um Passwort/Sessions, Container-Härtung und Datenschutz ergänzt; Handbuch in 6 Sprachen aktualisiert.

## [1.4.1] – 2026-11-21

### Sicherheit
- **Gespeichertes XSS in der Detailansicht behoben.** Hostname, Hersteller, Notiz, Dienstnamen und
  Ereignistexte stammen aus dem Netz (mDNS, DNS, TR-064, OUI-Online-Lookup) und wurden ungeprüft per
  `innerHTML` eingesetzt. Ein Gerät im Netz konnte so über einen präparierten Hostnamen JavaScript
  im Browser eines angemeldeten Admins ausführen. Alle Werte laufen jetzt durch `esc()`, Links nur `http(s)`.
- **HTTP-Security-Header** auf allen Antworten: Content-Security-Policy (`script-src 'self'`),
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`,
  `Permissions-Policy`, `Cross-Origin-Opener-Policy`.
- `/embed` darf weiterhin eingebettet werden; erlaubte Einbetter über neue Variable `NETZ_EMBED_ANCESTORS` (Default `*`).
- **Login-Drosselung:** 5 Fehlversuche je IP+Benutzer bzw. 20 je IP in 15 Minuten → 15 Minuten Sperre (HTTP 429).
- Längenbegrenzung für Login-Felder und Gerätenotizen.
- Inline-Skript der Login-Seite nach `static/login.js` ausgelagert (Voraussetzung für die strikte CSP).

### Behoben
- Kategorie ändern im Detail-Panel schlug in nicht-deutschen Sprachen fehl (übersetzter Name statt Schlüssel gesendet).

### Barrierefreiheit
- Beschriftungen in der Detailtabelle sind jetzt Zeilenüberschriften (`<th scope="row">`).

### Dokumentation
- Neu: [Sicherheitskonzept](docs/03-sicherheit.md) mit Bedrohungsmodell, Grundschutz-Bezug und Restrisiken.
- Neu: `SECURITY.md`, dieser Changelog. README-Versionsangabe korrigiert.
