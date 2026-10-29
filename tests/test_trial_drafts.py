"""Partial measurements are portable work, never implicit completed evidence."""
import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta
from io import BytesIO
from zipfile import ZipFile

import pytest
from streamlit.testing.v1 import AppTest

from app.trials import analyze_trials, load_trial_records
from app.utils.trial_bundle import (
    MAX_TRIAL_DRAFT_BYTES,
    decode_trial_bundle,
    encode_trial_bundle,
    trial_comparison_rows,
    update_trial_bundle,
)
from tests.test_app_smoke import _APP
from tests.test_trial_editor import _app, _click, _completed, _draft, _start, _zip


def _partial():
    bundle = _draft()
    return update_trial_bundle(bundle, swatch=bundle.record.swatch.model_dump(),
                               observation={"overall_height_cm": 19.2, "notes": "用线尚未称重",
                                            "pattern_modified": True}, completed=False)


def _members(bundle):
    with ZipFile(BytesIO(encode_trial_bundle(bundle))) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_partial_roundtrip_preserves_fields_without_entering_cli_completed_analysis(tmp_path):
    bundle = _partial()
    before = deepcopy(bundle)
    archive = encode_trial_bundle(bundle)
    restored = decode_trial_bundle(archive)
    assert restored == before == bundle
    assert restored.record.status == "draft" and restored.record.observation is None
    assert restored.draft.overall_height_cm == 19.2 and restored.draft.yarn_used_grams is None
    assert restored.draft.completed_on is None
    members = _members(bundle)
    assert set(members) == {"pattern.json", "trial-a.trial.json", "draft.json"}
    assert json.loads(members["draft.json"])["record_sha256"] == hashlib.sha256(
        members["trial-a.trial.json"]).hexdigest()
    # The normal CLI glob only reads *.trial.json, even with the draft alongside.
    for name, blob in members.items():
        (tmp_path / name).write_bytes(blob)
    records = load_trial_records(tmp_path)
    assert records == [restored.record]
    assert analyze_trials(records)["cases"] == []
    assert len(trial_comparison_rows(restored)) == 2  # Gauge only until completed.


def test_completed_record_can_return_to_draft_and_be_completed_without_losing_measurements():
    finished = _completed(modified=True)
    original = deepcopy(finished)
    draft = update_trial_bundle(finished, swatch=finished.record.swatch.model_dump(),
                                observation=None, completed=False)
    assert draft.draft.model_dump() == finished.record.observation.model_dump()
    assert draft.record.observation is None and finished == original
    restored = decode_trial_bundle(encode_trial_bundle(draft))
    complete = update_trial_bundle(restored, swatch=restored.record.swatch.model_dump(),
                                   observation=restored.draft.model_dump(), completed=True)
    assert complete.record == finished.record and complete.draft is None
    assert complete.source == finished.source
    assert "draft.json" not in _members(complete)


def test_swatch_only_update_retains_partial_work_and_explicit_empty_input_can_clear_it():
    bundle = _partial()
    updated = update_trial_bundle(bundle, swatch={**bundle.record.swatch.model_dump(), "hook_mm": 4.0},
                                  observation=None)
    assert updated.draft == bundle.draft
    cleared = update_trial_bundle(updated, swatch=updated.record.swatch.model_dump(),
                                  observation={}, completed=False)
    assert cleared.draft is None and cleared.record.status == "draft"
    assert "draft.json" not in _members(cleared)
    assert updated.draft == bundle.draft


@pytest.mark.parametrize("completed", [False, True])
def test_original_two_member_bundles_remain_compatible(completed):
    bundle = _completed() if completed else _draft()
    assert len(_members(bundle)) == 2
    assert decode_trial_bundle(encode_trial_bundle(bundle)) == bundle


@pytest.mark.parametrize("damage", ["incomplete", "unmeasured", "missing_modifications"])
def test_marking_complete_enforces_full_evidence_contract_and_keeps_partial_on_failure(damage):
    bundle = _partial()
    observation = _completed().record.observation.model_dump()
    swatch = {**bundle.record.swatch.model_dump(), "measured": True}
    if damage == "incomplete":
        observation = bundle.draft.model_dump()
    elif damage == "unmeasured":
        swatch["measured"] = False
    else:
        observation.update(pattern_modified=True, modifications=[])
    before = deepcopy(bundle)
    with pytest.raises(ValueError):
        update_trial_bundle(bundle, swatch=swatch, observation=observation, completed=True)
    assert bundle == before


@pytest.mark.parametrize("field,value", [
    ("overall_height_cm", True), ("yarn_used_grams", 0), ("active_minutes", 2.5),
    ("yarn_used_meters", float("inf")), ("overall_height_cm", float("nan")),
    ("pattern_modified", "false"), ("time_scope", "unknown"),
    ("completed_on", date.today() + timedelta(days=1)), ("notes", "字" * 2001),
])
def test_partial_values_still_obey_types_ranges_and_lengths(field, value):
    bundle = _draft()
    with pytest.raises(ValueError):
        update_trial_bundle(bundle, swatch=bundle.record.swatch.model_dump(),
                            observation={field: value}, completed=False)


