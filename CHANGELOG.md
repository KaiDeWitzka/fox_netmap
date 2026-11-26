# Changelog

## [Unreleased]

Produktionsreife Welle 1 (Bausteine, siehe docs/produktionsreife/UEBERGABE.md):
- Neues zentrales Einstellungs-Schema `app/settings_schema.py`; `GET /api/settings` liefert getypte Werte und Secrets nur noch als `{"configured": true}` (nie Klartext) (S-8)
- Gespeicherte Einstellungen werden beim Start von Web UND Scanner uebernommen (`effective_settings`, C-1); ungueltige DB-Werte loggen WARNING statt still auf Default zu fallen (SF-4); leerer String ueberschreibt Umgebung bewusst (C-2), leere Altzeilen werden migriert
- `auth_enabled` ist nicht mehr per UI/PATCH schaltbar, nur noch `NETZ_AUTH_ENABLED` (S-9/E-2) - der Schalter in den Einstellungen wirkungslos, UI-Anpassung folgt in W5
- TR-064-Endpunktwechsel verwirft ein gespeichertes `fritz_pass` bzw. verlangt bei Env-Passwort Neueingabe im selben PATCH (S-7); URLs mit Zugangsdaten (user:pass@) werden abgelehnt (S-8)
- `docker-compose.yml` reicht alle `NETZ_*`-Variablen durch, `.env.example` neu (D-2); `snmp_switches` wirkt jetzt auch im Scanner (N-2)
- Eine MAC-Normalisierung in `app/netutil.py`; API-Pfad `/api/device/{mac}` case-insensitive, `ip:`-Platzhalter unveraemmelt (Q-9, C-15, N-3)
- Logger `fox_netmap.notify`/`fox_netmap.mdns` landen in `netmap.log` und im Log-Reiter (Q-8)
- Welle 2 (Sicherheit): Embed-Token-Scope gilt ueberall - `/api/device/{mac}?token=` antwortet bei fremden Geraeten mit 404, Multi-Subnetz-Tokens zeigen alle erlaubten Subnetze, angefragte Werte ausserhalb erweitern den Scope nie (S-1/C-7/T-5)
- `/api/meta`, `/api/sites`, `/api/scan/status` und `/api/health` ohne Login nicht mehr erreichbar bzw. auf `{"status": "ok"}` gekuerzt (S-10); `POST /api/export/pdf` hatte keinen Login-Schutz (T-1)
- CSV-Export schuetzt Freitextfelder vor Formelinjection (`'`-Praefix bei =,+,-,@,Tab,CR) (S-3); PDF-Export deckelt Bilder auf 16 Megapixel und akzeptiert mit Embed-Token kein Bild, `mem_limit` in Compose (S-6)
- Login-Drossel zaehlt parallele Versuche mit (pending unter Lock), richtiges Passwort hebt eine Sperre auf (S-4/S-5); Embed-Tokens werden im uvicorn-Accesslog geschwaerzt (S-12); `X-Forwarded-For` wird ohne `NETZ_FORWARDED_ALLOW_IPS` nicht ausgewertet (S-13)
- mDNS-Rueckwaertsaufloesung akzeptiert nur passende Eigentuemer/Quellen und bereinigt Namen (S-11); Online-OUI ohne Redirects, 4-KB-Lesecap, 128 Zeichen, keine Loopback/Link-Local-Ziele, Protokollfehler brechen den Scan nicht mehr ab (S-14/N-5); TR-064 deckelt Host-Anzahl (4096) und Antwortgroesse (1 MB), kaputte Zahlen -> TR064Error (S-15)
- CSRF: unsichere Methoden mit Sitzungscookie brauchen passenden Origin/Referer (S-16); `umask 077` + DB/Log 0600 (S-17); `expires_hours` fuer Embed-Tokens validiert (C-10)
- E-3 (Kais Wahl C): TR-064-HTTPS-zu-HTTP-Fallback bleibt bestehen (WARN je Lauf); Restrisiko wird in W8 in `docs/03-sicherheit.md` Abschnitt 4 dokumentiert - kein Code-Eingriff in W2

