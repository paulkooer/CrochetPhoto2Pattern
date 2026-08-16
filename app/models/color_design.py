"""Photo-driven colorwork design — map the photo's vertical color bands
to per-round yarn colors for each amigurumi part.

设计思路（让针法配色真正来自照片）：
1. 估计背景色（四角众数），逐横带取"非背景像素"的平均色；
2. 平均色经 CIE Lab 匹配到毛线色表（与全局色板同一来源）；
3. 相邻同色带合并；按部件在主体上的纵向占比（PART_SPAN）切片，
   得到该部件自上而下的色段；
4. 色段按圈数等比铺开 → 每圈一个颜色，颜色变化处生成"换线"说明。

近似性声明：不做人体分割，背景剔除是启发式的；部件纵向占比是
Amigurumi 常规比例的先验。结果可在 UI「局部修正」中逐圈调整。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from PIL import Image

from .colors import nearest_yarn

logger = logging.getLogger(__name__)

# 部件在主体（照片纵向）上的占比区间（顶部 → 底部），Amigurumi 常规比例先验
PART_SPAN: Dict[str, Tuple[float, float]] = {
    "帽子": (0.00, 0.18),
    "头部": (0.05, 0.30),
    "耳朵": (0.18, 0.30),
    "身体": (0.30, 0.62),
    "手臂": (0.32, 0.55),
    "裙子": (0.55, 0.78),
    "腿部": (0.62, 1.00),
    "尾巴": (0.45, 0.60),
}

_BG_DIST_THRESHOLD = 48  # 与背景色的欧氏距离超过此值视为主体像素


def estimate_background(px) -> Tuple[int, int, int]:
    """四角小块的众数（mode）背景色。

    真·众数：量化到 16 级/通道后按出现次数取最大——双色背景（白墙+深色
    地板）会命中其中一色而非两者的中间值（旧实现是"量化后均值"，系统性
    偏暗且可能落在两色之间导致背景剔除失效）。
    """
    import numpy as np

    h, w = px.shape[:2]
    k = max(2, min(h, w) // 20)
    corners = np.concatenate([
        px[:k, :k].reshape(-1, 3), px[:k, -k:].reshape(-1, 3),
        px[-k:, :k].reshape(-1, 3), px[-k:, -k:].reshape(-1, 3),
    ]).astype(np.int64)
    q = corners // 16
    packed = q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2]
    values, counts = np.unique(packed, return_counts=True)
    m = int(values[counts.argmax()])
    # 返回该量化桶的中心（+8），比桶左沿更接近真值
    return ((m >> 16) & 255) * 16 + 8, ((m >> 8) & 255) * 16 + 8, (m & 255) * 16 + 8


def vertical_color_bands(image: Image.Image, n_bands: int = 10) -> List[Dict]:
    """把照片纵向切成 n_bands 个横带，返回每带的毛线色（自上而下）。

    Returns [{"start": 0.0, "end": 0.1, "color": "浅肤色"}, ...]
    失败（异常图）返回 []，调用方按"无配色"降级。
    """
    try:
        import numpy as np
    except ImportError:
        return []
    try:
        img = image.convert("RGB")
        img.thumbnail((160, 160))
        px = np.asarray(img, dtype=np.int16)
        h, w = px.shape[:2]
        if h < n_bands or w < 4:
            return []
        bg = np.array(estimate_background(px), dtype=np.int16)
        bands: List[Dict] = []
        subject_total = 0
        pixel_total = 0
        for i in range(n_bands):
            y0, y1 = h * i // n_bands, h * (i + 1) // n_bands
            block = px[y0:y1].reshape(-1, 3)
            dist = np.abs(block - bg).sum(axis=1)
            subject = block[dist > _BG_DIST_THRESHOLD]
            subject_total += len(subject)
            pixel_total += len(block)
            # 主体像素不足的带兜底用整带均值（背景带），但若全图几乎无主体
            # → 视为"没有可分析的物体"，返回空让上层降级为单色
            mean = subject.mean(axis=0) if len(subject) else block.mean(axis=0)
            name, _rgb = nearest_yarn(*(int(v) for v in mean))
            bands.append({
                "start": i / n_bands,
                "end": (i + 1) / n_bands,
                "color": name,
            })
        if pixel_total and subject_total / pixel_total < 0.05:
            return []
        # 相邻同色合并
        merged: List[Dict] = []
        for b in bands:
            if merged and merged[-1]["color"] == b["color"]:
                merged[-1]["end"] = b["end"]
            else:
                merged.append(dict(b))
        return merged
    except Exception as e:
        logger.warning("color band extraction failed: %s", e)
        return []


def color_blocks_for_part(
    bands: List[Dict], part_name: str
) -> List[Tuple[float, float, str]]:
    """取某部件纵向占比内的色段（合并相邻同色后）。"""
    span = PART_SPAN.get(part_name)
    if not span or not bands:
        return []
    start, end = span
    blocks: List[Tuple[float, float, str]] = []
    for b in bands:
        s, e = max(b["start"], start), min(b["end"], end)
        if e - s <= 1e-9:
            continue
        if blocks and blocks[-1][2] == b["color"]:
            blocks[-1] = (blocks[-1][0], e, b["color"])
        else:
            blocks.append((s, e, b["color"]))
    return blocks


def round_color(frac: float, blocks: List[Tuple[float, float, str]]) -> Optional[str]:
    """主体纵向位置 frac（0 顶 → 1 底）落在的色段颜色。"""
    for s, e, name in blocks:
        if s <= frac < e:
            return name
    return blocks[-1][2] if blocks else None


def blocks_summary_text(round_colors: List[Optional[str]]) -> str:
    """逐圈颜色列表 → "R1–R4 浅肤色；R5–R10 深棕色" 摘要。"""
    segs: List[str] = []
    i = 0
    while i < len(round_colors):
        j = i
        while j + 1 < len(round_colors) and round_colors[j + 1] == round_colors[i]:
            j += 1
        color = round_colors[i] or "?"
        segs.append(f"R{i + 1}–R{j + 1} {color}" if j > i else f"R{i + 1} {color}")
        i = j + 1
    return "；".join(segs)
