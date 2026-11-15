"""Strict trial records and shared trial policy constants."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from app.utils.counts import integer_count
from app.utils.numbers import finite_float

TRIAL_SCHEMA_VERSION = Literal[2]
TRIAL_REPORT_SCHEMA_VERSION = 3
EXTERNAL_EVIDENCE_SCHEMA_VERSION = Literal[1]
MAX_PATTERN_BYTES = 20 * 1024 * 1024
MAX_TRIAL_BYTES = 512 * 1024
MAX_EXTERNAL_EVIDENCE_BYTES = 1024 * 1024
MAX_TRIAL_FILES = 500
MIN_CALIBRATION_TRIALS = 5
MIN_DISTINCT_PATTERNS = 3
MIN_VALIDATION_TRIALS = 3
MIN_DISTINCT_VALIDATION_PATTERNS = 2
MIN_DISTINCT_MAKERS = 2
MAX_RELATIVE_MEDIAN_ABSOLUTE_DEVIATION = 0.25
CURATED_EXTERNAL_EVIDENCE_NAME = "external-trial-evidence.json"


class TrialDataError(ValueError):
    """A pattern or trial record is invalid and cannot be analyzed safely."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# 与 schemas.py 同一约定：布尔值不是测量值，截断小数不是整数。试钩记录
# 会进入校准统计，静默强转（true→1、2.9→2）会污染所有下游中位数。
TrialInt = Annotated[int, BeforeValidator(integer_count)]
TrialFloat = Annotated[float, BeforeValidator(finite_float)]


class TrialGauge(_StrictModel):
    stitches_per_10cm: TrialFloat = Field(ge=6.0, le=40.0)
    rows_per_10cm: TrialFloat = Field(ge=8.0, le=50.0)