Produktionsreife Welle 3 (Datenbank + Nebenlaeufigkeit, siehe docs/produktionsreife/UEBERGABE.md):
- Geraete-Zusammenfuehrung neu in `app/dedupe.py`: nur noch `ip:`-Platzhalter werden in die echte MAC derselben IP eingemischt (Quellen vereint, "online" gewinnt, juengster last_seen); zwei echte MACs auf derselben IP werden nie verschmolzen - sonst gaenge ein Geraet samt Notiz/Verlauf verloren (K-3/C-14); `init_db` sichert Schema + scan_state vor der Dedupe per Commit und rollt bei Fehler nur die Dedupe zurueck (K-12)
- `connect()` fuehrt die Journal-Schreibprobe (WAL/Fallback + BEGIN IMMEDIATE) nur noch einmal je Prozess und Pfad aus - reine Lesezugriffe und der Healthcheck nehmen keinen Schreib-Lock mehr (K-1); `set_oui_cache` committet sofort, der Scanner haelt keine offene Schreibtransaktion mehr (K-2); Migrationen ueberleben ein "duplicate column name" (Web + Scanner starten gleichzeitig) (K-4)
- Scanner: `apply_scan` nimmt sofort `BEGIN IMMEDIATE` und rollt bei einem Fehler den GANZEN Scan zurueck, statt einen halben Stand zu speichern (K-10/K-5); SIGTERM/SIGINT beendet die Scan-Schleife sauber (`init: true` in docker-compose) (K-8); Auto-Export schreibt atomar (tmp-Datei + os.replace) aus einem konsistenten Lese-Schnappschuss `db.read_snapshot` (K-8/K-11)
- Upsert: leere Felder ueberschreiben Hostname/Hersteller/IPv6/IP nicht mehr (COALESCE, C-6), und eine MAC mit gemeldeter IP leert die IP anderer (stale) Zeilen (N-1); `set_layout` schreibt spaltengenau per UPSERT, gleichzeitige Aenderungen anderer Spalten gehen nicht verloren (K-6)
- `scan_state` um Fehler-Spalten erweitert (`last_error`, `last_error_at`, `consecutive_failures`, `scan_started_at`) - Basis fuer die Scan-Fehleranzeige (SF-2) in W4

Produktionsreife Welle 4 (Scanner + stille Fehler, siehe docs/produktionsreife/UEBERGABE.md):
- Dual-Stack: IPv4 gewinnt bei `merge_sources` fuer `ip`, die IPv6-Adresse landet in `ip6` (vorher verlor ein Geraet mit v4+v6 seine IPv4); TR-064-IPv4 schlaegt erkannte IPv6 ebenfalls (C-4)
- Leere/gescheiterte Erkennung setzt bei online Bestand nichts mehr offline und loescht nichts mehr (SF-1): ERROR + Sperre nur wenn keine Subnetze bekannt oder Sonden-Binaerdateien fehlen, sonst WARNING und normaler Offline-Uebergang (ein wirklich leeres Netz zeigt weiter offline)
- Scanfehler landen in `scan_state` (`last_error`, `last_error_at`, `consecutive_failures`, bei Erfolg zurueckgesetzt) und in `/api/scan/status`; Docker-Healthcheck (nur lesende DB-Verbindung) ist ab 3 Fehlern unhealthy (SF-2); haengende Scans (`scanning=1` laenger als max(30 Min, 3x Intervall)) sind unhealthy und in `/api/scan/status` als `stale_scanning` markiert (SF-3/K-9)
- `last_seen` wird nur noch bei online gesetzt (C-5); die Aufbewahrung nutzt bei leerem `last_seen` das `first_seen`, sonst wuerden offline gemeldete TR-064-Hosts nie geloescht
- Benachrichtigungen: HTTP ab 300 (inkl. Redirects) und Verbindungsfehler gelten als Fehlschlag, `notify_new_devices` liefert bool, Zustellstatus liegt persistent in `last_notify_status`/`last_notify_at` (Anzeige in der UI folgt in W5) (SF-5)
- Grosse IPv6-Netze: die nach dem ff02::1-Multicast neu berechnete NDP-Tabelle geht ins Ergebnis ein (C-8); SNMP-CAM ignoriert Uplink-Ports (mehrere MACs) sowie MACs anderer Switches und des Gateways (C-9); eigene Portliste wird auf 1-65535 validiert, Maximum fuer `port_top` (1040) dokumentiert (C-13)
- Stille Fehler im Scanner loggen jetzt: fehlende Binaerdateien (ping/ip/snmpwalk/arp) einmal je Lauf als WARNING (`logsetup.warn_once`), erwartbare DNS/mDNS-Fehlschlaege und Sondenfehler als DEBUG mit exc_info (SF-8/TL-1); WAN-Werte werden bei TR-064-Ausfall geleert statt vom letzten Lauf zu stehen
- PDF-Export: nur Bild-Lesefehler (`UnidentifiedImageError`/OSError mit Bild) werden als 422 gemeldet, echte Serverfehler landen mit `log.exception` als 500 (N-4); Entrypoint meldet eine fehlgeschlagene chown-Rechtepruefung als WARN statt sie still zu uebergehen (SF-7); Auto-Exportziel bleibt per realpath-Pruefung im Datenverzeichnis (T-6)
- Tests: `run_once`/Hauptschleife abgedeckt (Notify nur fuer neue Nicht-VPN-Nicht-Whitelist, `scanning=0` nach Fehler, Schleife ruft `run_once`) (T-2), Retention-Grenzen 29/31 Tage + online bleibt + Ereignis-Grenze (T-3), Auto-Export-Dateien/Inhalt/Pfad (T-6)

