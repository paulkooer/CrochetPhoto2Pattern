import hashlib
import json
from pathlib import Path

import pytest

from app.models.gauge import BASE_STITCH_AREA_CM2
from app.trials import (
    ExternalEvidenceBundle,
    TrialDataError,
    TrialRecord,
    analyze_trial_directory,
    analyze_trials,
    create_trial_draft,
    load_curated_external_evidence,
    load_external_evidence,
    load_trial_records,
    main,
    summarize_external_evidence,
)

CURATED_EXTERNAL_EVIDENCE = (
    Path(__file__).resolve().parents[1] / "app" / "data" / "external-trial-evidence.json"
)


def _pattern_payload():
    return {
        "analysis": {"height_cm": 18.0},
        "params": {
            "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
            "estimated_time_minutes": 44,
            "parts": [
                {
                    "name": "头部",
                    "quantity": 1,
                    "rounds": [{"stitches": 6}, {"stitches": 12}],
                },
                {
                    "name": "手臂",
                    "quantity": 2,
                    "rounds": [{"stitches": 6}],
                },
            ],
        },
    }


def _record(
    index,
    *,
    pattern_hash=None,
    modified=False,
    status="completed",
    cohort="calibration",
):
    stitches = 1000
    rounds = 60
    stitch_area = (10.0 / 13.0) * (10.0 / 16.0)
    grams = 0.09 * stitch_area / BASE_STITCH_AREA_CM2 * stitches
    payload = {
        "schema_version": 2,
        "trial_id": f"trial-{index}",
        "maker_id": f"maker-{index % 2}",
        "status": status,
        "cohort": cohort,
        "pattern": {
            "sha256": pattern_hash or f"{index % 3 + 1:064x}",
            "application_version": "0.2.0b1",
            "target_height_cm": 20.0,
            "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
            "total_stitches": stitches,
            "total_physical_rounds": rounds,
            "estimated_time_minutes": 120,
        },
        "swatch": {
            "measured": status == "completed",
            "stitches_per_10cm": 13.0,
            "rows_per_10cm": 16.0,
            "hook_mm": 4.0,
            "yarn_brand": "Test Yarn",
        },
        "observation": None,
    }
    if status == "completed":
        payload["observation"] = {
            "completed_on": "2026-08-30",
            "overall_height_cm": 21.0,
            "yarn_used_grams": grams,
            "yarn_used_meters": 200.0,
            "active_minutes": 130,
            "time_scope": "round_crochet_baseline",
            "pattern_modified": modified,
            "modifications": ["added two body rounds"] if modified else [],
        }
    return payload


def _external_bundle_payload():
    return {
        "schema_version": 1,
        "created_on": "2026-08-30",
        "sources": [{
            "source_id": "source-a",
            "title": "Published timer aggregate",
            "publisher": "Example publisher",
            "source_url": "https://example.com/trials",
            "accessed_on": "2026-08-30",
            "evidence_kind": "platform_timer_aggregate",
            "verification": "source_claim",
            "declared_sample_size": 10,
            "raw_records_available": False,
            "methodology_available": True,
            "reuse_basis": "public_facts_with_attribution",
            "license_identifier": None,
            "calibration_allowed": False,
            "observations": [{
                "observation_id": "bear-18cm",
                "project_label": "Bear",
                "project_type": "amigurumi",
                "measurement_scope": "source_aggregate",
                "finished_height_cm": 18,
                "completion_minutes_median": 840,
                "completion_minutes_min": 600,
                "completion_minutes_max": 1200,
            }],
        }],
    }


def test_create_trial_draft_binds_exact_pattern_and_recomputes_counts(tmp_path):
    pattern_path = tmp_path / "pattern.json"
    blob = json.dumps(_pattern_payload(), ensure_ascii=False)
    pattern_path.write_text(blob, encoding="utf-8")

    draft = create_trial_draft(pattern_path, trial_id="trial-a", maker_id="maker-a")
    assert draft["status"] == "draft"
    assert draft["cohort"] == "calibration"
    assert draft["pattern"]["sha256"] == hashlib.sha256(blob.encode()).hexdigest()
    assert draft["pattern"]["total_stitches"] == 30
    assert draft["pattern"]["total_physical_rounds"] == 4
    assert draft["pattern"]["target_height_cm"] == 18.0
    assert draft["swatch"]["measured"] is False
    assert draft["observation"] is None


