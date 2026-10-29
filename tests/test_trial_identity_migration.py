"""Trial identity upgrades preserve saved work and cannot invent independent designs."""
import hashlib
import json
from copy import deepcopy
from datetime import date
from io import BytesIO
from itertools import islice, permutations
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.trials import (
    TrialRecord,
    _design_fingerprint,
    analyze_trials,
    create_trial_draft_from_bytes,
    main,
)
from app.utils.trial_bundle import (
    create_trial_bundle,
    decode_trial_bundle,
    encode_trial_bundle,
    update_trial_bundle,
)
from tests.test_app_smoke import _mock_result

_FIXTURES = Path(__file__).parent / "fixtures"


def _zip(source, record, sidecar=None):
    out = BytesIO()
    payload = json.loads(record)
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("pattern.json", source)
        archive.writestr(f"{payload['trial_id']}.trial.json", record)
        if sidecar is not None:
            archive.writestr("draft.json", sidecar)
    return out.getvalue()


def _legacy(label="draft", folder="trial_legacy_v2"):
    root = _FIXTURES / folder
    sidecar = (root / "partial-draft.json").read_bytes() if label == "partial" else None
    return (root / "pattern.json").read_bytes(), (root / f"{label}.trial.json").read_bytes(), sidecar


def _complete(bundle):
    return update_trial_bundle(
        bundle, swatch={**bundle.record.swatch.model_dump(), "measured": True},
        observation={"completed_on": date.today(), "overall_height_cm": 18,
                     "yarn_used_grams": 60,
                     "active_minutes": bundle.record.pattern.estimated_time_minutes,
                     "time_scope": "round_crochet_baseline", "pattern_modified": False},
    ).record


@pytest.mark.parametrize("folder,label", [
    ("trial_legacy_v2", "draft"), ("trial_legacy_v2", "completed"),
    ("trial_legacy_v2", "partial"), ("trial_unversioned_fingerprint", "draft"),
])
def test_frozen_legacy_bundles_upgrade_without_rewriting_source_or_measurements(folder, label):
    source, raw_record, raw_draft = _legacy(label, folder)
    original = json.loads(raw_record)
    restored = decode_trial_bundle(_zip(source, raw_record, raw_draft))
    assert restored.source == source
    assert restored.record.pattern.sha256 == hashlib.sha256(source).hexdigest()
    assert restored.record.pattern.design_fingerprint_version == "1"
    assert restored.record.pattern.design_fingerprint == _design_fingerprint(json.loads(source)["params"])
    for field in ("trial_id", "maker_id", "status", "cohort", "swatch", "observation"):
        assert restored.record.model_dump(mode="json")[field] == original[field]
    if raw_draft:
        assert restored.draft.model_dump(mode="json") == json.loads(raw_draft)["observation"]
    assert decode_trial_bundle(encode_trial_bundle(restored)) == restored
    if raw_draft:
        with ZipFile(BytesIO(encode_trial_bundle(restored))) as archive:
            trial = archive.read(f"{restored.record.trial_id}.trial.json")
            sidecar = json.loads(archive.read("draft.json"))
            assert sidecar["record_sha256"] == hashlib.sha256(trial).hexdigest()


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64), ("total_stitches", 1), ("estimated_time_minutes", 1),
    ("design_fingerprint", "0" * 64),
])
def test_legacy_migration_still_rejects_tampered_source_metadata(field, value):
    source, raw_record, _ = _legacy(folder="trial_unversioned_fingerprint")
    record = json.loads(raw_record)
    record["pattern"][field] = value
    with pytest.raises(ValueError, match="不匹配"):
        decode_trial_bundle(_zip(source, json.dumps(record)))


def test_legacy_sidecar_binding_is_checked_before_migration():
    source, raw_record, raw_draft = _legacy("partial")
    record = json.loads(raw_record)
    record["maker_id"] = "changed-after-sidecar"
    with pytest.raises(ValueError, match="未完成测量草稿与试钩记录不匹配"):
        decode_trial_bundle(_zip(source, json.dumps(record), raw_draft))


def test_reordered_parts_cannot_pass_calibration_or_holdout_cli(tmp_path):
    base = _mock_result("reordered")
    records = []
    for index, order in enumerate(islice(permutations(range(len(base["params"]["parts"]))), 8)):
        result = deepcopy(base)
        result["params"]["parts"] = [result["params"]["parts"][i] for i in order]
        records.append(_complete(create_trial_bundle(
            result, trial_id=f"order-{index}", maker_id=f"maker-{index % 2}",
            cohort="calibration" if index < 5 else "validation")))
    assert len({record.pattern.sha256 for record in records}) == 8
    report = analyze_trials(records)
    assert report["summary"]["distinct_patterns"] == 1
    assert not report["summary"]["calibration_ready"]
    assert not report["independent_validation"]["sample_ready"]
    assert not report["independent_validation"]["cohort_pattern_hashes_disjoint"]
    for record in records:
        (tmp_path / f"{record.trial_id}.trial.json").write_text(record.model_dump_json())
    assert main(["analyze", "--records", str(tmp_path), "--require-validation",
                 "--out", str(tmp_path / "report.json")]) == 2


