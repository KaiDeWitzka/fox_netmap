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

## Release-Checkliste (D-10, beim Taggen von `vX.Y.Z`)

1. `bash scripts/gate.sh` lokal grün (inkl. `prettier --check` auf Markdown und `tests/test_docs.py`); CI auf Python 3.12/3.13 sowie der docker/Trivy-Job grün
2. Version nur in `app/__init__.py` bumped; Tag `vX.Y.Z` pushen — `release.yml` bricht ab, wenn Tag ≠ `app.__version__`
3. `CHANGELOG.md`: Abschnitt `## [Unreleased]` in `## [X.Y.Z] – YYYY-MM-DD` umbenennen und neuen leeren `## [Unreleased]` anlegen (Test: `tests/test_docs.py::test_changelog_has_unreleased_section`)
4. Keine veralteten Versionen in README/README.en (Test: `tests/test_docs.py::test_readme_has_no_stale_version`)
5. Doku-Parität: alle 6 Handbücher gleiche Überschriften-Level und gleiche `/api/`-Verweise (`tests/test_docs.py::test_handbooks_same_structure`); Umgebungsvariablen-Referenz aktuell (`uv run python scripts/gen_env_table.py --check`)
6. CI `main-scan.yml`: Image-Bau, Trivy-Gate, SBOM (CycloneDX + SPDX) + Trivy-Bericht als Artefakt; das Release hängt SBOM und Scan-Bericht an
7. Nach dem Release den wöchentlichen Nachscan (`image-scan.yml`) im Auge behalten

## Manuell zu pflegen (Dependabot sieht das nicht)

| Ressource            | Datei                                | Pruefbefehl                                                             |
| -------------------- | ------------------------------------ | ----------------------------------------------------------------------- |
| Cytoscape (vendored) | `app/static/vendor/cytoscape.min.js` | `npm view cytoscape version` vs. Kopfzeile der Datei                    |
| gitleaks-Version     | `.github/workflows/gitleaks.yml`     | `gh api repos/gitleaks/gitleaks/releases/latest --jq .tag_name`         |
| Trivy-Image          | `scripts/trivy.sh`                   | `docker buildx imagetools inspect ghcr.io/aquasecurity/trivy:<version>` |
