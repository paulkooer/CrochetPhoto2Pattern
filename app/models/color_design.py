"""Photo-driven colorwork design — map the photo's vertical color bands
to per-round yarn colors for each amigurumi part.

设计思路（让针法配色真正来自照片）：
1. 估计背景色（四角众数），逐横带统计非背景像素映射到毛线色表后的覆盖率；
2. 选覆盖率最高的毛线色，避免不同颜色平均后产生不存在的中间色；
3. 用持续、覆盖充分的逐行主色细化边界，保留窄横条纹；相邻同色带合并；
   按部件在主体上的纵向占比（PART_SPAN）切片，
   得到该部件自上而下的色段；
4. 色段按圈数等比划分 → 每圈按区间覆盖量选色，颜色变化处生成"换线"说明；
   未分配对应圈色的色段明确提示复核。

近似性声明：不做人体分割，背景剔除是启发式的；部件纵向占比是
Amigurumi 常规比例的先验。结果可在 UI「局部修正」中逐圈调整。
"""
from __future__ import annotations

import logging
import re

from PIL import Image

from ..schemas import PART_LABELS_ZH, PartKind
from .colors import nearest_yarn_batch
from .subject import SubjectObservation

logger = logging.getLogger(__name__)

# 部件在主体（照片纵向）上的占比区间（顶部 → 底部），Amigurumi 常规比例先验。
# 单一来源用 PartKind 键（i18n 迁移收口）；PART_SPAN 为派生的中文键视图——
# 姿态实测（pose.measured_spans）与 result["spans"] 的既有口径仍是中文名，
# 边界处直接以视图消费，保持旧备份/实测数据完全兼容。
PART_SPAN_BY_KIND: dict[PartKind, tuple[float, float]] = {
    PartKind.HAT: (0.00, 0.18),
    PartKind.HEAD: (0.05, 0.30),
    PartKind.EARS: (0.18, 0.30),
    PartKind.BODY: (0.30, 0.62),
    PartKind.ARMS: (0.32, 0.55),
    PartKind.SKIRT: (0.55, 0.78),
    PartKind.LEGS: (0.62, 1.00),
    PartKind.TAIL: (0.45, 0.60),
}
PART_SPAN: dict[str, tuple[float, float]] = {
    PART_LABELS_ZH[kind]: span for kind, span in PART_SPAN_BY_KIND.items()}

_BG_DIST_THRESHOLD = 48  # 与背景色的欧氏距离超过此值视为主体像素


def estimate_background(px) -> tuple[int, int, int]:
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


def vertical_color_bands(image: Image.Image, n_bands: int = 10, *,
                         subject: SubjectObservation | None = None,
                         observation: dict | None = None,
                         refine_stripes: bool = True) -> list[dict]:
    """以 n_bands 个横带为基线，细化稳定横条纹后返回自上而下毛线色。

    refine_stripes=False 保留原固定横带投票，供可复现对照使用。
    observation 始终保留原始固定横带计数及二维色块，不随细化丢弃证据。

    主体判定优先 GrabCut 分割（subject.extract_subject，对双色/相近背景
    更稳）；失败回退四角众数背景 + 颜色距离阈值的启发式。

    Returns [{"start": 0.0, "end": 0.1, "color": "浅肤色"}, ...]
    失败（异常图）返回 []，调用方按"无配色"降级。
    """
    if observation is not None:
        observation.clear()
    try:
        import numpy as np
    except ImportError:
        return []
    try:
        img = image.convert("RGB")
        img.thumbnail((160, 160))
        px = np.asarray(img, dtype=np.int16)
        h, w = px.shape[:2]
        if n_bands < 1 or h < n_bands or w < 4:
            return []
        # 主体掩码：GrabCut 优先（掩码与小图对齐），退化/不可用回退阈值法
        from .subject import color_interior, extract_subject
        res = (subject.extract_colors(image) if subject is not None
               else color_interior(extract_subject(image, max_side=160)))
        mask = None if res is None else res[0]
        if mask is not None and mask.shape != (h, w):
            mask = None
        mask_source = "segmentation" if mask is not None else "background_distance"
        if mask is None:
            bg = np.array(estimate_background(px), dtype=np.int16)
            mask = np.abs(px - bg).sum(axis=2) > _BG_DIST_THRESHOLD
            if mask.mean() < 0.05:
                return []
        # Map actual foreground colors once, then vote per horizontal band.
        # A mean of black and white would invent grey; coverage preserves yarn.
        ys, _xs = np.nonzero(mask)
        if not len(ys):
            return []
        unique, inverse = np.unique(px[mask], axis=0, return_inverse=True)
        names, _rgbs = nearest_yarn_batch(unique)
        yarn_names, name_ids = np.unique(names, return_inverse=True)
        pixel_ids = name_ids[inverse]
        colors: list[str | None] = []
        for i in range(n_bands):
            y0, y1 = h * i // n_bands, h * (i + 1) // n_bands
            ids = pixel_ids[(ys >= y0) & (ys < y1)]
            colors.append(str(yarn_names[np.bincount(ids).argmax()]) if len(ids) else None)
        # Empty bands inherit the nearest observed band, never the background.
        # Ties choose the preceding band, independently of scan direction.
        observed = [i for i, color in enumerate(colors) if color is not None]
        bands = []
        for i, color in enumerate(colors):
            if color is None:
                color = colors[min(observed, key=lambda j: (abs(j - i), j))]
            bands.append({"start": i / n_bands, "end": (i + 1) / n_bands,
                          "color": color})
        if observation is not None:
            from .color_observation import build_observation

            observation.update(build_observation(mask, pixel_ids, yarn_names, n_bands, mask_source))
        if refine_stripes:
            bands = _refine_stripes(bands, mask, ys, pixel_ids, yarn_names)
        return _merge_bands(bands)
    except Exception as e:
        logger.warning("color band extraction failed: %s", e)
        return []


