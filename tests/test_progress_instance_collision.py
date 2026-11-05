"""Separate physical copies even when a graph ID matches a fallback copy ID."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from streamlit.testing.v1 import AppTest

from app.services.progress_state import (
    install_progress,
    progress_entries,
    progress_impact,
    reconcile_restored_progress,
    retained_progress,
)
from app.services.result_logic import import_backup, rebuild_params
from app.utils.project import project_backup, read_project_state
from tests.progress_helpers import checked_keys, progress_from_keys
from tests.test_app_smoke import _mock_result
from tests.test_project_backup import RENDER
from tests.test_swatch_provenance import source

FIXTURE = Path(__file__).parent / "fixtures" / "progress_instance_collision"
IMPORTER = "from app.ui.backup_import import render_backup_import\nrender_backup_import()"


def legacy_project():
    payload = (FIXTURE / "legacy-project.json").read_bytes()
    provenance = json.loads((FIXTURE / "provenance.json").read_text())
    assert hashlib.sha256(payload).hexdigest() == provenance["project_sha256"]
    return json.loads(payload)


def collision_result(result_id="live"):
    return import_backup(legacy_project(), result_id)


@pytest.mark.parametrize("copies", [(1,), (2,), (1, 2)])
def test_project_roundtrip_preserves_each_copy_independently(copies):
    result = collision_result()
    entries = [(identity, key) for identity, key, part in progress_entries(result, "result")
               if part["name"] == "头部" and json.loads(identity)[2] == 1]
    assert len(entries) == 2 and entries[0][0] != entries[1][0]
    progress = progress_from_keys(result, {entries[i - 1][1] for i in copies})
    project = project_backup(result, progress, "保留其他线索")
    assert project["project_state"]["progress_identity_version"] == "2"
    restored = import_backup(project, "restored")
    saved, notes = read_project_state(project, restored)
    state = {}
    install_progress(restored, "result", saved, state)
    assert notes == "保留其他线索"
    shown = checked_keys(restored, state)
    for i, key in enumerate(("chk_restored_头部_0", "chk_restored_头部_copy2_0"), start=1):
        assert (key in shown) == (i in copies)


def test_paged_progress_keeps_its_physical_copy_after_project_restore():
    result = collision_result("paged")
    head = next(part for part in result["params"]["parts"] if part["name"] == "头部")
    head["rounds"] = [{"row": i + 1, "stitches": 6, "increase": 0, "decrease": 0,
                       "notes": "魔法环起6针（X×6）" if i == 0 else "6X"} for i in range(300)]
    result["params"] = rebuild_params(result["params"])
    progress = progress_from_keys(result, {"chk_paged_头部_copy2_299"})
    project = project_backup(result, progress, "分页进度")
    restored = import_backup(project, "newpage")
    saved, notes = read_project_state(project, restored)
    state = {}
    install_progress(restored, "result", saved, state)
    assert notes == "分页进度"
    assert checked_keys(restored, state) == {"chk_newpage_头部_copy2_299"}


def test_nonconflicting_projects_keep_existing_identity_format():
    result = source()
    entries = list(progress_entries(result, "result"))
    assert len({identity for identity, _, _ in entries}) == len(entries)
    project = project_backup(result, {}, "")
    assert "progress_identity_version" not in project["project_state"]
    assert read_project_state(project, import_backup(project, "again")) == ({}, "")


def test_fallback_avoids_all_existing_graph_instance_ids():
    result = collision_result()
    head = next(part for part in result["structure"]["parts"] if part["name"] == "头部")
    first = head["instances"][0]
    first["instance_id"] = "copy3"
    second = deepcopy(first)
    second["instance_id"] = "copy3_"
    head["instances"].append(second)
    head["count"] = 2
    next(part for part in result["params"]["parts"] if part["name"] == "头部")["quantity"] = 3
    restored = import_backup(result, "three")
    identities = [identity for identity, _, part in progress_entries(restored, "result")
                  if part["name"] == "头部" and json.loads(identity)[2] == 1]
    assert len(set(identities)) == 3
    assert [json.loads(identity)[1] for identity in identities] == ["copy3", "copy3_", "copy3__"]


@settings(max_examples=100, deadline=None)
@given(st.lists(st.sampled_from(["head", "copy1", "copy2", "copy2_", "copy3", "copy3_", "copy4"]),
                min_size=1, max_size=5, unique=True),
       st.sets(st.integers(min_value=0, max_value=6)))
def test_generated_copy_identities_and_selected_progress_are_independent(graph_ids, selected):
    result = {"result_id": "before", "structure": {"schema_version": "2.0", "parts": [
        {"name": "样本", "instances": [{"instance_id": identity} for identity in graph_ids]}]},
        "params": {"parts": [{"name": "样本", "quantity": len(graph_ids) + 2,
                              "rounds": [{"row": 1, "stitches": 6}]}]}}
    entries = list(progress_entries(result, "result"))
    assert len({identity for identity, _, _ in entries}) == len(entries)
    chosen = {index for index in selected if index < len(entries)}
    ticked = {key for index, (_, key, _) in enumerate(entries) if index in chosen}
    progress = progress_from_keys(result, ticked)
    restored = {**result, "result_id": "after"}
    installed = {}
    install_progress(restored, "result", progress, installed)
    after = list(progress_entries(restored, "result"))
    shown = checked_keys(restored, installed)
    assert {index for index, (_, key, _) in enumerate(after) if key in shown} == chosen


@pytest.mark.parametrize("new_graph_id", ["renamed", "copy2_"])
def test_changing_a_graph_id_never_moves_progress_to_another_copy(new_graph_id):
    current = collision_result()
    updated = deepcopy(current)
    head = next(part for part in updated["structure"]["parts"] if part["name"] == "头部")
    head["instances"][0]["instance_id"] = new_graph_id
    old = [(identity, key) for identity, key, part in progress_entries(current, "result")
           if part["name"] == "头部" and json.loads(identity)[2] == 1]
    new = [(identity, key) for identity, key, part in progress_entries(updated, "result")
           if part["name"] == "头部" and json.loads(identity)[2] == 1]
    first_only = progress_from_keys(current, {old[0][1]})
    assert retained_progress(current, updated, "result", first_only) == {}

    second_only = progress_from_keys(current, {old[1][1]})
    assert retained_progress(current, updated, "result", second_only) == {new[1][0]: True}
    impact = next(row for row in progress_impact(current, updated, "result", second_only)
                  if row["部件"] == "头部")
    assert impact["保留完成圈次"] == 1 and impact["清除完成圈次"] == 0


def test_undo_carries_latest_fallback_progress_without_confusing_graph_ids():
    restored = collision_result()
    current = deepcopy(restored)
    head = next(part for part in current["structure"]["parts"] if part["name"] == "头部")
    head["instances"][0]["instance_id"] = "copy2_"
    old = [identity for identity, _, part in progress_entries(restored, "result")
           if part["name"] == "头部" and json.loads(identity)[2] == 1]
    new = [identity for identity, _, part in progress_entries(current, "result")
           if part["name"] == "头部" and json.loads(identity)[2] == 1]

    # The graph copy changed identity; the extra copy still has the same role,
    # even though its fallback ID changes to avoid a collision.
    saved = {old[0]: True, old[1]: True}
    assert reconcile_restored_progress(current, restored, {new[0]: True}, saved) == ({old[0]: True}, 1)
    assert reconcile_restored_progress(current, restored, {new[1]: True}, {}) == ({old[1]: True}, 0)


def test_retained_progress_ignores_unknown_and_noncanonical_identities():
    result = collision_result()
    invalid = {"not JSON": True, '["头部", "copy2", true]': True,
               '["头部", "copy2", 1.0]': True, '["头部","copy2",1]': True,
               '["头部", "nonexistent", 1]': True, '["头部", "copy2", 9999]': True}
    assert retained_progress(result, result, "result", invalid) == {}


def test_legacy_ambiguous_progress_requires_explicit_recovery():
    data = legacy_project()
    original = deepcopy(data)
    result = import_backup(data, "restored")
    with pytest.raises(ValueError, match="无法区分"):
        read_project_state(data, result)
    progress, notes = read_project_state(data, result, clear_legacy_ambiguity=True)
    assert notes == "原始合成备注"
    assert len(progress) == 1 and json.loads(next(iter(progress)))[0] == "帽子"
    state = {}
    install_progress(result, "result", progress, state)
    shown = checked_keys(result, state)
    assert "chk_restored_帽子_0" in shown
    assert "chk_restored_头部_0" not in shown and "chk_restored_头部_copy2_0" not in shown
    assert data == original


def test_recovery_does_not_ignore_other_invalid_progress():
    data = legacy_project()
    data["project_state"]["completed_rounds"]['["不存在", "copy1", 1]'] = True
    result = import_backup(data, "restored")
    with pytest.raises(ValueError, match="不存在"):
        read_project_state(data, result, clear_legacy_ambiguity=True)


def test_legacy_collision_without_ambiguous_completions_restores_normally():
    data = legacy_project()
    data["project_state"]["completed_rounds"] = {
        identity: value for identity, value in data["project_state"]["completed_rounds"].items()
        if json.loads(identity)[0] == "帽子"}
    result = import_backup(data, "restored")
    progress, _ = read_project_state(data, result)
    assert progress == data["project_state"]["completed_rounds"]


def test_ui_requires_explicit_recovery_and_preserves_other_progress_and_notes():
    data = legacy_project()
    current = _mock_result("kept")
    at = AppTest.from_string(IMPORTER, default_timeout=30)
    at.session_state["result"] = deepcopy(current)
    at.session_state["project_notes_kept"] = "现有工作"
    at.run()
    at.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    at.text_area(key="open_backup_text").input(json.dumps(data, ensure_ascii=False)).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception and at.session_state["result"] == current
    assert at.session_state["project_notes_kept"] == "现有工作"
    assert any("无法区分" in warning.value for warning in at.warning)
    at.button(key="open_backup_recover_ambiguous").click().run()
    assert not at.exception
    restored = at.session_state["result"]
    rid = restored["result_id"]
    assert at.session_state["workspace_result"]["result_id"] == rid
    assert at.session_state["workspace_result"]["notes"] == "原始合成备注"
    shown = checked_keys(restored, at.session_state)
    assert f"chk_{rid}_帽子_0" in shown
    assert f"chk_{rid}_头部_0" not in shown and f"chk_{rid}_头部_copy2_0" not in shown
    assert at.session_state["workspace_result"]["recovery_notice"]


def test_recovery_confirmation_does_not_transfer_to_a_different_payload():
    at = AppTest.from_string(IMPORTER, default_timeout=30).run()
    at.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    at.text_area(key="open_backup_text").input(json.dumps(legacy_project(), ensure_ascii=False)).run()
    at.button(key="open_backup_apply").click().run()
    assert at.button(key="open_backup_recover_ambiguous")
    at.text_area(key="open_backup_text").input("{} ").run()
    assert not any(button.key == "open_backup_recover_ambiguous" for button in at.button)


def test_result_page_recovery_displays_notice_and_keeps_it_after_an_edit():
    current = _mock_result("current")
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = current
    at.run()
    at.text_area(key="import_current").input(json.dumps(legacy_project(), ensure_ascii=False)).run()
    at.button(key="importbtn_current").click().run()
    assert at.session_state["result"] == current
    at.button(key="import_current_recover_ambiguous").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert any("无法区分" in item.value and "重新勾选" in item.value for item in at.warning)
    at.number_input(key=f"edit_{rid}_weight").set_value(60)
    next(button for button in at.button if button.label == "更新材料估算").click().run()
    assert not at.exception
    new_id = at.session_state["result"]["result_id"]
    assert new_id != rid
    assert any("无法区分" in item.value and "重新勾选" in item.value for item in at.warning)


def test_legacy_undo_snapshot_does_not_guess_which_copy_was_completed():
    data = legacy_project()
    current = import_backup(data, "current")
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = current
    at.session_state["edit_history_result"] = {
        "current_id": "current", "undo": [{"result": deepcopy(current),
            "progress": data["project_state"]["completed_rounds"]}], "redo": [], "comparison": None}
    at.run()
    at.button(key="edit_current_undo").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert at.checkbox(key=f"chk_{rid}_帽子_0").value
    assert not at.checkbox(key=f"chk_{rid}_头部_0").value
    assert not at.checkbox(key=f"chk_{rid}_头部_copy2_0").value
    assert any("旧" in warning.value and "无法区分" in warning.value for warning in at.warning)


def test_new_undo_redo_snapshots_keep_the_selected_copy():
    result = collision_result("undo")
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.checkbox(key="chk_undo_头部_copy2_0").check().run()
    at.number_input(key="edit_undo_weight").set_value(60)
    next(button for button in at.button if button.label == "更新材料估算").click().run()
    for action in ("undo", "redo"):
        rid = at.session_state["result"]["result_id"]
        at.button(key=f"edit_{rid}_{action}").click().run()
        assert not at.exception
        rid = at.session_state["result"]["result_id"]
        assert at.checkbox(key=f"chk_{rid}_头部_copy2_0").value
        assert not at.checkbox(key=f"chk_{rid}_头部_0").value
