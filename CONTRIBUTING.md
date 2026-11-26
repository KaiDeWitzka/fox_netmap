# Mitmachen (Contributing)

Danke für dein Interesse an fox_netmap! 🎉

## schnellstart

```bash
git clone https://github.com/KaiDeWitzka/fox_netmap.git && cd fox_netmap
uv sync
npm ci
bash scripts/gate.sh   # ruff + format + mypy + pytest+cov + UI-DOM + eslint + pip-audit
```

## Pull Requests

- Branch vom aktuellen `main`: `vibe/<kurz-slug>` (z. B. `vibe/neues-feature`)
- Ein PR = ein Thema; kleine, fokussierte Commits
- Vor dem PR lokal: `bash scripts/gate.sh` muss grün sein (ruff + format + mypy + pytest+cov + UI-DOM + eslint + pip-audit; CI prüft dasselbe auf Python 3.12 und 3.13)
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

## Manuell zu pflegen (Dependabot sieht das nicht)

| Ressource | Datei | Pruefbefehl |
| --- | --- | --- |
| Cytoscape (vendored) | `app/static/vendor/cytoscape.min.js` | `npm view cytoscape version` vs. Kopfzeile der Datei |
| gitleaks-Version | `.github/workflows/gitleaks.yml` | `gh api repos/gitleaks/gitleaks/releases/latest --jq .tag_name` |
| Trivy-Image | `scripts/trivy.sh` | `docker buildx imagetools inspect ghcr.io/aquasecurity/trivy:<version>` |
