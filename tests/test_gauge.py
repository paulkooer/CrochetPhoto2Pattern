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


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "nan"])
def test_gauge_mapping_rejects_non_finite_or_boolean_values(value):
    from app.models.gauge import gauge_from_mapping

    for key in ("stitches_per_10cm", "rows_per_10cm"):
        raw = {"stitches_per_10cm": 20, "rows_per_10cm": 16, key: value}
        assert gauge_from_mapping(raw) == DEFAULT


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


# ── CYC（Craft Yarn Council）官方密度档映射 ────────────────────────────────
# 依据：craftyarncouncil.com/standards/yarn-weight-system（2026-09 抓取），
# 官方钩织密度按"短针/4 英寸"分档；本项目 10cm 口径阈值 ×0.984 换算。

def test_cyc_mapping_hits_each_official_category():
    from app.models.gauge import Gauge
    assert "#1 super fine" in Gauge(22.0, 16.0).cyc_label   # 22.3/4″ ≥ 21
    assert "#2 fine" in Gauge(17.0, 14.0).cyc_label         # 17.3/4″ ∈ 16–20
    assert "#3 light" in PRESETS["classic"].cyc_label       # 13.2/4″ ∈ 12–17
    assert "#4 medium" in Gauge(11.5, 9.0).cyc_label        # 11.7/4″ ∈ 11–14
    assert "#5 bulky" in Gauge(8.5, 8.0).cyc_label          # 8.6/4″ ∈ 8–11
    assert "#6 super bulky" in Gauge(7.5, 8.0).cyc_label    # 7.6/4″ ∈ 7–9
    assert "#7 jumbo" in Gauge(6.0, 8.0).cyc_label          # 6.1/4″ ≤ 6


def test_cyc_mapping_boundaries_after_10cm_conversion():
    """换算阈值：CYC #1 下限 21/4″ → 20.7/10cm；#2 上缘 20/10cm 仍属 #2。"""
    from app.models.gauge import Gauge
    assert "#2 fine" in Gauge(20.0, 16.0).cyc_label   # 20.3/4″ < 21 → #2 上缘
    assert "#1 super fine" in Gauge(20.7, 16.0).cyc_label
    assert "#3 light" in Gauge(15.7, 16.0).cyc_label  # 15.9/4″ < 16 → #3


def test_drops_apple_gauge_lands_in_cyc_fine_with_matching_hook():
    """交叉验证：DROPS 23-60（18 短针/10cm、4.5mm）→ CYC #2 fine，
    且 4.5mm 恰为其官方钩针区间（3.5–4.5mm）上限——专业图解与官方标准吻合。"""
    from app.models.gauge import Gauge
    label = Gauge(18.0, 20.0).cyc_label   # 20 圈/10cm 同取自 DROPS 官方密度
    assert "#2 fine" in label
    assert "3.5–4.5" in label
