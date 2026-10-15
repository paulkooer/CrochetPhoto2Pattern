"""Local crop/review helpers. Coordinates are relative to the cropped image."""

from __future__ import annotations

import math
from copy import copy
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.schemas import ImageAnalysis

from .subject import SubjectObservation

if TYPE_CHECKING:
    from .orchestrator import PhotoDraft


def crop_photo(image: Image.Image, horizontal: tuple[int, int], vertical: tuple[int, int]) -> Image.Image:
    if any(not 0 <= lo < hi <= 100 for lo, hi in (horizontal, vertical)):
        raise ValueError("裁剪范围必须有宽度和高度")
    w, h = image.size
    box = (
        round(w * horizontal[0] / 100),
        round(h * vertical[0] / 100),
        round(w * horizontal[1] / 100),
        round(h * vertical[1] / 100),
    )
    if box[2] - box[0] < 20 or box[3] - box[1] < 20:
        raise ValueError("裁剪后图片至少需要 20 × 20 像素")
    return image.crop(box)


def review_overlay(
    subject: SubjectObservation, head_box: tuple[float, float, float, float] | None = None,
    body_box: tuple[float, float, float, float] | None = None,
) -> Image.Image:
    """Green = subject mask; orange = head; blue = user-selected body region."""
    img = subject.image.copy().convert("RGB")
    img.thumbnail((800, 800))
    segmentation = subject.segmentation
    if segmentation is not None:
        mask, _ = segmentation
        pil_mask = Image.fromarray(mask.astype(np.uint8) * 255)
        eroded = pil_mask.filter(ImageFilter.MinFilter(3))
        edge = Image.fromarray(np.asarray(pil_mask) - np.asarray(eroded))
        edge = edge.resize(img.size, Image.Resampling.NEAREST)
        img.paste((0, 210, 120), mask=edge)
    if head_box is not None:
        x0, y0, x1, y1 = head_box
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("头部框必须位于裁剪图内且具有面积")
        ImageDraw.Draw(img).rectangle(
            (x0 * (img.width - 1), y0 * (img.height - 1), x1 * (img.width - 1), y1 * (img.height - 1)),
            outline=(255, 145, 0),
            width=3,
        )
    if body_box is not None:
        _validate_body_box(body_box)
        x0, y0, x1, y1 = body_box
        ImageDraw.Draw(img).rectangle(
            (x0 * (img.width - 1), y0 * (img.height - 1), x1 * (img.width - 1), y1 * (img.height - 1)),
            outline=(30, 120, 255), width=3,
        )
    return img


def _validate_body_box(box: tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("身体框必须位于裁剪图内且具有面积")


def with_reviewed_body(draft: PhotoDraft, box: tuple[float, float, float, float]) -> PhotoDraft:
    """Restrict shape measurement to a user box without mutating the draft.

    Keep the full image coordinate system: existing span consumers, backups
    and resizing can reuse the measured profile without the original image.
    A box selects existing foreground; it never invents a rectangular body.
    """
    from .color_design import PART_SPAN
    from .geometry import BodyRegionObservation, _mask_width_profile

    _validate_body_box(box)
    if not draft.geometry.used_for_generation:
        raise ValueError("Mock 模式不使用照片身体轮廓，请切换本地分析")
    segmentation = draft.subject.segmentation
    if segmentation is None:
        raise ValueError("未取得可靠主体掩码，无法按身体框测量；请重新裁剪或关闭身体框")
    mask, small = segmentation
    x0, y0, x1, y1 = box
    left, right = round(x0 * small.width), round(x1 * small.width)
    top, bottom = round(y0 * small.height), round(y1 * small.height)
    if right - left < 3 or bottom - top < 3 or (y1 - y0) * 40 < 3:
        raise ValueError("身体框过小，请扩大范围以测量至少三个轮廓采样带")
    selected = np.zeros_like(mask)
    selected[top:bottom, left:right] = mask[top:bottom, left:right]
    profile = _mask_width_profile(selected, 40)
    if profile is None:
        raise ValueError("身体框内没有足够的主体像素，请调整范围")
    observation = BodyRegionObservation(box=box, profile=profile)
    reviewed = copy(draft)
    reviewed.geometry = draft.geometry.model_copy(deep=True)
    reviewed.geometry.body_region = observation
    reviewed.spans = {**PART_SPAN, **(draft.spans or {}), "身体": (y0, y1)}
    reviewed.spans_measured = [name for name in draft.spans_measured if name != "身体"]
    return reviewed


def head_ratio(subject: SubjectObservation, head_box: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = head_box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("头部框必须位于裁剪图内且具有面积")
    w, h = subject.image.size
    height = h
    if subject.segmentation is not None:
        mask, small = subject.segmentation
        occupied = np.flatnonzero(mask.any(axis=1))
        if len(occupied):
            height = (occupied[-1] - occupied[0] + 1) / small.height * h
    ratio = max((x1 - x0) * w, (y1 - y0) * h) / height
    if not 0 < ratio <= 1:
        raise ValueError("头部范围超过主体高度，请重新调整裁剪或头部框")
    return float(ratio)


def reviewed_analysis(analysis: ImageAnalysis, parts: list[str], ratio: float) -> ImageAnalysis:
    if not parts:
        raise ValueError("请至少选择一个部件")
    if not math.isfinite(ratio) or not 0 < ratio <= 1:
        raise ValueError("头身比例必须在 0–1 之间")
    return ImageAnalysis.model_validate(
        {**analysis.model_dump(), "parts": parts, "height_cm": 18, "head_diameter_cm": ratio * 18}
    )
