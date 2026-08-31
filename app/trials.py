"""Physical crochet trial records and conservative calibration analysis.

This module closes the measurement loop without mutating production constants.
It creates a draft tied to an exact pattern JSON hash, validates completed trial
records, and reports candidate calibration values only after basic diversity
requirements are met.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections.abc import Iterable
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.crochet_params import SECONDS_PER_ROUND_OVERHEAD, SECONDS_PER_STITCH
from app.models.gauge import BASE_GRAMS_PER_STITCH, BASE_STITCH_AREA_CM2

TRIAL_SCHEMA_VERSION = 2
TRIAL_REPORT_SCHEMA_VERSION = 3
EXTERNAL_EVIDENCE_SCHEMA_VERSION = 1
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


class TrialGauge(_StrictModel):
    stitches_per_10cm: float = Field(ge=6.0, le=40.0)
    rows_per_10cm: float = Field(ge=8.0, le=50.0)


class PatternSource(_StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    application_version: str = Field(min_length=1, max_length=80)
    target_height_cm: float = Field(gt=0.0, le=200.0)
    gauge: TrialGauge
    total_stitches: int = Field(gt=0)
    total_physical_rounds: int = Field(gt=0)
    estimated_time_minutes: int = Field(gt=0)


class SwatchMeasurement(_StrictModel):
    measured: bool = False
    stitches_per_10cm: float = Field(ge=6.0, le=40.0)
    rows_per_10cm: float = Field(ge=8.0, le=50.0)
    hook_mm: Optional[float] = Field(default=None, gt=0.0, le=20.0)
    yarn_brand: Optional[str] = Field(default=None, max_length=100)
    yarn_line: Optional[str] = Field(default=None, max_length=100)
    yarn_lot: Optional[str] = Field(default=None, max_length=100)
    fiber: Optional[str] = Field(default=None, max_length=200)


class TrialObservation(_StrictModel):
    completed_on: date
    overall_height_cm: float = Field(gt=0.0, le=300.0)
    yarn_used_grams: float = Field(gt=0.0, le=5000.0)
    yarn_used_meters: Optional[float] = Field(default=None, gt=0.0, le=100_000.0)
    active_minutes: int = Field(gt=0, le=100_000)
    time_scope: Literal["round_crochet_baseline", "full_project"]
    pattern_modified: bool
    modifications: list[str] = Field(default_factory=list, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("completed_on")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("completed_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _modification_details(self) -> "TrialObservation":
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
    observation: Optional[TrialObservation] = None

    @model_validator(mode="after")
    def _completed_contract(self) -> "TrialRecord":
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
    finished_height_cm: Optional[float] = Field(default=None, gt=0.0, le=300.0)
    finished_length_cm: Optional[float] = Field(default=None, gt=0.0, le=300.0)
    yarn_used_grams: Optional[float] = Field(default=None, gt=0.0, le=5000.0)
    yarn_used_meters: Optional[float] = Field(default=None, gt=0.0, le=100_000.0)
    completion_minutes_median: Optional[int] = Field(default=None, gt=0, le=100_000)
    completion_minutes_min: Optional[int] = Field(default=None, gt=0, le=100_000)
    completion_minutes_max: Optional[int] = Field(default=None, gt=0, le=100_000)
    stitches_per_10cm: Optional[float] = Field(default=None, ge=1.0, le=100.0)
    hook_mm: Optional[float] = Field(default=None, gt=0.0, le=30.0)

    @model_validator(mode="after")
    def _measurement_contract(self) -> "ExternalObservation":
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
    declared_sample_size: Optional[int] = Field(default=None, gt=0, le=1_000_000)
    raw_records_available: bool
    methodology_available: bool
    reuse_basis: Literal[
        "public_facts_with_attribution",
        "open_license",
        "user_authorized_export",
    ]
    license_identifier: Optional[str] = Field(default=None, max_length=100)
    calibration_allowed: Literal[False] = False
    observations: list[ExternalObservation] = Field(min_length=1, max_length=100)

    @field_validator("accessed_on")
    @classmethod
    def _access_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("accessed_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _source_contract(self) -> "ExternalEvidenceSource":
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
    def _unique_sources(self) -> "ExternalEvidenceBundle":
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source_id values must be unique")
        return self


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrialDataError(f"JSON contains duplicate key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, max_bytes: int) -> Any:
    if not path.is_file():
        raise TrialDataError(f"file does not exist: {path}")
    if path.stat().st_size > max_bytes:
        raise TrialDataError(f"file exceeds {max_bytes} byte limit: {path.name}")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except TrialDataError:
        raise
    except Exception as exc:
        raise TrialDataError(f"invalid JSON in {path.name}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _application_version() -> str:
    try:
        return version("crochet-photo2pattern")
    except PackageNotFoundError:
        return "source-tree"


def _part_quantity(part: dict[str, Any]) -> int:
    try:
        return max(1, int(part.get("quantity", 1)))
    except (TypeError, ValueError):
        raise TrialDataError("pattern part quantity must be an integer") from None


def _pattern_counts(parts: list[dict[str, Any]]) -> tuple[int, int]:
    total_stitches = 0
    total_rounds = 0
    for part in parts:
        if not isinstance(part, dict):
            raise TrialDataError("pattern parts must be JSON objects")
        rounds = part.get("rounds") or []
        if not isinstance(rounds, list) or not rounds:
            raise TrialDataError("every pattern part must contain rounds")
        quantity = _part_quantity(part)
        total_rounds += len(rounds) * quantity
        for crochet_round in rounds:
            try:
                stitches = int(crochet_round["stitches"])
            except (KeyError, TypeError, ValueError):
                raise TrialDataError("every pattern round must contain integer stitches") from None
            if stitches <= 0:
                raise TrialDataError("pattern round stitches must be positive")
            total_stitches += stitches * quantity
    return total_stitches, total_rounds


def create_trial_draft(
    pattern_path: str | Path,
    *,
    trial_id: str,
    maker_id: str,
    cohort: Literal["calibration", "validation"] = "calibration",
) -> dict[str, Any]:
    """Create an editable draft bound to an exact generated pattern file."""
    path = Path(pattern_path).expanduser().resolve()
    payload = _read_json(path, MAX_PATTERN_BYTES)
    if not isinstance(payload, dict):
        raise TrialDataError("pattern JSON root must be an object")
    params = payload.get("params", payload)
    if not isinstance(params, dict):
        raise TrialDataError("pattern params must be an object")
    parts = params.get("parts") or []
    if not isinstance(parts, list) or not parts:
        raise TrialDataError("pattern has no parts")
    total_stitches, total_rounds = _pattern_counts(parts)
    gauge = params.get("gauge") or {}
    analysis = payload.get("analysis") or {}
    try:
        source = PatternSource(
            sha256=_sha256(path),
            application_version=_application_version(),
            target_height_cm=float(analysis["height_cm"]),
            gauge=TrialGauge.model_validate(gauge),
            total_stitches=total_stitches,
            total_physical_rounds=total_rounds,
            estimated_time_minutes=int(params["estimated_time_minutes"]),
        )
        draft = TrialRecord(
            schema_version=TRIAL_SCHEMA_VERSION,
            trial_id=trial_id,
            maker_id=maker_id,
            status="draft",
            cohort=cohort,
            pattern=source,
            swatch=SwatchMeasurement(
                measured=False,
                stitches_per_10cm=source.gauge.stitches_per_10cm,
                rows_per_10cm=source.gauge.rows_per_10cm,
            ),
        )
    except Exception as exc:
        raise TrialDataError(f"pattern is missing required trial metadata: {exc}") from exc
    return draft.model_dump(mode="json")


def load_trial_records(records_dir: str | Path) -> list[TrialRecord]:
    root = Path(records_dir).expanduser().resolve()
    if not root.is_dir():
        raise TrialDataError(f"trial directory does not exist: {root}")
    files = sorted(root.glob("*.trial.json"))
    if not files:
        raise TrialDataError(f"no *.trial.json files found in {root}")
    if len(files) > MAX_TRIAL_FILES:
        raise TrialDataError(f"trial directory exceeds {MAX_TRIAL_FILES} records")
    records: list[TrialRecord] = []
    for path in files:
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise TrialDataError(f"trial record escapes directory: {path.name}") from exc
        try:
            records.append(TrialRecord.model_validate(_read_json(resolved, MAX_TRIAL_BYTES)))
        except TrialDataError:
            raise
        except Exception as exc:
            raise TrialDataError(f"invalid trial record {path.name}: {exc}") from exc
    ids = [record.trial_id for record in records]
    if len(set(ids)) != len(ids):
        raise TrialDataError("trial_id values must be unique across the directory")
    return records


def load_external_evidence(path: str | Path) -> ExternalEvidenceBundle:
    """Load a bounded, provenance-bearing external evidence bundle."""
    resolved = Path(path).expanduser().resolve()
    try:
        return ExternalEvidenceBundle.model_validate(
            _read_json(resolved, MAX_EXTERNAL_EVIDENCE_BYTES)
        )
    except TrialDataError:
        raise
    except Exception as exc:
        raise TrialDataError(f"invalid external evidence {resolved.name}: {exc}") from exc


def load_curated_external_evidence() -> ExternalEvidenceBundle:
    """Load the attribution-preserving evidence shipped inside the wheel."""
    resource = (
        resource_files("app")
        .joinpath("data")
        .joinpath(CURATED_EXTERNAL_EVIDENCE_NAME)
    )
    try:
        blob = resource.read_bytes()
        if len(blob) > MAX_EXTERNAL_EVIDENCE_BYTES:
            raise TrialDataError(
                f"curated evidence exceeds {MAX_EXTERNAL_EVIDENCE_BYTES} byte limit"
            )
        payload = json.loads(
            blob.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
        return ExternalEvidenceBundle.model_validate(payload)
    except TrialDataError:
        raise
    except Exception as exc:
        raise TrialDataError(f"invalid packaged curated evidence: {exc}") from exc


def summarize_external_evidence(bundle: ExternalEvidenceBundle) -> dict[str, Any]:
    """Return attributed context without deriving any calibration candidates."""
    timed_context: list[dict[str, Any]] = []
    yarn_context: list[dict[str, Any]] = []
    kinds: dict[str, int] = {}
    project_types: dict[str, int] = {}
    total_observations = 0
    sources: list[dict[str, Any]] = []
    for source in bundle.sources:
        kinds[source.evidence_kind] = kinds.get(source.evidence_kind, 0) + 1
        total_observations += len(source.observations)
        sources.append({
            "source_id": source.source_id,
            "title": source.title,
            "publisher": source.publisher,
            "source_url": source.source_url,
            "accessed_on": source.accessed_on.isoformat(),
            "evidence_kind": source.evidence_kind,
            "verification": source.verification,
            "declared_sample_size": source.declared_sample_size,
            "raw_records_available": source.raw_records_available,
            "methodology_available": source.methodology_available,
            "reuse_basis": source.reuse_basis,
        })
        for observation in source.observations:
            project_types[observation.project_type] = (
                project_types.get(observation.project_type, 0) + 1
            )
            identity = {
                "source_id": source.source_id,
                "observation_id": observation.observation_id,
                "project_label": observation.project_label,
                "project_type": observation.project_type,
                "measurement_scope": observation.measurement_scope,
            }
            if observation.completion_minutes_median is not None:
                timed_context.append({
                    **identity,
                    "finished_height_cm": observation.finished_height_cm,
                    "finished_length_cm": observation.finished_length_cm,
                    "completion_minutes_median": observation.completion_minutes_median,
                    "completion_minutes_min": observation.completion_minutes_min,
                    "completion_minutes_max": observation.completion_minutes_max,
                })
            if (
                observation.yarn_used_grams is not None
                or observation.yarn_used_meters is not None
            ):
                yarn_context.append({
                    **identity,
                    "finished_height_cm": observation.finished_height_cm,
                    "finished_length_cm": observation.finished_length_cm,
                    "yarn_used_grams": observation.yarn_used_grams,
                    "yarn_used_meters": observation.yarn_used_meters,
                    "stitches_per_10cm": observation.stitches_per_10cm,
                    "hook_mm": observation.hook_mm,
                })
    return {
        "external_evidence_schema_version": bundle.schema_version,
        "created_on": bundle.created_on.isoformat(),
        "policy": {
            "used_for_calibration": False,
            "automatic_changes_applied": False,
            "reason": (
                "External sources are not bound to an exact generated pattern hash, "
                "verified stitch count, and controlled local trial protocol."
            ),
        },
        "coverage": {
            "sources": len(bundle.sources),
            "observations": total_observations,
            "source_kinds": dict(sorted(kinds.items())),
            "project_types": dict(sorted(project_types.items())),
        },
        "sources": sources,
        "amigurumi_timed_context": [
            item for item in timed_context if item["project_type"] == "amigurumi"
        ],
        "yarn_context": yarn_context,
        "limitations": [
            "Published figures remain source claims unless raw_records_reviewed is set.",
            "Size alone does not control for stitch count, yarn, skill, details, or seaming.",
            "Do not infer per-stitch constants from this contextual report.",
        ],
    }


def _median(values: Iterable[float]) -> Optional[float]:
    data = list(values)
    return round(float(statistics.median(data)), 6) if data else None


def _median_absolute_deviation(values: list[float]) -> Optional[float]:
    if not values:
        return None
    center = statistics.median(values)
    return round(float(statistics.median(abs(value - center) for value in values)), 6)


def _distribution(values: list[float]) -> dict[str, Optional[float] | int]:
    return {
        "count": len(values),
        "median": _median(values),
        "median_absolute_deviation": _median_absolute_deviation(values),
        "min": round(min(values), 6) if values else None,
        "max": round(max(values), 6) if values else None,
    }


def analyze_trials(
    records: list[TrialRecord],
    external_evidence: Optional[ExternalEvidenceBundle] = None,
) -> dict[str, Any]:
    completed = [record for record in records if record.status == "completed"]
    unmodified = [
        record
        for record in completed
        if record.observation is not None and not record.observation.pattern_modified
    ]
    eligible = [record for record in unmodified if record.cohort == "calibration"]
    validation_eligible = [
        record for record in unmodified if record.cohort == "validation"
    ]
    time_eligible = [
        record
        for record in eligible
        if record.observation is not None
        and record.observation.time_scope == "round_crochet_baseline"
    ]
    validation_time_eligible = [
        record
        for record in validation_eligible
        if record.observation is not None
        and record.observation.time_scope == "round_crochet_baseline"
    ]
    distinct_patterns = {record.pattern.sha256 for record in eligible}
    distinct_time_patterns = {record.pattern.sha256 for record in time_eligible}
    validation_patterns = {record.pattern.sha256 for record in validation_eligible}
    validation_time_patterns = {
        record.pattern.sha256 for record in validation_time_eligible
    }
    distinct_makers = {record.maker_id for record in eligible}
    distinct_time_makers = {record.maker_id for record in time_eligible}
    validation_makers = {record.maker_id for record in validation_eligible}
    validation_time_makers = {
        record.maker_id for record in validation_time_eligible
    }
    cohort_pattern_overlap = distinct_patterns & validation_patterns
    grams_blockers: list[str] = []
    time_blockers: list[str] = []
    validation_blockers: list[str] = []
    if len(eligible) < MIN_CALIBRATION_TRIALS:
        grams_blockers.append(
            f"need at least {MIN_CALIBRATION_TRIALS} completed unmodified trials; have {len(eligible)}"
        )
    if len(distinct_patterns) < MIN_DISTINCT_PATTERNS:
        grams_blockers.append(
            f"need at least {MIN_DISTINCT_PATTERNS} distinct pattern hashes; have {len(distinct_patterns)}"
        )
    if len(distinct_makers) < MIN_DISTINCT_MAKERS:
        grams_blockers.append(
            f"need at least {MIN_DISTINCT_MAKERS} distinct calibration makers; "
            f"have {len(distinct_makers)}"
        )
    if len(time_eligible) < MIN_CALIBRATION_TRIALS:
        time_blockers.append(
            f"need at least {MIN_CALIBRATION_TRIALS} unmodified "
            "round_crochet_baseline time trials; "
            f"have {len(time_eligible)}"
        )
    if len(distinct_time_patterns) < MIN_DISTINCT_PATTERNS:
        time_blockers.append(
            f"need at least {MIN_DISTINCT_PATTERNS} distinct pattern hashes for time; "
            f"have {len(distinct_time_patterns)}"
        )
    if len(distinct_time_makers) < MIN_DISTINCT_MAKERS:
        time_blockers.append(
            f"need at least {MIN_DISTINCT_MAKERS} distinct calibration makers for time; "
            f"have {len(distinct_time_makers)}"
        )
    if len(validation_eligible) < MIN_VALIDATION_TRIALS:
        validation_blockers.append(
            f"need at least {MIN_VALIDATION_TRIALS} completed unmodified validation trials; "
            f"have {len(validation_eligible)}"
        )
    if len(validation_patterns) < MIN_DISTINCT_VALIDATION_PATTERNS:
        validation_blockers.append(
            f"need at least {MIN_DISTINCT_VALIDATION_PATTERNS} distinct validation "
            f"pattern hashes; have {len(validation_patterns)}"
        )
    if len(validation_makers) < MIN_DISTINCT_MAKERS:
        validation_blockers.append(
            f"need at least {MIN_DISTINCT_MAKERS} distinct validation makers; "
            f"have {len(validation_makers)}"
        )
    if len(validation_time_eligible) < MIN_VALIDATION_TRIALS:
        validation_blockers.append(
            f"need at least {MIN_VALIDATION_TRIALS} validation "
            "round_crochet_baseline time trials; "
            f"have {len(validation_time_eligible)}"
        )
    if len(validation_time_patterns) < MIN_DISTINCT_VALIDATION_PATTERNS:
        validation_blockers.append(
            f"need at least {MIN_DISTINCT_VALIDATION_PATTERNS} distinct validation "
            f"pattern hashes for time; have {len(validation_time_patterns)}"
        )
    if len(validation_time_makers) < MIN_DISTINCT_MAKERS:
        validation_blockers.append(
            f"need at least {MIN_DISTINCT_MAKERS} distinct validation makers for time; "
            f"have {len(validation_time_makers)}"
        )
    if cohort_pattern_overlap:
        validation_blockers.append(
            "calibration and validation cohorts must use disjoint pattern hashes; "
            f"overlap={len(cohort_pattern_overlap)}"
        )
    height_ratios: list[float] = []
    time_ratios: list[float] = []
    stitch_gauge_ratios: list[float] = []
    row_gauge_ratios: list[float] = []
    normalized_base_grams: list[float] = []
    implied_seconds_per_stitch: list[float] = []
    meters_per_100g: list[float] = []
    validation_height_ratios: list[float] = []
    validation_normalized_base_grams: list[float] = []
    validation_implied_seconds_per_stitch: list[float] = []
    validation_baseline_time_ratios: list[float] = []
    validation_full_project_time_ratios: list[float] = []
    cases: list[dict[str, Any]] = []

    for record in completed:
        observation = record.observation
        assert observation is not None
        height_ratio = observation.overall_height_cm / record.pattern.target_height_cm
        time_ratio = observation.active_minutes / record.pattern.estimated_time_minutes
        stitch_ratio = (
            record.swatch.stitches_per_10cm / record.pattern.gauge.stitches_per_10cm
        )
        row_ratio = record.swatch.rows_per_10cm / record.pattern.gauge.rows_per_10cm
        height_ratios.append(height_ratio)
        time_ratios.append(time_ratio)
        stitch_gauge_ratios.append(stitch_ratio)
        row_gauge_ratios.append(row_ratio)

        unmodified_eligible = not observation.pattern_modified
        calibration_eligible = unmodified_eligible and record.cohort == "calibration"
        validation_record_eligible = (
            unmodified_eligible and record.cohort == "validation"
        )
        time_calibration_eligible = (
            calibration_eligible
            and observation.time_scope == "round_crochet_baseline"
        )
        time_validation_eligible = (
            validation_record_eligible
            and observation.time_scope == "round_crochet_baseline"
        )
        normalized_grams: Optional[float] = None
        if unmodified_eligible:
            stitch_area = (
                10.0 / record.swatch.stitches_per_10cm
                * 10.0 / record.swatch.rows_per_10cm
            )
            grams_per_stitch = observation.yarn_used_grams / record.pattern.total_stitches
            normalized_grams = grams_per_stitch * BASE_STITCH_AREA_CM2 / stitch_area
        if calibration_eligible:
            assert normalized_grams is not None
            normalized_base_grams.append(normalized_grams)
            if observation.yarn_used_meters is not None:
                meters_per_100g.append(
                    observation.yarn_used_meters / observation.yarn_used_grams * 100.0
                )
        elif validation_record_eligible:
            assert normalized_grams is not None
            validation_height_ratios.append(height_ratio)
            validation_normalized_base_grams.append(normalized_grams)

        implied_seconds: Optional[float] = None
        if time_calibration_eligible or time_validation_eligible:
            residual_seconds = (
                observation.active_minutes * 60
                - record.pattern.total_physical_rounds * SECONDS_PER_ROUND_OVERHEAD
            )
            implied_seconds = max(
                0.0, residual_seconds / record.pattern.total_stitches
            )
        if time_calibration_eligible:
            assert implied_seconds is not None
            implied_seconds_per_stitch.append(implied_seconds)
        elif time_validation_eligible:
            assert implied_seconds is not None
            validation_implied_seconds_per_stitch.append(implied_seconds)
            validation_baseline_time_ratios.append(time_ratio)
        elif validation_record_eligible:
            validation_full_project_time_ratios.append(time_ratio)
        cases.append({
            "trial_id": record.trial_id,
            "maker_id": record.maker_id,
            "cohort": record.cohort,
            "pattern_sha256": record.pattern.sha256,
            "pattern_modified": observation.pattern_modified,
            "calibration_eligible": calibration_eligible,
            "validation_eligible": validation_record_eligible,
            "time_scope": observation.time_scope,
            "time_calibration_eligible": time_calibration_eligible,
            "time_validation_eligible": time_validation_eligible,
            "height_ratio_actual_to_target": round(height_ratio, 6),
            "time_ratio_actual_to_estimate": round(time_ratio, 6),
            "stitch_gauge_ratio_actual_to_pattern": round(stitch_ratio, 6),
            "row_gauge_ratio_actual_to_pattern": round(row_ratio, 6),
        })

    for label, values, plausible_range, metric_blockers in (
        ("normalized yarn grams", normalized_base_grams, (0.005, 0.5), grams_blockers),
        ("implied stitch seconds", implied_seconds_per_stitch, (0.5, 60.0), time_blockers),
    ):
        center = _median(values)
        deviation = _median_absolute_deviation(values)
        if center is None or deviation is None:
            continue
        if not plausible_range[0] <= center <= plausible_range[1]:
            metric_blockers.append(
                f"{label} median {center} is outside plausible range {plausible_range}"
            )
        elif center == 0 or deviation / center > MAX_RELATIVE_MEDIAN_ABSOLUTE_DEVIATION:
            metric_blockers.append(
                f"{label} relative median absolute deviation exceeds "
                f"{MAX_RELATIVE_MEDIAN_ABSOLUTE_DEVIATION:.0%}"
            )
    blockers = grams_blockers + [
        blocker for blocker in time_blockers if blocker not in grams_blockers
    ]
    ready = not blockers
    grams_ready = not grams_blockers
    time_ready = not time_blockers
    validation_sample_ready = not validation_blockers
    candidate_grams = _median(normalized_base_grams) if grams_ready else None
    candidate_seconds = _median(implied_seconds_per_stitch) if time_ready else None
    candidate_meters = (
        _median(meters_per_100g) if grams_ready and meters_per_100g else None
    )
    return {
        "report_schema_version": TRIAL_REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application_version": _application_version(),
        "summary": {
            "records": len(records),
            "drafts": len(records) - len(completed),
            "completed": len(completed),
            "calibration_eligible": len(eligible),
            "time_calibration_eligible": len(time_eligible),
            "validation_eligible": len(validation_eligible),
            "time_validation_eligible": len(validation_time_eligible),
            "distinct_patterns": len(distinct_patterns),
            "distinct_time_patterns": len(distinct_time_patterns),
            "distinct_validation_patterns": len(validation_patterns),
            "distinct_validation_time_patterns": len(validation_time_patterns),
            "distinct_makers": len(distinct_makers),
            "distinct_time_makers": len(distinct_time_makers),
            "distinct_validation_makers": len(validation_makers),
            "distinct_validation_time_makers": len(validation_time_makers),
            "calibration_ready": ready,
            "blockers": blockers,
            "independent_validation_sample_ready": validation_sample_ready,
        },
        "observed": {
            "height_ratio_actual_to_target": _distribution(height_ratios),
            "time_ratio_actual_to_estimate": _distribution(time_ratios),
            "stitch_gauge_ratio_actual_to_pattern": _distribution(stitch_gauge_ratios),
            "row_gauge_ratio_actual_to_pattern": _distribution(row_gauge_ratios),
            "normalized_base_grams_per_stitch": _distribution(normalized_base_grams),
            "implied_seconds_per_stitch": _distribution(implied_seconds_per_stitch),
            "observed_meters_per_100g": _distribution(meters_per_100g),
        },
        "recommendations": {
            "automatic_changes_applied": False,
            "base_grams_per_stitch": {
                "current": BASE_GRAMS_PER_STITCH,
                "candidate": candidate_grams,
                "ready": grams_ready,
                "blockers": grams_blockers,
            },
            "seconds_per_stitch": {
                "current": SECONDS_PER_STITCH,
                "candidate": candidate_seconds,
                "ready": time_ready,
                "blockers": time_blockers,
                "assumed_round_overhead_seconds": SECONDS_PER_ROUND_OVERHEAD,
            },
            "meters_per_100g": {
                "candidate": candidate_meters,
                "note": "Only trials with measured yarn length contribute.",
            },
        },
        "independent_validation": {
            "sample_ready": validation_sample_ready,
            "automatic_pass_assigned": False,
            "blockers": validation_blockers,
            "cohort_pattern_hashes_disjoint": not cohort_pattern_overlap,
            "observed": {
                "height_ratio_actual_to_target": _distribution(
                    validation_height_ratios
                ),
                "normalized_base_grams_per_stitch": _distribution(
                    validation_normalized_base_grams
                ),
                "grams_ratio_to_current_constant": _distribution([
                    value / BASE_GRAMS_PER_STITCH
                    for value in validation_normalized_base_grams
                ]),
                "implied_seconds_per_stitch": _distribution(
                    validation_implied_seconds_per_stitch
                ),
                "seconds_ratio_to_current_constant": _distribution([
                    value / SECONDS_PER_STITCH
                    for value in validation_implied_seconds_per_stitch
                ]),
                "round_crochet_time_ratio_actual_to_estimate": _distribution(
                    validation_baseline_time_ratios
                ),
                "full_project_time_ratio_to_baseline_estimate": _distribution(
                    validation_full_project_time_ratios
                ),
            },
            "note": (
                "Sample readiness proves holdout size and independence only. "
                "It does not declare the current or candidate constants accurate."
            ),
        },
        "external_evidence": (
            summarize_external_evidence(external_evidence)
            if external_evidence is not None
            else {
                "attached": False,
                "policy": {
                    "used_for_calibration": False,
                    "automatic_changes_applied": False,
                },
            }
        ),
        "cases": cases,
    }


def analyze_trial_directory(
    records_dir: str | Path,
    external_evidence_path: Optional[str | Path] = None,
    *,
    curated_external_evidence: bool = False,
) -> dict[str, Any]:
    if external_evidence_path is not None and curated_external_evidence:
        raise TrialDataError("choose either custom or curated external evidence")
    if curated_external_evidence:
        external = load_curated_external_evidence()
    elif external_evidence_path is not None:
        external = load_external_evidence(external_evidence_path)
    else:
        external = None
    return analyze_trials(load_trial_records(records_dir), external)


def write_json(payload: dict[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crochet2pattern-trials",
        description="创建实体试钩记录并分析尺寸、用线和工时偏差",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="从图解 JSON 创建绑定哈希的试钩草稿")
    init.add_argument("--pattern", required=True)
    init.add_argument("--trial-id", required=True)
    init.add_argument("--maker-id", required=True, help="稳定的匿名制作者 ID")
    init.add_argument(
        "--cohort",
        choices=("calibration", "validation"),
        default="calibration",
        help="校准集或独立留出验证集；默认 calibration",
    )
    init.add_argument("--out", required=True, help="建议使用 *.trial.json")
    init.add_argument("--force", action="store_true", help="允许覆盖已有草稿文件")
    analyze = commands.add_parser("analyze", help="分析目录内全部 *.trial.json")
    analyze.add_argument("--records", required=True)
    analyze.add_argument("--out", help="JSON 报告路径；省略则输出到 stdout")
    external_context = analyze.add_mutually_exclusive_group()
    external_context.add_argument(
        "--external-evidence",
        help="外部证据 JSON；只附加背景，不参与校准",
    )
    external_context.add_argument(
        "--curated-external-evidence",
        action="store_true",
        help="附加发行包内置精选证据；只作背景，不参与校准",
    )
    analyze.add_argument(
        "--allow-insufficient",
        action="store_true",
        help="样本不足时返回 0；报告仍保持 calibration_ready=false",
    )
    analyze.add_argument(
        "--require-validation",
        action="store_true",
        help="独立验证集样本不足或与校准图解重叠时返回 2",
    )
    external = commands.add_parser(
        "external-report",
        help="验证并汇总外部试钩证据；不需要本地试钩记录",
    )
    evidence_source = external.add_mutually_exclusive_group(required=True)
    evidence_source.add_argument("--evidence", help="用户提供的外部证据 JSON")
    evidence_source.add_argument(
        "--curated",
        action="store_true",
        help="使用发行包内置、带来源边界的精选证据",
    )
    external.add_argument("--out", help="JSON 报告路径；省略则输出到 stdout")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            output_path = Path(args.out)
            if output_path.exists() and not args.force:
                raise TrialDataError(f"refusing to overwrite existing trial: {output_path}")
            draft = create_trial_draft(
                args.pattern,
                trial_id=args.trial_id,
                maker_id=args.maker_id,
                cohort=args.cohort,
            )
            path = write_json(draft, output_path)
            print(f"试钩草稿: {path}", file=sys.stderr)
            return 0
        if args.command == "external-report":
            evidence = (
                load_curated_external_evidence()
                if args.curated
                else load_external_evidence(args.evidence)
            )
            report = summarize_external_evidence(evidence)
            if args.out:
                path = write_json(report, args.out)
                print(f"外部证据报告: {path}", file=sys.stderr)
            else:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            coverage = report["coverage"]
            print(
                f"外部证据: sources={coverage['sources']} · "
                f"observations={coverage['observations']} · calibration=false",
                file=sys.stderr,
            )
            return 0
        report = analyze_trial_directory(
            args.records,
            args.external_evidence,
            curated_external_evidence=args.curated_external_evidence,
        )
    except TrialDataError as exc:
        print(f"试钩数据无效: {exc}", file=sys.stderr)
        return 1
    if args.out:
        path = write_json(report, args.out)
        print(f"试钩报告: {path}", file=sys.stderr)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    summary = report["summary"]
    print(
        f"试钩分析: completed={summary['completed']} · "
        f"eligible={summary['calibration_eligible']} · "
        f"time_eligible={summary['time_calibration_eligible']} · "
        f"ready={summary['calibration_ready']} · "
        f"validation_ready={summary['independent_validation_sample_ready']}",
        file=sys.stderr,
    )
    analysis_ready = summary["calibration_ready"] and (
        not args.require_validation
        or summary["independent_validation_sample_ready"]
    )
    return 0 if analysis_ready or args.allow_insufficient else 2


if __name__ == "__main__":
    raise SystemExit(main())
