"""Names belong to the current workspace and must survive content snapshots."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.utils import history
from tests.test_app_smoke import _APP


def _material(at, rid):
    return next(b for b in at.button if b.label == "更新材料估算" and rid in b.key)


@pytest.mark.parametrize("path", ["undo", "preview"])
def test_saved_title_survives_old_snapshot_apply_undo_redo_and_resave(path):
    at = AppTest.from_file(_APP, default_timeout=30).run()
    at.button(key="btn_manual").click().run()
    rid = at.session_state["manual_result"]["result_id"]
    if path == "undo":
        _material(at, rid).click().run()
        rid = at.session_state["manual_result"]["result_id"]
    else:
        at.slider(key=f"edit_{rid}_part0_i0_x").set_value(0.1)
        next(b for b in at.button if b.label == "预览部件修改影响" and rid in b.key).click().run()
    at.text_input(key=f"hist_title_{rid}").input("命名的娃娃").run()
    at.button(key=f"hist_save_{rid}").click().run()
    stored_id = at.session_state["manual_result"]["history_id"]
    at.button(key=f"edit_{rid}_{'undo' if path == 'undo' else 'preview_apply'}").click().run()
    for direction in (None, "redo" if path == "undo" else "undo", "undo" if path == "undo" else "redo"):
        if direction:
            rid = at.session_state["manual_result"]["result_id"]
            at.button(key=f"edit_{rid}_{direction}").click().run()
        assert not at.exception
        current = at.session_state["manual_result"]
        rid = current["result_id"]
        assert current.get("title") == "命名的娃娃"
        assert at.text_input(key=f"hist_title_{rid}").value == "命名的娃娃"
        at.button(key=f"hist_save_{rid}").click().run()
        assert history.load_result(stored_id)["title"] == "命名的娃娃"
        assert [item["rid"] for item in history.list_results(query="命名的娃娃")] == [stored_id]


def test_unsaved_title_draft_survives_edit_and_stays_independent_between_tabs():
    at = AppTest.from_file(_APP, default_timeout=30).run()
    at.button(key="btn_manual").click().run()
    rid = at.session_state["manual_result"]["result_id"]
    at.text_input(key=f"hist_title_{rid}").input("未保存的名称").run()
    _material(at, rid).click().run()
    rid = at.session_state["manual_result"]["result_id"]
    assert not at.exception
    assert at.text_input(key=f"hist_title_{rid}").value == "未保存的名称"
    assert history.list_results() == []
    at.button(key=f"hist_save_{rid}").click().run()
    stored_id = at.session_state["manual_result"]["history_id"]
    at.run()
    at.button(key=f"hist_load_{stored_id}").click().run()
    photo_id = at.session_state["result"]["result_id"]
    at.text_input(key=f"hist_title_{photo_id}").input("照片页名称草稿").run()
    _material(at, photo_id).click().run()
    new_photo_id = at.session_state["result"]["result_id"]
    assert at.text_input(key=f"hist_title_{new_photo_id}").value == "照片页名称草稿"
    assert at.text_input(key=f"hist_title_{rid}").value == "未保存的名称"
    assert history.load_result(stored_id)["title"] == "未保存的名称"


def test_explicit_title_clear_is_not_resurrected_from_saved_blob_or_undo():
    at = AppTest.from_file(_APP, default_timeout=30).run()
    at.button(key="btn_manual").click().run()
    rid = at.session_state["manual_result"]["result_id"]
    at.text_input(key=f"hist_title_{rid}").input("旧名称").run()
    at.button(key=f"hist_save_{rid}").click().run()
    stored_id = at.session_state["manual_result"]["history_id"]
    at.run()
    at.button(key=f"hist_load_{stored_id}").click().run()
    rid = at.session_state["result"]["result_id"]
    at.text_input(key=f"hist_title_{rid}").input("").run()
    at.button(key=f"hist_save_{rid}").click().run()
    assert not history.load_result(stored_id).get("title")
    _material(at, rid).click().run()
    rid = at.session_state["result"]["result_id"]
    at.button(key=f"edit_{rid}_undo").click().run()
    rid = at.session_state["result"]["result_id"]
    assert at.text_input(key=f"hist_title_{rid}").value == ""
    at.button(key=f"hist_save_{rid}").click().run()
    assert not history.load_result(stored_id).get("title")


def test_history_storage_title_column_and_blob_agree_when_cleared():
    from tests.test_app_smoke import _mock_result

    result = deepcopy(_mock_result("title-storage"))
    result["title"] = "旧名称"
    history.save_result(result, title=None)
    assert not history.load_result("title-storage").get("title")