def test_five_unmodified_trials_across_three_patterns_produce_candidates():
    records = [TrialRecord.model_validate(_record(index)) for index in range(5)]
    report = analyze_trials(records)

    assert report["summary"]["calibration_ready"] is True
    assert report["summary"]["calibration_eligible"] == 5
    assert report["summary"]["distinct_patterns"] == 3
    assert report["observed"]["height_ratio_actual_to_target"]["median"] == 1.05
    assert report["recommendations"]["automatic_changes_applied"] is False
    assert report["recommendations"]["base_grams_per_stitch"]["candidate"] == pytest.approx(0.09)
    assert report["recommendations"]["seconds_per_stitch"]["candidate"] == pytest.approx(7.2)


def test_modified_trial_is_reported_but_excluded_from_calibration():
    records = [TrialRecord.model_validate(_record(index)) for index in range(4)]
    records.append(TrialRecord.model_validate(_record(4, modified=True)))
    report = analyze_trials(records)

    assert report["summary"]["completed"] == 5
    assert report["summary"]["calibration_eligible"] == 4
    assert report["summary"]["calibration_ready"] is False
    assert report["recommendations"]["base_grams_per_stitch"]["candidate"] is None
    modified = next(case for case in report["cases"] if case["trial_id"] == "trial-4")
    assert modified["calibration_eligible"] is False


def test_high_dispersion_blocks_candidate_even_when_sample_count_is_met():
    records = []
    stitch_area = (10.0 / 13.0) * (10.0 / 16.0)
    for index, normalized_grams in enumerate((0.01, 0.03, 0.09, 0.27, 0.49)):
        payload = _record(index)
        payload["observation"]["yarn_used_grams"] = (
            normalized_grams * stitch_area / BASE_STITCH_AREA_CM2 * 1000
        )
        records.append(TrialRecord.model_validate(payload))
    report = analyze_trials(records)
    assert report["summary"]["calibration_ready"] is False
    assert any("relative median absolute deviation" in item
               for item in report["summary"]["blockers"])
    assert report["recommendations"]["base_grams_per_stitch"]["candidate"] is None


def test_full_project_time_is_context_only_but_yarn_can_still_calibrate():
    records = []
    for index in range(5):
        payload = _record(index)
        payload["observation"]["time_scope"] = "full_project"
        records.append(TrialRecord.model_validate(payload))

    report = analyze_trials(records)
    assert report["summary"]["calibration_ready"] is False
    assert report["summary"]["calibration_eligible"] == 5
    assert report["summary"]["time_calibration_eligible"] == 0
    assert report["recommendations"]["base_grams_per_stitch"]["ready"] is True
    assert report["recommendations"]["base_grams_per_stitch"]["candidate"] == pytest.approx(0.09)
    assert report["recommendations"]["seconds_per_stitch"]["ready"] is False
    assert report["recommendations"]["seconds_per_stitch"]["candidate"] is None
    assert all(not case["time_calibration_eligible"] for case in report["cases"])


def test_independent_validation_is_disjoint_and_never_changes_candidates():
    calibration = [TrialRecord.model_validate(_record(index)) for index in range(5)]
    baseline = analyze_trials(calibration)
    validation = [
        TrialRecord.model_validate(_record(
            10 + index,
            cohort="validation",
            pattern_hash=f"{4 + index % 2:064x}",
        ))
        for index in range(3)
    ]

    report = analyze_trials(calibration + validation)
    assert report["recommendations"] == baseline["recommendations"]
    assert report["summary"]["validation_eligible"] == 3
    assert report["summary"]["time_validation_eligible"] == 3
    assert report["summary"]["independent_validation_sample_ready"] is True
    assert report["independent_validation"]["cohort_pattern_hashes_disjoint"] is True
    assert report["independent_validation"]["automatic_pass_assigned"] is False
    assert report["independent_validation"]["observed"][
        "grams_ratio_to_current_constant"
    ]["median"] == pytest.approx(1.125)
    assert all(
        case["validation_eligible"]
        for case in report["cases"]
        if case["cohort"] == "validation"
    )


