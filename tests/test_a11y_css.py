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
    # T-8 (W6): billiger Wachposten - Literal im Quelltext, kein Verhaltenstest
    assert "if (el.textContent !== text) el.textContent = text;" in JS


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    vals = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in vals]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted([_lum(fg), _lum(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _color_of(sel_frag: str, extra_sel: str = ""):
    for sel, body in re.findall(r"([^{}]+)\{\s*([^{}]*?)\s*\}", CSS):
        if sel_frag in sel and (not extra_sel or extra_sel in sel):
            m = re.search(r"(?<![\w-])color:\s*(#[0-9a-fA-F]{6})", body)
            if m:
                return m.group(1).lower()
    return None


def test_log_level_and_badge_contrast():
    # F-11: Log-Stufen und VPN-Badge brauchen in beiden Themes >= 4,5:1 (WCAG 1.4.3)
    for level in ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"):
        dark = _color_of(f".lv-{level}")
        light = _color_of(f".lv-{level}", extra_sel='[data-theme="light"]')
        assert dark and light, level
        assert _contrast(dark, "#0f172a") >= 4.5, (level, dark, _contrast(dark, "#0f172a"))
        assert _contrast(light, "#f8fafc") >= 4.5, (level, light, _contrast(light, "#f8fafc"))
    badge_dark = _color_of(".badge-vpn")
    badge_light = _color_of(".badge-vpn", extra_sel='[data-theme="light"]')
    assert badge_dark and badge_light
    assert _contrast(badge_dark, "#1e293b") >= 4.5, (badge_dark, _contrast(badge_dark, "#1e293b"))
    assert _contrast(badge_light, "#ffffff") >= 4.5, (badge_light, _contrast(badge_light, "#ffffff"))


def test_print_block_forces_light_theme():
    # F-10: Druck erzwingt helle Variablen und bricht Zellen um (sonst unlesbar/nowrap)
    start = CSS.index("@media print")
    i = CSS.index("{", start)
    depth, j = 1, i
    while depth > 0:
        j += 1
        depth += {"{": 1, "}": -1}.get(CSS[j], 0)
    block = CSS[i : j + 1]
    assert "--bg: #ffffff" in block
    assert "--fg: #0f172a" in block
    assert "white-space: normal" in block
