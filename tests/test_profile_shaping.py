"""Tests for profile-driven shaping（照片剖面 → 旋转体逐圈针数，M1.2/M1.5）。"""
import math

from app.models.gauge import DEFAULT
from app.models.profile_shaping import (
    profile_to_rounds,
    render_silhouette_svg,
    rounds_to_notes,
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
    assert all(abs(b - a) <= 6 for a, b in zip(wall, wall[1:]))  # ±6 物理极限
    assert all(n >= 6 for n in wall)
    assert max(wall[1:-1]) > min(wall[0], wall[-1])  # 中段最宽（梨形保留）


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
