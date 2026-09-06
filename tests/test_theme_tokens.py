"""Design tokens stay in sync across theme.py, config.toml, the CSS and renderers.

The Streamlit theme cannot import Python, and the SVG/canvas renderers live in
the model layer; this test is what keeps the four surfaces from drifting apart.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from app import theme
from app.models.ring_chart import render_ring_svg, render_symbol_strip
from app.ui.design_system import build_css, ring_mark_svg

_REPO = Path(__file__).resolve().parent.parent


def _config_theme() -> dict:
    data = tomllib.loads((_REPO / ".streamlit/config.toml").read_text(encoding="utf-8"))
    return data["theme"]


def test_streamlit_theme_mirrors_tokens():
    th = _config_theme()
    assert th["primaryColor"] == theme.INK
    assert th["backgroundColor"] == theme.PAPER
    assert th["secondaryBackgroundColor"] == theme.SHEET
    assert th["textColor"] == theme.INK
    assert th["borderColor"] == theme.EDGE
    assert th["dataframeBorderColor"] == theme.RULE
    assert th["greenColor"] == theme.OK_INK
    assert th["yellowColor"] == theme.WARN_INK
    assert th["redColor"] == theme.ERR_INK
    assert th["font"] == theme.FONT_SANS
    assert th["headingFont"] == theme.FONT_SERIF
    assert th["codeFont"] == theme.FONT_MONO
    assert th["sidebar"]["backgroundColor"] == theme.DESK


def test_css_uses_tokens_and_marker_is_never_text():
    css = build_css()
    for value in (theme.PAPER, theme.SHEET, theme.INK, theme.INK_SOFT,
                  theme.RULE, theme.EDGE, theme.MARKER, theme.MARKER_SOFT):
        assert value in css
    # The marker means "where you are / what you have done": it is a fill
    # under ink text, never a text colour (contrast would collapse).
    assert not re.findall(r"(?<![\w-])color:\s*var\(--marker", css)
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media print" in css
    # No external font or asset requests: the app keeps its offline stance.
    assert "@import" not in css
    assert "http" not in css


def test_legacy_palette_is_gone():
    files = [*(_REPO / "app").rglob("*.py"), _REPO / ".streamlit/config.toml"]
    offenders = []
    for path in files:
        if path.name == "theme.py":
            continue
        text = path.read_text(encoding="utf-8").lower()
        offenders.extend(
            (str(path.relative_to(_REPO)), legacy)
            for legacy in theme.LEGACY_HEX if legacy in text
        )
    assert not offenders, offenders


def test_ring_chart_uses_theme_colours_and_plain_labels():
    part = {"name": "头部", "rounds": [
        {"row": 1, "stitches": 6, "color": "白色"},
        {"row": 2, "stitches": 12, "increase": 6, "color": "白色"},
        {"row": 3, "stitches": 18, "increase": 6, "color": "红色"},
    ]}
    svg = render_ring_svg(part)
    assert theme.SHEET in svg and theme.INK in svg
    assert " · " not in svg
    assert "R3" in svg and "18X" in svg and "红色" in svg
    strip = render_symbol_strip(part)
    assert theme.SHEET in strip and " · " not in strip


def test_hero_mark_draws_six_rings_and_has_static_variant():
    svg = ring_mark_svg()
    assert svg.count('class="ring"') == 6
    assert svg.count("stroke-dasharray:") == 6
    assert 'class="magic"' in svg
    assert "is-static" not in svg
    assert "is-static" in ring_mark_svg(animate=False)
