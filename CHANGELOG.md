# Changelog

Alle relevanten Änderungen an fox_netmap. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/). Frühere Versionen siehe
[GitHub-Releases](https://github.com/KaiDeWitzka/fox_netmap/releases).

## [Unreleased]

### Neu
- **VPN-Erkennung:** TR-064-Schnittstellentyp „VPN“ (z. B. FRITZ!Box IPSec .201) markiert Geräte als
  VPN-Client — protokollbasiert, ohne Pool-Annahme. Optional zusätzlich Adresspool-Heuristik über das
  neue Setting `vpn_pool` (`NETZ_VPN_POOL`, Default `off`; `auto` = FRITZ!-Konvention: letzte Oktett ≥ 201
  im /24 des Gateways; auch CIDRs und Bereiche `a-b`, kommagetrennt). Damit lassen sich auch
  WireGuard-Peers (.202) erfassen, die TR-064 nicht meldet.
- **Anzeige:** VPN-Geräte tragen ein „VPN"-Badge in der Tabelle, einen gestrichelten Rand in der Karte,
  eine Zeile „VPN-Verbindung“ im Detail-Panel und ein `vpn`-Feld in JSON/CSV/API. Neue Spalte
  `devices.vpn` (DB-Migration automatisch).
- **Alarme:** VPN-Geräte lösen keinen „neues Gerät“-Alarm aus (kommen und gehen mit dem Tunnel);
  sie werden stattdessen als „neues VPN-Gerät (kein Alarm)“ ins Log geschrieben.
- **Export:** `link_port` (konkreter Anschluss am Elternknoten aus dem FRITZ!Box-Mesh, z. B. `LAN:2`
  oder `AP:5G:0`) ist jetzt auch in JSON- und CSV-Export enthalten.

## [1.6.2] – 2026-11-22

Versionsnummer im UI-Header und IPv6-Adresse pro Gerät (PR #67).

### Neu
- **Versionsnummer im Header:** `fox_netmap vX.Y.Z` neben dem Titel; die Nummer kommt aus `/api/meta`
  und ändert sich mit jedem Release automatisch.
- **IPv6 pro Gerät:** IPv6-Adresse aus dem NDP-Cache über die MAC-Adresse zugeordnet (Link-Local-Adressen
  `fe80::` ausgeschlossen) in neuer Spalte `devices.ip6`. Sichtbar im Detail-Panel, in JSON/CSV-Export
  und API. Die Datenbank-Migration legt die Spalte beim Start automatisch an.

### Hinweise zum Update
- Keine Konfigurationsänderung nötig; bestehende Datenbanken werden migriert (`devices.ip6`).

## [1.6.1] – 2026-11-22

Neues Knotendesign der Karte nach dem Soll-Entwurf ([Plan](docs/plaene/v1.6.1-knotendesign.md)).

### Geändert
- **Knoten:** neutraler Kreis mit Kategorie-Symbol (Lucide, lokal in `app/static/icons.js`) statt farbiger Fläche
  und Emoji. Hubs (Router, Switch, Repeater/AP, Server/NAS, Internet) 40 px, Endgeräte 34 px. Für Clients
  Feinsymbole Laptop, Tablet und Spielkonsole.
- **Beschriftung zweizeilig:** Name (ab 20 Zeichen gekürzt, voller Name als Tooltip) und `IP · Kategorie`,
  dazu `(+N)` und `· offline`. Internet-Knoten mit `WAN <IP>`. Emojis aus allen sechs Sprachen entfernt.
- **Gateway als Wurzel** mit Ring in Akzentfarbe, nur für das Gerät mit der Gateway-IP. Repeater mit hellem Rand.
- **Offline:** Körper abgeblendet und gestrichelt, Beschriftung bleibt lesbar (vorher Deckkraft auf alles).
- **Kanten:** gerade, LAN durchgezogen, WLAN gestrichelt, Powerline gepunktet, zwischen Standorten blasser.
- **Subnetz-Rahmen:** Beschriftung `Subnetz · Standort (Anzahl)`.
- **Baum-Layout:** größere Abstände für die zweizeiligen Beschriftungen.
- **Übergänge** 150 ms für Auswahl und Hervorhebung, entfallen bei „Bewegung reduzieren“.

### Neu
- **Legende** unten links, einklappbar (`<details>`, Zustand in `localStorage` `fox_legend`, standardmäßig zu).
- **Tabelle:** Kategorie-Symbol vor dem Text; Druckansicht ohne Auswahlspalte und Mehrfach-Leiste.
- `THIRD_PARTY.md` mit den Lizenzen von Cytoscape.js, Lucide und Feather.

### Barrierefreiheit
- Kategorie nicht mehr nur über Farbe erkennbar (WCAG 1.4.1). Kontraste in beiden Themes automatisch geprüft:
  Text ≥ 4,5:1, Ränder und Symbole ≥ 3:1 (WCAG 1.4.3, 1.4.11).

### Sicherheit und Datenschutz
- Keine externen Quellen: Symbole als `data:`-URI aus festen Pfaden, CSP unverändert. Karten-Snapshot für den
  PDF-Export funktioniert weiter. Sicherheitskonzept §2.17, Datenschutzhinweis ergänzt.

### Dokumentation
- Benutzerhandbuch in sechs Sprachen (§2, §3, §18) mit echten Karten-Aufnahmen hell und dunkel, README mit Bild.

### Hinweise zum Update
- Keine Datenbank- oder Konfigurationsänderung. Gespeicherte Kartenpositionen bleiben; wer das neue Baum-Layout mit
  den größeren Abständen sehen will, nutzt den Knopf **↺ Layout**.
- Die API ist unverändert; Emojis gab es nur in der Oberfläche.

## [1.6.0] – 2026-11-22

Fasst die Vorab-Versionen rc.1 bis rc.3 zusammen und ergänzt die Mehrfach-Zuordnung. Erste Version der Reihe 1.6
mit `latest`.

### Überblick
- **Topologie:** FRITZ!Box-Mesh über TR-064, Anzeige von Anschluss und WLAN-Band, Switch-Heuristik (rc.1).
- **Gerätekategorien:** Punktesystem, mDNS-Dienstsuche, drei neue Kategorien, „Erkannt über“ (rc.2).
- **Sicherheit und Datenschutz:** Löschfrist für Ereignisse, gehashte Embed-Tokens, Gotify-Token im Header, SNMP
  ohne Standard-Community (rc.3).

### Neu: Mehrfach-Zuordnung von Hand
- In der Tabelle lassen sich Geräte über eine Auswahlspalte markieren (Kopf-Kästchen = alle) und gemeinsam einem
  Router, Switch oder Repeater zuordnen; `auto` hebt die manuelle Zuordnung auf. Neue Schnittstelle
  `POST /api/devices/connect`.
- Alles oder nichts in einer Transaktion. Unbekannte Geräte, unbekannte Ziele, Selbstbezug und Kreise werden
  abgelehnt; der Kreis-Test folgt der Kette über MAC und IP.
- Barrierefreiheit: Kästchen mit eindeutiger Beschriftung je Gerät, Leiste als beschriftete Gruppe, Ergebnis per
  `role="status"`, bedienbar mit Tab und Leertaste, ohne die Detailansicht zu öffnen.

### Geändert
- Die Einzelzuordnung im Detail-Panel (`PATCH /api/device/{mac}`) prüft jetzt ebenfalls, ob das Ziel existiert und
  keinen Kreis bildet. Vorher wurde jeder Wert gespeichert.

### Hinweise zum Update
- Gilt alles aus den Abschnitten rc.1 bis rc.3, vor allem: `NETZ_SNMP_COMMUNITY` setzen, wenn SNMP genutzt wird;
  vorhandene Embed-Tokens bleiben gültig, sind aber nicht mehr anzeigbar; Ereignisse älter als 90 Tage werden
  gelöscht (`NETZ_EVENT_RETENTION_DAYS=0` behält sie).
- Wer per API eine Zuordnung auf eine IP oder ein nicht vorhandenes Gerät setzt, erhält jetzt `422`. Bereits
  gespeicherte Zuordnungen bleiben unverändert.

## [1.6.0-rc.3] – 2026-11-22

Dritte Vorab-Version. Wird nicht als `latest` markiert.

### Sicherheit und Datenschutz
- **Löschfrist für Ereignisse:** Ereignisse werden nach `NETZ_EVENT_RETENTION_DAYS` Tagen gelöscht (Standard 90,
  `0` = nie), auch bei Geräten, die weiter online sind. Einstellbar in der Oberfläche.
- **Embed-Tokens gehasht:** In der Datenbank liegt nur noch ein SHA-256-Hash. Das Token wird nur einmal nach dem
  Anlegen angezeigt, die Liste zeigt die ersten 6 Zeichen. Löschen über `DELETE /api/tokens/{id}`.
- **Gotify-Token im Header** `X-Gotify-Key` statt in der URL. Benachrichtigungen folgen keinen Weiterleitungen;
  Fehler werden ohne URL und Token protokolliert statt still verworfen.
- **SNMP ohne Standard-Community:** `NETZ_SNMP_COMMUNITY` ist standardmäßig leer statt `public`. Ohne Community
  wird SNMP übersprungen, mit Hinweis im Log und in den Einstellungen.

### Hinweise zum Update
- Wer SNMP mit `public` genutzt hat, ohne die Community zu setzen, muss `NETZ_SNMP_COMMUNITY` jetzt setzen
  (Umgebung oder Einstellungen). In der Oberfläche gespeicherte Werte bleiben erhalten.
- Vorhandene Embed-Tokens werden beim Start gehasht. Bestehende Links bleiben gültig, das vollständige Token ist in
  der Liste aber nicht mehr sichtbar. Wer es nicht mehr hat, legt ein neues an.
- Beim ersten Scan werden Ereignisse älter als 90 Tage gelöscht. Wer sie behalten will, setzt vorher
  `NETZ_EVENT_RETENTION_DAYS=0`.

## [1.6.0-rc.2] – 2026-11-22

Zweite Vorab-Version. Wird nicht als `latest` markiert.

### Gerätekategorien
- **Drei neue Kategorien:** Repeater/AP, Mobilgerät, Multimedia (TV, Streaming, Konsole, Lautsprecher).
- **Punktesystem statt „erster Treffer gewinnt“:** Standard-Gateway > FRITZ!Box-Mesh-Rolle > mDNS-Modell > Hostname >
  mDNS-Dienst > Hersteller > Ports > private WLAN-Adresse. Details im Handbuch §11.
- **mDNS-Dienstsuche (DNS-SD):** eine Anfrage im lokalen Netz erkennt Drucker (`_ipp`), Cast-Geräte, AirPlay,
  HomeKit, Sonos und Apple-Modelle (`iPhone…`, `MacBook…`, `AppleTV…`).
- **Hostnamen nur am Wortanfang:** `string` ist kein Ring-Gerät, `honest` kein Nest mehr. Neue Muster u. a. für
  iPhone, iPad, Mac, PS5, webOS-TV, MagentaTV, HP-Standardnamen (`NPI…`) und Brother (`BRW…`).
- **Ports:** 53 allein macht kein Gerät mehr zum Router, SMB (445) allein gilt als Client. Zusätzlich werden 15
  eindeutige hohe Ports geprüft (z. B. 62078 iOS, 8009 Cast, 1400 Sonos), außer bei eigener Liste in `NETZ_PORTS`.
- **AVM-Geräte** außer dem Gateway gelten als Repeater/AP statt als Router.
- **„Erkannt über“** in der Detailansicht zeigt das entscheidende Signal (neue Spalte `devices.category_reason`).
  Eine von Hand gesetzte Kategorie hat weiter Vorrang.
- Repeater/AP zählt in Karte und Details als Netzknoten (Kinder-Liste, Baum).

### Hinweis zum Update
Beim ersten Scan nach dem Update werden alle Geräte ohne manuelle Kategorie neu eingeordnet. Durch die zusätzlichen
Ports kann einmalig das Ereignis „Ports geändert“ erscheinen.

### Sicherheit
- **Behoben:** Ein manipuliertes mDNS-Paket mit Zeiger-Schleife konnte den Hostnamen-Parser in eine Endlosschleife
  bringen. Jetzt höchstens 16 Sprünge; dazu Grenzen für Paketgröße, Paketzahl, Datensätze und TXT-Länge.

## [1.6.0-rc.1] – 2026-11-22

Vorab-Version zum Testen an einer echten FRITZ!Box. Wird nicht als `latest` markiert.

### Topologie
- **FRITZ!Box-Mesh über TR-064:** fox_netmap liest die Mesh-Liste der Box (`X_AVM-DE_GetMeshListPath`) und ordnet
  Geräte ihrem tatsächlichen Anschluss zu: Repeater, LAN-Port oder WLAN-Band. Priorität jetzt manuell > SNMP >
  Mesh > TR-064-Repeater > WLAN > Gateway. Abschaltbar mit `NETZ_FRITZ_MESH=false`. Benötigt laut AVM das Recht
  „App“ oder „Phone“ für den TR-064-Benutzer.
- **Switch-Heuristik:** Sieht die Box an einem LAN-Port mehrere Geräte und ist genau eines davon ein Switch, hängen
  die übrigen am Switch. Bei zwei Switches am selben Port bleibt alles beim Router.
- **Anschluss in der Detailansicht**, z. B. `WLAN · 5 GHz` oder `LAN · LAN 1` (neue Spalte `devices.link_port`,
  automatische Migration).

### Behoben
- **WLAN-Erkennung über TR-064 griff nie:** Die Box meldet den Schnittstellentyp als `802.11`, nicht als `wlan`.
  Jetzt werden `Ethernet`, `802.11` und `HomePlug` korrekt als `lan`, `wlan` und `plc` erkannt.

### Sicherheit
- Mesh-Abruf nur über relative Pfade (SSRF-Schutz), ohne Weiterleitungen, max. 5 MB; Session-ID wird nicht protokolliert.

### CI
- Tags mit Vorab-Kennung (z. B. `v1.6.0-rc.1`) erzeugen ein GitHub-Pre-Release und kein `latest`-Image.

## [1.5.4] – 2026-11-22

### Karte
- **Baum als Standard-Layout:** `auto` ordnet die Karte jetzt hierarchisch nach der Topologie an (Internet → Router →
  Switch/Repeater → Endgeräte), wie in den Anforderungen festgelegt. Bisher lief ein Kräfte-Layout (`cose`), das ein
  Netz mit vielen Geräten an einem Knoten als Strahlenkranz mit überlappenden Labels zeigte. Viele Endgeräte an
  einem Knoten stehen kompakt im Raster darunter, Geräte ohne Zuordnung unter dem Baum. `tree` nutzt dasselbe
  Verfahren, `force` bleibt als Kräfte-Layout wählbar. Gespeicherte Positionen haben in `auto` weiter Vorrang.
- **Kanten zeigen vom Vorgänger zum Gerät** (vorher umgekehrt). WLAN-Kanten gestrichelt, Internet-Anbindung kräftiger.

### Behoben
- **Router erschien doppelt als virtueller „Gateway“-Knoten:** Ein `connected_to` mit IP-Adresse wurde nicht auf das
  passende Gerät abgebildet. Jetzt gilt: MAC, IP, dann Hostname eines bekannten Geräts; nur ohne Treffer entsteht ein
  virtueller Gateway-Knoten. Die FRITZ!Box ist damit die Wurzel unter „Internet“.
- **Subnetz-Gruppierung blendete Kanten aus:** Bei aktiver Gruppierung (ab 25 Geräten automatisch) entfielen alle Kanten
  innerhalb eines Subnetzes; Kanten zwischen Subnetzen liefen nur von Rahmen zu Rahmen. Die Kanten zwischen Geräten
  bleiben jetzt erhalten.
- Kanten zu ausgeblendeten Geräten (z. B. „Nur online“) erzeugen keine falschen „Gateway“-Knoten mit MAC-Adresse mehr.

### Aus PR #59 (nach v1.5.3 gemergt)
- Auto-Subnetzgruppen ab > 25 Geräten, Labels unter Zoom 0,85 nur für Hubs, „Nur online“ standardmäßig an.

### Dokumentation
- Handbuch §3 und §12 (6 Sprachen): Layout, Kantenrichtung, Gruppierung; Steuerzeichen im deutschen Handbuch entfernt.

## [1.5.3] – 2026-11-21

Nachgetragen (Releases aus PR #55, #57, #58).

### Geändert
- PDF-Export ohne Überlappung, Ausrichtung hoch/quer wählbar (`POST /api/export/pdf`).
- Log-Ansicht mit Level-Farben (XSS-sicher), Karten-Entzerrung (kompaktere Knoten, dünnere Kanten, Labels ab Zoom 0,85).

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
