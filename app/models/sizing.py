"""Separate dimensionless photo proportions from chosen finished dimensions."""
from __future__ import annotations

import math
from typing import Any

from ..schemas import ImageAnalysis

MIN_PHOTO_TARGET_HEIGHT_CM = 10.0
MAX_PHOTO_TARGET_HEIGHT_CM = 60.0
MIN_BODY_TO_HEAD_RATIO = 2.0
MAX_BODY_TO_HEAD_RATIO = 8.0

# 头身比例风格：照片身高/头径（钳到 2–8）线性压缩到玩偶区间 [2, 上限]。照片保留的是
# 被摄者的写实比例，常见 Amigurumi 玩偶约 1:2–1:3；直接套用写实比例会让头部和四肢
# 小到钩不成形。上限是设计取舍，不是照片实测，生成结果仍记录原始照片比例。
PROPORTION_STYLES: dict[str, float] = {"q": 3.0, "balanced": 4.5, "photo": MAX_BODY_TO_HEAD_RATIO}
PROPORTION_STYLE_LABELS: dict[str, str] = {
    "q": "Q 版（推荐）", "balanced": "适中", "photo": "写实（照片原比例）",
}
DEFAULT_PROPORTION_STYLE = "q"


def styled_body_ratio(photo_body_ratio: float, style: str) -> float:
    """Map a photo height/head ratio into the chosen style's doll range."""
    if style not in PROPORTION_STYLES:
        raise ValueError(f"头身比例风格必须是 {'/'.join(PROPORTION_STYLES)}，得到 {style!r}")
    low, high = MIN_BODY_TO_HEAD_RATIO, MAX_BODY_TO_HEAD_RATIO
    clamped = min(max(photo_body_ratio, low), high)
    return low + (clamped - low) * (PROPORTION_STYLES[style] - low) / (high - low)


def sizing_meta_for_analysis(
    analysis: ImageAnalysis,
    source: str,
    *,
    photo_head_to_height_ratio: float | None = None,
    ratio_clamped: bool = False,
    proportion_style: str | None = None,
) -> dict[str, Any]:
    """Build serializable provenance for dimensions used by the generators."""
    applied_ratio = analysis.head_diameter_cm / analysis.height_cm
    note = "厘米尺寸由用户直接指定，不是从照片测得"
    if photo_head_to_height_ratio is not None:
        styled = (f"已按「{PROPORTION_STYLE_LABELS[proportion_style]}」风格换算为玩偶比例；"
                  if proportion_style not in (None, "photo") else "")
        note = f"单张照片只提供相对头身比例；{styled}厘米尺寸来自用户选择或显式默认值"
    meta = {
        "source": source,
        "target_height_cm": round(float(analysis.height_cm), 1),
        "target_head_diameter_cm": round(float(analysis.head_diameter_cm), 1),
        "photo_head_to_height_ratio": (
            round(float(photo_head_to_height_ratio), 4)
            if photo_head_to_height_ratio is not None else None
        ),
        "applied_head_to_height_ratio": round(applied_ratio, 4),
        "ratio_clamped": bool(ratio_clamped),
        "absolute_scale_from_photo": False,
        "note": note,
    }
    if proportion_style is not None:
        meta["proportion_style"] = proportion_style
    return meta


def scale_analysis_to_target_height(
    analysis: ImageAnalysis,
    target_height_cm: float,
    *,
    source: str,
    proportion_style: str = "photo",
) -> tuple[ImageAnalysis, dict[str, Any]]:
    """Apply a target height while retaining only the parser's head/body ratio.

    The parser fields use a reference scale because a single photo has no metric
    scale.  Clamp the inferred body-to-head ratio to the same 2–8 head range as
    the local vision path, map it into ``proportion_style``'s doll range, then
    derive the target head diameter deterministically.  The default ``photo``
    style keeps the photo ratio; product entry points pass their chosen style.
    """
    target = float(target_height_cm)
    if (not math.isfinite(target)
            or not MIN_PHOTO_TARGET_HEIGHT_CM <= target <= MAX_PHOTO_TARGET_HEIGHT_CM):
        raise ValueError(
            f"照片目标高度必须在 {MIN_PHOTO_TARGET_HEIGHT_CM:g}–"
            f"{MAX_PHOTO_TARGET_HEIGHT_CM:g} cm 之间")

    raw_body_ratio = analysis.height_cm / max(analysis.head_diameter_cm, 1e-6)
    body_ratio = styled_body_ratio(raw_body_ratio, proportion_style)
    photo_ratio = 1.0 / raw_body_ratio
    target_head = round(target / body_ratio, 1)
    scaled = analysis.model_copy(update={
        "height_cm": round(target, 1),
        "head_diameter_cm": target_head,
    })
    clamped = min(max(raw_body_ratio, MIN_BODY_TO_HEAD_RATIO), MAX_BODY_TO_HEAD_RATIO)
    return scaled, sizing_meta_for_analysis(
        scaled,
        source,
        photo_head_to_height_ratio=photo_ratio,
        ratio_clamped=not math.isclose(raw_body_ratio, clamped),
        proportion_style=proportion_style,
    )
