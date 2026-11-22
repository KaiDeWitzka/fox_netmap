# fox_netmap – Datenschutzhinweis

Stand: v1.5.2. Dieser Hinweis beschreibt, welche Daten fox_netmap erhebt, wo sie liegen, wie lange sie
gespeichert bleiben und wann Daten das lokale Netz verlassen. Er richtet sich an Betreiberinnen und Betreiber
der Software. fox_netmap ist ein selbst gehostetes Werkzeug: Es gibt **keinen Cloud-Dienst, keine Telemetrie,
kein Tracking und keine externen Schriften oder CDNs**. Alle Daten bleiben auf dem eigenen Server, solange
keine der unten genannten Ausnahmen aktiv eingeschaltet wird.

## 1. Wer ist verantwortlich?

Verantwortlich im Sinne der DSGVO ist, wer fox_netmap betreibt – nicht die Entwicklerin oder der Entwickler
der Software.

- **Privates Heimnetz:** Die Nutzung für rein persönliche oder familiäre Zwecke fällt in der Regel unter die
  Haushaltsausnahme (Art. 2 Abs. 2 lit. c DSGVO). Trotzdem gilt: Mitbewohnerinnen, Gäste und Familienmitglieder
  sollten wissen, dass ihre Geräte erfasst werden.
- **Verein, Büro, Behörde, Unternehmen:** Dann gilt die DSGVO voll. Nötig sind mindestens eine Rechtsgrundlage
  (meist Art. 6 Abs. 1 lit. f, Netzsicherheit und IT-Betrieb), ein Eintrag im Verzeichnis von
  Verarbeitungstätigkeiten (Art. 30), eine Information der Betroffenen (Art. 13) und eine Löschfrist.
  Werden Geräte von Beschäftigten erfasst, ist fox_netmap eine technische Einrichtung, die zur
  Verhaltens- und Leistungskontrolle geeignet ist: Der Betriebs- oder Personalrat ist zu beteiligen
  (§ 87 Abs. 1 Nr. 6 BetrVG bzw. die Personalvertretungsgesetze).

## 2. Welche Daten werden erhoben?

| Daten | Quelle | Personenbezug |
|---|---|---|
| MAC-Adresse, IP-Adresse (IPv4/IPv6), Subnetz | ARP/NDP, ping, TCP, TR-064, SNMP | Ja, sobald ein Gerät einer Person zugeordnet werden kann (z. B. Smartphone) |
| Hostname | DNS-Rückwärtsauflösung, mDNS, TR-064 | Oft direkt, z. B. „iPhone-von-Anna“ |
| Kategorie und Begründung (seit v1.6.0) | Hostname, Hersteller, Ports, mDNS-Dienste und -Modell (z. B. `iPhone14,2`) | Indirekt: Gerätetyp. Gespeichert wird nur das entscheidende Signal, keine mDNS-Rohdaten |
| Hersteller (OUI) | Lokale OUI-Datenbank, optional Online-Abfrage | Indirekt |
| Offene TCP-Ports und Dienstnamen | Port-Scan | Indirekt (Rückschluss auf genutzte Software) |
| Online-/Offline-Verlauf mit Zeitstempel, erste/letzte Sichtung | Jeder Scan | **Ja – ergibt bei persönlichen Geräten ein Anwesenheitsprofil** |
| Ereignisse (z. B. „neues Gerät“) | Scanner | Indirekt |
| Kategorie, Notiz, Kartenposition, Verbindung | Manuelle Eingabe | Je nach Inhalt der Notiz |
| Benutzername, Passwort-Hash (PBKDF2-SHA256) | Login-Verwaltung | Ja (Admin-Konto) |
| Login-Protokoll: Benutzername, Client-IP, Erfolg/Fehlschlag | Anwendungslog | Ja |
| Embed-Tokens mit Filter und Ablaufdatum | Einstellungen | Nein |

**Nicht** erhoben werden: Inhalte des Datenverkehrs, besuchte Webseiten, DNS-Anfragen der Geräte,
Standortdaten außerhalb des Netzes.

## 3. Wo liegen die Daten?

Ausschließlich im Datenverzeichnis `./data` (Container: `/data`) auf dem eigenen Server:

- `netmap.db` – SQLite-Datenbank mit allen Geräte-, Verlaufs- und Einstellungsdaten
- `netmap.log` – Anwendungslog (rotierend)
- `exports/` – automatische und manuelle Exporte (JSON, CSV, PDF), falls aktiviert
- `initial-admin-password.txt` – nur, wenn kein `NETZ_AUTH_PASS` gesetzt ist (Rechte 0600)

Die Dateien gehören UID 10001 und sind nicht verschlüsselt. Schutz erfolgt über Zugriffsrechte des
Servers; für Backups gilt dieselbe Vertraulichkeit wie für das Original.

**Im Browser** speichert fox_netmap ein technisch notwendiges Session-Cookie (`fox_session`, HttpOnly,
SameSite=Lax, 12 Stunden) und im `localStorage` reine Anzeige-Einstellungen: Sprache, Theme, Layout,
Tabellenspalten und -breiten, eingeklappte Gruppen. Es werden keine Tracking-Cookies gesetzt; ein
Cookie-Banner ist daher nicht erforderlich (§ 25 Abs. 2 Nr. 2 TDDDG).

## 4. Speicherdauer und Löschung

