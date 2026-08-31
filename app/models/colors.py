"""colors.py - Shared yarn color table and perceptual color matching.

毛线色表的单一来源（image_parser 与 grid_pattern 共用，替代原先两份重复表）。
最近邻匹配的色差用 CIEDE2000（CIE 2000 公式）计算：
- RGB 欧氏距离感知不均匀（蓝区/近中性区误差大），已在 fable5 轮升级为
  CIE Lab（CIE76）；CIE76 对蓝色 hue 旋转与中性色仍系统性失真。
- CIEDE2000（Sharma, Wu & Dalal 2005 的实现注记是标准参考）在 hue/
  彩度/明度三轴引入非线性校正，是当前工业与人眼感知对齐的主流公式。
- 实现按 Sharma 官方实现注记逐步转写，tests/test_colors.py 用论文提供的
  34 组官方补充测试数据逐对验证（±1e-4）。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

RGB = Tuple[int, int, int]
LAB = Tuple[float, float, float]

YARN_COLORS: List[Tuple[RGB, str]] = [
    ((255, 228, 196), "米色"),
    ((255, 218, 185), "桃肤色"),
    ((246, 237, 228), "白皙肤色"),
    ((245, 194, 158), "浅肤色"),
    ((210, 140,  80), "棕肤色"),
    ((160, 126,  86), "小麦肤色"),
    ((130,  92,  67), "咖啡肤色"),
    (( 96,  65,  52), "深肤色"),
    (( 58,  49,  42), "暗肤色"),
    (( 41,  36,  32), "深褐肤色"),
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


def srgb_to_lab(r: int, g: int, b: int) -> LAB:
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


def ciede2000(lab1: LAB, lab2: LAB, kl: float = 1.0, kc: float = 1.0,
              kh: float = 1.0) -> float:
    """CIEDE2000 色差 ΔE00（Sharma, Wu & Dalal 2005 实现注记口径）。

    官方 34 组补充测试数据见 tests/test_colors.py（数据源：
    gsharma/ciede2000 dataNprograms/ciede2000testdata.txt）。
    """
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2.0
    c_bar7 = c_bar ** 7
    g = 0.5 * (1.0 - math.sqrt(c_bar7 / (c_bar7 + 25.0 ** 7)))
    a1p = (1.0 + g) * a1
    a2p = (1.0 + g) * a2
    c1p = math.hypot(a1p, b1)
    c2p = math.hypot(a2p, b2)

    def _hue(ap: float, b: float) -> float:
        if ap == 0.0 and b == 0.0:
            return 0.0
        h = math.degrees(math.atan2(b, ap))
        return h + 360.0 if h < 0.0 else h

    h1p = _hue(a1p, b1)
    h2p = _hue(a2p, b2)

    dlp = l2 - l1
    dcp = c2p - c1p

    if c1p * c2p == 0.0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180.0:
            dhp -= 360.0
        elif dhp < -180.0:
            dhp += 360.0
    dhp_big = 2.0 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2.0)

    lbp = (l1 + l2) / 2.0
    cbp = (c1p + c2p) / 2.0

    if c1p * c2p == 0.0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hbp = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        hbp = (h1p + h2p + 360.0) / 2.0
    else:
        hbp = (h1p + h2p - 360.0) / 2.0

    t = (1.0 - 0.17 * math.cos(math.radians(hbp - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * hbp))
         + 0.32 * math.cos(math.radians(3.0 * hbp + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * hbp - 63.0)))
    dtheta = 30.0 * math.exp(-(((hbp - 275.0) / 25.0) ** 2))
    cbp7 = cbp ** 7
    rc = 2.0 * math.sqrt(cbp7 / (cbp7 + 25.0 ** 7))
    sl = 1.0 + (0.015 * (lbp - 50.0) ** 2
                / math.sqrt(20.0 + (lbp - 50.0) ** 2))
    sc = 1.0 + 0.045 * cbp
    sh = 1.0 + 0.015 * cbp * t
    rt = -math.sin(math.radians(2.0 * dtheta)) * rc

    sl_term = dlp / (kl * sl)
    sc_term = dcp / (kc * sc)
    sh_term = dhp_big / (kh * sh)
    return math.sqrt(sl_term ** 2 + sc_term ** 2 + sh_term ** 2
                     + rt * sc_term * sh_term)


def _srgb_to_lab_vec(rgb: "np.ndarray") -> "np.ndarray":
    """srgb_to_lab 的向量化版：(N,3) uint8/float → (N,3) Lab。数值一致。"""
    c = rgb.astype(np.float64) / 255.0
    lin = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    rl, gl, bl = lin[:, 0], lin[:, 1], lin[:, 2]
    x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) / 0.95047
    y = (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750)
    z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) / 1.08883
    f = np.where(np.stack([x, y, z], axis=1) > 0.008856,
                 np.clip(np.stack([x, y, z], axis=1), 1e-12, None) ** (1 / 3),
                 7.787 * np.stack([x, y, z], axis=1) + 16.0 / 116.0)
    fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
    return np.stack([116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)],
                    axis=1)


def ciede2000_vec(lab1: "np.ndarray", lab2: "np.ndarray",
                  pairwise: Optional[bool] = None) -> "np.ndarray":
    """ciede2000 的向量化版（K1）。

    lab1: (N,3)；lab2: (N,3) 或 (M,3)。pairwise=None 自动判（lab2 行数
    == lab1 行数 → 逐对，否则广播成 N×M）；显式传 False 强制矩阵语义
    （N==M 时自动判会误判——如 1 桶 vs 1 选色）。
    逐行/逐对与标量 ciede2000 数值一致（官方 34 组 + 随机等价测试锁定）。
    """
    a = np.atleast_2d(np.asarray(lab1, dtype=np.float64))
    b = np.atleast_2d(np.asarray(lab2, dtype=np.float64))
    if pairwise is None:
        pairwise = b.shape[0] == a.shape[0]
    l1, a1, b1 = a[:, 0], a[:, 1], a[:, 2]
    if not pairwise:
        # M 分支：左端升为 (N,1) 以按行广播成 (N,M)
        l1, a1, b1 = l1[:, None], a1[:, None], b1[:, None]
    l2, a2, b2 = b[:, 0], b[:, 1], b[:, 2]

    c1 = np.hypot(a1, b1)
    c2 = np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2.0
    c_bar7 = c_bar ** 7
    g = 0.5 * (1.0 - np.sqrt(c_bar7 / (c_bar7 + 25.0 ** 7)))
    a1p = (1.0 + g) * a1
    a2p = (1.0 + g) * a2
    c1p = np.hypot(a1p, b1)
    c2p = np.hypot(a2p, b2)

    def _hue(ap, bb):
        h = np.degrees(np.arctan2(bb, ap))
        return np.where(h < 0.0, h + 360.0, h)

    h1p = np.where((a1p == 0) & (b1 == 0), 0.0, _hue(a1p, b1))
    h2p = np.where((a2p == 0) & (b2 == 0), 0.0, _hue(a2p, b2))

    dlp = l2 - l1
    dcp = c2p - c1p
    degenerate = (c1p * c2p) == 0.0
    raw_dhp = h2p - h1p
    wrapped = np.where(raw_dhp > 180.0, raw_dhp - 360.0,
                       np.where(raw_dhp < -180.0, raw_dhp + 360.0, raw_dhp))
    dhp = np.where(degenerate, 0.0, wrapped)
    dhp_big = 2.0 * np.sqrt(c1p * c2p) * np.sin(np.radians(dhp) / 2.0)

    lbp = (l1 + l2) / 2.0
    cbp = (c1p + c2p) / 2.0
    sum_h = h1p + h2p
    hbp = np.where(
        degenerate, sum_h,
        np.where(np.abs(h1p - h2p) <= 180.0, sum_h / 2.0,
                 np.where(sum_h < 360.0, (sum_h + 360.0) / 2.0,
                          (sum_h - 360.0) / 2.0)))

    t = (1.0 - 0.17 * np.cos(np.radians(hbp - 30.0))
         + 0.24 * np.cos(np.radians(2.0 * hbp))
         + 0.32 * np.cos(np.radians(3.0 * hbp + 6.0))
         - 0.20 * np.cos(np.radians(4.0 * hbp - 63.0)))
    dtheta = 30.0 * np.exp(-(((hbp - 275.0) / 25.0) ** 2))
    cbp7 = cbp ** 7
    rc = 2.0 * np.sqrt(cbp7 / (cbp7 + 25.0 ** 7))
    sl = 1.0 + (0.015 * (lbp - 50.0) ** 2 / np.sqrt(20.0 + (lbp - 50.0) ** 2))
    sc = 1.0 + 0.045 * cbp
    sh = 1.0 + 0.015 * cbp * t
    rt = -np.sin(np.radians(2.0 * dtheta)) * rc

    sl_t = dlp / sl
    sc_t = dcp / sc
    sh_t = dhp_big / sh
    return np.sqrt(sl_t ** 2 + sc_t ** 2 + sh_t ** 2 + rt * sc_t * sh_t)


def nearest_yarn_batch(rgbs: "np.ndarray") -> Tuple[List[str], List[RGB]]:
    """最近邻匹配的批量版（K1）：(N,3) RGB → (色名列表, 色表 RGB 列表)。

    与逐像素调用 nearest_yarn 结果一致（等价测试锁定）；网格/色板等
    大批量场景用此路径（实测 33× 提速）。
    """
    arr = np.asarray(rgbs, dtype=np.int32)
    labs = _srgb_to_lab_vec(arr)
    table_labs = np.array([lab for lab, _n, _r in _YARN_LAB], dtype=np.float64)
    dist = ciede2000_vec(labs, table_labs, pairwise=False)  # (N, len(table))
    best = np.argmin(dist, axis=1)
    names = [_YARN_LAB[i][1] for i in best]
    rgbs_out = [_YARN_LAB[i][2] for i in best]
    return names, rgbs_out


# Precomputed Lab values for the table (module import time, 24 entries)
_YARN_LAB: List[Tuple[LAB, str, RGB]] = [
    (srgb_to_lab(*rgb), name, rgb) for rgb, name in YARN_COLORS
]


# 品牌色号对照（U6）——仅收录**已联网核实**的 Scheepjes Catona 色号
# （来源：scheepjes.com 官方与 woolwarehouse.co.uk 等零售商商品页，2026-08
# 核实）。毛线界无 DMC 级统一标准，未收录的色名不提供色号（宁缺毋错），
# 购买请以实物色卡为准。
BRAND_CODES: Dict[str, str] = {
    "黑色": "Catona 110 (Jet Black)",
    "白色": "Catona 106 (Snow White)",
    "橙色": "Catona 189 (Royal Orange)",
    "黄色": "Catona 208 (Yellow Gold)",
    "草绿色": "Catona 389 (Apple Green)",
    "青色": "Catona 397 (Cyan)",
    "红色": "Catona 506 (Candy Apple)",
    "蓝色": "Catona 113 (Delphinium，近似)",
}


def brand_code(name: str) -> Optional[str]:
    """毛线色名 → 品牌参考色号；未收录返回 None（不编造）。"""
    return BRAND_CODES.get(name)


def color_distance(rgb1: RGB, rgb2: RGB) -> float:
    """两个 sRGB 颜色间的感知距离（CIEDE2000）——语义色吸附等处共用。"""
    return ciede2000(srgb_to_lab(*rgb1), srgb_to_lab(*rgb2))


def pick_yarn_palette(pixels, n_colors: int) -> List[RGB]:
    """像素集合 → 覆盖率最高的 n_colors 种毛线色（S3 直量化）。

    旧路径"RGB 中位切分出任意色 → 再映射毛线表"是双重量化：切分中心
    本身不可购买。这里直接在毛线色表上做分配——16 级/通道量化桶统计
    覆盖率，取前 n 种，再把所有像素重新分配给所选色（CIEDE2000 最近邻）。
    结果的每一色都是真实可购买的毛线，且对照片的颜色分布更忠实。

    Args:
        pixels:   可迭代的 (r, g, b) 元组（建议先量化降采样）。
        n_colors: 目标色数（钳到 [1, 色表大小]）。

    Returns:
        按覆盖率降序的毛线 RGB 列表（可能少于 n_colors：低覆盖噪声剔除）。
    """
    from collections import Counter

    counts = Counter(pixels)
    if not counts:
        return []
    n = max(1, min(n_colors, len(YARN_COLORS)))
    total = sum(counts.values())

    # 桶级 CIEDE2000（K1 批量版）：桶色 → 全色表的最近色名
    uniq_rgbs = np.array(list(counts.keys()), dtype=np.int32)
    uniq_cnts = np.array(list(counts.values()), dtype=np.int64)
    bucket_names, _ = nearest_yarn_batch(uniq_rgbs)
    yarn_cover: Counter = Counter()
    if len(bucket_names) != len(uniq_cnts):
        raise RuntimeError("nearest-yarn result count does not match color buckets")
    for name, cnt in zip(bucket_names, uniq_cnts):  # noqa: B905 - length checked above
        yarn_cover[name] += int(cnt)

    chosen = [name for name, _c in yarn_cover.most_common(n)]
    chosen_rgb = {name: rgb for rgb, name in YARN_COLORS if name in set(chosen)}
    chosen_lab = np.array([srgb_to_lab(*chosen_rgb[name]) for name in chosen],
                          dtype=np.float64)

    # 重新分配：每桶归入所选色中 CIEDE2000 最近者（批量），覆盖率归并
    labs = _srgb_to_lab_vec(uniq_rgbs)
    dmat = ciede2000_vec(labs, chosen_lab, pairwise=False)  # (桶数, n)
    best_idx = dmat.argmin(axis=1)
    final_cover: Counter = Counter()
    if len(best_idx) != len(uniq_cnts):
        raise RuntimeError("palette assignment count does not match color buckets")
    for bi, cnt in zip(best_idx, uniq_cnts):  # noqa: B905 - length checked above
        final_cover[chosen[bi]] += int(cnt)

    # 覆盖率 <1% 的长尾剔除（噪声桶被强并到大色后的虚假占位）
    floor = 0.01 * total
    out_names = [name for name, c in final_cover.most_common(n) if c >= floor]
    return [chosen_rgb[name] for name in out_names] or [
        chosen_rgb[final_cover.most_common(1)[0][0]]]


def nearest_yarn(r: int, g: int, b: int) -> Tuple[str, RGB]:
    """Return (yarn name, table RGB) perceptually nearest to the given color."""
    lab1 = srgb_to_lab(r, g, b)
    best_name, best_rgb, best_dist = "未知色", (r, g, b), float("inf")
    for lab2, name, rgb in _YARN_LAB:
        dist = ciede2000(lab1, lab2)
        if dist < best_dist:
            best_dist, best_name, best_rgb = dist, name, rgb
    return best_name, best_rgb
