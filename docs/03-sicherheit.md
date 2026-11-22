# fox_netmap – Sicherheitskonzept

Stand: v1.6.1. Dieses Dokument beschreibt die umgesetzten Schutzmaßnahmen, ihren Bezug zum
BSI IT-Grundschutz und die bekannten Restrisiken. Es wird mit jedem sicherheitsrelevanten
Release fortgeschrieben.

## 1. Schutzbedarf und Bedrohungsmodell

fox_netmap inventarisiert das lokale Netz (IP, MAC, Hersteller, Hostnamen, offene Ports,
Online-Historie). Diese Daten sind für Angreifer wertvoll (Aufklärung) und teilweise
personenbeziehbar (Geräte lassen sich Personen zuordnen, Anwesenheit über Online-Historie).
Schutzbedarf: **normal bis hoch** für Vertraulichkeit, normal für Integrität und Verfügbarkeit.

Betrachtete Angreifer:

| Angreifer | Beispiel | Relevante Maßnahmen |
|---|---|---|
| Gerät im eigenen Netz | kompromittiertes IoT-Gerät setzt einen präparierten mDNS-/DHCP-Hostnamen | Ausgabe-Escaping, CSP |
| Fremde Webseite | bindet die UI per iframe ein (Clickjacking) oder liest Embed-Token über den Referer | `frame-ancestors`, `X-Frame-Options`, `Referrer-Policy` |
| Netzteilnehmer ohne Zugang | probiert Passwörter durch | Login-Drosselung, PBKDF2 |
| Dritter Online-Dienst | liefert manipulierte Herstellernamen (OUI-Lookup) | Ausgabe-Escaping, CSP |

## 2. Umgesetzte Maßnahmen

### 2.1 Ausgabe-Escaping (seit v1.4.1)

Alle Werte, die aus dem Netz oder von Benutzern stammen (Hostname, Hersteller, Notiz,
Dienstname, Ereignistexte, Kategorien), werden in `app/static/app.js` über `esc()` HTML-codiert
oder per `textContent` gesetzt. Links in der Detailansicht werden über `safeUrl()` auf `http(s)`
beschränkt. Regel für Beiträge: **kein `innerHTML` ohne `esc()`.** Der UI-Test
`tests/ui_dom_check.mjs` prüft das mit typischen XSS-Payloads.

### 2.2 HTTP-Security-Header (seit v1.4.1)

Gesetzt durch `app/security.py` auf **allen** Antworten (auch 401/303):

| Header | Wert | Zweck |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` | Zweite Verteidigungslinie gegen XSS; kein Inline-JS, keine fremden Skripte |
| `X-Frame-Options` | `DENY` (nicht bei `/embed`) | Clickjacking-Schutz für ältere Browser |
| `Referrer-Policy` | `no-referrer` | Embed-Token in der URL fließt nicht an verlinkte Seiten ab |
| `X-Content-Type-Options` | `nosniff` | Kein MIME-Sniffing |
| `Permissions-Policy` | Kamera, Mikrofon, Standort, Payment, USB aus | Minimalprinzip |
| `Cross-Origin-Opener-Policy` | `same-origin` | Isolation gegenüber geöffneten Fenstern |

`style-src 'unsafe-inline'` ist nötig, weil Cytoscape und die Spaltenbreiten der Tabelle
Inline-Styles setzen. Styles können kein JavaScript ausführen; das Restrisiko ist gering.

**Embed:** Nur `/embed` darf eingebettet werden. Erlaubte Einbetter steuert
`NETZ_EMBED_ANCESTORS` (CSP-Syntax, Default `*` = alle, für Kompatibilität mit bestehenden
Einbettungen). Empfehlung: auf die eigenen Seiten einschränken, z. B.
`NETZ_EMBED_ANCESTORS="https://wiki.example.org https://home.example.org"`.

### 2.3 Login-Drosselung (seit v1.4.1)

- 5 Fehlversuche je Kombination **Client-IP + Benutzer** in 15 Minuten → diese IP wird für
  diesen Benutzer 15 Minuten gesperrt.
- 20 Fehlversuche je **Client-IP** (beliebige Benutzer) in 15 Minuten → IP 15 Minuten gesperrt.
- Antwort während der Sperre: HTTP `429` mit `Retry-After`. Die Login-Seite zeigt einen Hinweis.
- Bewusst **nicht** pro Benutzer allein, damit ein Angreifer den Admin nicht netzweit aussperren kann.
- Erfolgreicher Login setzt den Zähler für IP+Benutzer zurück. Fehlversuche werden mit IP geloggt.
- Zustand nur im Speicher; ein Neustart setzt die Sperren zurück.
- Hinter einem Reverse Proxy sieht fox_netmap nur die Proxy-IP; `X-Forwarded-For` wird bewusst
  nicht ausgewertet (fälschbar). Dann greift faktisch die Grenze pro Benutzer über alle Clients.

### 2.4 Passwort-Hash und Sessions (seit v1.5.0)

- PBKDF2-HMAC-SHA256 mit **600.000 Iterationen** (OWASP Password Storage Cheat Sheet), 128-Bit-Salt.
  Format `pbkdf2_sha256$<iterationen>$<salt>$<hash>`. Hashes aus v1.4.x (100.000 Iterationen) bleiben
  gültig und werden beim nächsten erfolgreichen Login automatisch neu berechnet.
- Unbekannte Benutzer werden gegen einen Dummy-Hash geprüft: gleiche Antwortzeit, keine User-Enumeration.
- Sessions: 12 h Laufzeit, abgelaufene Einträge werden bei jedem Login und spätestens minütlich entfernt,
  höchstens 200 gleichzeitig (älteste zuerst verdrängt). Logout entwertet die Session serverseitig.
- Session-Cookie `fox_session`: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` gemäß
  `NETZ_COOKIE_SECURE` – `auto` (Default) setzt `Secure`, sobald die Anfrage per HTTPS kommt oder ein
  Reverse Proxy `X-Forwarded-Proto: https` meldet; `true`/`false` erzwingen bzw. unterdrücken es.
