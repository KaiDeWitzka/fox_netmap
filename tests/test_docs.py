"""W8 (D-1/D-3/D-4/D-10/N-6): Doku-Regressionstests - die Doku muss zum Code passen (UEBERGABE Abschnitt 8, W8)."""

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HANDBUECHER = [REPO / "docs" / f"02-benutzerhandbuch{suffix}.md" for suffix in ("", ".en", ".fr", ".es", ".it", ".pt")]


def _load_gen_env_table():
    spec = importlib.util.spec_from_file_location("gen_env_table", REPO / "scripts" / "gen_env_table.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _without_codefences(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def test_readme_has_no_stale_version():
    """D-1: README pinnt keine konkrete Release-Version mehr (Platzhalter statt :X.Y.Z, keine 'Aktuell'-Zeile)."""
    for name in ("README.md", "README.en.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert not re.search(r"fox_netmap:\d+\.\d+\.\d+", text), f"{name}: gepinnte Vollversion"
        assert "1.6.4" not in text, f"{name}: veraltete Version 1.6.4"
        assert "Aktuell:" not in text and "Current:" not in text, f"{name}: 'Aktuell'-Zeile steht noch"
        assert "fox_netmap:latest" in text, f"{name}: :latest-Beispiel fehlt"


def test_changelog_has_unreleased_section():
    """D-3: CHANGELOG hat einen [Unreleased]-Abschnitt (CONTRIBUTING verlangt Eintraege dort)."""
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(r"^## \[Unreleased\]$", text, re.M)


def test_env_reference_covers_all_settings():
    """D-4: generierte Env-Referenz in docs/05-betrieb.md deckt jedes NETZ_* aus .env.example und settings_schema."""
    gen = _load_gen_env_table()
    doc = (REPO / "docs" / "05-betrieb.md").read_text(encoding="utf-8")
    assert gen.START in doc and gen.END in doc
    assert gen.render_block().rstrip("\n") in doc, "Env-Tabelle driftet - bitte scripts/gen_env_table.py ausfuehren"
    section = doc.split(gen.START, 1)[1].split(gen.END, 1)[0]
    env_keys = set()
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(NETZ_[A-Z0-9_]+)=", line.strip())
        if m:
            env_keys.add(m.group(1))
    schema_keys = {"NETZ_" + k.upper() for k in gen.FIELDS}
    for key in sorted(env_keys | schema_keys):
        assert f"`{key}`" in section, f"{key} fehlt in der Env-Referenz (docs/05-betrieb.md)"


def test_ops_docs_exist():
    """D-10: Runbook (Backup/Upgrade/Rollback + Env-Referenz) und Architektur existieren."""
    betrieb = (REPO / "docs" / "05-betrieb.md").read_text(encoding="utf-8")
    arch = (REPO / "docs" / "06-architektur.md").read_text(encoding="utf-8")
    for kw in ("## 2. Backup", "## 3. Upgrade", "## 4. Rollback", "## 7. Umgebungsvariablen"):
        assert kw in betrieb, kw
    for kw in ("## 1. Komponenten", "Datenfluss", "Sicherheitsgrenzen", "Teststrategie"):
        assert kw in arch, kw


def test_security_doc_names_global_lockout_and_forwarded_for():
    """N-6: Sicherheitskonzept nennt in 2.3 die globale Sperre hinter einem Proxy und die X-Forwarded-For-Regel."""
    text = (REPO / "docs" / "03-sicherheit.md").read_text(encoding="utf-8")
    sec = text.split("### 2.3", 1)[1].split("### 2.4", 1)[0]
    assert "X-Forwarded-For" in sec
    assert re.search(r"global", sec, re.I)
    assert "NETZ_FORWARDED_ALLOW_IPS" in sec


def test_handbooks_same_structure():
    """W8-Abnahme: alle 6 Handbuecher haben dieselben Ueberschriften-Level und dieselben /api/-Verweise."""
    levels, api_sets = [], []
    for path in HANDBUECHER:
        text = _without_codefences(path.read_text(encoding="utf-8"))
        levels.append([len(m) for m in re.findall(r"^(#{1,6}) ", text, re.M)])
        api_sets.append({r.rstrip(".,;:)]}'\"") for r in re.findall(r"/api/[A-Za-z0-9_./{}-]+", text)})
    for path, lv in zip(HANDBUECHER, levels, strict=True):
        assert lv == levels[0], f"{path.name}: andere Ueberschriften-Struktur als das deutsche Handbuch"
    for path, refs in zip(HANDBUECHER, api_sets, strict=True):
        assert refs == api_sets[0], f"{path.name}: andere /api/-Verweise: {sorted(refs ^ api_sets[0])}"


def test_docs_url_disabled(tmp_path):
    """D-3: /docs und /openapi.json werden nicht registriert - auch nicht bei NETZ_AUTH_ENABLED=false."""
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.web import create_app

    app = create_app(Settings(data_dir=str(tmp_path), auth_enabled=False))
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/docs" not in paths
    assert "/openapi.json" not in paths
    with TestClient(app) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
