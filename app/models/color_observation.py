"""Bounded photo-color evidence; not instructions or inferred crochet topology."""
from __future__ import annotations

from typing import Annotated, Any, Literal

import numpy as np
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.utils.numbers import finite_float

Fraction = Annotated[float, BeforeValidator(finite_float), Field(ge=0, le=1)]
Count = Annotated[int, Field(strict=True, ge=0, le=25600)]
MAX_REGIONS = 64


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ColorCoverage(Evidence):
    color: str = Field(min_length=1, max_length=40)
    pixels: Count


class BandCoverage(Evidence):
    start: Fraction
    end: Fraction
    colors: list[ColorCoverage] = Field(max_length=128)

    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end:
            raise ValueError("配色观测区间无效")
        return self


class ColorRegion(Evidence):
    color: str = Field(min_length=1, max_length=40)
    pixels: Count
    box: tuple[Fraction, Fraction, Fraction, Fraction]

    @model_validator(mode="after")
    def ordered(self):
        x0, y0, x1, y1 = self.box
        if x0 >= x1 or y0 >= y1 or not self.pixels:
            raise ValueError("配色区域必须具有面积")
        return self


class ColorObservation(Evidence):
    version: Literal[1] = 1
    coordinates: Literal["cropped_image_normalized"] = "cropped_image_normalized"
    mask_source: Literal["segmentation", "background_distance"]
    width: int = Field(strict=True, ge=1, le=160)
    height: int = Field(strict=True, ge=1, le=160)
    foreground_pixels: Count
    coverage: list[ColorCoverage] = Field(max_length=128)
    band_coverage: list[BandCoverage] = Field(min_length=1, max_length=160)
    regions: list[ColorRegion] = Field(max_length=MAX_REGIONS)
    omitted_region_count: Count
    omitted_pixels: Count

    @model_validator(mode="after")
    def consistent(self):
        total = self.foreground_pixels
        if not total or total > self.width * self.height:
            raise ValueError("配色观测前景面积无效")
        if sum(c.pixels for c in self.coverage) != total:
            raise ValueError("配色观测颜色计数不一致")
        if sum(c.pixels for b in self.band_coverage for c in b.colors) != total:
            raise ValueError("配色观测色带计数不一致")
        if sum(r.pixels for r in self.regions) + self.omitted_pixels != total:
            raise ValueError("配色观测区域计数不一致")
        counts = {c.color: c.pixels for c in self.coverage}
        if len(counts) != len(self.coverage):
            raise ValueError("配色观测颜色重复")
        by_band: dict[str, int] = {}
        previous = 0.0
        for band in self.band_coverage:
            if band.start != previous or len({c.color for c in band.colors}) != len(band.colors):
                raise ValueError("配色观测色带必须连续且颜色不重复")
            previous = band.end
            for color in band.colors:
                by_band[color.color] = by_band.get(color.color, 0) + color.pixels
        if previous != 1.0 or by_band != counts:
            raise ValueError("配色观测色带与颜色分布不一致")
        for color_name in {r.color for r in self.regions}:
            if sum(r.pixels for r in self.regions if r.color == color_name) > counts.get(color_name, 0):
                raise ValueError("配色观测区域与颜色分布不一致")
        return self

    @property
    def minority_fraction(self) -> float:
        lost = sum(sum(c.pixels for c in b.colors) - max((c.pixels for c in b.colors), default=0)
                   for b in self.band_coverage)
        return lost / self.foreground_pixels

    @property
    def requires_review(self) -> bool:
        # A UI noise threshold, not a calibrated accuracy/confidence estimate.
        return self.minority_fraction >= 0.02


def build_observation(mask, pixel_ids, yarn_names, n_bands: int, mask_source: str) -> dict:
    """Keep all color counts and the largest 4-connected regions at <=160px."""
    h, w = mask.shape
    labels = np.full((h, w), -1, dtype=np.int16)
    labels[mask] = pixel_ids
    total = int(mask.sum())

    def counts(ids):
        hist = np.bincount(ids, minlength=len(yarn_names))
        return [{"color": str(yarn_names[i]), "pixels": int(n)} for i, n in enumerate(hist) if n]

    band_coverage = []
    for i in range(n_bands):
        rows = labels[h * i // n_bands:h * (i + 1) // n_bands]
        band_coverage.append({"start": i / n_bands, "end": (i + 1) / n_bands,
                              "colors": counts(rows[rows >= 0])})
    # Integer flood fill keeps OpenCV optional and work bounded by 25,600 pixels.
    visited = labels < 0
    regions: list[dict[str, Any]] = []
    omitted_count, omitted_pixels = 0, 0
    minimum = max(4, int(np.ceil(total * 0.002)))
    for y, x in zip(*np.nonzero(mask), strict=True):
        if visited[y, x]:
            continue
        label = labels[y, x]
        stack = [(int(y), int(x))]
        visited[y, x] = True
        size, x0, x1, y0, y1 = 0, int(x), int(x), int(y), int(y)
        while stack:
            cy, cx = stack.pop()
            size += 1
            x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and labels[ny, nx] == label:
                    visited[ny, nx] = True
                    stack.append((ny, nx))
        if size < minimum:
            omitted_count += 1
            omitted_pixels += size
        else:
            regions.append({"color": str(yarn_names[label]), "pixels": size,
                            "box": [x0 / w, y0 / h, (x1 + 1) / w, (y1 + 1) / h]})
    regions.sort(key=lambda r: (-r["pixels"], r["color"], r["box"]))
    omitted_count += len(regions[MAX_REGIONS:])
    omitted_pixels += sum(r["pixels"] for r in regions[MAX_REGIONS:])
    return ColorObservation.model_validate({
        "mask_source": mask_source, "width": w, "height": h, "foreground_pixels": total,
        "coverage": counts(pixel_ids), "band_coverage": band_coverage,
        "regions": regions[:MAX_REGIONS], "omitted_region_count": omitted_count,
        "omitted_pixels": omitted_pixels,
    }).model_dump(mode="json")