def test_validation_pattern_overlap_is_reported_and_blocks_sample_readiness():
    records = [TrialRecord.model_validate(_record(index)) for index in range(5)]
    records.extend(
        TrialRecord.model_validate(_record(
            20 + index,
            cohort="validation",
            pattern_hash=f"{1 + index % 2:064x}",
        ))
        for index in range(3)
    )

    report = analyze_trials(records)
    assert report["summary"]["calibration_ready"] is True
    assert report["summary"]["independent_validation_sample_ready"] is False
    assert report["independent_validation"]["cohort_pattern_hashes_disjoint"] is False
    assert any(
        "disjoint pattern hashes" in blocker
        for blocker in report["independent_validation"]["blockers"]
    )


def test_schema_v2_without_cohort_remains_calibration_compatible():
    payload = _record(1)
    payload.pop("cohort")
    record = TrialRecord.model_validate(payload)
    assert record.cohort == "calibration"


def test_single_maker_cannot_set_global_calibration_candidates():
    records = []
    for index in range(5):
        payload = _record(index)
        payload["maker_id"] = "maker-only"
        records.append(TrialRecord.model_validate(payload))

    report = analyze_trials(records)
    assert report["summary"]["distinct_makers"] == 1
    assert report["summary"]["calibration_ready"] is False
    assert any(
        "distinct calibration makers" in blocker
        for blocker in report["summary"]["blockers"]
    )
    assert report["recommendations"]["base_grams_per_stitch"]["candidate"] is None


def test_completed_record_requires_measured_swatch_and_modification_details():
    payload = _record(1)
    payload["swatch"]["measured"] = False
    with pytest.raises(ValueError, match="measured swatch"):
        TrialRecord.model_validate(payload)

    payload = _record(1, modified=True)
    payload["observation"]["modifications"] = []
    with pytest.raises(ValueError, match="at least one modification"):
        TrialRecord.model_validate(payload)

    payload = _record(1)
    payload["observation"]["completed_on"] = "2999-01-01"
    with pytest.raises(ValueError, match="cannot be in the future"):
        TrialRecord.model_validate(payload)


