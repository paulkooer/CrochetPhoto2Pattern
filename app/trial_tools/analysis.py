"""Physical trial analysis."""
from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.crochet_params import SECONDS_PER_ROUND_OVERHEAD, SECONDS_PER_STITCH
from app.models.gauge import BASE_GRAMS_PER_STITCH, BASE_STITCH_AREA_CM2

from .external import (
    load_curated_external_evidence,
    load_external_evidence,
    summarize_external_evidence,
)
from .io import (
    _application_version,
    load_trial_records,
)
from .schemas import (
    MAX_RELATIVE_MEDIAN_ABSOLUTE_DEVIATION,
    MIN_CALIBRATION_TRIALS,
    MIN_DISTINCT_MAKERS,
    MIN_DISTINCT_PATTERNS,
    MIN_DISTINCT_VALIDATION_PATTERNS,
    MIN_VALIDATION_TRIALS,
    TRIAL_REPORT_SCHEMA_VERSION,
    ExternalEvidenceBundle,
    TrialDataError,
    TrialRecord,
)


def _median(values: Iterable[float]) -> float | None:
    data = list(values)
    return round(float(statistics.median(data)), 6) if data else None


def _median_absolute_deviation(values: list[float]) -> float | None:
    if not values:
        return None
    center = statistics.median(values)
    return round(float(statistics.median(abs(value - center) for value in values)), 6)


def _distribution(values: list[float]) -> dict[str, float | None | int]:
    return {
        "count": len(values),
        "median": _median(values),
        "median_absolute_deviation": _median_absolute_deviation(values),
        "min": round(min(values), 6) if values else None,
        "max": round(max(values), 6) if values else None,
    }


def analyze_trials(
    records: list[TrialRecord],
    external_evidence: ExternalEvidenceBundle | None = None,
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
    def identities(group: list[TrialRecord]) -> set[str]:
        return {record.pattern.design_fingerprint for record in group
                if record.pattern.design_fingerprint_version == "1"
                and record.pattern.design_fingerprint is not None}

    def unverified(group: list[TrialRecord]) -> int:
        return sum(record.pattern.design_fingerprint_version != "1" for record in group)

    distinct_patterns = identities(eligible)
    distinct_time_patterns = identities(time_eligible)
    validation_patterns = identities(validation_eligible)
    validation_time_patterns = identities(validation_time_eligible)
    distinct_makers = {record.maker_id for record in eligible}
    distinct_time_makers = {record.maker_id for record in time_eligible}
    validation_makers = {record.maker_id for record in validation_eligible}
    validation_time_makers = {
        record.maker_id for record in validation_time_eligible
    }
    cohort_pattern_overlap = distinct_patterns & validation_patterns
    source_overlap = ({record.pattern.sha256 for record in eligible}
                      & {record.pattern.sha256 for record in validation_eligible})
    identity_complete = not unverified(unmodified)
    grams_blockers: list[str] = []
    time_blockers: list[str] = []
    validation_blockers: list[str] = []
    for group, group_blockers in ((eligible, grams_blockers), (time_eligible, time_blockers),
                                 (validation_eligible, validation_blockers)):
        unknown = unverified(group)
        if unknown:
            group_blockers.append(
                f"design identity missing or outdated in {unknown} records; "
                "reopen the original trial bundle or use migrate with the exact source pattern")
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
    if cohort_pattern_overlap or source_overlap:
        validation_blockers.append(
            "calibration and validation cohorts must use disjoint pattern hashes; "
            f"design overlap={len(cohort_pattern_overlap)}, source overlap={len(source_overlap)}"
        )
    if unverified(eligible):
        validation_blockers.append(
            "calibration design identity is incomplete; holdout independence is unverified")
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
        normalized_grams: float | None = None
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

        implied_seconds: float | None = None
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
            "design_fingerprint": record.pattern.design_fingerprint,
            "design_fingerprint_version": record.pattern.design_fingerprint_version,
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
        "generated_at": datetime.now(UTC).isoformat(),
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
            "unverified_design_records": unverified(unmodified),
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
            "cohort_pattern_hashes_disjoint": (
                identity_complete and not (cohort_pattern_overlap or source_overlap)),
            "design_identity_complete": identity_complete,
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
    external_evidence_path: str | Path | None = None,
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
