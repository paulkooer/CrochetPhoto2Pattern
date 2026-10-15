"""Bounded, image-bound manual segmentation corrections; no image generation."""
from __future__ import annotations

import hashlib
from copy import copy
from typing import TYPE_CHECKING, Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from .orchestrator import PhotoDraft


class MaskReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["user_brush"] = "user_brush"
    image_token: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    width: int = Field(strict=True, ge=1, le=160)
    height: int = Field(strict=True, ge=1, le=160)
    pixels: str = Field(min_length=1, max_length=25600, pattern=r"^[01]+$")

    @model_validator(mode="after")
    def dimensions_match(self) -> MaskReview:
        if len(self.pixels) != self.width * self.height:
            raise ValueError("修正掩码与图片尺寸不一致")
        if "1" not in self.pixels:
            raise ValueError("主体已全部擦除，请补选主体或恢复自动分割")
        return self


def mask_editor_input(draft: PhotoDraft) -> tuple[Image.Image, np.ndarray, str]:
    segmentation = draft.subject.segmentation
    if segmentation is None:
        small = draft.image.convert("RGB")
        small.thumbnail((160, 160))
        mask = np.zeros((small.height, small.width), dtype=bool)
    else:
        mask, small = segmentation
    token = hashlib.sha256(
        f"{small.width}x{small.height}:".encode() + small.convert("RGB").tobytes()
    ).hexdigest()
    return small, mask, token


def with_reviewed_mask(draft: PhotoDraft, payload: dict) -> PhotoDraft:
    """Recompute geometry and palette from an independent corrected observation.

    Other semantic/proportion estimates remain user-reviewable, not silently
    reinterpreted. Body selection is recomputed if this draft already has one.
    """
    from .geometry import observe_geometry
    from .image_parser import extract_color_palette
    from .photo_review import with_reviewed_body
    from .subject import SubjectObservation

    if not draft.geometry.used_for_generation:
        raise ValueError("Mock 模式不能修正照片主体，请切换本地分析")
    correction = MaskReview.model_validate(payload)
    small, _, token = mask_editor_input(draft)
    if (correction.image_token != token
            or (correction.width, correction.height) != small.size):
        raise ValueError("修正掩码不属于当前裁剪照片，请重新修正")
    mask = np.frombuffer(correction.pixels.encode("ascii"), dtype=np.uint8).reshape(
        correction.height, correction.width) == ord("1")
    observed = SubjectObservation.from_reviewed_mask(draft.image, mask, small)
    reviewed = copy(draft)
    reviewed.subject = observed
    reviewed.geometry = observe_geometry(draft.image, subject=observed)
    reviewed.geometry.mask_review = correction
    reviewed.analysis = draft.analysis.model_copy(deep=True)
    reviewed.analysis.recommended_colors = extract_color_palette(draft.image, subject=observed) or None
    if draft.geometry.body_region is not None:
        reviewed = with_reviewed_body(reviewed, draft.geometry.body_region.box)
    return reviewed