def test_loader_rejects_duplicate_trial_ids(tmp_path):
    for index in range(2):
        payload = _record(index)
        payload["trial_id"] = "duplicate"
        (tmp_path / f"{index}.trial.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    with pytest.raises(TrialDataError, match="trial_id values must be unique"):
        load_trial_records(tmp_path)


def test_analyze_directory_keeps_drafts_out_of_completed_metrics(tmp_path):
    for index, status in enumerate(("completed", "draft")):
        (tmp_path / f"{index}.trial.json").write_text(
            json.dumps(_record(index, status=status), ensure_ascii=False), encoding="utf-8"
        )
    report = analyze_trial_directory(tmp_path)
    assert report["summary"]["records"] == 2
    assert report["summary"]["completed"] == 1
    assert report["summary"]["drafts"] == 1


def test_cli_init_and_insufficient_analysis_exit_codes(tmp_path):
    pattern = tmp_path / "pattern.json"
    pattern.write_text(json.dumps(_pattern_payload()), encoding="utf-8")
    records = tmp_path / "records"
    records.mkdir()
    trial_path = records / "first.trial.json"
    assert main([
        "init", "--pattern", str(pattern), "--trial-id", "first",
        "--maker-id", "maker-a", "--out", str(trial_path),
    ]) == 0

    draft = json.loads(trial_path.read_text(encoding="utf-8"))
    assert draft["cohort"] == "calibration"
    completed = _record(1, pattern_hash=draft["pattern"]["sha256"])
    completed["trial_id"] = "first"
    completed["maker_id"] = "maker-a"
    trial_path.write_text(json.dumps(completed), encoding="utf-8")
    report_path = tmp_path / "report.json"
    base_args = ["analyze", "--records", str(records), "--out", str(report_path)]
    assert main(base_args) == 2
    assert main(base_args + ["--allow-insufficient"]) == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["summary"][
        "calibration_ready"
    ] is False

    assert main([
        "init", "--pattern", str(pattern), "--trial-id", "second",
        "--maker-id", "maker-a", "--out", str(trial_path),
    ]) == 1


def test_curated_external_evidence_is_valid_and_attributed():
    bundle = load_curated_external_evidence()
    disk_bundle = load_external_evidence(CURATED_EXTERNAL_EVIDENCE)
    report = summarize_external_evidence(bundle)

    assert bundle == disk_bundle
    assert report["coverage"]["sources"] == 4
    assert report["coverage"]["observations"] == 21
    assert len(report["amigurumi_timed_context"]) == 17
    assert report["policy"]["used_for_calibration"] is False
    assert all(source["source_url"].startswith("https://") for source in report["sources"])


def test_external_evidence_cannot_change_calibration_candidates():
    records = [TrialRecord.model_validate(_record(index)) for index in range(5)]
    baseline = analyze_trials(records)
    external = ExternalEvidenceBundle.model_validate(_external_bundle_payload())
    contextualized = analyze_trials(records, external)

    assert contextualized["recommendations"] == baseline["recommendations"]
    assert contextualized["summary"] == baseline["summary"]
    assert contextualized["external_evidence"]["policy"]["used_for_calibration"] is False
    assert contextualized["external_evidence"]["amigurumi_timed_context"][0][
        "completion_minutes_median"
    ] == 840


def test_external_evidence_rejects_calibration_and_ambiguous_ranges():
    payload = _external_bundle_payload()
    payload["sources"][0]["calibration_allowed"] = True
    with pytest.raises(ValueError, match="calibration_allowed"):
        ExternalEvidenceBundle.model_validate(payload)

    payload = _external_bundle_payload()
    payload["sources"][0]["observations"][0].pop("completion_minutes_max")
    with pytest.raises(ValueError, match="requires both min and max"):
        ExternalEvidenceBundle.model_validate(payload)


def test_external_report_cli_and_analyze_attachment(tmp_path):
    external_report = tmp_path / "external-report.json"
    assert main([
        "external-report", "--curated",
        "--out", str(external_report),
    ]) == 0
    assert json.loads(external_report.read_text(encoding="utf-8"))["coverage"][
        "sources"
    ] == 4

    records = tmp_path / "records"
    records.mkdir()
    (records / "one.trial.json").write_text(
        json.dumps(_record(1), ensure_ascii=False), encoding="utf-8"
    )
    report_path = tmp_path / "combined.json"
    assert main([
        "analyze", "--records", str(records), "--curated-external-evidence",
        "--out", str(report_path),
        "--allow-insufficient",
    ]) == 0
    combined = json.loads(report_path.read_text(encoding="utf-8"))
    assert combined["report_schema_version"] == 3
    assert combined["external_evidence"]["coverage"]["observations"] == 21


def test_cli_creates_validation_draft_and_can_require_holdout(tmp_path):
    pattern = tmp_path / "pattern.json"
    pattern.write_text(json.dumps(_pattern_payload()), encoding="utf-8")
    validation_draft = tmp_path / "validation.trial.json"
    assert main([
        "init", "--pattern", str(pattern), "--trial-id", "validation-1",
        "--maker-id", "maker-v", "--cohort", "validation",
        "--out", str(validation_draft),
    ]) == 0
    assert json.loads(validation_draft.read_text(encoding="utf-8"))[
        "cohort"
    ] == "validation"

    records = tmp_path / "records"
    records.mkdir()
    for index in range(5):
        (records / f"{index}.trial.json").write_text(
            json.dumps(_record(index), ensure_ascii=False), encoding="utf-8"
        )
    args = ["analyze", "--records", str(records)]
    assert main(args) == 0
    assert main(args + ["--require-validation"]) == 2
