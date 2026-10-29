"""Keep only demonstrably unchanged work and review changes before applying."""
import json
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.ui.progress_state import progress_entries, progress_impact, retained_progress
from app.ui.result_logic import import_backup
from app.utils.project import project_backup, read_project_state
from tests.test_project_backup import RENDER, _result


def _flat():
    result = _result()
    arm = next(p for p in result["params"]["parts"] if p["name"] == "手臂")
    arm["rounds"] = [dict(arm["rounds"][0], row=i + 1, stitches=6, increase=0,
                          decrease=0, notes="魔法环起6针（X×6）" if not i else "6X") for i in range(20)]
    return result


def _all(result):
    return {identity: True for identity, _, _ in progress_entries(result, "result")}


@pytest.mark.parametrize("index", [0, 5, 19])
@pytest.mark.parametrize("field,value", [("color", "红色"), ("notes", "6X；留线准备下一步")])
def test_changes_keep_only_the_exact_prefix_across_physical_copies(index, field, value):
    result = _flat()
    updated = deepcopy(result)
    arm = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")
    arm["rounds"][index][field] = value
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)
    assert kept == {identity: True for identity in progress
                    if json.loads(identity)[0] != "手臂" or json.loads(identity)[2] <= index}
    impact = next(p for p in progress_impact(result, updated, "result", progress) if p["部件"] == "手臂")
    assert impact["保留完成圈次"] == index * 2
    assert impact["清除完成圈次"] == (20 - index) * 2
    assert f"第 {index + 1} 圈" in impact["变化范围"]


@pytest.mark.parametrize("mode", ["append", "remove", "insert", "reorder"])
def test_sequence_changes_do_not_transfer_progress_to_shifted_rows(mode):
    result = _flat()
    updated = deepcopy(result)
    rows = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")["rounds"]
    if mode == "append":
        rows.append(dict(rows[-1], row=21))
        prefix = 20
    elif mode == "remove":
        rows.pop()
        prefix = 19
    elif mode == "insert":
        rows.insert(5, dict(rows[4], row=99))
        prefix = 5
    else:
        rows[5], rows[6] = rows[6], rows[5]
        prefix = 5
    kept = retained_progress(result, updated, "result", _all(result))
    assert len([k for k in kept if json.loads(k)[0] == "手臂"]) == 2 * prefix
    project = project_backup(updated, kept)
    assert read_project_state(project, import_backup(project, "restored"))[0] == kept


def test_part_wide_changes_remain_conservative_but_material_estimates_keep_progress():
    result = _flat()
    progress = _all(result)
    updated = deepcopy(result)
    updated["params"]["material_summary"] = {"grams": 1}
    assert retained_progress(result, updated, "result", progress) == progress
    updated["params"]["parts"][0]["notes"] = "先填充再继续"
    kept = retained_progress(result, updated, "result", progress)
    assert all(json.loads(k)[0] != updated["params"]["parts"][0]["name"] for k in kept)


def test_preview_is_read_only_then_apply_undo_redo_keep_exact_progress_and_notes():
    result = _flat()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    for key in ("chk_project_手臂_2", "chk_project_手臂_copy2_8"):
        at.checkbox(key=key).check().run()
    at.text_area(key="project_notes_project").input("暂停在右臂").run()
    changed = deepcopy(result["params"])
    arm = next(p for p in changed["parts"] if p["name"] == "手臂")
    arm["rounds"][5]["color"] = "红色"
    at.text_area(key="json_edit_project").input(json.dumps(changed, ensure_ascii=False)).run()
    at.button(key="edit_project_json_preview").click().run()
    assert not at.exception
    assert at.session_state["result"] == result
    assert any("从第 6 圈起" in str(t.value) for t in at.table)
    # Changes to progress after preview must be included when applying it.
    at.checkbox(key="chk_project_手臂_copy2_1").check().run()
    at.button(key="edit_project_preview_apply").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert at.checkbox(key=f"chk_{rid}_手臂_2").value
    assert at.checkbox(key=f"chk_{rid}_手臂_copy2_1").value
    assert not at.checkbox(key=f"chk_{rid}_手臂_copy2_8").value
    assert at.text_area(key=f"project_notes_{rid}").value == "暂停在右臂"
    at.button(key=f"edit_{rid}_undo").click().run()
    rid = at.session_state["result"]["result_id"]
    assert at.checkbox(key=f"chk_{rid}_手臂_copy2_8").value
    at.button(key=f"edit_{rid}_redo").click().run()
    rid = at.session_state["result"]["result_id"]
    assert not at.checkbox(key=f"chk_{rid}_手臂_copy2_8").value
    assert at.checkbox(key=f"chk_{rid}_手臂_2").value


def test_preview_refuses_to_apply_against_a_replaced_result():
    at = AppTest.from_string('''
from app.ui.edit_history import preview_edit
import streamlit as st
preview_edit("result", st.session_state.old, st.session_state.candidate)
''')
    at.session_state["old"] = _flat()
    at.session_state["candidate"] = _flat()
    at.session_state["result"] = {**_flat(), "result_id": "replacement"}
    at.run()
    assert not at.exception and any("当前图解已变化" in w.value for w in at.warning)
    assert not any(b.label == "应用这次修改" for b in at.button)


def test_cancel_preview_keeps_the_pattern_progress_and_notes():
    result = _flat()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.session_state["chk_project_手臂_0"] = True
    at.session_state["project_notes_project"] = "保留此备注"
    at.run()
    at.button(key="edit_project_json_preview").click().run()
    at.button(key="edit_project_preview_cancel").click().run()
    assert not at.exception and at.session_state["result"] == result
    assert at.checkbox(key="chk_project_手臂_0").value
    assert at.text_area(key="project_notes_project").value == "保留此备注"
    assert "edit_project_pending_preview" not in at.session_state
