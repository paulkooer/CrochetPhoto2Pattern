"""Separate dimensionless photo proportions from chosen finished dimensions."""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from ..schemas import ImageAnalysis

MIN_PHOTO_TARGET_HEIGHT_CM = 10.0
MAX_PHOTO_TARGET_HEIGHT_CM = 60.0
MIN_BODY_TO_HEAD_RATIO = 2.0
MAX_BODY_TO_HEAD_RATIO = 8.0


def sizing_meta_for_analysis(
    analysis: ImageAnalysis,
    source: str,
    *,
    photo_head_to_height_ratio: Optional[float] = None,
    ratio_clamped: bool = False,
) -> Dict[str, Any]:
    """Build serializable provenance for dimensions used by the generators."""
    applied_ratio = analysis.head_diameter_cm / analysis.height_cm
    return {
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
        "note": (
            "单张照片只提供相对头身比例；厘米尺寸来自用户选择或显式默认值"
            if photo_head_to_height_ratio is not None
            else "厘米尺寸由用户直接指定，不是从照片测得"
        ),
    }


def scale_analysis_to_target_height(
    analysis: ImageAnalysis,
    target_height_cm: float,
    *,
    source: str,
) -> Tuple[ImageAnalysis, Dict[str, Any]]:
    """Apply a target height while retaining only the parser's head/body ratio.

    The parser fields use a reference scale because a single photo has no metric
    scale.  Clamp the inferred body-to-head ratio to the same 2–8 head range as
    the local vision path, then derive the target head diameter deterministically.
    """
    target = float(target_height_cm)
    if (not math.isfinite(target)
            or not MIN_PHOTO_TARGET_HEIGHT_CM <= target <= MAX_PHOTO_TARGET_HEIGHT_CM):
        raise ValueError(
            f"照片目标高度必须在 {MIN_PHOTO_TARGET_HEIGHT_CM:g}–"
            f"{MAX_PHOTO_TARGET_HEIGHT_CM:g} cm 之间")

    raw_body_ratio = analysis.height_cm / max(analysis.head_diameter_cm, 1e-6)
    body_ratio = min(max(raw_body_ratio, MIN_BODY_TO_HEAD_RATIO),
                     MAX_BODY_TO_HEAD_RATIO)
    photo_ratio = 1.0 / raw_body_ratio
    target_head = round(target / body_ratio, 1)
    scaled = analysis.model_copy(update={
        "height_cm": round(target, 1),
        "head_diameter_cm": target_head,
    })
    return scaled, sizing_meta_for_analysis(
        scaled,
        source,
        photo_head_to_height_ratio=photo_ratio,
        ratio_clamped=not math.isclose(raw_body_ratio, body_ratio),
    )