def _refine_stripes(bands, mask, ys, pixel_ids, yarn_names) -> list[dict]:
    """Overlay sustained row-majority runs on coarse bands, without filling gaps.

    Thresholds are conservative noise heuristics, not photo-calibrated confidence.
    Require >=75% agreement, sufficient foreground support and >=2 rows / 1.5%
    image height. Minority patches stay in ColorObservation, not whole rounds.
    Empty/ambiguous rows retain the coarse estimate. Work is bounded by 160 rows.
    """
    import numpy as np

    h = mask.shape[0]
    histogram = np.zeros((h, len(yarn_names)), dtype=np.int32)
    np.add.at(histogram, (ys, pixel_ids), 1)
    support = histogram.sum(axis=1)
    winners = histogram.argmax(axis=1)
    minimum_support = max(4, int(np.ceil(support.max() * 0.2)))
    reliable = ((support >= minimum_support)
                & (histogram[np.arange(h), winners] >= 0.75 * support))
    rows = np.where(reliable, winners, -1)
    minimum_height = max(2, int(np.ceil(h * 0.015)))
    runs = []
    start = 0
    while start < h:
        end = start + 1
        while end < h and rows[end] == rows[start]:
            end += 1
        if rows[start] >= 0 and end - start >= minimum_height:
            runs.append({"start": start / h, "end": end / h,
                         "color": str(yarn_names[rows[start]])})
        start = end
    # Preserve exact coarse boundaries, including when h is not divisible by n_bands.
    edges = sorted({b[k] for b in bands + runs for k in ("start", "end")})
    refined = []
    for start, end in zip(edges, edges[1:], strict=False):
        middle = (start + end) / 2
        source = next((r for r in runs if r["start"] <= middle < r["end"]), None)
        if source is None:
            source = next(b for b in bands if b["start"] <= middle < b["end"])
        refined.append({"start": start, "end": end, "color": source["color"]})
    return refined


def _merge_bands(bands: list[dict]) -> list[dict]:
    """相邻同色带合并（两条提取路径共用的收尾步骤）。"""
    merged: list[dict] = []
    for b in bands:
        if merged and merged[-1]["color"] == b["color"]:
            merged[-1]["end"] = b["end"]
        else:
            merged.append(dict(b))
    return merged


def color_blocks_for_part(
    bands: list[dict], part_name: str,
    spans: dict[str, tuple[float, float]] | None = None,
) -> list[tuple[float, float, str]]:
    """取某部件纵向占比内的色段（合并相邻同色后）。

    spans（S1）：姿态关键点实测的部件占比；None 时回退 PART_SPAN 先验。
    """
    span = (spans or PART_SPAN).get(part_name)
    if not span or not bands:
        return []
    start, end = span
    blocks: list[tuple[float, float, str]] = []
    for b in bands:
        s, e = max(b["start"], start), min(b["end"], end)
        if e - s <= 1e-9:
            continue
        if blocks and blocks[-1][2] == b["color"]:
            blocks[-1] = (blocks[-1][0], e, b["color"])
        else:
            blocks.append((s, e, b["color"]))
    return blocks


def round_color(frac: float, blocks: list[tuple[float, float, str]]) -> str | None:
    """主体纵向位置 frac（0 顶 → 1 底）落在的色段颜色。"""
    for s, e, name in blocks:
        if s <= frac < e:
            return name
    return blocks[-1][2] if blocks else None


