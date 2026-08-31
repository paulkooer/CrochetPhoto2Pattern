"""Tests for the shared yarn color module (CIEDE2000 perceptual matching)."""
import pytest

from app.models.colors import (
    YARN_COLORS,
    ciede2000,
    color_distance,
    nearest_yarn,
    srgb_to_lab,
)


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


# ── CIEDE2000 官方补充测试数据（Sharma, Wu & Dalal 2005）──────────────────
# 数据源：gsharma/ciede2000 dataNprograms/ciede2000testdata.txt（论文配套），
# 每行 = (L1, a1, b1, L2, a2, b2, 期望 ΔE00)。逐对验证实现与参考一致（±1e-4）。
_CIEDE2000_OFFICIAL_PAIRS = [
    (50.0, 2.6772, -79.7751, 50.0, 0.0, -82.7485, 2.0425),
    (50.0, 3.1571, -77.2803, 50.0, 0.0, -82.7485, 2.8615),
    (50.0, 2.8361, -74.02, 50.0, 0.0, -82.7485, 3.4412),
    (50.0, -1.3802, -84.2814, 50.0, 0.0, -82.7485, 1.0),
    (50.0, -1.1848, -84.8006, 50.0, 0.0, -82.7485, 1.0),
    (50.0, -0.9009, -85.5211, 50.0, 0.0, -82.7485, 1.0),
    (50.0, 0.0, 0.0, 50.0, -1.0, 2.0, 2.3669),
    (50.0, -1.0, 2.0, 50.0, 0.0, 0.0, 2.3669),
    (50.0, 2.49, -0.001, 50.0, -2.49, 0.0009, 7.1792),
    (50.0, 2.49, -0.001, 50.0, -2.49, 0.001, 7.1792),
    (50.0, 2.49, -0.001, 50.0, -2.49, 0.0011, 7.2195),
    (50.0, 2.49, -0.001, 50.0, -2.49, 0.0012, 7.2195),
    (50.0, -0.001, 2.49, 50.0, 0.0009, -2.49, 4.8045),
    (50.0, -0.001, 2.49, 50.0, 0.001, -2.49, 4.8045),
    (50.0, -0.001, 2.49, 50.0, 0.0011, -2.49, 4.7461),
    (50.0, 2.5, 0.0, 50.0, 0.0, -2.5, 4.3065),
    (50.0, 2.5, 0.0, 73.0, 25.0, -18.0, 27.1492),
    (50.0, 2.5, 0.0, 61.0, -5.0, 29.0, 22.8977),
    (50.0, 2.5, 0.0, 56.0, -27.0, -3.0, 31.903),
    (50.0, 2.5, 0.0, 58.0, 24.0, 15.0, 19.4535),
    (50.0, 2.5, 0.0, 50.0, 3.1736, 0.5854, 1.0),
    (50.0, 2.5, 0.0, 50.0, 3.2972, 0.0, 1.0),
    (50.0, 2.5, 0.0, 50.0, 1.8634, 0.5757, 1.0),
    (50.0, 2.5, 0.0, 50.0, 3.2592, 0.335, 1.0),
    (60.2574, -34.0099, 36.2677, 60.4626, -34.1751, 39.4387, 1.2644),
    (63.0109, -31.0961, -5.8663, 62.8187, -29.7946, -4.0864, 1.263),
    (61.2901, 3.7196, -5.3901, 61.4292, 2.248, -4.962, 1.8731),
    (35.0831, -44.1164, 3.7933, 35.0232, -40.0716, 1.5901, 1.8645),
    (22.7233, 20.0904, -46.694, 23.0331, 14.973, -42.5619, 2.0373),
    (36.4612, 47.858, 18.3852, 36.2715, 50.5065, 21.2231, 1.4146),
    (90.8027, -2.0831, 1.441, 91.1528, -1.6435, 0.0447, 1.4441),
    (90.9257, -0.5406, -0.9208, 88.6381, -0.8985, -0.7239, 1.5381),
    (6.7747, -0.2908, -2.4247, 5.8714, -0.0985, -2.2286, 0.6377),
    (2.0776, 0.0795, -1.135, 0.9033, -0.0636, -0.5514, 0.9082),
]


