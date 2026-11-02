"""Per-tab workspace: non-widget result state lives and dies with its result."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.services.workspace import carried_workspace, new_workspace, workspace, workspace_key
from tests.test_app_smoke import _mock_result

_RENDER = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
'''


def test_workspace_for_another_result_starts_fresh_and_tabs_stay_independent():
    state: dict = {}
    photo = workspace({"result_id": "a1"}, "result", state)
    photo["export_cache"]["markdown"] = "a1"
    photo["notes"] = "a1 notes"
    manual = workspace({"result_id": "m1"}, "manual_result", state)
    manual["share"] = {"token": "m1"}

    assert workspace({"result_id": "a1"}, "result", state) is photo
    replaced = workspace({"result_id": "a2"}, "result", state)
    assert replaced == new_workspace({"result_id": "a2"}, "result")
    assert state[workspace_key("result")] is replaced
    assert state[workspace_key("manual_result")] is manual


def test_preparing_a_workspace_does_not_touch_the_session():
    state = {workspace_key("result"): new_workspace({"result_id": "live"}, "result")}
    before = deepcopy(state)
    workspace({"result_id": "next"}, "result", state, create=False)["notes"] = "draft"
    assert state == before


def test_edit_carries_the_users_text_but_not_result_bound_state():
    current = {**new_workspace({"result_id": "old", "title": "saved name"}, "result"),
               "notes": "继续右臂", "title": "renamed", "recovery_notice": "核对帽子",
               "notice": "same", "success": "done", "pending_preview": {"candidate": {}},
               "export_cache": {"markdown": "old"}, "export_trace": {"pdf": 1},
               "pdf": {"format": 1, "bytes": b"%PDF"}, "share": {"token": "old"}}
    carried = carried_workspace(current, {"result_id": "new"}, "result")
    assert carried == {**new_workspace({"result_id": "new"}, "result"),
                       "notes": "继续右臂", "title": "renamed", "recovery_notice": "核对帽子"}


def test_a_new_workspace_starts_from_the_saved_history_title():
    assert new_workspace({"result_id": "r", "title": "小熊"}, "result")["title"] == "小熊"
    assert new_workspace({"result_id": "r"}, "result")["title"] == ""


@pytest.mark.parametrize("other_slot", ["result", "manual_result"])
def test_purge_keeps_every_tab_record_for_a_generated_result_id(monkeypatch, other_slot):
    from app.ui import result_renderer as rr

    rid = "3f9c0a1b2d4e"
    tab_records = {f"{prefix}_{slot}": {"kept": True}
                   for prefix in ("workspace", "project_progress", "edit_history", "trial_workspace")
                   for slot in ("result", other_slot)}
    widgets = {f"chk_{rid}_头部_0": True, f"project_notes_{rid}": "旧备注",
               f"leg_join_manual_result_{rid}_left_row": 7, f"edit_{rid}_head_open": True}
    state = {**tab_records, **widgets, f"chk_{rid}0_头部_0": True}
    monkeypatch.setattr(rr.st, "session_state", state)
    rr.purge_result_state({"result_id": rid})
    assert state == {**tab_records, f"chk_{rid}0_头部_0": True}


def test_notes_and_title_come_back_from_the_workspace_when_widget_state_is_gone():
    result = {**_mock_result("ws-reseed"), "title": "保存过的名字"}
    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.session_state["workspace_result"] = {**new_workspace(result, "result"), "notes": "暂停在第 9 圈"}
    at.run()
    assert not at.exception
    assert at.text_area(key="project_notes_ws-reseed").value == "暂停在第 9 圈"
    assert at.text_input(key="hist_title_ws-reseed").value == "保存过的名字"

    at.text_area(key="project_notes_ws-reseed").input("改到第 10 圈").run()
    at.text_input(key="hist_title_ws-reseed").input("新名字").run()
    assert at.session_state["workspace_result"]["notes"] == "改到第 10 圈"
    assert at.session_state["workspace_result"]["title"] == "新名字"


def test_edit_moves_typed_notes_title_and_success_message_to_the_new_result():
    import json

    result = _mock_result("ws-edit")
    at = AppTest.from_string(_RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.text_area(key="project_notes_ws-edit").input("线材换成棉线")
    at.text_input(key="hist_title_ws-edit").input("棉线版")
    edited = deepcopy(result["params"])
    edited["parts"][0]["rounds"] = edited["parts"][0]["rounds"][:3]
    at.text_area(key="json_edit_ws-edit").input(json.dumps(edited, ensure_ascii=False, default=str))
    at.button(key="regen_ws-edit").click().run()
    assert not at.exception

    rid = at.session_state["result"]["result_id"]
    assert rid != "ws-edit"
    ws = at.session_state["workspace_result"]
    assert ws["result_id"] == rid and ws["success"] is None
    assert any("已根据修正" in str(s.value) for s in at.success)
    assert at.text_area(key=f"project_notes_{rid}").value == "线材换成棉线"
    assert at.text_input(key=f"hist_title_{rid}").value == "棉线版"
    assert "project_notes_ws-edit" not in at.session_state
