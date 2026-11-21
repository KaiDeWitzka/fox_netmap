# Changelog

Alle relevanten Änderungen an fox_netmap. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/). Frühere Versionen siehe
[GitHub-Releases](https://github.com/KaiDeWitzka/fox_netmap/releases).

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