@pytest.mark.parametrize("damage", ["version", "binding", "record_changed", "extra", "completed", "oversize"])
def test_sidecar_corruption_is_rejected_before_installation(damage):
    members = _members(_partial())
    sidecar = json.loads(members["draft.json"])
    if damage == "version":
        sidecar["schema_version"] = "999"
    elif damage == "binding":
        sidecar["record_sha256"] = "0" * 64
    elif damage == "record_changed":
        record = json.loads(members["trial-a.trial.json"])
        record["maker_id"] = "someone-else"
        members["trial-a.trial.json"] = json.dumps(record).encode()
    elif damage == "extra":
        sidecar["observation"]["unknown"] = "ignored?"
    elif damage == "completed":
        members["trial-a.trial.json"] = _completed().record.model_dump_json().encode()
        sidecar["record_sha256"] = hashlib.sha256(members["trial-a.trial.json"]).hexdigest()
    members["draft.json"] = (b" " * (MAX_TRIAL_DRAFT_BYTES + 1) if damage == "oversize"
                              else json.dumps(sidecar).encode())
    with pytest.raises(ValueError):
        decode_trial_bundle(_zip(members.items()))


def test_export_checks_draft_byte_limit():
    bundle = _draft()
    large = update_trial_bundle(bundle, swatch=bundle.record.swatch.model_dump(),
                                 observation={"modifications": ["x" * MAX_TRIAL_DRAFT_BYTES]},
                                 completed=False)
    with pytest.raises(ValueError, match="512 KiB"):
        encode_trial_bundle(large)


def test_partial_form_survives_state_toggle_and_fresh_session_before_completion(monkeypatch):
    at = _app()
    prefix = _start(at)
    assert at.date_input(key=prefix + "date").value is None
    at.number_input(key=prefix + "overall_height_cm").set_value(19.2)
    at.text_area(key=prefix + "notes").input("等线团称重后再补")
    # complete/measured 等都在 st.form 内：真实浏览器里勾选表单内控件不会触发
    # rerun（表单只在提交时生效），且 streamlit≥1.66 的 AppTest 会在中途 .run()
    # 丢弃未提交的表单值。故切换勾选不加 .run()，忠实模拟“填写→切换→提交”。
    at.checkbox(key=prefix + "complete").check()
    at.checkbox(key=prefix + "complete").uncheck()
    assert at.number_input(key=prefix + "overall_height_cm").value == 19.2
    assert at.text_area(key=prefix + "notes").value == "等线团称重后再补"
    _click(at, "保存记录并更新下载")
    assert not at.exception and not at.error
    saved = at.session_state["trial_workspace_result"]["bundle"]
    assert saved.record.observation is None and saved.draft.overall_height_cm == 19.2
    assert not at.metric
    archive = at.session_state["trial_workspace_result"]["archive"]
    upload = BytesIO(archive)
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader",
                        lambda *a, **k: upload if k.get("key") == "trial_open_file" else None)
    fresh = AppTest.from_file(_APP, default_timeout=30).run()
    fresh.button(key="trial_open_apply").click().run()
    workspace = fresh.session_state["trial_workspace_result"]
    new_prefix = f"trial_fields_result_{workspace['token']}_"
    assert not fresh.exception and workspace["bundle"] == saved
    assert fresh.number_input(key=new_prefix + "overall_height_cm").value == 19.2
    assert fresh.text_area(key=new_prefix + "notes").value == "等线团称重后再补"
    assert fresh.number_input(key=new_prefix + "yarn_used_grams").value is None
    assert fresh.date_input(key=new_prefix + "date").value is None
    before = workspace["archive"]
    fresh.checkbox(key=new_prefix + "complete").check()
    _click(fresh, "保存记录并更新下载")
    assert any("实测小样" in error.value for error in fresh.error)
    assert fresh.session_state["trial_workspace_result"]["archive"] == before
    fresh.checkbox(key=new_prefix + "measured").check()
    fresh.date_input(key=new_prefix + "date").set_value(date.today())
    fresh.number_input(key=new_prefix + "yarn_used_grams").set_value(70.5)
    fresh.number_input(key=new_prefix + "minutes").set_value(110)
    _click(fresh, "保存记录并更新下载")
    assert not fresh.exception and not fresh.error
    finished = fresh.session_state["trial_workspace_result"]["bundle"]
    assert finished.record.status == "completed" and finished.draft is None
    assert finished.record.observation.notes == saved.draft.notes
    assert "draft.json" not in _members(finished)
    fresh.checkbox(key=new_prefix + "complete").uncheck()
    _click(fresh, "保存记录并更新下载")
    draft = fresh.session_state["trial_workspace_result"]["bundle"]
    assert not fresh.exception and draft.draft.model_dump() == finished.record.observation.model_dump()
    assert draft.record.status == "draft" and draft.record.observation is None


def test_failed_sidecar_restore_preserves_active_partial_work(monkeypatch):
    upload = None
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader", lambda *a, **k: upload)
    at = _app()
    prefix = _start(at)
    at.text_area(key=prefix + "notes").input("保留这份草稿")
    _click(at, "保存记录并更新下载")
    before = deepcopy(at.session_state["trial_workspace_result"])
    damaged = _members(_partial())
    sidecar = json.loads(damaged["draft.json"])
    sidecar["record_sha256"] = "0" * 64
    damaged["draft.json"] = json.dumps(sidecar).encode()
    upload = BytesIO(_zip(damaged.items()))
    at.run()
    at.button(key="trial_restore_result").click().run()
    assert not at.exception and any("不匹配" in error.value for error in at.error)
    assert at.session_state["trial_workspace_result"] == before
    assert at.text_area(key=prefix + "notes").value == "保留这份草稿"
