"""Tests for the shared yarn color module (Lab perceptual matching)."""
from app.models.colors import YARN_COLORS, nearest_yarn, srgb_to_lab


def test_exact_table_colors_map_to_themselves():
    """每个色表条目对自身 RGB 的最近邻必须是它自己（距离 0 且唯一）。"""
    for rgb, name in YARN_COLORS:
        got_name, got_rgb = nearest_yarn(*rgb)
        assert got_name == name
        assert got_rgb == rgb


def test_lab_extremes():
    l_black, _, _ = srgb_to_lab(0, 0, 0)
    l_white, a_white, b_white = srgb_to_lab(255, 255, 255)
    assert abs(l_black) < 0.01
    assert abs(l_white - 100.0) < 0.01
    assert abs(a_white) < 0.01 and abs(b_white) < 0.01


def test_near_skin_tone_stays_in_skin_family():
    """接近肤色的输入应落在肤色系，而不是被灰阶吸走。"""
    name, _ = nearest_yarn(240, 190, 160)
    assert name in ("浅肤色", "桃肤色", "米色", "棕肤色")
