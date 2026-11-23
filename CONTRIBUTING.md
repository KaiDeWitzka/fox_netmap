# Mitmachen (Contributing)

Danke für dein Interesse an fox_netmap! 🎉

## schnellstart

```bash
git clone https://github.com/KaiDeWitzka/fox_netmap.git && cd fox_netmap
python3 -m venv /tmp/venv-fox && /tmp/venv-fox/bin/pip install --require-hashes --no-deps -r requirements-dev.txt
npm ci
/tmp/venv-fox/bin/ruff check .
/tmp/venv-fox/bin/python -m pytest -q
node tests/ui_dom_check.mjs
```

## Pull Requests

- Branch vom aktuellen `main`: `vibe/<kurz-slug>` (z. B. `vibe/neues-feature`)
- Ein PR = ein Thema; kleine, fokussierte Commits
- Vor dem PR lokal: `ruff check .`, `pytest -q`, `node tests/ui_dom_check.mjs` müssen grün sein (CI prüft dasselbe)
- **Doku mitpflegen:** User-Änderungen gehören in `docs/02-benutzerhandbuch.*` (6 Sprachen: de/en/fr/es/it/pt), README (`README.md` de + `README.en.md` en) und `CHANGELOG.md` (`[Unreleased]`)
- **Version:** wird zentral vom Maintainer gebumpt (PR + Tag `vX.Y.Z`); bitte nicht selbst erhöhen
- PR-Template ausfüllen (siehe `.github/PULL_REQUEST_TEMPLATE.md`)

## Issues

- Bug? → Issue-Template „Bug report" (inkl. Version, Log-Ausschnitt, Schritte zur Reproduktion)
- Idee? → Issue-Template „Feature request"
- **Sicherheitslücken bitte NICHT als öffentliches Issue** — siehe [SECURITY.md](SECURITY.md) (Private Vulnerability Reporting)

## Stil

- Python: `ruff` (Konfig in `pyproject.toml`), Deutsch in Logs/UI-Default, UI-Texte i18n in 6 Sprachen
- JS: Vanilla, `node --check`, UI-Audit via `tests/ui_dom_check.mjs` (jsdom)
- Commits auf Deutsch oder Englisch, prägnant

## Lizenz

Mit dem PR stimmst du zu, dass dein Beitrag unter der [MIT-Lizenz](LICENSE) steht.
