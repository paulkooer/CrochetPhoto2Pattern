"""Saved trial versions are reversible without losing pending input or pattern work."""
import json
from copy import deepcopy
from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pytest
from streamlit.testing.v1 import AppTest

from app.utils.trial_bundle import (
    create_trial_bundle,
    decode_trial_bundle,
    encode_trial_bundle,
    update_trial_bundle,
)
from app.utils.trial_history import (
    MAX_TRIAL_HISTORY_BYTES,
    MAX_TRIAL_SNAPSHOTS,
    restore_trial_version,
    save_trial_version,
)
from tests.test_app_smoke import _mock_result
from tests.test_project_backup import RENDER
from tests.test_trial_editor import _app, _click, _completed, _draft, _start


def _workspace(bundle=None):
    bundle = bundle or _draft()
    return {"bundle": bundle, "archive": encode_trial_bundle(bundle), "token": "old-session"}


def _partial(bundle, notes):
    return update_trial_bundle(bundle, swatch=bundle.record.swatch.model_dump(),
                               observation={"overall_height_cm": 19.2, "notes": notes}, completed=False)


def _prefix(at):
    return f"trial_fields_result_{at.session_state['trial_workspace_result']['token']}_"


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def test_save_undo_redo_retains_partial_and_completed_versions_with_matching_downloads():
    start = _workspace()
    original = deepcopy(start)
    partial = _partial(start["bundle"], "第一版")
    first = save_trial_version(start, partial)
    complete = _completed(partial)
    second = save_trial_version(first, complete)
    assert start == original and len(first["undo"]) == 1
    assert len(second["undo"]) == 2
    undone = restore_trial_version(second, "undo")
    assert undone["bundle"] == partial
    assert decode_trial_bundle(undone["archive"]) == partial
    baseline = restore_trial_version(undone, "undo")
    assert baseline["bundle"] == start["bundle"]
    assert restore_trial_version(baseline, "undo") is baseline
    redone = restore_trial_version(restore_trial_version(baseline, "redo"), "redo")
    assert redone["bundle"] == complete
    assert decode_trial_bundle(redone["archive"]) == complete
    assert second["bundle"] == complete  # Pure operations do not consume earlier workspaces.
    with ZipFile(BytesIO(redone["archive"])) as archive:
        assert set(archive.namelist()) == {"pattern.json", "trial-a.trial.json"}


def test_identical_save_preserves_redo_and_exact_download_without_serializing_again(monkeypatch):
    start = _workspace()
    saved = save_trial_version(start, _partial(start["bundle"], "saved"))
    undone = restore_trial_version(saved, "undo")
    def fail(*args):
        raise AssertionError("unchanged save must reuse the existing download")
    monkeypatch.setattr("app.utils.trial_history.encode_trial_bundle", fail)
    assert save_trial_version(undone, deepcopy(undone["bundle"])) is undone
    assert undone["redo"]


def test_editing_after_undo_starts_new_branch_and_does_not_share_mutable_measurements():
    start = _workspace()
    first = save_trial_version(start, _partial(start["bundle"], "first"))
    second = save_trial_version(first, _partial(first["bundle"], "second"))
    back = restore_trial_version(second, "undo")
    candidate = _partial(back["bundle"], "replacement")
    branch = save_trial_version(back, candidate)
    candidate.draft.notes = "changed after save"
    assert branch["bundle"].draft.notes == "replacement"
    assert not branch["redo"] and back["redo"]
    assert restore_trial_version(branch, "undo")["bundle"].draft.notes == "first"


def test_snapshot_count_is_bounded_and_closest_versions_remain_available():
    workspace = _workspace()
    for index in range(MAX_TRIAL_SNAPSHOTS + 4):
        workspace = save_trial_version(workspace, _partial(workspace["bundle"], str(index)))
    assert len(workspace["undo"]) == MAX_TRIAL_SNAPSHOTS
    previous = restore_trial_version(workspace, "undo")
    assert previous["bundle"].draft.notes == str(MAX_TRIAL_SNAPSHOTS + 2)
    assert len(previous["undo"]) + len(previous["redo"]) == MAX_TRIAL_SNAPSHOTS


