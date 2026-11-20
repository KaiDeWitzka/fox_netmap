# fox_netmap – Anforderungen & Zielarchitektur

Ergebnis des Anforderungs-Chats (Chat 1). Grundlage für die Umsetzung in Chat 2.

## 1. Produktziel

Interaktive, bearbeitbare Karte des eigenen Heimnetzes (mehrere Subnetze/VLANs, Ziel: bis 200 Geräte), die in andere Webseiten einbettbar ist. Pro Gerät werden gesammelt: Kategorie, IP, MAC, Hostname, Hersteller (OUI), offene Ports, „Verbunden mit“ (Router/Switch). Die Karte ist durchsuchbar, filterbar, zoom-/verschiebbar, mit Klick-Details (inkl. Liste der an einem Router/Switch angeschlossenen Geräte, in der Karte hervorgehoben) und zusätzlicher Tabellenansicht. Export als PDF, JSON und CSV. Daten liegen dauerhaft in einer Datenbank und werden in regelmäßigen Zyklen aktualisiert. TR-064 wird unterstützt.

## 2. Festgelegte Entscheidungen

| Thema | Entscheidung |
|---|---|
| Ausgangslage | Sauberer Neuaufbau in `fox_netmap`; Code aus netmap v1.10.0 (foxhole) nur punktuell als Referenz, kein Weiterbasteln am alten Stand |
| Plattform | Primär standalone Docker-Container; RunTipi-Verpackung (`config.json` + `metadata/` in `foxhole`) kommt später dazu |
| Netzwerk-Umfang | Ein Heimnetz mit mehreren Subnetzen/VLANs; mehrere Standorte → Backlog |
| Skalierung | Bis 200 Geräte performant; darüber → Backlog |
| Lebendigkeit | Ping-Sweep (ICMP+ARP) über alle Subnetze; nicht pingende, aber per ARP/DHCP/mDNS sichtbare Geräte als „passiv erkannt“ |
| Ports | TCP-Connect-Scan; Default Top 1000, „alle 65535“ und eigene Liste konfigurierbar; parallelisiert |
| IPv6 | Nur IPv4; IPv6 → Backlog |
| TR-064 | Generischer TR-064-Client, FRITZ!Box zuerst getestet; Daten: Host-Liste (IP/MAC/Hostname/aktiv/Verbindungstyp LAN-WLAN), WAN-Status; Auth per Benutzer+Passwort (Env); mehrere Endpunkte via `NETZ_FRITZ_URLS` (z. B. Repeater — deren Clients werden dem Endpunkt zugeordnet) |
| „Verbunden mit“ | Priorität: manueller Override (Dropdown im Detail-Panel) > SNMP CAM + LLDP-MIB (verwaltete Switche) > TR-064-Endpunkt (Repeater) > TR-064 WLAN/LAN (virtueller WLAN-Knoten) > Gateway; unmanaged Switche ohne SNMP nur manuell bestimmbar |
| Geräte-Identität | Primärschlüssel MAC; Abgleich auch per IP: ARP-MAC gewinnt bei Konflikt gegen TR-064 (Konflikt wird geloggt), MAC-lose Funde adoptieren bekannte MAC per IP aus der DB (sonst temporärer Schlüssel `ip:<ip>`); Duplikate derselben IP werden beim Start automatisch zusammengeführt (Quelle vereint, online gewinnt, Ports/Layout bleiben) |
| OUI | Lokale OUI-Datenbank im Image (offline, DSGVO-sauber, aktualisierbar); Online-Lookup nur optionaler Fallback |
| Hostname | Kombination aus DNS-Reverse, NetBIOS, mDNS, TR-064 |
| Kategorie | Heuristik-Vorschlag (Ports, Hostname, OUI, TR-064-Typ) + manueller Override; Kategorien: Router, Switch, Server/NAS, Client, Drucker, Smart-Home/IoT, Unbekannt |
| Persistenz | SQLite (WAL) im Daten-Volume; gespeichert: Snapshot, Online/Offline-Historie, Änderungsereignisse; Historie wird nach konfigurierter Zeit getrimmt (Default 30 Tage); Geräte, die länger offline sind, werden nach `NETZ_DEVICE_RETENTION_DAYS` automatisch entfernt (Default 30, 0 = nie löschen) |
| Update-Zyklen | Intervall Default 900 s, konfigurierbar + „Jetzt scannen“-Button; Scans im Hintergrund, UI zeigt letzter/nächster Scan + Fortschritt; während eines Scans sichtbarer „Scan läuft…“-Indikator (pulsierender Punkt im Header), Geräteliste aktualisiert sich automatisch nach Scan-Ende; Änderungserkennung mit Alarm (Webhook/Gotify/Ntfy) + Whitelist bekannter Geräte |
| Tech-Stack | Python (FastAPI) + SQLite Backend; Vanilla JS + Cytoscape.js Frontend; REST-API dazwischen; eine Sprache, ein Image |
| Layout | Hierarchisches Auto-Layout nach Topologie (alternativ Force-Directed); Drag-&-Drop-Positionen werden in der DB gespeichert |
| Editieren in der Karte | Geräte verschieben, manuelles „Verbunden mit“, Notiz/Label, Icon+Farbe je Kategorie; Gruppieren nach Räumen → Backlog |
| Suche/Filter | Freitext (IP, Hostname, MAC, Hersteller, Notiz) + Filter: Kategorie, online/offline, Subnetz, „hat offene Ports“; Treffer in Karte hervorgehoben |
| Klick-Details | Side-Panel mit allen Feldern + Online/Offline-Kurzverlauf; bei Router/Switch: Liste angeschlossener Geräte + Highlight in der Karte |
| Tabellenansicht | Sortier-/filterbar (gleiches Filterset), direkt editierbar (Kategorie, Notiz, „Verbunden mit“), Spalten ein-/ausblendbar, Export-Buttons dort |
| Darstellung | Farbcodierung nach Kategorie + Status; Badge mit Port-Anzahl am Knoten; Dark/Light-Theme (persistent) |
| Embed | Dedizierte `/embed`-URL, read-only (Zoom/Pan/Klick ok), hinter Login; optionaler Share-Token mit Ablaufdatum; pro Token optional nur bestimmte Subnetze/Kategorien |
| Export | JSON (vollständiges Schema, alle oder gefilterte Geräte); CSV (UTF-8, Komma/Semikolon wählbar, Default Semikolon); PDF = druckoptimierte Ansicht (serverseitiges PDF → Backlog); optional automatische tägliche Exporte in Export-Ordner |
| Auth | App-eigener Session-Login (Default an, im LAN abschaltbar); RunTipi legt zusätzlich eigenen Login davor |
| Betrieb | Scanner im Host-Netzwerkmodus (ARP/MAC, NET_RAW/NET_ADMIN), dokumentiert; Credentials nur als Env-Variablen, nie im Klartext in DB/UI/Logs; vollständig offline betreibbar |
| Out of Scope | Kein dauerhaftes Monitoring jenseits „neues Gerät“-Alarm; keine Gerätesteuerung (WoL, Reboot); SNMP nur lesend; Sprache: Deutsch zuerst, weitere Sprachen → Backlog |