def round_color_plan(
    blocks: list[tuple[float, float, str]],
    span: tuple[float, float],
    n_rounds: int,
    *,
    bottom_up: bool = False,
    height_ranges: list[tuple[float, float]] | None = None,
) -> tuple[list[str | None], int]:
    """Choose one yarn per axial round by total interval overlap.

    Minimizes mismatched vertical length for each round, rather than magnifying
    a tiny stripe that happens to cross its midpoint. Equal coverage keeps the
    midpoint color when possible, then the first color in image order. Compute
    top-down once and reverse for equal-height bottom-up work; explicit axial
    ranges instead follow their physical positions. Return blocks with no overlapping
    round assigned their color; this is resolution loss, not a confidence score.
    Blocks are ordered, non-overlapping photo intervals from color_blocks_for_part.
    """
    import math

    start, end = span
    if n_rounds < 1 or not (math.isfinite(start) and math.isfinite(end) and start < end):
        raise ValueError("配色映射需要正圈数和有效部件区间")
    if height_ranges is None:
        intervals = [(start + (end - start) * j / n_rounds,
                      start + (end - start) * (j + 1) / n_rounds) for j in range(n_rounds)]
    else:
        if len(height_ranges) != n_rounds or any(
            not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b) for a, b in height_ranges
        ):
            raise ValueError("配色映射需要每圈的有效纵向范围")
        extent = max(b for _a, b in height_ranges)
        intervals = [(start + (end - start) * a / extent,
                      start + (end - start) * b / extent)
                     for a, b in ([(extent - b, extent - a) for a, b in height_ranges]
                                  if bottom_up else height_ranges)]
    colors: list[str | None] = []
    represented: set[int] = set()
    for lo, hi in intervals:
        overlaps = [(i, name, min(e, hi) - max(s, lo))
                    for i, (s, e, name) in enumerate(blocks) if min(e, hi) > max(s, lo)]
        coverage: dict[str, float] = {}
        for _i, name, length in overlaps:
            coverage[name] = coverage.get(name, 0.0) + length
        if not coverage:
            colors.append(None)
            continue
        maximum = max(coverage.values())
        tied = [name for name, length in coverage.items()
                if math.isclose(length, maximum, rel_tol=1e-12, abs_tol=0.0)]
        midpoint = round_color((lo + hi) / 2, blocks)
        selected = midpoint if midpoint in tied else tied[0]
        colors.append(selected)
        represented.update(i for i, name, _length in overlaps if name == selected)
    eligible = {i for i, (s, e, _name) in enumerate(blocks) if min(e, end) > max(s, start)}
    if bottom_up and height_ranges is None:
        colors.reverse()
    return colors, len(eligible - represented)


def blocks_summary_text(round_colors: list[str | None], rows: list[int] | None = None) -> str:
    """逐圈颜色列表 → "R1–R4 浅肤色；R5–R10 深棕色" 摘要。"""
    segs: list[str] = []
    i = 0
    while i < len(round_colors):
        j = i
        while j + 1 < len(round_colors) and round_colors[j + 1] == round_colors[i]:
            j += 1
        color = round_colors[i] or "?"
        first, last = (rows[i], rows[j]) if rows is not None else (i + 1, j + 1)
        segs.append(f"R{first}–R{last} {color}" if j > i else f"R{first} {color}")
        i = j + 1
    return "；".join(segs)


# Exact legacy generated phrases only; unrelated maker notes are preserved.
_COLOR_CHANGE_RE = re.compile(
    r"；?换线：[^（；\n]+（前一针最后一次挂线改用新色；螺旋圈仍可能出现台阶）")
_COLOR_SUMMARY_RE = re.compile(r" 配色（按钩织圈序，自[上下]而[上下]）：[^。]*。")


def refresh_color_instructions(part: dict) -> None:
    """Derive transitions and summaries from current yarns, retaining manual prose.

    Track generated fragments separately while keeping the composed notes readable
    by older consumers. Legacy backups are migrated using exact known phrases.
    """
    rounds = part["rounds"]
    colors = [rd.get("color") or part.get("color") or "未指定" for rd in rounds]
    mapped = any(rd.get("color") for rd in rounds)
    for i, rd in enumerate(rounds):
        if mapped:
            # Freeze inherited yarns before recomputing the part's dominant yarn;
            # repeated refreshes must not recolor previously unspecified rows.
            rd["color"] = colors[i]
        note = rd.get("notes") or ""
        auto = rd.get("auto_color_note")
        if auto:
            note = note.replace("；" + auto, "").removeprefix(auto)
        note = _COLOR_CHANGE_RE.sub("", note)
        auto = None
        if mapped and i and colors[i] != colors[i - 1]:
            auto = (f"换线：{colors[i]}（前一针最后一次挂线改用新色；"
                    "螺旋圈仍可能出现台阶）")
            note = f"{note}；{auto}" if note else auto
        rd["notes"] = note or None
        rd["auto_color_note"] = auto
    note = part.get("notes") or ""
    auto = part.get("auto_color_summary")
    if auto:
        note = note.replace(auto, "")
    note = _COLOR_SUMMARY_RE.sub("", note)
    auto = None
    if mapped:
        part["color"] = max(dict.fromkeys(colors), key=colors.count)
        if len(set(colors)) > 1:
            direction = "自下而上" if part["name"] in {"身体", "手臂", "腿部"} else "自上而下"
            auto = (f" 配色（按钩织圈序，{direction}）："
                    f"{blocks_summary_text(colors, [rd['row'] for rd in rounds])}。")
            note += auto
    part["notes"] = note or None
    part["auto_color_summary"] = auto