| Daten | Standard | Einstellung |
|---|---|---|
| Online-/Offline-Verlauf | 720 Stunden (30 Tage) | `NETZ_HISTORY_HOURS` bzw. Einstellungen → Historie |
| Geräte samt Ports, Verlauf, Ereignissen und Kartenposition | gelöscht nach 30 Tagen offline | `NETZ_DEVICE_RETENTION_DAYS` (0 = nie) |
| Ereignisse (auch von Geräten, die weiter online sind) | 90 Tage | `NETZ_EVENT_RETENTION_DAYS` (0 = nie), auch in den Einstellungen |
| Anwendungslog | rotierend, 4 Dateien à 1 MB | – |
| Exporte in `exports/` | unbegrenzt | manuell löschen |
| Sessions | nur im Arbeitsspeicher, max. 12 Stunden | – |
| Hersteller-Cache (`oui_cache`) | unbegrenzt, nur MAC-Präfixe | – |

Einzelne Geräte lassen sich im Detail-Panel unter **Gerät löschen** entfernen (oder per `DELETE /api/device/{mac}`). Vollständige Löschung aller Daten:
`docker compose down -v` bzw. das Verzeichnis `./data` entfernen.

## 5. Wann verlassen Daten das lokale Netz?

Nur, wenn eine der folgenden Funktionen bewusst eingerichtet wird. In der Grundeinstellung ist **keine**
davon aktiv.

| Funktion | Was wird gesendet | An wen | Standard |
|---|---|---|---|
| Online-Herstellerabfrage (`NETZ_OUI_ONLINE_ENABLED`) | erste 3 Bytes der MAC-Adresse (Herstellerkennung), max. 10 je Scan | `api.macvendors.com` oder eigene URL | **aus** seit v1.5.0 |
| Alarm-Webhook (`NETZ_NOTIFY_WEBHOOK`) | MAC, IP, Hostname, Hersteller neuer Geräte | frei konfigurierte URL | aus |
| Gotify / ntfy (`NETZ_NOTIFY_GOTIFY`, `NETZ_NOTIFY_NTFY`) | Hostname bzw. IP und MAC neuer Geräte | eigener oder öffentlicher Push-Dienst | aus |
| OUI-Datenbank aktualisieren (`scripts/update_oui.py`) | nur ein Download, keine Gerätedaten | `standards-oui.ieee.org` | manuell |
| TR-064 / SNMP (inkl. FRITZ!Box-Mesh-Liste seit v1.6.0) | Abfragen an eigene Router und Switche im lokalen Netz | lokal | TR-064 aus, SNMP an (nur lokale Geräte) |

Empfehlung: Für Benachrichtigungen einen selbst gehosteten Dienst nutzen (z. B. eigene Gotify- oder
ntfy-Instanz). Bei öffentlichen Diensten wie `ntfy.sh` sind Gerätenamen und MAC-Adressen für den Betreiber des
Dienstes und – ohne Zugriffsschutz – für jeden lesbar, der den Topic-Namen kennt.

**Einbettung (`/embed`):** Wer einen Embed-Link weitergibt, gibt die gefilterte Gerätekarte frei. Tokens
deshalb mit Ablaufdatum und engem Filter (Subnetz, Kategorie) anlegen und nur auf vertrauenswürdigen Seiten
einbinden (`NETZ_EMBED_ANCESTORS`).

## 6. Datensparsame Konfiguration (Empfehlung)

1. Nur die Subnetze scannen, die wirklich gebraucht werden (`NETZ_SUBNETS`); kein Gäste-WLAN.
2. Verlauf kurz halten, z. B. `NETZ_HISTORY_HOURS=168` (7 Tage), wenn kein Langzeitverlauf nötig ist.
3. Retention aktiv lassen (`NETZ_DEVICE_RETENTION_DAYS=30` oder kürzer).
4. Online-Herstellerabfrage aus lassen; stattdessen die lokale OUI-Datenbank aktualisieren.
5. Persönliche Geräte, für die kein Alarm nötig ist, in `NETZ_ALARM_WHITELIST` eintragen.
6. In Notizen keine Namen oder sonstigen personenbezogenen Angaben ablegen, wenn das nicht nötig ist.
7. Exporte regelmäßig löschen und Backups von `./data` geschützt aufbewahren.
8. Login aktiviert lassen und fox_netmap nicht ohne Reverse-Proxy mit HTTPS ins Internet stellen.

## 7. Rechte betroffener Personen

Betroffene haben die Rechte aus Art. 15–21 DSGVO (Auskunft, Berichtigung, Löschung, Einschränkung,
Widerspruch). Praktisch umsetzbar in fox_netmap:

- **Auskunft:** Gerät in der Tabelle suchen und als JSON/CSV exportieren.
- **Löschung:** Detail-Panel → **Gerät löschen**; damit sich ein weiter aktives Gerät nicht neu einträgt,
  Subnetz einschränken oder das Gerät aus dem Netz nehmen.
- **Widerspruch:** Subnetz ausschließen oder Gerät dauerhaft aus dem Scan herausnehmen.

## 8. Bezug zu Sicherheit und Grundschutz

Technische und organisatorische Maßnahmen (Art. 32 DSGVO) sind im [Sicherheitskonzept](03-sicherheit.md)
beschrieben. Relevante Grundschutz-Bausteine: CON.2 Datenschutz, CON.6 Löschen und Vernichten,
OPS.1.1.5 Protokollierung.