## 3. Zielarchitektur

### 3.1 Stack & Deployment (standalone, primär)

- **Image:** ein Python-Image (z. B. `python:3.12-alpine` bzw. slim), gleiche Codebasis für beide Rollen.
- **docker-compose (standalone):** zwei Services
  - `netmap` — Web + REST-API (FastAPI), Port z. B. 8399, Bridge-Netz.
  - `netmap-scanner` — Scan-Loop, `network_mode: host`, `cap_add: NET_RAW, NET_ADMIN`, schreibt in dasselbe Daten-Volume.
  - gemeinsames Volume `./data:/data` (SQLite-DB, Exporte, Config).
- **RunTipi (später):** in `foxhole/apps/netmap/` zusätzlich `config.json` (form_fields → `NETZ_*` Env-Variablen, Port, `exposable`), `docker-compose.yml` mit `x-runtipi` (`is_main` auf Web-Service, `internal_port`), `metadata/` (Logo, description). Validierung über `__tests__/apps.test.ts`.

### 3.2 Komponenten & Datenfluss

```
Scanner (zyklisch/manuell)
  → Ping/ARP, TCP-Ports, passive Quellen, TR-064, SNMP-CAM, OUI, DNS/mDNS
  → Normalisierung, Kategorie-Heuristik, Topologie-Auto, Änderungserkennung/Alarm
  → SQLite (WAL) ──reads── Web/API (FastAPI) ──REST+HTML/JS── Browser (Cytoscape.js)
                        ↑── manuelle Edits (Position, Kategorie, Notiz, Verbunden-mit, Settings, Tokens)
```

### 3.3 DB-Schema (High-Level)

- `devices` (MAC als Schlüssel, IP, Hostname, Hersteller/OUI, Kategorie, Status, Subnetz, Quelle, letzte Seen)
- `device_ports` (MAC, Port, Protokoll, Dienst, Scan-Zeitstempel)
- `device_history` (MAC, Zeitstempel, online/offline)
- `device_events` (Änderungsereignisse: neu/weg/Ports/Kategorie/Notiz geändert)
- `device_layout` (manuelle Positionen, manuelle „Verbunden mit“-Overrides)
- `device_overrides` (Kategorie, Notiz)
- `settings`, `embed_tokens` (Token, Ablauf, Selektion), `users` (Login)