@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_legacy_and_current_records_detect_the_exact_same_source(reverse):
    source, raw_record, _ = _legacy("completed")
    old = TrialRecord.model_validate_json(raw_record)
    new = create_trial_draft_from_bytes(source, trial_id="fresh", maker_id="maker-b", cohort="validation")
    new.update(status="completed", swatch={**new["swatch"], "measured": True},
               observation=old.observation.model_dump(mode="json"))
    current = TrialRecord.model_validate(new)
    if reverse:
        old = old.model_copy(update={"cohort": "validation"})
        current = current.model_copy(update={"cohort": "calibration"})
    assert old.pattern.sha256 == current.pattern.sha256
    report = analyze_trials([old, current])
    assert not report["independent_validation"]["cohort_pattern_hashes_disjoint"]


def test_missing_design_identity_never_claims_holdout_independence():
    from tests.test_trials import _record

    records = []
    for index in range(8):
        payload = _record(index, pattern_hash=f"{index + 1:064x}",
                          cohort="calibration" if index < 5 else "validation")
        payload["pattern"].pop("design_fingerprint", None)
        payload["pattern"].pop("design_fingerprint_version", None)
        records.append(TrialRecord.model_validate(payload))
    report = analyze_trials(records)
    assert report["summary"]["completed"] == 8
    assert not report["summary"]["calibration_ready"]
    assert not report["independent_validation"]["sample_ready"]
    assert not report["independent_validation"]["cohort_pattern_hashes_disjoint"]
    assert not report["independent_validation"]["design_identity_complete"]


def test_fingerprint_ignores_labels_numeric_spelling_and_equivalent_copy_grouping():
    base = {"gauge": {"stitches_per_10cm": 13, "rows_per_10cm": 16}, "parts": [
        {"name": "双臂", "quantity": 2, "rounds": [{"stitches": 6}, {"stitches": 12, "increase": 6}]},
    ]}
    equivalent = {"gauge": {"stitches_per_10cm": "13.0", "rows_per_10cm": 16.0}, "parts": [
        {"name": "左臂", "rounds": deepcopy(base["parts"][0]["rounds"])},
        {"name": "右臂", "rounds": deepcopy(base["parts"][0]["rounds"])},
    ]}
    assert _design_fingerprint(base) == _design_fingerprint(equivalent)
    changed = deepcopy(base)
    changed["parts"][0]["rounds"].reverse()
    assert _design_fingerprint(base) != _design_fingerprint(changed)
    changed = deepcopy(base)
    changed["parts"][0]["quantity"] = 1
    assert _design_fingerprint(base) != _design_fingerprint(changed)


def test_standalone_migration_cli_preserves_measurements_and_refuses_overwrites(tmp_path):
    source, raw_record, _ = _legacy("completed")
    source_file = tmp_path / "pattern.json"
    record_file = tmp_path / "old.trial.json"
    output = tmp_path / "upgraded.trial.json"
    source_file.write_bytes(source)
    record_file.write_bytes(raw_record)
    args = ["migrate", "--pattern", str(source_file), "--record", str(record_file), "--out", str(output)]
    assert main(args) == 0
    upgraded = json.loads(output.read_bytes())
    assert upgraded["pattern"]["design_fingerprint_version"] == "1"
    assert upgraded["observation"] == json.loads(raw_record)["observation"]
    assert source_file.read_bytes() == source and record_file.read_bytes() == raw_record
    assert main(args) == 1
    assert main(args + ["--force"]) == 0
    source_file.write_bytes(source + b"\n")
    before = output.read_bytes()
    assert main(args + ["--force"]) == 1
    assert output.read_bytes() == before


def test_genuinely_different_round_sequences_can_still_meet_both_gates():
    from app.ui.result_logic import rebuild_params

    records = []
    for index in range(8):
        result = _mock_result(f"different-{index}")
        arm = next(part for part in result["params"]["parts"] if part["name"] == "手臂")
        last = arm["rounds"][-1]
        arm["rounds"].extend({"row": last["row"] + offset + 1, "stitches": last["stitches"],
                              "increase": 0, "decrease": 0, "notes": f"{last['stitches']}X"}
                             for offset in range(index))
        result["params"] = rebuild_params(result["params"])
        records.append(_complete(create_trial_bundle(
            result, trial_id=f"different-{index}", maker_id=f"maker-{index % 2}",
            cohort="calibration" if index < 5 else "validation")))
    report = analyze_trials(records)
    assert report["summary"]["calibration_ready"]
    assert report["summary"]["distinct_patterns"] == 5
    assert report["independent_validation"]["sample_ready"]
    assert report["independent_validation"]["design_identity_complete"]
    assert report["independent_validation"]["cohort_pattern_hashes_disjoint"]