def test_snapshot_bytes_are_bounded_for_large_imported_measurements():
    workspace = _workspace()
    for index in range(8):
        candidate = update_trial_bundle(
            workspace["bundle"], swatch=workspace["bundle"].record.swatch.model_dump(),
            observation={"modifications": ["x" * 400_000], "notes": str(index)}, completed=False)
        workspace = save_trial_version(workspace, candidate)
    assert sum(map(len, workspace["undo"] + workspace["redo"])) <= MAX_TRIAL_HISTORY_BYTES
    assert len(workspace["undo"]) < MAX_TRIAL_SNAPSHOTS
    previous = restore_trial_version(workspace, "undo")
    assert previous["bundle"].draft.notes == "6"
    assert sum(map(len, previous["undo"] + previous["redo"])) <= MAX_TRIAL_HISTORY_BYTES


def test_history_does_not_duplicate_the_source_pattern():
    result = _mock_result("large-source")
    result["preview"] = "preview-data-" * 50_000
    bundle = create_trial_bundle(result, trial_id="large-source", maker_id="maker-a")
    workspace = save_trial_version(_workspace(bundle), _partial(bundle, "measurement"))
    assert len(workspace["undo"][0]) < 10_000 < len(bundle.source)
    assert restore_trial_version(workspace, "undo")["bundle"].source == bundle.source


@pytest.mark.parametrize("damage", ["identity", "metadata", "json"])
def test_corrupted_history_cannot_replace_current_data_or_download(damage):
    workspace = _workspace()
    saved = save_trial_version(workspace, _partial(workspace["bundle"], "current"))
    payload = json.loads(saved["undo"][-1])
    if damage == "identity":
        payload["record"]["trial_id"] = "another-trial"
    elif damage == "metadata":
        payload["record"]["pattern"]["total_stitches"] = 1
    saved["undo"][-1] = b"{" if damage == "json" else json.dumps(payload).encode()
    before = deepcopy(saved)
    with pytest.raises(ValueError):
        restore_trial_version(saved, "undo")
    assert saved == before


def test_cross_trial_save_and_serialization_failure_leave_history_unchanged(monkeypatch):
    workspace = _workspace()
    before = deepcopy(workspace)
    unrelated = create_trial_bundle(_mock_result("other"), trial_id="other", maker_id="maker-a")
    with pytest.raises(ValueError, match="同一份试钩"):
        save_trial_version(workspace, unrelated)
    def fail(*args):
        raise ValueError("cannot encode")
    monkeypatch.setattr("app.utils.trial_history.encode_trial_bundle", fail)
    with pytest.raises(ValueError, match="cannot encode"):
        save_trial_version(workspace, _partial(workspace["bundle"], "new"))
    assert workspace == before


def test_invalid_direction_is_rejected():
    with pytest.raises(ValueError):
        restore_trial_version(_workspace(), "delete")