- Startpasswort: Ohne `NETZ_AUTH_PASS` wird **nur beim ersten Start** ein Zufallspasswort erzeugt und in
  `<data>/initial-admin-password.txt` mit Rechten `0600` abgelegt, nicht im Log. Spätere Starts behalten
  das Passwort. Sobald `NETZ_AUTH_PASS` gesetzt ist, wird die Datei gelöscht.

### 2.5 Container-Härtung (seit v1.5.0)

| Maßnahme | Web-Oberfläche (`netmap`) | Scanner (`netmap-scanner`) |
|---|---|---|
| Benutzer | UID/GID 10001 | UID/GID 10001 |
| Capabilities (Bounding-Set) | keine | nur `NET_RAW` (für ping) |
| `no-new-privileges` | ja | nein – ping erhält `NET_RAW` über eine Datei-Capability |
| Root-Dateisystem | schreibgeschützt, `/tmp` als tmpfs | schreibgeschützt, `/tmp` als tmpfs |
| Netzwerk | Bridge, nur Port 8399 | Host-Netzwerk (nötig für ARP/NDP) |
| Healthcheck | `GET /api/health` | Scan-Schleife darf nicht > 5 min überfällig sein |

Ablauf: Der Container startet als root nur für den Entrypoint (`docker/entrypoint.sh`). Dieser übergibt
Bestandsdaten im Daten-Volume einmalig an UID 10001 (Upgrade von v1.4.x), entfernt alle nicht benötigten
Capabilities aus dem Bounding-Set und startet die Anwendung per `setpriv` als UID 10001. `NET_ADMIN`
wird nicht mehr vergeben. Läuft der Container bereits mit `user:` als Nicht-root, startet die App direkt.
Die CI prüft UID, Capabilities, `NoNewPrivs`, Schreibschutz und ping im laufenden Compose-Stack.

### 2.6 Datenschutz (Privacy by Default, seit v1.5.0)

Die Online-Herstellerabfrage (`NETZ_OUI_ONLINE_ENABLED`) ist standardmäßig **aus**. Eingeschaltet
sendet der Scanner die ersten drei Bytes unbekannter MAC-Adressen an den konfigurierten Dienst
(Default `https://api.macvendors.com`). Wer die Funktion bereits in den Einstellungen gespeichert
hatte, behält seine Wahl. Ohne Online-Abfrage nutzt fox_netmap nur die lokale OUI-Datenbank.

### 2.7 Eingabeprüfung

- Login: Benutzername max. 128, Passwort max. 1024 Zeichen (Schutz vor teuren PBKDF2-Läufen).
- Gerätenotiz: max. 2000 Zeichen.
- Einstellungen: Wertebereiche, IP/CIDR-Syntax, Export-Ordner nur relativ im Daten-Volume,
  URLs nur `http(s)` (siehe `validate_settings` in `app/api.py`).
- SQL ausschließlich parametrisiert.

### 2.8 Bestehende Maßnahmen (vor v1.4.1)

