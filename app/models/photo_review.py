"""Local crop/review helpers. Coordinates are relative to the cropped image."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.schemas import ImageAnalysis

from .subject import SubjectObservation


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
    subject: SubjectObservation, head_box: tuple[float, float, float, float] | None = None
) -> Image.Image:
    """Green = available subject mask; orange = detected or user-defined head."""
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
    return img


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
