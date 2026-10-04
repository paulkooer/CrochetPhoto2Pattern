"""Validate imported metadata before any renderer or regeneration consumes it.

Legacy records may omit metadata. Known fields are typed; unknown provenance
fields are retained without being interpreted as verified evidence.
"""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter

from app.utils.numbers import finite_float

from .geometry import GeometryObservation

Finite = Annotated[float, BeforeValidator(finite_float)]
Fraction = Annotated[Finite, Field(ge=0, le=1)]


class Metadata(BaseModel):
    model_config = ConfigDict(extra="allow")


class SizingMetadata(Metadata):
    source: str | None = None
    note: str | None = None
    target_height_cm: Finite | None = None
    target_head_diameter_cm: Finite | None = None
    photo_head_to_height_ratio: Fraction | None = None
    applied_head_to_height_ratio: Fraction | None = None
    ratio_clamped: bool = False
    absolute_scale_from_photo: bool = False


class LegacySilhouette(Metadata):
    profile: list[Fraction] | None = None
    confidence: Fraction | None = None


class VisionMetadata(Metadata):
    source: str | None = None
    note: str | None = None
    body_ratio: Finite | None = None
    silhouette: LegacySilhouette | None = None


class AttemptMetadata(Metadata):
    provider: str
    model: str
    status: str
    seconds: Finite = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    usage_known: bool = False
    error_type: str | None = None


class StageMetadata(Metadata):
    stage: str
    seconds: Finite = Field(ge=0)
    status: str


class TraceMetadata(Metadata):
    budget_seconds: Finite | None = Field(default=None, gt=0, le=600)
    active_seconds: Finite | None = Field(default=None, ge=0)
    budget_mode: str | None = None
    stages: list[StageMetadata] = Field(default_factory=list, max_length=100)
    fallbacks: list[str] = Field(default_factory=list, max_length=100)


class DiagnosticsMetadata(TraceMetadata):
    exports: dict[Literal["markdown", "pdf"], TraceMetadata] = Field(default_factory=dict)


class UsageMetadata(Metadata):
    provider: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


    usage_complete: bool | None = None
    attempts: list[AttemptMetadata] = Field(default_factory=list, max_length=100)


class StyleMetadata(BaseModel):
    # These keys are expanded directly into ShapingStyle during regeneration.
    model_config = ConfigDict(extra="forbid")
    sphere_mode: Literal["ladder", "ideal", "egg"] = "ladder"
    one_piece: bool = False
    skirt_style: Literal["ring", "attached"] = "ring"
    ruffle_hem: bool = False


class ColorBand(Metadata):
    start: Fraction
    end: Fraction
    color: str


def validate_result_metadata(data: dict[str, Any]) -> None:
    """Normalize known types without inventing missing provenance fields."""
    for key, model in (
        ("geometry", GeometryObservation), ("sizing", SizingMetadata),
        ("vision_meta", VisionMetadata), ("usage", UsageMetadata),
        ("style", StyleMetadata), ("diagnostics", DiagnosticsMetadata),
    ):
        if data.get(key) is not None:
            data[key] = model.model_validate(data[key]).model_dump(mode="json", exclude_unset=True)
    if data.get("spans") is not None:
        spans = TypeAdapter(dict[str, tuple[Fraction, Fraction]]).validate_python(data["spans"])
        if any(start >= end for start, end in spans.values()):
            raise ValueError("部件分段起点必须小于终点")
        data["spans"] = {key: list(span) for key, span in spans.items()}
    if data.get("color_bands") is not None:
        bands = TypeAdapter(list[ColorBand]).validate_python(data["color_bands"])
        if any(band.start >= band.end for band in bands):
            raise ValueError("配色分段起点必须小于终点")
        data["color_bands"] = [band.model_dump(mode="json", exclude_unset=True) for band in bands]