- Passwortvergleich zeitkonstant (`hmac.compare_digest`).
- `GET /api/settings` liefert keine Secrets; FRITZ!Box-Passwort ist write-only.
- Embed-Tokens: zufällig (192 Bit), ablauffähig, filterbar, nur lesend, in der DB nur als Hash (2.12).
- Die Web-Oberfläche läuft ohne Host-Netzwerk.

### 2.9 Lieferkette (Supply Chain, seit v1.5.1)

| Maßnahme | Umsetzung |
|---|---|
| Hash-gepinnte Python-Abhängigkeiten | `requirements.txt` per `pip-compile --generate-hashes`; Installation in Image und CI nur mit `--require-hashes --no-deps` |
| Gepinntes Basis-Image | `python:3.12-slim@sha256:…`; zusätzlich `apt-get upgrade` beim Build |
| Gepinnte CI-Bausteine | Alle GitHub Actions per Commit-SHA (Versionskommentar dahinter), `npm ci` gegen `package-lock.json` |
| Trivy ohne `trivy-action` | `scripts/trivy.sh` startet `ghcr.io/aquasecurity/trivy` per Digest. Hintergrund: Am 19.03.2026 wurden Tags von `trivy-action` und `setup-trivy` sowie das Binary v0.69.4 manipuliert ([GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23), CVE-2026-33634, [BSI-Warnung](https://www.bsi.bund.de/SharedDocs/Cybersicherheitswarnungen/DE/2026/2026-237970-1032.pdf?__blob=publicationFile&v=4)). Ein Digest kann nachträglich nicht umgebogen werden. |
| Schwachstellen-Gate | CI (`docker`-Job) und Release brechen bei fixbaren `CRITICAL`/`HIGH`-Befunden ab; `trivy fs` prüft zusätzlich Dockerfile/Compose (Misconfig) und Secrets. Ausnahmen nur begründet in `.trivyignore` |
| Scan pro Merge | `main-scan.yml` läuft bei jedem Push auf `main`: Image bauen, Trivy-Gate (CRITICAL/HIGH mit Fix), SBOM (CycloneDX/SPDX) + Trivy-Bericht als Artefakt (30 Tage), dann Multi-Arch-Push als `:main` / `:sha-<sha>` nach GHCR — nur nach grünem Gate |
| Nachscan | `image-scan.yml` scannt `latest` **und** `main` wöchentlich gegen die aktuelle Schwachstellen-Datenbank |
| SBOM | CycloneDX und SPDX (Trivy) je Merge als CI-Artefakt (`main-scan-<sha>`) und je Release als Anhang; zusätzlich BuildKit-SBOM- und Provenance-Attestierung (`mode=max`) am Image in GHCR. Orientierung: BSI TR-03183-2 (SBOM-Formate CycloneDX/SPDX) |
| Updates | Dependabot wöchentlich für pip, npm, Docker, Actions; 7 Tage Cooldown gegen kurzlebige kompromittierte Releases |
| Release-Integrität | Image wird nur aus Tags gebaut, die zur App-Version passen, und nur nach grünem Test- und Trivy-Lauf gepusht |

Nicht genutzt, weil im privaten Repository ohne GitHub Advanced Security nicht verfügbar: Code-Scanning-Upload (SARIF) und GitHub-Artifact-Attestations. Ersatz: Berichte als Artefakt/Release-Anhang und BuildKit-Attestierungen in der Registry.

### 2.10 FRITZ!Box-Mesh-Abfrage (seit v1.6.0)

- Der Pfad der Mesh-Liste kommt aus der SOAP-Antwort der Box. Akzeptiert werden nur relative Pfade; absolute URLs,
  `//host` und Schemata werden abgelehnt (Schutz vor SSRF über eine manipulierte Antwort).
- Abruf nur von der konfigurierten Box, ohne Weiterleitungen, mit Zeitlimit und Größenlimit 5 MB (gestreamt).
- Der Pfad enthält eine Session-ID. Sie wird weder protokolliert noch gespeichert; Fehlermeldungen nennen nur den Statuscode.
- Ungültiges JSON oder ein Fehler führt nur zum Rückfall auf die bisherige Topologie, der Scan läuft weiter.

### 2.11 mDNS-Dienstsuche und Einordnung (seit v1.6.0)

- Eine einzelne Anfrage an die mDNS-Gruppe im lokalen Netz (Legacy Unicast, RFC 6762 Abschnitt 6.7), Laufzeit 2 s.
  Abschaltbar mit `NETZ_MDNS_ENABLED=false`.
- Antworten stammen von beliebigen Geräten im Netz und gelten als nicht vertrauenswürdig. Der Parser begrenzt
  Paketgröße (9000 Byte), Paketanzahl (2000), Datensätze je Paket (512), TXT-Werte (64 Zeichen) und
  Namenskompressions-Sprünge (16). Ein Zeiger auf sich selbst führte vorher im Hostnamen-Parser zu einer
  Endlosschleife; das ist behoben und getestet.
- Gespeichert werden nur Kategorie und Begründung (z. B. `svc:_ipp._tcp`), keine Rohdaten. Die Oberfläche gibt beides
  escaped aus (siehe 2.1).
- Zusätzlich zur Portliste werden bis zu 15 eindeutige hohe Ports je Gerät geprüft (TCP-Connect, gleiche Zeitlimits).

### 2.12 Embed-Tokens gehasht (seit v1.6.0)

- Die Datenbank enthält nur `sha256:<Hash>` des Tokens und einen Hinweis aus den ersten 6 Zeichen. Wer die
  Datenbank oder ein Backup liest, kann damit keine Karte abrufen.
- Das Token wird nach dem Erstellen genau einmal angezeigt. Die Liste zeigt nur den Hinweis, gelöscht wird über die
  Hash-ID (`DELETE /api/tokens/{id}`).
- Vorhandene Klartext-Tokens werden beim Start einmalig gehasht (idempotente Migration). Bestehende Links bleiben
  gültig.
- Bei 192 Bit Zufall reicht ein ungesalzener SHA-256; ein Wörterbuchangriff ist nicht möglich.

### 2.13 Benachrichtigungen (seit v1.6.0)

- Gotify erhält das App-Token im Header `X-Gotify-Key`, nicht mehr als `?token=` in der URL. So landet es nicht in
  Proxy- oder Zugriffslogs.
- Webhook, ntfy und Gotify folgen keinen Weiterleitungen (`follow_redirects=False`), damit Inhalte nicht an ein
  anderes Ziel gehen.
- Fehler werden protokolliert, aber nur mit Dienstname und Fehlertyp oder HTTP-Status, nie mit URL oder Token.
  Vorher wurden Fehler still verworfen.

### 2.14 SNMP ohne Standard-Community (seit v1.6.0)

- `NETZ_SNMP_COMMUNITY` hat keinen Standardwert mehr; vorher galt `public`. Ohne gesetzte Community fragt der
  Scanner kein Gerät per SNMP ab und vermerkt das im Log.
- Die Einstellungen weisen darauf hin, keine Standard-Community wie `public` zu verwenden.

### 2.15 Löschfrist für Ereignisse (seit v1.6.0)

- Ereignisse (neu, online, offline, Ports geändert) werden nach `NETZ_EVENT_RETENTION_DAYS` Tagen gelöscht,
  Standard 90, `0` = nie. Das gilt auch für Geräte, die weiter online sind (DSGVO Art. 5 Abs. 1 lit. e,
  Speicherbegrenzung). Einstellbar auch in der Oberfläche (0–3650).

### 2.16 Mehrfach-Zuordnung (seit v1.6.0)

- `POST /api/devices/connect` verlangt eine Anmeldung und nimmt höchstens 1000 MAC-Adressen an (Ziel höchstens
  64 Zeichen). Doppelte Einträge werden zusammengefasst.
- Alles oder nichts: Ist ein Gerät unbekannt oder das Ziel ungültig, wird nichts geändert (eine Transaktion).
- Das Ziel muss ein vorhandenes Gerät sein, darf nicht selbst markiert sein und darf keinen Kreis erzeugen. Die
  Prüfung folgt der bestehenden Kette über MAC und IP. Dieselbe Prüfung gilt jetzt auch für die Einzelzuordnung
  (`PATCH /api/device/{mac}`), die vorher beliebige Werte annahm.
- Jede Mehrfach-Zuordnung wird mit Anzahl und Ziel protokolliert (OPS.1.1.5).

### 2.17 Kartensymbole ohne fremde Quellen (seit v1.6.1)

- Die Knotensymbole stammen aus Lucide (ISC-Lizenz) und liegen als feste SVG-Pfade in `app/static/icons.js`.
  Es gibt keinen Abruf von CDN, Schrift- oder Symboldienst; die Oberfläche bleibt ohne Internet vollständig.
- Die Symbole werden im Browser als `data:image/svg+xml`-URI erzeugt. Die bestehende CSP erlaubt das bereits
  (`img-src 'self' data: blob:`), sie wurde nicht erweitert. In die URI fließen nur feste Pfade und die
  Farbe aus der eigenen Palette, keine Gerätedaten; ein Einschleusen über Hostnamen ist damit ausgeschlossen.
- Data-URIs gelten als gleiche Herkunft, die Zeichenfläche bleibt sauber: Der Karten-Snapshot für den
  PDF-Export (`cy.png()`) funktioniert weiter (geprüft).
- Der volle Gerätename als Tooltip wird über die Eigenschaft `title` gesetzt, nicht als HTML.
- Lizenzhinweise der Fremdkomponenten: [THIRD_PARTY.md](../THIRD_PARTY.md) (CON.8.A6, APP.6).

## 3. Bezug zum IT-Grundschutz

| Baustein / Anforderung | Umsetzung |
|---|---|
| APP.3.1.A1 Authentisierung | Login mit Drosselung, Passwort-Hashing |
| APP.3.1.A14 Schutz vertraulicher Daten | keine Secrets in API-Antworten, `no-referrer` |
| APP.3.1.A21 Sichere HTTP-Konfiguration | Security-Header, CSP |
| CON.10.A1 / A6 Webentwicklung: Ausgabe-Kodierung | `esc()`, `textContent`, UI-Test |
| ORP.4.A13 Schutz gegen Brute Force | Login-Drosselung |
| ORP.4.A8 Passwortgebrauch / Speicherung | PBKDF2 mit 600.000 Iterationen, Startpasswort nicht im Log |
| SYS.1.6.A3 / A8 / A21 Container: Rechte, Ressourcen, Härtung | Nicht-root, minimale Capabilities, Read-only-Root-FS, Healthcheck |
| DSGVO Art. 25 Privacy by Default | Online-Herstellerabfrage standardmäßig aus |
| CON.8 Software-Entwicklung (A6 Bibliotheken aus vertrauenswürdigen Quellen, A20 Prüfung von Komponenten) | Hash-gepinnte Abhängigkeiten, Trivy-Gate, SBOM |
| OPS.1.1.3 Patch- und Änderungsmanagement | Dependabot, wöchentlicher Nachscan, Patch-Releases |
| SYS.1.6.A6 / A12 Container-Images aus vertrauenswürdigen Quellen, Verteilung | Basis-Image per Digest, eigenes Image in GHCR mit Provenance |
| APP.6 Allgemeine Software (Beschaffung, Inventar) | SBOM je Release, Lizenzhinweise in `THIRD_PARTY.md` |
| CON.2 Datenschutz, CON.6 Löschen | [Datenschutzhinweis](04-datenschutz.md), Gerät löschen, Löschfristen für Geräte, Verlauf und Ereignisse |
| APP.3.1.A14 / CON.8 Schutz gespeicherter Zugangsdaten | Embed-Tokens nur als Hash, Gotify-Token im Header |
| OPS.1.1.5 Protokollierung | Login-Erfolg/-Fehlschlag mit IP im Log |

## 4. Bekannte Restrisiken

| Risiko | Bewertung / geplante Maßnahme |
|---|---|
| Embed-Token in der URL | Nötig, damit ein iframe ohne Login funktioniert. `no-referrer` verhindert den Abfluss über den Referer; Tokens laufen ab und sind nur lesend. In der DB liegt nur der Hash (2.12) |
| SNMPv2c ohne Verschlüsselung | Die Community geht im Klartext durchs Netz. Nur Read-only-Community verwenden, SNMPv3 ist nicht umgesetzt |
| Sessions nur im Speicher | Bewusst: Neustart meldet alle ab, keine Session-Daten auf der Platte |
| Scanner ohne `no-new-privileges` | Nötig für ping; Bounding-Set auf `NET_RAW` begrenzt |
| `style-src 'unsafe-inline'` in der CSP | Nötig für Cytoscape; Styles können kein JavaScript ausführen |
| Paket in GHCR privat | Solange das Repository privat ist; Pull nur mit Token (`read:packages`). Für eine Runtipi-App müsste das Paket öffentlich werden |
| Fixlose Schwachstellen im Basis-Image | Werden gemeldet, aber nicht als Gate gewertet (`--ignore-unfixed`); Abhilfe über Dependabot-Digest-Updates |

## 5. Sicherheitslücken melden

Bitte keine öffentlichen Issues für Sicherheitslücken. Meldung direkt an den Maintainer
(GitHub: @KaiDeWitzka), siehe [SECURITY.md](../SECURITY.md).