def test_editor_undo_redo_resets_form_and_download_but_preserves_pattern_progress():
    at = AppTest.from_string(RENDER, default_timeout=30)
    original = _mock_result("trial-source")
    at.session_state["result"] = original
    at.run()
    at.checkbox(key="chk_trial-source_头部_0").check().run()
    at.text_area(key="project_notes_trial-source").input("工程备注保留").run()
    prefix = _start(at)
    assert _button(at, "↶ 撤销保存").disabled and _button(at, "↷ 重做保存").disabled
    at.number_input(key=prefix + "overall_height_cm").set_value(19.2)
    at.text_area(key=prefix + "notes").input("未称重")
    _click(at, "保存记录并更新下载")
    partial = deepcopy(at.session_state["trial_workspace_result"]["bundle"])
    assert not _button(at, "↶ 撤销保存").disabled
    at.checkbox(key=prefix + "measured").check()
    at.checkbox(key=prefix + "complete").check()
    at.date_input(key=prefix + "date").set_value(date.today())
    at.number_input(key=prefix + "yarn_used_grams").set_value(70.5)
    at.number_input(key=prefix + "minutes").set_value(110)
    at.text_area(key=prefix + "notes").input("完成测量")
    _click(at, "保存记录并更新下载")
    complete = deepcopy(at.session_state["trial_workspace_result"]["bundle"])
    _click(at, "↶ 撤销保存")
    prefix = _prefix(at)
    assert not at.exception
    assert not at.checkbox(key=prefix + "complete").value
    assert at.number_input(key=prefix + "yarn_used_grams").value is None
    assert at.text_area(key=prefix + "notes").value == "未称重"
    assert decode_trial_bundle(at.session_state["trial_workspace_result"]["archive"]) == partial
    download = at.session_state["trial_workspace_result"]["archive"]
    _click(at, "保存记录并更新下载")
    assert at.session_state["trial_workspace_result"]["archive"] == download
    assert not _button(at, "↷ 重做保存").disabled
    _click(at, "↷ 重做保存")
    prefix = _prefix(at)
    assert not at.exception
    assert at.checkbox(key=prefix + "complete").value
    assert at.number_input(key=prefix + "yarn_used_grams").value == 70.5
    assert at.text_area(key=prefix + "notes").value == "完成测量"
    assert decode_trial_bundle(at.session_state["trial_workspace_result"]["archive"]) == complete
    assert at.session_state["result"] == original
    assert at.checkbox(key="chk_trial-source_头部_0").value
    assert at.text_area(key="project_notes_trial-source").value == "工程备注保留"
    assert not at.session_state["edit_history_result"]["undo"]


@pytest.mark.parametrize("direction", ["undo", "redo"])
@pytest.mark.parametrize("invalid", [False, True])
def test_history_action_preserves_unsaved_form_values_and_current_archive(direction, invalid):
    at = _app()
    prefix = _start(at)
    at.text_area(key=prefix + "notes").input("first")
    _click(at, "保存记录并更新下载")
    at.text_area(key=prefix + "notes").input("second")
    _click(at, "保存记录并更新下载")
    if direction == "redo":
        _click(at, "↶ 撤销保存")
        prefix = _prefix(at)
    before = deepcopy(at.session_state["trial_workspace_result"])
    if invalid:
        at.number_input(key=prefix + "hook").set_value(0.0)
    else:
        at.text_area(key=prefix + "notes").input("unsaved third version")
    _click(at, "↶ 撤销保存" if direction == "undo" else "↷ 重做保存")
    assert not at.exception and any("当前输入已保留" in error.value for error in at.error)
    assert at.session_state["trial_workspace_result"] == before
    if invalid:
        assert at.number_input(key=prefix + "hook").value == 0.0
    else:
        assert at.text_area(key=prefix + "notes").value == "unsaved third version"


def test_reopening_exported_bundle_starts_empty_history_and_preserves_current_version(monkeypatch):
    upload = None
    monkeypatch.setattr("app.ui.trial_editor.st.file_uploader", lambda *a, **k: upload)
    at = _app()
    prefix = _start(at)
    at.text_area(key=prefix + "notes").input("saved version")
    _click(at, "保存记录并更新下载")
    saved = at.session_state["trial_workspace_result"]
    assert saved["undo"]
    upload = BytesIO(saved["archive"])
    at.run()
    at.button(key="trial_restore_result").click().run()
    assert not at.exception
    restored = at.session_state["trial_workspace_result"]
    assert restored["bundle"] == saved["bundle"]
    assert not restored["undo"] and not restored["redo"]
    assert _button(at, "↶ 撤销保存").disabled
    at.button(key="trial_close_result").click().run()
    assert "trial_workspace_result" not in at.session_state
