"""colors.py - Shared yarn color table and perceptual color matching.

毛线色表的单一来源（image_parser 与 grid_pattern 共用，替代原先两份重复表）。
最近邻匹配在 CIE Lab 色彩空间做（CIE76 距离）：RGB 欧氏距离感知不均匀，
在肤色 / 灰阶区域容易误判；Lab 更接近人眼感知，纯 Python 实现，零新依赖。
"""
from __future__ import annotations

from typing import List, Tuple

RGB = Tuple[int, int, int]

YARN_COLORS: List[Tuple[RGB, str]] = [
    ((255, 228, 196), "米色"),
    ((255, 218, 185), "桃肤色"),
    ((245, 194, 158), "浅肤色"),
    ((210, 140,  80), "棕肤色"),
    ((139,  90,  43), "深棕色"),
    ((255, 255, 255), "白色"),
    ((240, 240, 240), "浅灰色"),
    ((180, 180, 180), "灰色"),
    ((100, 100, 100), "深灰色"),
    (( 30,  30,  30), "黑色"),
    ((255,   0,   0), "红色"),
    ((220,  50,  50), "暗红色"),
    ((255, 150, 150), "粉红色"),
    ((255, 105, 180), "玫红色"),
    ((255, 200,   0), "金黄色"),
    ((255, 165,   0), "橙色"),
    ((255, 255,   0), "黄色"),
    (( 50, 205,  50), "草绿色"),
    ((  0, 128,   0), "深绿色"),
    ((  0, 200, 200), "青色"),
    ((  0, 120, 215), "蓝色"),
    (( 70, 130, 180), "钢蓝色"),
    ((128,   0, 128), "紫色"),
    ((216, 191, 216), "薰衣草色"),
]


def srgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert 8-bit sRGB to CIE Lab (D65 white point)."""

    def _linear(c: float) -> float:
        c /= 255.0
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    rl, gl, bl = _linear(r), _linear(g), _linear(b)
    x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / 0.95047
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / 1.08883

    def _f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = _f(x), _f(y), _f(z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


# Precomputed Lab values for the table (module import time, 24 entries)
_YARN_LAB: List[Tuple[Tuple[float, float, float], str, RGB]] = [
    (srgb_to_lab(*rgb), name, rgb) for rgb, name in YARN_COLORS
]


def nearest_yarn(r: int, g: int, b: int) -> Tuple[str, RGB]:
    """Return (yarn name, table RGB) perceptually nearest to the given color."""
    l1, a1, b1 = srgb_to_lab(r, g, b)
    best_name, best_rgb, best_dist = "未知色", (r, g, b), float("inf")
    for (l2, a2, b2), name, rgb in _YARN_LAB:
        dist = (l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2
        if dist < best_dist:
            best_dist, best_name, best_rgb = dist, name, rgb
    return best_name, best_rgb
