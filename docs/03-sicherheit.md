# fox_netmap – Sicherheitskonzept

Stand: v1.4.1. Dieses Dokument beschreibt die umgesetzten Schutzmaßnahmen, ihren Bezug zum
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

### 2.4 Eingabeprüfung

- Login: Benutzername max. 128, Passwort max. 1024 Zeichen (Schutz vor teuren PBKDF2-Läufen).
- Gerätenotiz: max. 2000 Zeichen.
- Einstellungen: Wertebereiche, IP/CIDR-Syntax, Export-Ordner nur relativ im Daten-Volume,
  URLs nur `http(s)` (siehe `validate_settings` in `app/api.py`).
- SQL ausschließlich parametrisiert.

### 2.5 Bestehende Maßnahmen (vor v1.4.1)

- Passwörter als PBKDF2-SHA256 mit Salt, Vergleich zeitkonstant (`hmac.compare_digest`).
- Session-Cookie `fox_session`: `HttpOnly`, `SameSite=Lax`, 12 h Laufzeit.
- `GET /api/settings` liefert keine Secrets; FRITZ!Box-Passwort ist write-only.
- Embed-Tokens: zufällig (192 Bit), ablauffähig, filterbar, nur lesend.
- Scanner-Container mit minimalen Capabilities (`NET_RAW`, `NET_ADMIN`); die Web-Oberfläche
  läuft ohne Host-Netzwerk und ohne Zusatzrechte.

## 3. Bezug zum IT-Grundschutz

| Baustein / Anforderung | Umsetzung |
|---|---|
| APP.3.1.A1 Authentisierung | Login mit Drosselung, Passwort-Hashing |
| APP.3.1.A14 Schutz vertraulicher Daten | keine Secrets in API-Antworten, `no-referrer` |
| APP.3.1.A21 Sichere HTTP-Konfiguration | Security-Header, CSP |
| CON.10.A1 / A6 Webentwicklung: Ausgabe-Kodierung | `esc()`, `textContent`, UI-Test |
| ORP.4.A13 Schutz gegen Brute Force | Login-Drosselung |
| OPS.1.1.5 Protokollierung | Login-Erfolg/-Fehlschlag mit IP im Log |

## 4. Bekannte Restrisiken (geplant für v1.5.0)

| Risiko | Geplante Maßnahme |
|---|---|
| Sessions nur im Speicher, ohne Aufräumen; Cookie ohne `Secure`-Flag | Ablauf-Bereinigung, `Secure` bei HTTPS |
| PBKDF2 mit 100.000 Runden (OWASP 2023: 600.000) | Rundenzahl erhöhen bzw. Argon2id, transparente Migration |
| Embed-Token in der URL und im Klartext in der DB | Token gehasht speichern |
| Container läuft als root, kein Healthcheck | Non-root-User für die Web-Oberfläche, `HEALTHCHECK` |
| Online-OUI-Lookup standardmäßig an (MAC-Präfixe an macvendors.com) | Default aus (Privacy by Default), Datenschutzhinweis |
| Startpasswort im Klartext im Container-Log | Einmal-Datei im Daten-Volume statt Log |
| SNMP-Community-Default `public` | Kein Default, Hinweis in der UI |

## 5. Sicherheitslücken melden

Bitte keine öffentlichen Issues für Sicherheitslücken. Meldung direkt an den Maintainer
(GitHub: @KaiDeWitzka), siehe [SECURITY.md](../SECURITY.md).
