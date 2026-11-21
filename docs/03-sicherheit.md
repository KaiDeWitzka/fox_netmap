# fox_netmap – Sicherheitskonzept

Stand: v1.5.0. Dieses Dokument beschreibt die umgesetzten Schutzmaßnahmen, ihren Bezug zum
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
- Embed-Tokens: zufällig (192 Bit), ablauffähig, filterbar, nur lesend.
- Die Web-Oberfläche läuft ohne Host-Netzwerk.

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
| OPS.1.1.5 Protokollierung | Login-Erfolg/-Fehlschlag mit IP im Log |

## 4. Bekannte Restrisiken

| Risiko | Bewertung / geplante Maßnahme |
|---|---|
| Embed-Token in der URL und im Klartext in der DB | Geplant v1.6.0: Token gehasht speichern, nur einmal anzeigen |
| SNMP-Community-Default `public` | Geplant v1.6.0: kein Default, Hinweis in der UI |
| Sessions nur im Speicher | Bewusst: Neustart meldet alle ab, keine Session-Daten auf der Platte |
| Scanner ohne `no-new-privileges` | Nötig für ping; Bounding-Set auf `NET_RAW` begrenzt |
| `style-src 'unsafe-inline'` in der CSP | Nötig für Cytoscape; Styles können kein JavaScript ausführen |
| Image-Build, Schwachstellen-Scan, SBOM | Geplant (Punkt 3): GHCR-Veröffentlichung, Trivy, Dependabot, SBOM |

## 5. Sicherheitslücken melden

Bitte keine öffentlichen Issues für Sicherheitslücken. Meldung direkt an den Maintainer
(GitHub: @KaiDeWitzka), siehe [SECURITY.md](../SECURITY.md).