class PatternSource(_StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Missing versions identify legacy records, whose design independence is
    # unknown until their exact source snapshot has been checked and upgraded.
    design_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    design_fingerprint_version: Literal["1"] | None = None
    application_version: str = Field(min_length=1, max_length=80)
    target_height_cm: TrialFloat = Field(gt=0.0, le=200.0)
    gauge: TrialGauge
    total_stitches: TrialInt = Field(gt=0)
    total_physical_rounds: TrialInt = Field(gt=0)
    estimated_time_minutes: TrialInt = Field(gt=0)

    @model_validator(mode="after")
    def _fingerprint_contract(self) -> PatternSource:
        if self.design_fingerprint_version is not None and self.design_fingerprint is None:
            raise ValueError("versioned design identity requires a fingerprint")
        return self


class SwatchMeasurement(_StrictModel):
    measured: bool = False
    stitches_per_10cm: TrialFloat = Field(ge=6.0, le=40.0)
    rows_per_10cm: TrialFloat = Field(ge=8.0, le=50.0)
    hook_mm: TrialFloat | None = Field(default=None, gt=0.0, le=20.0)
    yarn_brand: str | None = Field(default=None, max_length=100)
    yarn_line: str | None = Field(default=None, max_length=100)
    yarn_lot: str | None = Field(default=None, max_length=100)
    fiber: str | None = Field(default=None, max_length=200)


class TrialObservation(_StrictModel):
    completed_on: date
    overall_height_cm: TrialFloat = Field(gt=0.0, le=300.0)
    yarn_used_grams: TrialFloat = Field(gt=0.0, le=5000.0)
    yarn_used_meters: TrialFloat | None = Field(default=None, gt=0.0, le=100_000.0)
    active_minutes: TrialInt = Field(gt=0, le=100_000)
    time_scope: Literal["round_crochet_baseline", "full_project"]
    pattern_modified: bool
    modifications: list[str] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("completed_on")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("completed_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _modification_details(self) -> TrialObservation:
        if self.pattern_modified and not self.modifications:
            raise ValueError("modified trials must describe at least one modification")
        if not self.pattern_modified and self.modifications:
            raise ValueError("unmodified trials must not list modifications")
        return self


class TrialRecord(_StrictModel):
    schema_version: Literal[TRIAL_SCHEMA_VERSION]
    trial_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    maker_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    status: Literal["draft", "completed"]
    cohort: Literal["calibration", "validation"] = "calibration"
    pattern: PatternSource
    swatch: SwatchMeasurement
    observation: TrialObservation | None = None

    @model_validator(mode="after")
    def _completed_contract(self) -> TrialRecord:
        if self.status == "completed":
            if self.observation is None:
                raise ValueError("completed trials require observation")
            if not self.swatch.measured:
                raise ValueError("completed trials require a measured swatch")
        elif self.observation is not None:
            raise ValueError("draft trials must not contain observation")
        return self


class ExternalObservation(_StrictModel):
    """A small set of factual measurements published by an external source.

    Pattern instructions, photographs, user names, and free-form project notes are
    intentionally outside this contract. External observations provide context
    only and can never become production calibration inputs.
    """

    observation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    project_label: str = Field(min_length=1, max_length=120)
    project_type: Literal["amigurumi", "other_crochet"]
    measurement_scope: Literal["single_item", "pair", "source_aggregate"]
    finished_height_cm: TrialFloat | None = Field(default=None, gt=0.0, le=300.0)
    finished_length_cm: TrialFloat | None = Field(default=None, gt=0.0, le=300.0)
    yarn_used_grams: TrialFloat | None = Field(default=None, gt=0.0, le=5000.0)
    yarn_used_meters: TrialFloat | None = Field(default=None, gt=0.0, le=100_000.0)
    completion_minutes_median: TrialInt | None = Field(default=None, gt=0, le=100_000)
    completion_minutes_min: TrialInt | None = Field(default=None, gt=0, le=100_000)
    completion_minutes_max: TrialInt | None = Field(default=None, gt=0, le=100_000)
    stitches_per_10cm: TrialFloat | None = Field(default=None, ge=1.0, le=100.0)
    hook_mm: TrialFloat | None = Field(default=None, gt=0.0, le=30.0)

    @model_validator(mode="after")
    def _measurement_contract(self) -> ExternalObservation:
        measurements = (
            self.finished_height_cm,
            self.finished_length_cm,
            self.yarn_used_grams,
            self.yarn_used_meters,
            self.completion_minutes_median,
            self.stitches_per_10cm,
            self.hook_mm,
        )
        if all(value is None for value in measurements):
            raise ValueError("external observations require at least one measurement")
        if (self.completion_minutes_min is None) != (self.completion_minutes_max is None):
            raise ValueError("completion time range requires both min and max")
        if self.completion_minutes_min is not None:
            assert self.completion_minutes_max is not None
            if self.completion_minutes_min > self.completion_minutes_max:
                raise ValueError("completion time min cannot exceed max")
            if (
                self.completion_minutes_median is not None
                and not self.completion_minutes_min
                <= self.completion_minutes_median
                <= self.completion_minutes_max
            ):
                raise ValueError("completion time median must fall within min and max")
        return self


class ExternalEvidenceSource(_StrictModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    publisher: str = Field(min_length=1, max_length=120)
    source_url: str = Field(pattern=r"^https://[^\s]+$", max_length=1000)
    accessed_on: date
    evidence_kind: Literal[
        "platform_timer_aggregate",
        "author_worked_sample",
        "published_pattern_specification",
    ]
    verification: Literal["source_claim", "raw_records_reviewed", "user_authorized_export"]
    declared_sample_size: TrialInt | None = Field(default=None, gt=0, le=1_000_000)
    raw_records_available: bool
    methodology_available: bool
    reuse_basis: Literal[
        "public_facts_with_attribution",
        "open_license",
        "user_authorized_export",
    ]
    license_identifier: str | None = Field(default=None, max_length=100)
    calibration_allowed: Literal[False] = False
    observations: list[ExternalObservation] = Field(min_length=1, max_length=100)

    @field_validator("accessed_on")
    @classmethod
    def _access_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("accessed_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _source_contract(self) -> ExternalEvidenceSource:
        if self.reuse_basis == "open_license" and not self.license_identifier:
            raise ValueError("open-license evidence requires license_identifier")
        ids = [observation.observation_id for observation in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("observation_id values must be unique within a source")
        return self


class ExternalEvidenceBundle(_StrictModel):
    schema_version: Literal[EXTERNAL_EVIDENCE_SCHEMA_VERSION]
    created_on: date
    sources: list[ExternalEvidenceSource] = Field(min_length=1, max_length=100)

    @field_validator("created_on")
    @classmethod
    def _created_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("created_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _unique_sources(self) -> ExternalEvidenceBundle:
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source_id values must be unique")
        return self
