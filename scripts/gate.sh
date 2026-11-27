#!/usr/bin/env bash
# Gate der Produktionsreife-Kampagne (docs/produktionsreife/UEBERGABE.md Abschnitt 9.5).
# Bricht beim ersten Fehler ab, am Ende eine Zeile je Pruefung. CI ruft dasselbe Skript.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '[gate] %s\n' "$1"; }

step "ruff check"
uv run ruff check .

step "ruff format --check"
uv run ruff format --check .

step "mypy app"
uv run mypy app

step "mypy --strict app (W7/TL-5)"
uv run mypy --strict app

step "pytest + coverage (fail_under in pyproject.toml)"
uv run pytest -q -p no:cacheprovider --cov=app --cov-branch --cov-report=term

step "npm ci + UI-DOM-Check"
npm ci --no-audit --no-fund
node tests/ui_dom_check.mjs

step "eslint"
npx --no-install eslint app/static tests/ui_dom_check.mjs

step "prettier --check (Markdown, W8/D-10)"
npx --yes prettier@3 --check README.md README.en.md CONTRIBUTING.md SECURITY.md CHANGELOG.md THIRD_PARTY.md docs/*.md docs/entscheidungen.md docs/produktionsreife/STAND.md docs/produktionsreife/ARCHIV.md

step "pip-audit (Lockfile, ohne Projekt selbst)"
uv export --frozen --no-hashes --no-emit-project --format requirements-txt | uvx pip-audit -r /dev/stdin

step "OK - alle Pruefungen gruen"