Produktionsreife Welle 5 (Oberflaeche, siehe docs/produktionsreife/UEBERGABE.md):
- Neuer zentraler API-Client `app/static/api.js` (Q-10): `apiJson()` wirft `ApiError` bei `!ok` und Netzwerkfehlern; alle Speichervorgaenge zeigen Fehler sichtbar in `role="alert"` (`#app-alert`) mit Server-Detail, die Eingabe bleibt erhalten und es wird nicht neu geladen (F-3/SF-6); Netzwerkfehler zeigen ein Offline-Banner, `init()` bindet die Handler vor den Requests und stirbt nicht mehr an einem fehlenden `/api/meta` (F-4)
- Veraltete Antworten werden verworfen (Sequenzzähler in `loadDevices`/`showDetail`, F-1); Tabellen-Neuaufbau stellt Fokus, Wert und Cursor der bearbeiteten Zelle wieder her (F-2); Auto-Layout verwendet gespeicherte x/y je Knoten, nur unpositionierte landen im Baum (F-5); Karten-Refresh passt Zoom/Ausschnitt nicht mehr an und schliesst das Detailfenster, wenn das Geraet weg ist (F-6); Kinderzahlen werden einmal je Render berechnet statt pro Knoten `devices.some` (kubisch) - 1000 Geraete rendern unter 1 s (F-7)
- Tastatur/A11y: Enter auf Links/Buttons in Tabellenzeilen wird nicht mehr verschluckt, Kopfzellen sind fokussierbar mit `aria-sort` und per Enter sortierbar (F-8); Seitenleiste setzt den Fokus ins Panel, Escape schliesst und gibt den Fokus an den Opener zurueck, Edit-Felder haben `aria-label`, Tabs `aria-controls` (F-9)
- Kontrast: Log-Stufen und VPN-Badge haben in beiden Themes >= 4,5:1 (theme-abhaengige Farben, geprueft in `tests/test_a11y_css.py`), Druck erzwingt helle Variablen + `white-space: normal` (F-10/F-11); Embed-Ansicht blendet PDF/Export/Bearbeiten aus und haengt den Token an die Exportlinks (F-12)
- i18n: feste deutsche Texte in Schluessel umgezogen, Zeitstempel per `Intl.DateTimeFormat(LANG)` (F-13/F-14), Paritaets-Test: alle 6 Sprachen gleiche Schluesselmenge, jede Kategorie hat `cat.*` (Q-11); Sprach-Fallback in app.js und login.js angeglichen
- Einstellungen: werden einmal je Oeffnen geladen (Tabwechsel leert nichts mehr), `settings-msg` wird beim Tabwechsel geleert, gespeichertes Theme wird sofort angewandt (F-15); Secrets (TR-064-Passwort, SNMP-Community) werden als `{"configured": bool}` behandelt mit "Loeschen"-Button - explizites `null` im PATCH loescht den gespeicherten Wert serverseitig (Zeile weg, S-8); `auth_enabled`-Schalter aus der UI entfernt (S-9); Zustellstatus der Alarme in den Einstellungen sichtbar (SF-5, Wert kommt ueber `/api/scan/status`)
- Mobil: `100dvh` statt `100vh` + Breakpoint fuer schmale Anzeigen, `#log-status` mit Schreibschutz, keine ueberlappenden Scan-Status-Abfragen (F-16); toter Code entfernt (`groupOf`, ungenutzte catch-Variablen, TL-4)
- D-5: cytoscape steht jetzt in `package.json` (3.35.0, via Dependabot/npm ueberwacht), `npm run update:vendor` (`scripts/update_vendor.mjs`) kopiert `dist/cytoscape.min.js` mit SHA-256-Pruefung nach `app/static/vendor/`, THIRD_PARTY.md nennt Version + Hash; eslint ignoriert `vendor/`
- Tests: `tests/ui/` (12 Dateien, laufen in `tests/ui_dom_check.mjs` mit): api_errors, table_edit, layout_positions, map_refresh, keyboard, focus_a11y, render_perf, embed_mode, i18n_parity, layout_responsive, settings_form, vendor_version; plus Kontrast-/Print-Tests in `test_a11y_css.py` und Secret-Null-Test in `test_settings_api.py`

