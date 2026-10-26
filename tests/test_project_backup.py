"""Restore independent physical-copy progress and notes against the exact pattern."""
import json
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.schemas import PatternResult
from app.ui.progress_state import capture_progress, install_progress, progress_entries, retained_progress
from app.ui.result_logic import import_backup
from app.utils.project import MAX_PROJECT_NOTES, pattern_revision, project_backup, read_project_state
from tests.test_app_smoke import _APP, _mock_result

RENDER = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
'''


def _result():
    result = _mock_result("project")
    arms = next(p for p in result["params"]["parts"] if p["name"] == "手臂")
    arms["quantity"] = 2
    return result


def _progress(result):
    # Pick one round on the first arm and a different round on the second arm.
    return {identity: True for identity, key, _ in progress_entries(result, "result")
            if key in ("chk_project_手臂_0", "chk_project_手臂_copy2_1")}


def test_project_roundtrip_keeps_copy_identity_and_notes_without_sharing_them():
    from app.utils.share import decode_result, encode_result

    result = _result()
    progress = _progress(result)
    assert len(progress) == 2
    project = project_backup(result, progress, "4号针；右臂下一圈换线")
    restored = import_backup(project, "new-session")
    saved, notes = read_project_state(project, restored)
    state = {}
    install_progress(restored, "result", saved, state)
    assert capture_progress(restored, "result", state) == progress
    assert state["chk_new-session_手臂_0"] and state["chk_new-session_手臂_copy2_1"]
    assert "chk_new-session_手臂_copy2_0" not in state
    assert notes == "4号针；右臂下一圈换线"
    assert "project_state" not in PatternResult.from_result(project).to_backup()
    token = encode_result(project)
    assert token is not None and "project_state" not in decode_result(token)
    assert pattern_revision(result) == pattern_revision({**result, "result_id": "new-session"})


@pytest.mark.parametrize("damage", ["revision", "version", "round", "copy", "false", "numeric_bool", "notes"])
def test_invalid_project_does_not_apply_progress(damage):
    result = _result()
    project = project_backup(result, _progress(result), "保留备注")
    state = project["project_state"]
    if damage == "revision":
        project["params"]["parts"][0]["rounds"][0]["color"] = "红色"
    elif damage == "version":
        state["schema_version"] = "999"
    elif damage in ("round", "copy"):
        identity = json.loads(next(iter(state["completed_rounds"])))
        identity[2 if damage == "round" else 1] = 999 if damage == "round" else "nonexistent-copy"
        state["completed_rounds"] = {json.dumps(identity, ensure_ascii=False): True}
    elif damage in ("false", "numeric_bool"):
        state["completed_rounds"][next(iter(state["completed_rounds"]))] = False if damage == "false" else 1
    else:
        state["notes"] = "字" * (MAX_PROJECT_NOTES + 1)
    restored = import_backup(project, "checked")
    with pytest.raises(ValueError):
        read_project_state(project, restored)


def test_old_pattern_backup_has_no_personal_state():
    result = _result()
    backup = PatternResult.from_result(result).to_backup()
    assert read_project_state(backup, import_backup(backup, "old")) == ({}, "")


def test_fresh_session_opens_project_and_preserves_latest_checkbox_snapshot(monkeypatch):
    result = _result()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.checkbox(key="chk_project_手臂_0").check().run()
    at.checkbox(key="chk_project_手臂_copy2_1").check().run()
    at.text_area(key="project_notes_project").input("私人线材备注").run()
    captured = []
    monkeypatch.setattr("app.ui.project_save._download_project",
                        lambda payload, *args: captured.append(payload))
    at.button(key="project_save_project").click().run()
    assert not at.exception
    data = json.loads(captured[-1])
    assert data["project_state"]["completed_rounds"] == _progress(result)
    # Later unchecked progress must not reuse a stale generated download.
    at.checkbox(key="chk_project_手臂_0").uncheck().run()
    at.button(key="project_save_project").click().run()
    assert len(json.loads(captured[-1])["project_state"]["completed_rounds"]) == 1

    fresh = AppTest.from_file(_APP, default_timeout=30).run()
    fresh.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    fresh.text_area(key="open_backup_text").input(captured[0]).run()
    fresh.button(key="open_backup_apply").click().run()
    assert not fresh.exception
    rid = fresh.session_state["result"]["result_id"]
    assert fresh.checkbox(key=f"chk_{rid}_手臂_0").value
    assert fresh.checkbox(key=f"chk_{rid}_手臂_copy2_1").value
    assert not fresh.checkbox(key=f"chk_{rid}_手臂_copy2_0").value
    assert fresh.text_area(key=f"project_notes_{rid}").value == "私人线材备注"
    assert "manual_result" not in fresh.session_state


def test_modified_project_file_is_rejected_atomically():
    original = _result()
    data = project_backup(original, _progress(original), "新备注")
    data["params"]["parts"][0]["color"] = "红色"
    at = AppTest.from_string("from app.ui.backup_import import render_backup_import\nrender_backup_import()")
    at.session_state["result"] = deepcopy(original)
    at.session_state["project_notes_project"] = "原备注"
    at.session_state["chk_project_手臂_0"] = True
    at.run()
    at.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    at.text_area(key="open_backup_text").input(json.dumps(data)).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception and any("版本不一致" in error.value for error in at.error)
    assert at.session_state["result"] == original
    assert at.session_state["project_notes_project"] == "原备注"
    assert at.session_state["chk_project_手臂_0"]


def test_edit_clears_affected_progress_and_undo_restores_it_with_notes():
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = _result()
    at.run()
    at.checkbox(key="chk_project_头部_0").check().run()
    at.checkbox(key="chk_project_手臂_copy2_1").check().run()
    at.text_area(key="project_notes_project").input("下一次继续右臂").run()
    at.number_input(key="edit_project_part0_diameter_cm").set_value(11)
    next(b for b in at.button if b.label == "应用部件修改").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert at.checkbox(key=f"chk_{rid}_手臂_copy2_1").value
    assert not at.checkbox(key=f"chk_{rid}_头部_0").value
    assert at.text_area(key=f"project_notes_{rid}").value == "下一次继续右臂"
    assert any("清除了 1 个" in warning.value for warning in at.warning)
    next(b for b in at.button if b.label == "↶ 撤销修改").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert at.checkbox(key=f"chk_{rid}_头部_0").value
    assert at.text_area(key=f"project_notes_{rid}").value == "下一次继续右臂"


def test_body_change_invalidates_dependent_skirt_progress():
    from tests.test_stitch_attachments import _result as attached_result

    result = attached_result()
    state = {key: True for _, key, _ in progress_entries(result, "result")}
    progress = capture_progress(result, "result", state)
    changed = deepcopy(result)
    body = next(p for p in changed["params"]["parts"] if p["name"] == "身体")
    body["rounds"][0]["color"] = "红色"
    kept = retained_progress(result, changed, "result", progress)
    assert kept
    assert all(json.loads(identity)[0] not in ("身体", "裙子") for identity in kept)


def test_paged_progress_survives_project_roundtrip_without_visible_widgets():
    result = _result()
    arms = next(p for p in result["params"]["parts"] if p["name"] == "手臂")
    arms["rounds"] = [{"row": i + 1, "stitches": 6, "increase": 0, "decrease": 0,
                       "notes": "魔法环起6针（X×6）" if i == 0 else "6X"} for i in range(520)]
    state = {"chk_project_手臂_519": True, "chk_project_手臂_copy2_513": True}
    progress = capture_progress(result, "result", state)
    data = project_backup(result, progress, "分页的末尾也要恢复")
    restored = import_backup(data, "paged")
    progress, notes = read_project_state(data, restored)
    destination = {}
    install_progress(restored, "result", progress, destination)
    assert len(destination["progress_paged"]) == 2
    assert capture_progress(restored, "result", destination) == progress
    assert notes == "分页的末尾也要恢复"


def test_save_dialog_provides_a_named_project_download():
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = _result()
    at.run()
    at.checkbox(key="chk_project_手臂_copy2_1").check().run()
    at.button(key="project_save_project").click().run()
    assert not at.exception
    assert any(button.label == "下载工程 JSON" for button in at.get("download_button"))
    assert any("已记录 1 个完成圈次" in caption.value for caption in at.caption)
