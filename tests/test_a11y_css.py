"""Barrierefreiheit im Stylesheet: Bewegung begrenzt und abschaltbar (WCAG 2.2.2, 2.3.3)."""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "app" / "static" / "styles.css").read_text(encoding="utf-8")
JS = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")


def _block(media: str) -> str:
    start = CSS.index(f"@media ({media})")
    depth, i = 0, CSS.index("{", start)
    for j in range(i, len(CSS)):
        depth += {"{": 1, "}": -1}.get(CSS[j], 0)
        if depth == 0:
            return CSS[i : j + 1]
    raise AssertionError("Block nicht geschlossen")


def test_keine_endlos_animation():
    assert "infinite" not in CSS


def test_animationen_enden_vor_fuenf_sekunden():
    for dur, count in re.findall(r"animation:\s*[\w-]+\s+([\d.]+)s\s+[\w-]+\s+(\d+)", CSS):
        assert float(dur) * int(count) < 5


def test_reduced_motion_schaltet_bewegung_ab():
    block = _block("prefers-reduced-motion: reduce")
    assert "animation: none" in block and "transition: none" in block


def test_druck_feedback_nur_ohne_reduced_motion():
    assert "scale(0.97)" in _block("prefers-reduced-motion: no-preference")
    outside = CSS.replace(_block("prefers-reduced-motion: no-preference"), "")
    assert "scale(" not in outside


def test_live_region_nur_bei_aenderung():
    assert "if (el.textContent !== text) el.textContent = text;" in JS
