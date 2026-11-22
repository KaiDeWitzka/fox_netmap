# Fremdkomponenten im Frontend

fox_netmap liefert alle Frontend-Bestandteile selbst aus, ohne CDN, Schrift- oder Symboldienst. Diese Datei nennt
die mitgelieferten Fremdkomponenten mit Lizenz. Die Python-Abhängigkeiten stehen mit Version und Hash in
`requirements.txt`; die vollständige Stückliste je Release liegt als SBOM (`sbom.cdx.json`, `sbom.spdx.json`) am
GitHub-Release.

| Komponente | Version | Datei | Lizenz | Quelle |
|---|---|---|---|---|
| Cytoscape.js | 3.30.2 | `app/static/vendor/cytoscape.min.js` | MIT, Copyright (c) 2016-2024 The Cytoscape Consortium | <https://github.com/cytoscape/cytoscape.js> |
| Lucide (14 Symbole) | Stand November 2026 | `app/static/icons.js` | ISC, Copyright (c) 2026 Lucide Icons and Contributors | <https://github.com/lucide-icons/lucide> |
| Feather (Ursprung einzelner Lucide-Symbole, z. B. monitor, server, smartphone, tablet, tv) | – | `app/static/icons.js` | MIT, Copyright (c) 2013-present Cole Bemis | <https://github.com/feathericons/feather> |
| IEEE-OUI-Liste (Auszug) | – | `app/data/oui_seed.txt` | öffentliche Registrierungsdaten der IEEE | <https://standards-oui.ieee.org> |

Die vollständigen Lizenztexte stehen jeweils im Kopf der Datei (`cytoscape.min.js`, `icons.js`).

## Verwendete Lucide-Symbole

globe (Internet), router (Router, Gateway), wifi (Repeater/AP, WLAN), network (Switch), server (Server/NAS),
monitor (Client), laptop, smartphone (Mobilgerät), tablet, tv (Multimedia), gamepad-2 (Spielkonsole),
printer (Drucker), lightbulb (Smart-Home/IoT), circle-question-mark (Unbekannt).

Die Pfade sind unverändert übernommen; Farbe und Größe setzt fox_netmap zur Laufzeit.
