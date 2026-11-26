# Entscheidungsvermerke der Produktionsreife-Kampagne (W7)

Vermerke zu Befunden, die bewusst **nicht** im Code umgesetzt werden (UEBERGABE Abschnitt 7.7,
Q-13/Q-12/Q-16). Verhalten aendert sich dadurch nicht.

## Q-13 – Benennung (Kategorien, Logger, Präfix) bleibt, wie sie ist

- **Fakt:** Kategorien (`Router`, `Drucker`, `Mobilgerät`, …) sind gespeicherte deutsche
  Anzeigetexte in `devices.category`; eine Umbenennung oder Umstellung auf sprachneutrale IDs
  verlangt eine Datenmigration plus Änderungen an API, UI und allen sechs Handbüchern.
  Logger heißen teils `fox_netmap.*`, teils `netmap.*`; das Env-Präfix ist `NETZ_`.
- **Entscheidung (W7):** In dieser Kampagne nur dokumentieren. Sprachneutrale Kategorie-IDs mit
  Übersetzungsetiketten sind eine eigene Kampagne (Datenmigration + UI + Doku), kein Nebenprodukt
  der Produktionsreife.
- **Konvention für neuen Code:** neue Module/Funktionen auf Englisch, neue Log-Namen unter
  `fox_netmap.*`, neue Env-Variablen mit `NETZ_`-Präfix.

## Q-12 – `/api/rooms` bleibt vorerst erhalten

- **Fakt:** Von 26 API-Routen hat nur `/api/rooms` keinen Bezug in `app/static` (das Frontend
  nutzt Räume nur als Filter-Query und PATCH-Feld). `/api/health` dient dem Docker-HEALTHCHECK.
- **Entscheidung (W7):** Route bleibt (API-Stabilität für externe Nutzer); sie ist in
  `tests/test_routes_inventory.py::test_no_unreferenced_routes` als bewusst gehalten
  (KEEP-Liste) dokumentiert. Ersatz durch eine Raumliste im Frontend bzw. Entfernung ist für
  eine kommende größere Version vorgesehen.

## Q-16 – Doppelpfade `subnet`/`subnets` und `fritz_url`/`fritz_urls`

- **Wahrheitsquelle (Dokumentation):** Umgebung ist der Startwert, die Datenbank ist die
  Laufzeitüberschreibung (`effective_settings` in `app/config.py`).
- **Umgesetzt in W7:** Datenbank-Altzeilen `subnet`/`fritz_url` werden beim Start automatisch
  auf die kanonischen `subnets`/`fritz_urls` migriert und gelöscht
  (`db._migrate_setting_aliases`, Test `test_settings_schema.py::test_legacy_alias_migrated`).
- **Noch offen (bewusst):** die Env-Aliase `NETZ_SUBNET` und `NETZ_FRITZ_URL` bleiben als
  deprecated kompatibel (`Settings.subnet`/`fritz_url` in `app/config.py`); sie werden in einer
  größeren Version zusammen mit der Datenmigration entfernt.