Produktionsreife Welle 6 (Testluecken + Mutanten, siehe docs/produktionsreife/UEBERGABE.md):
- `scripts/mutants.sh` neu: Kill-Liste M10, B2, B3, M11, R1, R2, R3, F4, F5, F6, F7 - jeder Mutant wird einzeln auf eine Repo-Kopie gepatcht und gegen die zugehoerigen Tests gejagt; kompletter Lauf: ALLE 11 MUTANTEN GETOETET (F7 haengt ohne run_once -> Timeout zaehlt als Kill)
- T-4/T-15: `tests/test_session_expiry.py` - abgelaufene Sitzung wird auch ohne Prune mit 401 abgelehnt (M10-Killer: `test_expired_session_rejected_without_prune`); autouse-Fixture `clean_auth_state` in `tests/conftest.py` leert `auth.SESSIONS` und den Prune-Zeitpunkt zwischen Tests (`test_sessions_isolated_between_tests`)
- B2/B3: Struktur-Test `tests/test_public_surface.py::test_jede_schreibende_api_route_traegt_require_auth` - jede mutierende /api-Route muss `require_auth`/`require_auth_or_token` als explizite Dependency tragen (die Middleware allein ist kein ausreichender Nachweis)
- T-16: jsdom `tests/ui/scan_indicator.mjs` (scanning=1 -> Klasse `running` + Text; Wechsel auf 0 mit neuem last_scan ruft `loadDevices()` - b454ca8), `tests/ui/hidden_css.mjs` (`[hidden]{display:none!important}` - 40f10cb), TCP-Sonde gegen lokalen Socket (`tests/test_network_paths.py::test_tcp_probe_sweep_against_local_socket` - e885216), PDF-Umbruch langer Zellen (`tests/test_pdf_errors.py::test_pdf_long_text_is_wrapped_not_overlapping` - 3846cc9)
- T-7: `tests/test_e2e_scan_api.py::test_scan_result_visible_via_api` - collect_devices gepatcht, `run_once`, dann GET /api/devices, /api/device/{mac}, Export JSON + PDF, /api/scan/status
- T-9: `tests/test_network_paths.py` - `tcp_probe`/`tcp_probe_sweep`/`scan_ports` gegen echte Sockets auf 127.0.0.1; aufgezeichnete Ausgaben von `ip addr`/`ip -6 neigh`/`ping`/`snmpwalk` als Fixtures in `tests/fixtures/net/`; `ports.py` und `snmp.py` jetzt je 96% Coverage (>80%)
- T-11: `tests/test_parsers_property.py` (hypothesis, bereits im Dev-Set): `mdns.parse_packet`/`parse_mdns_answers`/`_decode_name` werfen bei Zufallsbytes nie und haengen nie, SOAP-Antworten werfen nur `TR064Error`, `normalize_mac` idempotent
- T-8/T-14: jsdom wartet in `tests/ui_dom_check.mjs` auf Bereitschaft (GET /api/devices) statt festem 200-ms-sleep; Literal-/Konstanten-Tests (test_a11y_css, test_hardening, test_security_v160) als billige Wachposten markiert; `check_web` in test_hardening nutzt einen frei gewaehlten geschlossenen Port statt Port 1
- T-12/T-13: `tests/test_load.py::test_500_devices_list_under_budget` (500 Geraete: Liste/Export/Detail je unter 10 s), `tests/test_api_contract.py` (Schluessel-Snapshots von /api/devices, /api/meta, /api/settings; Secrets nur als `{"configured": bool}`); jsdom-Fixture aus der echten API erzeugt und committet (`tests/fixtures/api_devices_sample.json`), DEVS liegt in `tests/ui/devs_fixture.mjs`, Paritaets-Test `tests/ui/fixture_parity.mjs`
- Stand nach W6: 385 pytest (Coverage 90,1%, Schwelle 84%), ALL UI CHECKS PASSED (15 tests/ui-Module), `scripts/gate.sh` 10x aufeinanderfolgend gruen

Produktionsreife Welle 7 (Struktur + Typen, siehe docs/produktionsreife/UEBERGABE.md) - Verhalten bleibt identisch (Charakterisierungstests pinnen alte Ausgaben):
- Q-3: Scanner-Pipeline neu in `app/scanner/pipeline.py` - reine Stufen (`gather_raw`, `endpoints_for`, `fetch_tr064_stage`, `port_plan_for`, `scan_ports_stage`, `names_mdns_stage`, `snmp_stage`, `finalize`); `run.py` haelt nur noch `run_once`/`apply_scan`/`apply_retention`/`main` und re-exportiert die Pipeline-Namen (bestehende Imports/Patches greifen weiter). Charakterisierung: `tests/test_pipeline.py::test_collect_devices_output_unchanged`
- Q-14: `discover` je Sonde zerlegt (`_probe_subnet_v4`/`_probe_subnet_v6`/`_devices_from_live`), `classify` in Score-Helfer mit den bestehenden Regeltabellen (`_score_gateway_mesh`/`_score_mdns`/`_score_hostname`/`_score_vendor`/`_score_ports`/`_pick_best`), `tr064.parse_mesh` in `_parse_nodes`/`_parse_links`/`_resolve_attachment`/`_node_summary`; Charakterisierung: `tests/test_categorize.py::test_rule_order_unchanged` + Snapshot-Parametrisierung. Alle `noqa: C901` entfernt - keine Funktion ueber Komplexitaet 15 (ruff C90)
- Q-4: `api.py` ist nur noch Compat-Re-Export; Routen liegen in `app/routers/` (devices, scan, export, settings, tokens, meta), Registrierung in `app/web.py`; Fachlogik in `app/services/` (`authz.py` Token-Scope, `devices.py` Listenfilter + `check_parent`); neue db-Helfer `device_exists`, `list_rooms`, `update_device`, `reset_layout`, `parent_chain`; `web.py::create_app` in `_register_middleware`/`_register_pages` zerlegt. Routentabelle gepinnt: `tests/test_routes_inventory.py::test_route_table_unchanged` + `test_no_unreferenced_routes` (`/api/health` Healthcheck, `/api/rooms` bewusst gehalten - siehe docs/entscheidungen.md)
- Q-2: `validate_settings` als `validation.validate_patch(data)` mit einzelnen Check-Helfern; Meldungen woertlich gleich
- TL-5: `app/types.py` mit `DeviceRow`/`Device`/`DeviceDetail` (TypedDict) + `response_model=` an devices/device/meta/health/categories/sites/scan-status/tokens/rooms; `uv run mypy --strict app` gruen (war 162 Fehler), neuer Gate-Schritt
- Q-16: DB-Alt-Aliase `subnet`/`fritz_url` werden beim Start auf `subnets`/`fritz_urls` migriert (`db._migrate_setting_aliases`, Tests `test_legacy_alias_migrated*`); env-Aliase bleiben deprecated (docs/entscheidungen.md)
- Q-13: nur als Entscheidungsvermerk in `docs/entscheidungen.md` (Kategorienamen, Logger, NETZ_-Praefix bleiben in dieser Kampagne)
- Stand nach W7: 416 pytest, `mypy --strict app` 0 Fehler, ruff C90 ohne Ausnahmen, gate gruen