### 3.4 API (Auszug)

- `GET /api/devices` (filterbar), `GET /api/device/{mac}` (inkl. Ports, Historie, Events)
- `POST /api/scan` (manueller Scan), `GET /api/scan/status` (läuft/letzter/nächster)
- `GET /api/export/json`, `GET /api/export/csv?sep=semicolon`, Druckansicht für PDF
- `PATCH /api/device/{mac}` (Kategorie, Notiz, Verbunden-mit, Position)
- `GET /embed?token=…` (read-only), `POST /api/login`, `POST /api/logout`

### 3.5 UI

- **Karte:** Cytoscape.js; hierarchisches Auto-Layout + gespeicherte Drag-Positionen; Klick → Side-Panel; Highlight der Geräte am selben Router/Switch; Freitext-Suche + Filter; Zoom/Pan; Farbcodierung Kategorie/Status; Port-Badge.
- **Tabelle:** eigene Ansicht, sortier-/filterbar, inline editierbar, Spalten wählbar, Export-Buttons.
- **Einstellungen:** Scan-Intervall, Subnetze, Port-Umfang, TR-064, SNMP, Alarm-Ziele, Theme, Login an/aus, Whitelist.
- **Theme:** Dark/Light, persistent.

## 4. Featureliste

1. Zyklischer Netzwerkscan (Intervall konfigurierbar, manueller Trigger) über mehrere Subnetze/VLANs
2. Geräte-Erkennung: IP, MAC, Hostname (DNS/NetBIOS/mDNS/TR-064), Hersteller via lokaler OUI-DB, offene Ports (TCP-Connect, konfigurierbarer Umfang), aktiv/passiv
3. TR-064-Integration (Host-Liste, WLAN-Gäste, WAN-Status)
4. Topologie: „Verbunden mit“ automatisch (SNMP-CAM/TR-064) + manueller Override
5. Kategorisierung mit Heuristik + manuellem Override
6. Interaktive Karte (Cytoscape.js): Auto-Layout + manuelle Positionen, Zoom/Pan, Suche, Filter, Klick-Details, Highlight angeschlossener Geräte
7. Tabellenansicht (sortier/filterbar/editierbar)
8. Persistenz in SQLite mit Historie und Änderungsereignissen (Aufbewahrung konfigurierbar)
9. Alarm bei neuem/unbekanntem Gerät (Webhook/Gotify/Ntfy) mit Whitelist
10. Export: JSON, CSV (Semikolon/Komma), PDF via Druckansicht; optional automatische tägliche Exporte
11. Embed via `/embed` (read-only, optional Share-Token mit Ablauf + Selektion)
12. App-eigener Login (abschaltbar), Credentials nur als Env
13. Dark/Light-Theme
14. Standalone-Docker-Betrieb; RunTipi-App als Verpackung in `foxhole`

## 5. Backlog

- Mehrere Standorte (VPN-vernetzte Netze): teilweise umgesetzt — entferntes VPN-Subnetz als weiteres `NETZ_SUBNETS` (Fund via TCP-Probe, da ICMP/ARP dort nicht greifen; MAC nur via TR-064, sonst synthetischer Schlüssel `ip:<ip>` und MAC-Anzeige „–“)
- Mehr als 200 Geräte (Performance-Optimierung)
- IPv6
- Serverseitig generiertes PDF (Karten-Snapshot + Tabelle)
- Gruppieren der Geräte nach Räumen/Etagen in der Karte
- Weitere Sprachen (Englisch zuerst)
- Online-OUI-Fallback

## 6. Out of Scope (bestätigt)

- Kein dauerhaftes Monitoring/Alarming jenseits des „neues Gerät“-Alarms
- Keine Geräte-Steuerung/-Konfiguration (kein Wake-on-LAN, kein Reboot)
- SNMP nur lesend
- Keine öffentlichen/exponierten Endpunkte ohne Auth (abgesehen von optionalen Share-Tokens)

## 7. Nächste Schritte (Chat 2: Umsetzung)

1. Projektgerüst in `fox_netmap`: Python-Package (FastAPI-App + Scanner-Modul), SQLite-Schema, `docker-compose.yml` (standalone), Dockerfile
2. Scanner: Ping/ARP, Port-Scan, OUI lokal, TR-064, SNMP-CAM, Heuristik, Topologie, Historie/Events, Alarme
3. API + Auth + Embed-Token
4. Frontend: Karte (Cytoscape.js), Side-Panel, Suche/Filter, Tabellenansicht, Einstellungen, Theme, Druckansicht
5. Exporte JSON/CSV + automatische Exporte
6. Tests + Doku; danach RunTipi-Verpackung in `foxhole`
