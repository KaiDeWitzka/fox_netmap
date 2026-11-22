## Summary
- Was ändert dieser PR? (1–3 Sätze)

## Art
- [ ] Bugfix
- [ ] Feature
- [ ] Doku
- [ ] CI/Chore
- [ ] Security

## Doku
- [ ] `docs/02-benutzerhandbuch.*` (alle 6 Sprachen) aktualisiert — falls UI/Verhalten betroffen
- [ ] `README.md` / `README.en.md` aktualisiert — falls Setup/Nutzung betroffen
- [ ] `CHANGELOG.md` unter `[Unreleased]` ergänzt

## Tests
- [ ] `ruff check .` grün
- [ ] `python -m pytest -q` grün
- [ ] `node tests/ui_dom_check.mjs` grün (bei UI-Änderungen inkl. neuer Checks)
- [ ] Manuell getestet: …

## Security
- [ ] Keine Secrets/neuen externen Aufrufe ohne Doku
- [ ] `gitleaks`-CI grün (Secret-Scan der History)
