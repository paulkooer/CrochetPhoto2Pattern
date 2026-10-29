"""Progress must follow all reserved-loop dependencies and resume the right copy."""
import itertools
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.validator import require_valid_pattern
from app.ui.progress_state import capture_progress, install_progress, progress_entries, retained_progress
from app.utils.project import project_backup
from tests.test_app_smoke import _mock_result

RENDER = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
'''


def _chain(order):
    result = _mock_result("chain")
    result["structure"] = {"parts": []}
    result["params"].pop("assembly_plan", None)
    sources = ("outer", "middle", "inner", "base", "independent")
    result["params"]["parts"] = [
        {"name": name, "type": "cylinder", "quantity": 1,
         "magic_ring": name in ("base", "independent"), "rounds": [
             {"row": 1, "stitches": 6,
              "notes": "魔法环起6针（X×6）" if name in ("base", "independent") else "BLO(6X)"},
             {"row": 2, "stitches": 6, "notes": "FLO(6X)"}]} for name in sources]
    links = [{"source_part": source, "target_part": target, "source_row": 1,
              "target_row": 1, "reservation_row": 2, "end_stitch": 6}
             for source, target in zip(sources[:3], sources[1:4], strict=True)]
    result["params"]["stitch_attachments"] = {
        "schema_version": "1", "connections": [links[i] for i in order]}
    require_valid_pattern(result["params"])
    return result


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_foundation_change_clears_all_dependent_progress_regardless_of_record_order(order):
    result = _chain(order)
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}
    updated = deepcopy(result)
    next(p for p in updated["params"]["parts"] if p["name"] == "base")["rounds"][0]["color"] = "红色"
    kept = retained_progress(result, updated, "result", progress)
    expected = {identity: True for identity, _, p in progress_entries(updated, "result")
                if p["name"] == "independent"}
    assert kept == expected
    # A new project must not resurrect progress in an indirectly affected layer.
    assert project_backup(updated, kept)["project_state"]["completed_rounds"] == expected


def test_reordering_connection_records_alone_preserves_progress():
    result = _chain((0, 1, 2))
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}
    updated = deepcopy(result)
    updated["params"]["stitch_attachments"]["connections"].reverse()
    assert retained_progress(result, updated, "result", progress) == progress


def test_changing_an_outer_layer_keeps_its_unmodified_foundations():
    result = _chain((0, 1, 2))
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}
    updated = deepcopy(result)
    updated["params"]["parts"][0]["rounds"][0]["color"] = "红色"
    kept = retained_progress(result, updated, "result", progress)
    assert kept == {identity: True for identity, _, p in progress_entries(updated, "result")
                    if p["name"] != "outer"}


def _paged():
    result = _mock_result("resume")
    arm = next(p for p in result["params"]["parts"] if p["name"] == "手臂")
    arm["quantity"] = 2
    arm["rounds"] = [{"row": i + 1, "stitches": 6, "increase": 0, "decrease": 0, "color": None,
                      "notes": "魔法环起6针（X×6）" if i == 0 else "6X"} for i in range(300)]
    result["params"]["parts"] = [arm]
    return result


def test_restored_progress_navigates_to_first_unfinished_round_of_second_copy():
    result = _paged()
    progress = {identity: True for i, (identity, _, _) in enumerate(progress_entries(result, "result"))
                if i < 307}
    prepared = {}
    install_progress(result, "result", progress, prepared)
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    for key, value in prepared.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception
    assert any("第 2 个 手臂 · 第 8 圈" in c.value for c in at.caption)
    assert at.selectbox(key="progress_page_resume_0").value == 0
    at.button(key="progress_next_resume_0").click().run()
    assert not at.exception and at.selectbox(key="progress_page_resume_0").value == 6
    assert not at.checkbox(key="chk_resume_手臂_copy2_7").value
    assert "None" not in at.checkbox(key="chk_resume_手臂_copy2_7").label
    assert capture_progress(result, "result", at.session_state.to_dict()) == progress
    at.checkbox(key="chk_resume_手臂_copy2_7").check().run()
    assert any("第 2 个 手臂 · 第 9 圈" in c.value for c in at.caption)
    assert len(capture_progress(result, "result", at.session_state.to_dict())) == 308


def test_completed_and_reset_progress_have_consistent_resume_controls():
    result = _paged()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.selectbox(key="progress_page_resume_0").select(10).run()
    at.button(key="all_resume_手臂").click().run()
    assert not at.exception and at.button(key="progress_next_resume_0").disabled
    assert any("所有实体圈次均已完成" in c.value for c in at.caption)
    at.button(key="clear_resume_手臂").click().run()
    at.button(key="progress_next_resume_0").click().run()
    assert not at.exception and at.selectbox(key="progress_page_resume_0").value == 0
    assert not capture_progress(result, "result", at.session_state.to_dict())
    assert len([c for c in at.checkbox if c.key.startswith("chk_")]) == 50