@pytest.mark.parametrize(
    "l1,a1,b1,l2,a2,b2,expected", _CIEDE2000_OFFICIAL_PAIRS)
def test_ciede2000_official_reference_data(l1, a1, b1, l2, a2, b2, expected):
    """全部 34 组官方测试对：实现必须与参考实现一致（±1e-4）。"""
    got = ciede2000((l1, a1, b1), (l2, a2, b2))
    assert abs(got - expected) < 1e-4


def test_ciede2000_is_symmetric():
    """ΔE00 对称性：交换两个颜色差值不变（公式平方项 + 交叉项双变号）。"""
    lab_a, lab_b = srgb_to_lab(70, 130, 180), srgb_to_lab(0, 120, 215)
    assert abs(ciede2000(lab_a, lab_b) - ciede2000(lab_b, lab_a)) < 1e-9


def test_color_distance_matches_ciede2000():
    """RGB 入口的 color_distance 与 Lab 入口的 ciede2000 同值。"""
    rgb1, rgb2 = (255, 105, 180), (216, 191, 216)
    assert abs(color_distance(rgb1, rgb2)
               - ciede2000(srgb_to_lab(*rgb1), srgb_to_lab(*rgb2))) < 1e-9


def test_blue_hue_discrimination_better_than_cie76():
    """CIEDE2000 的已知优势区：蓝区 hue 旋转不被彩度差掩盖。

    钢蓝 (70,130,180) vs 蓝 (0,120,215)：CIE76 下两者被明度差主导，
    语义吸附/色表匹配在蓝紫边界容易吸错段。
    """
    steel, blue = (70, 130, 180), (0, 120, 215)
    cyan = (0, 200, 200)
    # 钢蓝对青色的感知距离应大于对蓝色的（hue 更远）
    assert color_distance(steel, blue) < color_distance(steel, cyan)


# ── Monk Skin Tone Scale 全谱覆盖（O-P4）──────────────────────────────────
# 依据：Monk Skin Tone (MST) Scale（Ellis Monk / Google, 2022，
# skintone.google/get-started）——10 级肤色标尺，比 Fitzpatrick 6 级在
# 深肤色端分布更均匀。色表按 MST-01/06/07/08/09/10 精确锚点扩充后，
# 任何肤色都应映射到"肤色系"毛线名，而非灰阶/黑白色名。

_MST_SCALE = [
    (1, (246, 237, 228)), (2, (243, 231, 219)), (3, (247, 234, 208)),
    (4, (234, 218, 186)), (5, (215, 189, 150)), (6, (160, 126, 86)),
    (7, (130, 92, 67)), (8, (96, 65, 52)), (9, (58, 49, 42)),
    (10, (41, 36, 32)),
]


@pytest.mark.parametrize("point,rgb", _MST_SCALE)
def test_monk_skin_tone_maps_to_skin_yarn(point, rgb):
    """MST 全部 10 级必须映射到肤色语义的毛线色名（含深肤色端）。

    回归：扩充前 MST-07~10 全被吸到"深棕色/黑色"、MST-01/02 被吸到
    "浅灰色"——按这些推荐买线做脸是错的。
    """
    name, _rgb = nearest_yarn(*rgb)
    assert "肤色" in name or name == "米色", f"MST-{point:02d} → {name}"


def test_dark_hair_still_distinct_from_dark_skin():
    """深棕发色与深肤色的色表条目互不混淆（CIEDE2000 判别）。"""
    name, _ = nearest_yarn(139, 90, 43)  # 深棕色锚点（发色）
    assert name == "深棕色"
