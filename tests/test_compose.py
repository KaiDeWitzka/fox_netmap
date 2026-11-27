"""Compose-/Dockerfile-Regression (Release 1.7.0): docker compose parst strikt - doppelte Keys und
GitHub-Actions-Syntax `${{...}}` in der Compose brechen den CI-Docker-Job (PR #115)."""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
COMPOSE = REPO / "docker-compose.yml"
DOCKERFILE = REPO / "Dockerfile"


class _StrictLoader(yaml.SafeLoader):
    pass


def _no_duplicate_keys(loader, node, deep=False):
    keys = []
    for k, _v in node.value:
        key = loader.construct_object(k, deep=deep)
        assert key not in keys, f"doppelter YAML-Key {key!r} in docker-compose.yml"
        keys.append(key)
    return loader.construct_mapping(node, deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def _compose_env_keys() -> set[str]:
    doc = yaml.load(COMPOSE.read_text(encoding="utf-8"), Loader=_StrictLoader)  # noqa: S506 - SafeLoader-abgeleitet, nur Dup-Key-Check
    env = doc["x-netz-env"]
    return {k for k in env if k.startswith("NETZ_")}


def test_compose_strict_yaml_no_duplicates_no_actions_syntax():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "${{" not in text, "GitHub-Actions-Syntax ${{...}} in docker-compose.yml (compose parst das nicht)"
    yaml.load(text, Loader=_StrictLoader)  # noqa: S506 - wirft bei doppelten Keys


def test_compose_env_covers_all_settings():
    from app.settings_schema import FIELDS

    known = {"NETZ_" + k.upper() for k in FIELDS} | {"NETZ_SQLITE_JOURNAL", "NETZ_FORWARDED_ALLOW_IPS"}
    env_keys = _compose_env_keys()
    assert known <= env_keys, f"in Compose fehlen: {sorted(known - env_keys)}"


def test_dockerfile_base_images_pinned_by_digest():
    text = DOCKERFILE.read_text(encoding="utf-8")
    froms = re.findall(r"^FROM\s+(\S+)", text, re.M)
    assert froms, "keine FROM-Zeilen gefunden"
    for image in froms:
        assert "@sha256:" in image, f"Basis-Image nicht per Digest gepinnt: {image}"
