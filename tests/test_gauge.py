"""Tests for gauge（小样密度与塑形上限的单一事实来源）。"""

import pytest

from app.models.gauge import (
    DEFAULT,
    PRESETS,
    gauge_from_ui,
    next_shaping_stitch_count,
)


def test_classic_preset_preserves_behavior():
    assert DEFAULT.stitches_for_diameter(9.0) == 36   # 经典锚点不变
    assert abs(DEFAULT.stitch_w_cm - 0.769) < 0.01
    assert abs(DEFAULT.row_h_cm - 0.625) < 0.01


def test_fine_preset_matches_real_amigurumi():
    """紧密玩偶规格下 9cm 头应落在 fable5 预测的 48–60 针区间。"""
    n = PRESETS["fine"].stitches_for_diameter(9.0)
    assert 48 <= n <= 60, n


def test_aspect_within_physical_range():
    """短针物理上高>宽（外部实务 w/h≈0.67–0.83）——除 classic 外预设须落区间内。"""
    for name in ("dk", "fine"):
        assert 0.6 <= PRESETS[name].aspect_wh <= 0.9, name


def test_hook_labels_by_stitch_width():
    assert "2.0–2.5" in PRESETS["fine"].hook_yarn_label
    assert "4–5" in PRESETS["classic"].hook_yarn_label  # 特粗（旧"2.5mm"标签的修正）


def test_grams_scale_with_area():
    assert PRESETS["fine"].grams_per_stitch < DEFAULT.grams_per_stitch


def test_unified_row_height_across_parts():
    """行高是纱线属性：同一 gauge 下身体/四肢圈数换算共用同一行高。"""
    g = PRESETS["fine"]
    assert g.rounds_for_height(4.5) == g.rounds_for_height(4.5)
    assert g.rounds_for_height(3.2) == int(3.2 / g.row_h_cm + 0.5)


def test_gauge_from_ui_custom_and_fallback():
    g = gauge_from_ui("custom", 22.0, 30.0)
    assert (g.stitches_per_10cm, g.rows_per_10cm) == (22.0, 30.0)
    assert gauge_from_ui("classic", None, None) is DEFAULT
    assert gauge_from_ui("custom", None, None) is DEFAULT  # 空值回退
    clamped = gauge_from_ui("custom", 999, -5)             # 越界钳制到边界
    assert (clamped.stitches_per_10cm, clamped.rows_per_10cm) == (40.0, 8.0)


def test_shaping_limit_is_derived_then_quantized_to_six_sectors():
    """连续几何值与可发布图解的六等分步长是两个不同概念。"""
    assert DEFAULT.shaping_continuous_delta == pytest.approx(5.105, abs=0.01)
    assert PRESETS["dk"].shaping_continuous_delta == pytest.approx(7.63, abs=0.01)
    assert PRESETS["fine"].shaping_continuous_delta == pytest.approx(7.85, abs=0.01)
    assert DEFAULT.max_shaping_change == 6
    assert PRESETS["dk"].max_shaping_change == 12
    assert PRESETS["fine"].max_shaping_change == 12


@pytest.mark.parametrize(
    ("current", "target", "cap", "expected"),
    [
        (6, 24, 12, 12),    # 只有 6 个源针，首圈仍只能每针加一次
        (12, 30, 12, 24),
        (24, 6, 12, 12),
        (18, 6, 12, 12),    # 18 针不能在一圈内合法减掉 12 针
        (30, 30, 12, 30),
    ],
)
def test_next_shaping_round_respects_cap_and_executable_operations(
        current, target, cap, expected):
    assert next_shaping_stitch_count(current, target, cap) == expected


def test_next_shaping_round_rejects_non_six_sector_topology():
    with pytest.raises(ValueError):
        next_shaping_stitch_count(10, 24, 12)