def test_unversioned_fingerprints_are_readable_but_do_not_establish_diversity():
    from tests.test_trials import _record

    records = []
    for index in range(8):
        payload = _record(index, pattern_hash=f"{index + 1:064x}",
                          cohort="calibration" if index < 5 else "validation")
        payload["pattern"].pop("design_fingerprint_version")
        records.append(TrialRecord.model_validate(payload))
    report = analyze_trials(records)
    assert report["summary"]["completed"] == 8
    assert report["summary"]["unverified_design_records"] == 8
    assert not report["summary"]["calibration_ready"]
    assert not report["independent_validation"]["sample_ready"]
    assert not report["independent_validation"]["cohort_pattern_hashes_disjoint"]


@pytest.mark.parametrize("fingerprint", [None, "0" * 64])
def test_current_bundle_cannot_hide_a_missing_or_tampered_fingerprint(fingerprint):
    bundle = create_trial_bundle(_mock_result("tampered-fingerprint"), trial_id="current", maker_id="maker-a")
    data = bundle.record.model_dump(mode="json")
    data["pattern"]["design_fingerprint"] = fingerprint
    with pytest.raises(ValueError):
        decode_trial_bundle(_zip(bundle.source, json.dumps(data)))


def test_same_source_hash_blocks_overlap_even_with_conflicting_current_fingerprints():
    from tests.test_trials import _record

    left = _record(1)
    right = _record(2, cohort="validation")
    right["pattern"]["sha256"] = left["pattern"]["sha256"]
    report = analyze_trials([TrialRecord.model_validate(left), TrialRecord.model_validate(right)])
    assert not report["independent_validation"]["cohort_pattern_hashes_disjoint"]


@pytest.mark.parametrize("destination", ["pattern", "record", "hardlink"])
def test_migration_cli_never_overwrites_source_inputs_even_with_force(tmp_path, destination):
    source, raw_record, _ = _legacy("completed")
    source_file, record_file = tmp_path / "pattern.json", tmp_path / "old.trial.json"
    source_file.write_bytes(source)
    record_file.write_bytes(raw_record)
    output = {"pattern": source_file, "record": record_file}.get(destination, tmp_path / "alias.json")
    if destination == "hardlink":
        output.hardlink_to(record_file)
    assert main(["migrate", "--pattern", str(source_file), "--record", str(record_file),
                 "--out", str(output), "--force"]) == 1
    assert source_file.read_bytes() == source and record_file.read_bytes() == raw_record


def test_migration_write_failure_retains_inputs_and_existing_output(tmp_path, monkeypatch):
    from app.utils import output_files

    source, raw_record, _ = _legacy("completed")
    source_file, record_file = tmp_path / "pattern.json", tmp_path / "old.trial.json"
    output = tmp_path / "upgraded.trial.json"
    source_file.write_bytes(source)
    record_file.write_bytes(raw_record)
    output.write_bytes(b"previous output")

    def fail(*args):
        raise OSError("synthetic replacement failure")

    monkeypatch.setattr(output_files.os, "replace", fail)
    assert main(["migrate", "--pattern", str(source_file), "--record", str(record_file),
                 "--out", str(output), "--force"]) == 1
    assert output.read_bytes() == b"previous output"
    assert source_file.read_bytes() == source and record_file.read_bytes() == raw_record
    assert not list(tmp_path.glob(".crochet-*"))


def test_browser_restores_legacy_partial_measurements_and_rebinds_download(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from app.ui.result_logic import import_backup
    from tests.test_trial_editor import RENDER

    source, raw_record, raw_draft = _legacy("partial")
    archive = _zip(source, raw_record, raw_draft)
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader", lambda *a, **k: BytesIO(archive))
    at = AppTest.from_string(RENDER, default_timeout=30)
    result = import_backup(json.loads(source), "legacy-ui")
    at.session_state["result"] = result
    at.run()
    at.button(key="trial_restore_result").click().run()
    assert not at.exception and not at.error
    workspace = at.session_state["trial_workspace_result"]
    assert workspace["bundle"].source == source
    assert workspace["bundle"].record.pattern.design_fingerprint_version == "1"
    prefix = f"trial_fields_result_{workspace['token']}_"
    assert at.number_input(key=prefix + "overall_height_cm").value == 18
    assert at.text_area(key=prefix + "notes").value == "synthetic partial measurement"
    downloaded = decode_trial_bundle(workspace["archive"])
    assert downloaded == workspace["bundle"]
    assert at.session_state["result"] == result