## [1.6.17] – 2026-11-26

TR-064 TLS-Zertifikatsprüfung auch in der Web-UI schaltbar (PR #108).

## [1.6.18] – 2026-11-26

TR-064 https→http-Fallback jetzt auch für WAN und Mesh + Port-Hinweis 49443 (PR #111).


### Behoben
- **TR-064 https→http-Fallback jetzt für alle Calls:** Bisher nur die Hostliste; WAN (`fetch_wan`) und Mesh (`fetch_mesh`) schlugen bei `https://…:49000` (Klartext-Port, `SSL: WRONG_VERSION_NUMBER`) fehl. Neu: `fetch_wan_with_fallback`/`fetch_mesh_with_fallback` + `tr064_tls_hint()` — Log-WARN enthält bei TLS/Port-Problemen den Hinweis „HTTPS-Port ist 49443, nicht 49000", zusätzlich Endpunkt-Warnung beim Scan-Start, wenn ein Endpunkt `https://…:49000` nutzt. 3 Tests. Doku: Handbuch 6 Sprachen (Port-Warnung im HTTPS-Absatz), READMEs.


### Dokumentiert
- **TR-064 HTTP 401 trotz korrektem Passwort — Ursache Sperre nach Fehlversuchen + Lösung dokumentiert:** `tr064_401_hint()` im Log ergänzt um den Hinweis, dass die FRITZ!Box den Benutzer nach mehreren Fehlversuchen kurzzeitig sperrt (Brute-Force-Schutz) und eine erfolgreiche Anmeldung als TR-064-Benutzer im Web-UI die Sperre aufhebt (alternativ einige Minuten warten; System → Ereignisse). Handbuch (6 Sprachen: Mesh-Absatz + Troubleshooting-Tabelle) und READMEs ergänzt. 1 Test-Assertion erweitert.

### Hinzugefügt
- **TR-064 TLS-Option jetzt auch in der Web-UI:** Häkchen „TLS-Zertifikatsprüfung abschalten“ (`NETZ_TR064_INSECURE_TLS`) in den Einstellungen, Gruppe TR-064, mit MITM-Warnhinweis (i18n 6 Sprachen); serverseitig in `SAFE_SETTINGS`/`SettingsPatch`/`OVERRIDABLE` (runtime ohne Neustart). Tests: API-Roundtrip + UI-DOM. Doku: Handbuch-Tabelle 6 Sprachen, READMEs.

Alle relevanten Änderungen an fox_netmap. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/). Frühere Versionen siehe
[GitHub-Releases](https://github.com/KaiDeWitzka/fox_netmap/releases).

## [1.6.16] – 2026-11-26

TR-064 über HTTPS nutzbar (PR #106): TLS-Abschwächung bewusst wählbar via `NETZ_TR064_INSECURE_TLS`.

### Hinzugefügt
- **TR-064 über HTTPS nutzbar, TLS-Abschwächung bewusst wählbar:** Neues Setting `NETZ_TR064_INSECURE_TLS` (Default `false` = Zertifikatsprüfung an). Bei `true` wird `verify=False` nur für die TR-064-Calls (Hosts, WAN, Mesh) gesetzt, damit das selbstsignierte FRITZ!Box-Zertifikat an `NETZ_FRITZ_URL=https://…:49443` akzeptiert wird. Risiko (MITM im LAN) wird beim Scan als WARN geloggt und in der Doku benannt (Handbuch 6 Sprachen, READMEs). 5 Tests (verify-Default/-Weitergabe in Hosts/WAN/Mesh, Settings-Parsing).

## [1.6.15] – 2026-11-25

VPN-Pool automatisch bei TR-064 (PR #103) + klarerer HTTP-401-Hinweis im Log (PR #104).

### Verbessert
- **VPN-Erkennung ohne manuelle Konfiguration:** Bei konfiguriertem TR-064 (FRITZ!Box mit User/Pass) und `NETZ_VPN_POOL=off` wird automatisch `auto` angenommen (FRITZ!-Konvention: letzte Oktett ≥ 201 im Gateway-/24). WireGuard-Peers (.201+), die nicht in TR-064 auftauchen, bekommen so ohne extra Einstellung das VPN-Badge, den gestrichelten Rand, keinen „neues Gerät“-Alarm und werden nicht als Ziel der Internet-Kante verwendet (Kategorie „Router“ bei Hostname fritz.box @ .201). Explizit konfigurierter Pool gewinnt weiterhin. Log-Hinweis im Scanner. Hinweis: TR-064 meldet den DHCP-Bereich der Box nicht — bei erweitertem DHCP-Pool (z. B. bis .220) ist `auto` unzutreffend, dann expliziten Bereich setzen (z. B. `192.168.178.221-192.168.178.254`). 1 Test + Doku (Handbuch 6 Sprachen, READMEs).
- **TR-064 HTTP 401 im Log verstaendlicher:** `tr064_401_hint()` haengt an die WARN-Meldungen (Mesh + allgemein) einen konkreten Hinweis an: TR-064-Benutzer braucht laut AVM die Berechtigung „App“/„Phone“ (am einfachsten Admin-Rechte) plus die globalen Schalter „Zugriff fuer Anwendungen zulassen“ und „Statusinformationen ueber UPnP uebermitteln“ (Heimnetz → Netzwerk → Netzwerkeinstellungen); manche Modelle lehnen einzelne Actions mit 401 ab. 1 Test. Doku: Mesh-Absatz im Handbuch (6 Sprachen).

## [1.6.14] – 2026-11-25

Räume/Ebenen pro Gerät + Karten-Performance (PR #98 Clutter-Skalierung, PR #99 room-Feature + Performance >200 Geräte).

### Neu
- **Räume/Ebenen pro Gerät:** neues Feld `room` (DB-Migration, max. 64 Zeichen) — setzbar im Geräte-Detail (`ed-room`) und per `PATCH /api/device/{mac}`; Liste via `GET /api/rooms`. Sichtbar als Tabellen-Spalte („Raum“), im JSON/CSV-Export (`room`), als Filter in der Filterleiste (`room`-Parameter in `/api/devices` + Exports) reine Zusatzinformation für die Tabelle (Spalte, Export, API-Filter `room`; Menüleiste ohne Raum-Filter; Karte unberührt). Dazu **Bearbeiten-Modus der Tabelle** (Button „Bearbeiten“: Kategorie/Notiz/Raum direkt in der Tabelle editieren, sofort per PATCH gespeichert). Scanner überschreibt `room` nicht. i18n in 6 Sprachen.

### Verbessert
- **Performance ab ~200 Geräten:** Tabelle rendert per DocumentFragment, gespeicherte Positionen laden ohne Animation (`preset animate:false`). Karten-Layout unverändert wie in v1.6.13 (fixe Knotengröße/Abstände).

### Doku
- Handbuch (alle 6 Sprachen, Abschnitt 6 „Räume/Ebenen“) + README (de/en): Doku zum Raum-Feature; Karte-Gruppierung nach Raum, Raum-Filter, Exporte.

## [1.6.13] – 2026-11-25

Karten-Fix (PR #96): Internet-Kante landet nicht mehr am VPN-Knoten; Doku-Empfehlung zu `NETZ_VPN_POOL` in Handbuch (6 Sprachen) + READMEs.

### Behoben
- **Karte: Internet-Kante landet am VPN-Knoten statt am Router:** `routerTargetId()` hat per TR-064-Endpunkt-Hostname (z. B. `fritz.box`) auch VPN-Clients (`.201+`, `vpn=1`) als Router-Ziel akzeptiert. VPN-Knoten werden jetzt in allen Fallbacks ausgeschlossen; ohne Gerätetrefffer landet die Kante am Gateway (Gerät mit Gateway-IP bzw. virtueller Gateway-Knoten). 1 UI-Test.

### Doku
- Handbuch (alle 6 Sprachen) + README (de/en): Empfehlung zu `NETZ_VPN_POOL` ergänzt — `auto` bei FRITZ!Box-VPN-Clients (.201+ im Gateway-/24), eigenes VPN-Subnetz als CIDR (z. B. `192.168.179.0/24`).

## [1.6.12] – 2026-11-24

SQLite-Thread-Fix (PR #94): `check_same_thread=False` gegen `ProgrammingError` im Web-Container; Doku zu `NETZ_SQLITE_JOURNAL` in den READMEs (PR #93).

### Behoben
- **SQLite `ProgrammingError: ... can only be used in that same thread` im Web-Container (`/api/scan/status` -> 500):** FastAPI/anyio fuehrt synchrone Generator-Depends (`get_conn`) mit Enter und Exit in unterschiedlichen Worker-Threads aus. `db.connect()` setzt jetzt `check_same_thread=False` (pro Request eine Connection, sequentiell genutzt; Locking ueber Datei + busy timeout). 1 Test.

### Doku
- README (de/en): `NETZ_SQLITE_JOURNAL` in die Env-Liste aufgenommen + Troubleshooting-Hinweis (`disk I/O error` auf Docker-Desktop-/NAS-Mounts -> `delete`).

## [1.6.11] – 2026-11-24

SQLite-Fix v2 (PR #91): echte Schreibprobe beim Connect, WAL->DELETE-Fallback, klare Fehlermeldung bei nicht beschreibbarem Datenverzeichnis; Dedupe nicht mehr fatal.

### Behoben
- **SQLite `disk I/O error` (RunTipi: beide Container crashen beim ersten DB-Schreibzugriff):** Journal-Modus wird per echter Schreibprobe (`BEGIN IMMEDIATE`) geprueft, bei Fehler Fallback WAL -> `journal_mode=DELETE`; schlaegt auch das fehl, klare Fehlermeldung im Log (Datenverzeichnis nicht beschreibbar -> Volume-Mount /data rw pruefen). Ausserdem ist das Dedupe beim Start nicht mehr fatal. Erzwingen mit `NETZ_SQLITE_JOURNAL=wal|delete|auto`. 6 Tests.

## [1.6.10] – 2026-11-24

SQLite-Stabilität im Container (PR #89): WAL-Fallback auf `journal_mode=DELETE` bei `disk I/O error`.

### Behoben

## [1.6.9] – 2026-11-24

Karte: Internet-Knoten wird bei TR-064-WAN mit dem Router verbunden (PR #86); CI image-scan gegen leere IMAGE-Env gehärtet (PR #87).

### Neu
- **Internet ↔ Router auf der Karte:** Liest TR-064 den WAN-Status (z. B. FRITZ!Box), verbindet die Karte den Internet-Knoten mit dem Router — über die Gateway-IP oder den TR-064-Endpunkt (Hostname/IP wie „fritz.box“, auch wenn das Gateway nicht in der Geräteliste steht; neues Feld `wan_endpoint` in `/api/meta`). WAN-Status ≠ „Connected“ → Internet-Knoten offline.

### Behoben
- **CI `image-scan.yml`:** `docker pull`/Trivy gegen leere `IMAGE`-Env gehärtet (Fallback auf `ghcr.io/kaidewitzka/fox_netmap` hartkodiert, Pulls einzeln mit `set -x`) — der Scheduled-Run 2026-11-23 schlug sonst mit „docker pull requires 1 argument“ fehl.

## [1.6.8] – 2026-11-23

CI-Security nach dem Go-public: CodeQL-Workflow im Repo (SHA-gepinnt) + CodeQL-Alert #1 gefixt (PRs #83, #84).

### Neu
- **CodeQL-Workflow im Repo:** `.github/workflows/codeql.yml` (Python + JavaScript, push/PR auf `main` + woechentlich; `github/codeql-action` v4.39.4 per SHA gepinnt). Default-Setup in den GitHub-Settings deaktiviert; Alerts landen im Security-Tab.

### Behoben
- **CodeQL `js/bad-tag-filter` (Security-Alert #1):** Test-Regex in `tests/ui_dom_check.mjs` jetzt case-insensitive (`/<script>/i`) — erkennt auch `<SCRIPT>`-Tags; UI-Checks weiterhin grün.

## [1.6.7] – 2026-11-23

Go-public (PR #81): Repository öffentlich (MIT), Anonymisierung von Tests/Doku/Screenshots, Secret-Scan-CI (gitleaks, volle History), Community-Dateien.

### Go-public-Vorbereitung
- **Anonymisierung:** echte WAN-IP, v6-Präfix, Hostnamen (`mrrobot`) und MACs aus Tests, Doku
  und Screenshots entfernt (TEST-NET-Adressen `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.10`,
  `2001:db8::/32`, Beispiel-MACs `02:00:00:…`); echte Screenshot-PNGs entfernt, Doku verweist auf
  die schematischen SVGs
- **Secret-Scan in der CI:** `.gitleaksignore` (False Positive `auth_pass="secret"` in
  `tests/conftest.py`) + Workflow `gitleaks.yml`: gitleaks-Binary aus gepinntem Release v8.24.3 mit SHA-256-Checksummen-Prüfung (gitleaks-action v3 ignoriert `--log-opts`), volle History via
  `--log-opts="--all"`)
- **Community-Dateien:** `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, Issue-Templates (Bug/Feature),
  PR-Template
- **SECURITY.md:** Supported Versions aktualisiert (1.6.x), Meldung via Private Vulnerability Reporting
- **READMEs:** GHCR-Paket öffentlich — `docker pull` ohne Login
- **Repository public:** MIT-Lizenz, GitHub Secret Protection + Push Protection + Private Vulnerability Reporting + Dependabot in den Settings aktiviert, GHCR-Paket `fox_netmap` public (Pull ohne Login)


## [1.6.6] – 2026-11-22

Karte: Subnetz-Gruppen starten auf Raster (keine Überlappung), Geräte ohne IP erst per Haken sichtbar (PR #79).

### Geändert
- **Karte: Subnetz-Gruppen überlappen nicht mehr zu Beginn** — beim Gruppieren bekommen die
  Rahmen ein eigenes Raster (Position pro Subnetz), Kinder ohne gespeicherte Position stehen
  ringförmig um das Gruppenzentrum.
- **Karte: Geräte ohne IP erst auf Wunsch sichtbar** — neue Checkbox „Ohne IP ausblenden“
  (Gruppe „Karte“, Default an, persistiert in `fox_noip`): Geräte ohne IP (z. B. nur per TR-064
  bekannte Namen wie `PC-76-84-…`) erscheinen erst auf der Karte, wenn man den Haken entfernt;
  in der Tabelle bleiben sie immer sichtbar.

## [1.6.5] – 2026-11-22

IPv6-Fund in großen v6-Netzen (SLAAC/EUI-64, ff02::1, DNS-AAAA), README zweisprachig (de/en), Settings-Menü nach Schwerpunkten gruppiert (PRs #76, #77).

### Geändert
- **Einstellungen nach Schwerpunkten gruppiert:** Das Settings-Formular ist jetzt in 7
  `<fieldset>`-Gruppen mit Legende gegliedert (Allgemein · Scan · TR-064 · SNMP · Alarme ·
  Exporte/Standorte/VPN · OUI), i18n in allen 6 Sprachen. Alle Feld-IDs unverändert.

### Neu
- **IPv6-Fund bei großen Netzen verbessert:** zusätzlich zu NDP/Gateway jetzt `ff02::1`-Multicast-Ping,
  **SLAAC/EUI-64-Kandidaten pro bekannter MAC** (aus ARP/TR-064) im konfigurierten v6-Subnetz per `ping6`
  und **DNS-AAAA pro Hostname** (per ping6 verifiziert). Gefundene globale v6-Adressen landen in
  `devices.ip6` und erscheinen in Tabelle, Detail-Panel und Export. (Bisher war die NDP-Tabelle oft nur
  mit Link-Local-Einträgen gefüllt → scheinbar „keine IPv6“.)
- **README zweisprachig:** `README.md` (Deutsch) + `README.en.md` (Englisch), mit gegenseitigem Sprach-Link.

## [1.6.4] – 2026-11-22

App-Icon (Fuchs + Netzwerk) und IPv6-Spalte in der Tabelle (PR #74).

### Neu
- **App-Icon:** Fuchs-Kopf mit Netzwerk-Motiv als SVG (`app/static/favicon.svg`) — Favicon in `index.html` und `login.html`, Logo im Header und auf der Login-Seite.
- **IPv6 in der Tabelle:** neue Spalte „IPv6“ direkt nach der IP-Spalte (Wert aus `devices.ip6` via NDP-MAC-Match, „–“ wenn keine bekannt).

## [1.6.3] – 2026-11-22

VPN-Erkennung, `link_port` im Export, Scan & gehärtetes Image bei jedem Merge auf `main`, zweizeiliger Header (PRs #69–#72).

### Geändert
- **Header zweizeilig nach Themenschwerpunkten gruppiert:** Zeile 1 „Ansicht“ (Logo + Versionsnummer,
  Karte/Tabelle/Log, Suche, Filter, Nur online, Scan-Status), Zeile 2 „Karte“ (Gruppierung, Layout),
  „Aktionen“ (Scan, JSON/CSV/PDF, Drucken) und „App“ (Theme, Sprache, Einstellungen, Logout).
  Der **Einstellungen-Button** ist jetzt deutlich sichtbar (⚙-Icon + Label, Akzent-Rahmen).

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

### CI / Supply Chain
- **Scan & Image bei jedem Merge auf `main`:** neuer Workflow `main-scan.yml` baut das gehärtete Image,
  führt das Trivy-Gate aus (fixbare CRITICAL/HIGH → Abbruch), erzeugt SBOM (CycloneDX + SPDX) und
  Trivy-Bericht als Artefakt (30 Tage) und pusht das Multi-Arch-Image als `:main` / `:sha-<sha>` nach
  GHCR (mit SBOM-/Provenance-Attestierung) — nur nach grünem Gate.
- **Wöchentlicher Nachscan** (`image-scan.yml`) prüft jetzt `:latest` **und** `:main`.
- Doku aktualisiert: README (Releases), `docs/03-sicherheit.md` §2.9.

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
