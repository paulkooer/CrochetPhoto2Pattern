"""Tests for profile-driven shaping（照片剖面 → 旋转体逐圈针数，M1.2/M1.5）。"""
import math
import re

from app.models.gauge import DEFAULT, PRESETS
from app.models.profile_shaping import (
    _sample_at,
    profile_to_rounds,
    render_silhouette_svg,
    rounds_to_notes,
    strip_dome,
)


def _pear_profile(n=40):
    """梨形剖面：两端窄、中段宽（变化幅度需超过 6 针量化粒度）。"""
    return [
        0.25 + 0.75 * math.sin(math.pi * i / (n - 1)) ** 2
        for i in range(n)
    ]


def _straight_profile(n=40):
    return [1.0] * n


def test_straight_profile_equals_constant_wall():
    wall = profile_to_rounds(_straight_profile(), (0.30, 0.62), 4.5, DEFAULT, 36)
    assert len(set(wall)) == 1 and wall[0] == 36   # 等剖面 → 等宽筒（模板圆柱等价）


def test_constraints_hold_for_pear():
    wall = profile_to_rounds(_pear_profile(), (0.0, 1.0), 6.0, DEFAULT, 36)
    assert all(n % 6 == 0 for n in wall)           # 6 的倍数
    assert all(abs(b - a) <= DEFAULT.max_shaping_change
               for a, b in zip(wall, wall[1:]))  # noqa: B905 - adjacent pairs truncate by design
    assert all(n >= 6 for n in wall)
    assert max(wall[1:-1]) > min(wall[0], wall[-1])  # 中段最宽（梨形保留）


def test_fine_gauge_can_use_twelve_stitch_transition():
    """细密度的行高相对针宽更大，陡轮廓可合法使用六区各加两针。"""
    profile = [0.2] * 20 + [1.0] * 20
    wall = profile_to_rounds(
        profile, (0.0, 1.0), 4.0, PRESETS["fine"], 60,
        direction="top_down")
    deltas = [b - a for a, b in zip(wall, wall[1:])]  # noqa: B905
    assert 12 in deltas
    assert max(map(abs, deltas)) <= PRESETS["fine"].max_shaping_change


def test_bottom_up_direction():
    """R1=照片低处：剖面底部值应成为第一圈锚定。"""
    prof = [0.9] * 20 + [0.3] * 20   # 上宽下窄
    wall = profile_to_rounds(prof, (0.0, 1.0), 3.0, DEFAULT, 36)
    assert wall[0] < wall[-1]        # 底部窄 → R1 小，向顶部变宽


def test_rounds_to_notes_standard_notation():
    notes = rounds_to_notes([30, 30, 36, 36, 30])
    assert notes[0] == "30X（起针圈）"
    assert notes[1] == "30X（不加不减）"
    assert "隔4针加1针" in notes[2]     # 30→36 = (4X,V)×6，隔 4
    assert "减1针" in notes[4]


def test_silhouette_svg_renders_both_layers():
    svg = render_silhouette_svg([36, 36, 30, 24], DEFAULT,
                                 photo_profile=[1.0] * 10, span=(0.3, 0.62))
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert svg.count("<polygon") == 2      # 生成侧影 + 照片剖面
    assert "照片轮廓" in svg


# ── N4/N7 回归：可视化正确性 ──────────────────────────────────────────────

def test_strip_dome_removes_bottom_disk():
    """圆盘剥离 = `_increase_rounds(wall[0])` 构造的逆操作。

    回归（N4）：渲染层旧版用 `_wall[0]//6`（魔法环首圈 6 针 → 恒为 1），
    圆盘加针段被画进筒壁侧影，照片剖面对照纵向错位。
    """
    # dome=[6,12,18,24,30]（5 圈）+ wall=[30,30,24]
    assert strip_dome([6, 12, 18, 24, 30, 30, 30, 24]) == [30, 30, 24]
    # wall[0]=6：圆盘只有魔法环 1 圈
    assert strip_dome([6, 6, 12]) == [6, 12]
    # 无魔法环前缀（如裙子腰部环起 36 针）→ 原样返回
    assert strip_dome([36, 36, 30]) == [36, 36, 30]
    assert strip_dome([]) == []


def test_silhouette_svg_true_scale_and_alignment():
    """生成侧影占满可用宽度；照片剖面峰值与生成侧影最宽处对齐（N7）。

    回归：旧版 scale_x 多除一次 2 且生成侧影按直径（而非半宽）定位，
    侧影只占画布 1/4；照片剖面又按主体归一值直接画——叠加层只有生成
    侧影的一半宽且系统性偏窄，"生成 vs 照片"对比失真。
    """
    svg = render_silhouette_svg(
        [30, 30, 24, 24, 18, 18, 24, 30, 30, 36], DEFAULT,
        photo_profile=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.95, 0.85, 0.7, 0.5],
        span=(0.30, 0.62), width_px=220, height_px=300)
    polys = re.findall(r'points="([^"]+)"', svg)
    assert len(polys) == 2
    gen_xs = [float(p.split(",")[0]) for p in polys[0].split()]
    photo_xs = [float(p.split(",")[0]) for p in polys[1].split()]
    pad, width = 14.0, 220
    usable = width - 2 * pad
    # 生成侧影占满可用宽度（留 0.5px 容差）
    assert abs((max(gen_xs) - min(gen_xs)) - usable) < 0.5
    # 照片剖面峰值与生成侧影最宽处对齐（同一右边缘）
    assert abs(max(photo_xs) - max(gen_xs)) < 0.5
    assert abs(min(photo_xs) - min(gen_xs)) < 0.5


# ── O-P6：剖面线性插值采样 ────────────────────────────────────────────────

def test_sample_at_linear_interpolation():
    """插值采样：中点取均值、端点取原值、越界钳到端点区间（O-P6）。

    最近邻采样在墙圈数高于剖面分辨率时产生阶梯伪影（相邻圈取到同一行）；
    线性插值给出平滑过渡。
    """
    assert _sample_at([0.0, 10.0], 0.5) == 5.0
    assert _sample_at([3.0, 7.0, 9.0], 0.0) == 3.0
    assert _sample_at([3.0, 7.0, 9.0], 1.0) == 9.0
    assert _sample_at([3.0, 7.0, 9.0], -0.3) == 3.0   # 越界钳位
    assert _sample_at([3.0, 7.0, 9.0], 1.3) == 9.0
    # 单调递增剖面的采样保持单调（阶梯会出现平台）
    ramp = [i / 7.0 for i in range(8)]
    samples = [_sample_at(ramp, (j + 0.5) / 15) for j in range(15)]
    assert all(b > a for a, b in zip(samples, samples[1:]))  # noqa: B905
