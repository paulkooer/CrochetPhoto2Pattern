"""Custom names must not collide with another part's physical-copy widget keys."""
import json
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as hs
from streamlit.testing.v1 import AppTest

from app.ui.progress_state import (
    capture_progress,
    install_progress,
    physical_rounds,
    progress_copy_prefixes,
    progress_entries,
)
from app.ui.result_logic import import_backup, rebuild_params
from app.utils.project import project_backup, read_project_state
from tests.test_app_smoke import _APP, _mock_result

_UI = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
'''


def _capture(result, at):
    return capture_progress(result, "result", at.session_state.to_dict())


def _result(names=("练习", "练习_copy2"), quantities=(2, 1), rows=2):
    result = _mock_result("key-isolation")
    parts = [{"name": name, "type": "cylinder", "color": "红色", "quantity": quantity,
              "magic_ring": True, "rounds": [
                  {"row": 7 + 3 * index, "stitches": 4, "notes": "4X"} for index in range(rows)
              ]} for name, quantity in zip(names, quantities, strict=True)]
    params = {**result["params"], "parts": parts}
    params.pop("assembly_plan", None)
    params.pop("stitch_attachments", None)
    result["params"] = rebuild_params(params)
    return result


def test_unique_part_names_produce_unique_keys_for_every_physical_round():
    result = _result()
    before = deepcopy(result)
    entries = list(progress_entries(result, "result"))
    assert len(entries) == len({identity for identity, _, _ in entries}) == 6
    assert len({key for _, key, _ in entries}) == 6
    assert result == before


def test_restoring_one_completion_does_not_mark_another_parts_copy_complete():
    result = _result()
    entries = list(progress_entries(result, "result"))
    selected = next(identity for identity, _, part in entries
                    if part["name"] == "练习_copy2" and json.loads(identity)[2] == 7)
    project = project_backup(result, {selected: True}, "保留实体位置")
    restored = import_backup(project, "restored-isolation")
    progress, notes = read_project_state(project, restored)
    state = {}
    install_progress(restored, "result", progress, state)
    assert capture_progress(restored, "result", state) == {selected: True}
    assert sum(value is True for key, value in state.items() if key.startswith("chk_")) == 1
    assert notes == "保留实体位置"


def test_inline_pattern_with_copy_like_names_renders_and_tracks_copies_independently():
    result = _result()
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    entries = list(progress_entries(result, "result"))
    identity, selected_key, _ = next(entry for entry in entries
                                    if entry[2]["name"] == "练习_copy2")
    at.checkbox(key=selected_key).check().run()
    at.run()
    assert not at.exception
    assert _capture(result, at) == {identity: True}
    assert all(at.checkbox(key=key).value == (key == selected_key) for _, key, _ in entries)


def test_inline_cleanup_does_not_remove_a_different_parts_completion():
    # No duplicate widgets here: one copy of A, and one independent A_copy2.
    # The old stale-copy regex nevertheless deleted the latter as A's "extra copy".
    result = _result(quantities=(1, 1))
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    selected = next(entry for entry in progress_entries(result, "result")
                    if entry[2]["name"] == "练习_copy2")
    at.checkbox(key=selected[1]).check().run()
    at.run()
    assert not at.exception
    assert at.checkbox(key=selected[1]).value
    assert _capture(result, at) == {selected[0]: True}


def test_noncolliding_names_keep_their_existing_session_keys():
    result = _result(names=("围巾", "耳朵"), quantities=(1, 2))
    keys = [key for _, key, _ in progress_entries(result, "result")]
    assert keys == ["chk_key-isolation_围巾_0", "chk_key-isolation_围巾_1",
                    "chk_key-isolation_耳朵_0", "chk_key-isolation_耳朵_1",
                    "chk_key-isolation_耳朵_copy2_0", "chk_key-isolation_耳朵_copy2_1"]


def test_disambiguation_does_not_take_another_parts_literal_prefix():
    result = _result(names=("练习", "练习_copy2", "练习_copy2_part1_copy2"), quantities=(2, 1, 1))
    prefixes = progress_copy_prefixes(result, "result")
    assert prefixes == progress_copy_prefixes(deepcopy(result), "result")
    flattened = [prefix for copies in prefixes for prefix in copies]
    assert len(flattened) == len(set(flattened)) == 4
    assert prefixes[2][0] == "chk_key-isolation_练习_copy2_part1_copy2_"
    assert prefixes[0][1] != prefixes[2][0]


@given(hs.lists(hs.sampled_from(["练习", "练习_copy2", "练习_copy3", "练习_copy2_part1_copy2",
                               "练习_copy2_part1_copy2_", "练习_copy2_copy2"]),
                min_size=1, max_size=6, unique=True), hs.integers(1, 4), hs.integers(0, 6))
def test_custom_name_and_copy_combinations_preserve_exact_completion_sets(names, quantity, offset):
    # A minimal result avoids making every property example run the generator.
    result = {"result_id": "property", "params": {"parts": [
        {"name": name, "quantity": quantity, "rounds": [{"row": 7}, {"row": 19}]}
        for name in names
    ]}}
    entries = list(progress_entries(result, "result"))
    assert len({key for _, key, _ in entries}) == physical_rounds(result)
    chosen = {identity: True for index, (identity, _, _) in enumerate(entries) if index % 7 == offset}
    state = {}
    install_progress(result, "result", chosen, state)
    assert capture_progress(result, "result", state) == chosen


def test_part_filter_keeps_the_full_patterns_key_mapping():
    result = _result()
    all_entries = list(progress_entries(result, "result"))
    for index, part in enumerate(result["params"]["parts"]):
        assert list(progress_entries(result, "result", part_index=index)) == [
            entry for entry in all_entries if entry[2] is part
        ]


def test_inline_cleanup_retains_valid_other_part_keys_and_removes_only_stale_rounds():
    result = _result(quantities=(1, 1))
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = result
    valid = "chk_key-isolation_练习_copy2_0"
    stale = ["chk_key-isolation_练习_99", "chk_key-isolation_练习_copy2_99",
             "chk_key-isolation_练习_copy3_0"]
    at.session_state[valid] = True
    at.session_state["chk_unrelated_练习_0"] = True
    for key in stale:
        at.session_state[key] = True
    at.run()
    assert not at.exception and at.checkbox(key=valid).value
    assert all(key not in at.session_state for key in stale)
    assert at.session_state["chk_unrelated_练习_0"]


@pytest.mark.parametrize("names", [("练习", "练习_copy2"), ("围巾", "耳朵")])
def test_mark_all_and_reset_affect_only_the_selected_logical_part(names):
    result = _result(names=names)
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    entries = list(progress_entries(result, "result"))
    other = next(entry for entry in entries if entry[2]["name"] == names[1])
    at.text_area(key="project_notes_key-isolation").input("另一部件已经开始").run()
    at.checkbox(key=other[1]).check().run()
    at.button(key=f"all_key-isolation_{names[0]}").click().run()
    assert not at.exception
    expected = {identity: True for identity, _, part in entries if part["name"] == names[0]}
    expected[other[0]] = True
    assert _capture(result, at) == expected
    at.button(key=f"clear_key-isolation_{names[0]}").click().run()
    at.run()
    assert not at.exception
    assert _capture(result, at) == {other[0]: True}
    assert at.text_area(key="project_notes_key-isolation").value == "另一部件已经开始"


def test_edit_reorder_and_undo_preserve_semantic_progress_and_notes(monkeypatch):
    from app.ui import edit_history

    result = _result()
    entries = list(progress_entries(result, "result"))
    chosen = {identity: True for identity, _, part in entries if part["name"] == "练习_copy2"}
    state = {"result": result, "project_notes_key-isolation": "记录我的进度"}
    install_progress(result, "result", chosen, state)
    monkeypatch.setattr(edit_history.st, "session_state", state)
    candidate = deepcopy(result)
    candidate["params"]["parts"].reverse()
    updated = edit_history.commit_edit("result", result, candidate)
    assert capture_progress(updated, "result", state) == chosen
    assert state[f"project_notes_{updated['result_id']}"] == "记录我的进度"
    restored = edit_history.restore_edit("result", updated, "undo")
    assert capture_progress(restored, "result", state) == chosen
    assert restored["params"]["parts"] == result["params"]["parts"]
    assert state[f"project_notes_{restored['result_id']}"] == "记录我的进度"


def test_paged_progress_and_project_save_share_the_complete_key_mapping(monkeypatch):
    result = _result(rows=171)
    entries = list(progress_entries(result, "result"))
    left = next(entry for entry in reversed(entries)
                if entry[2]["name"] == "练习" and json.loads(entry[0])[1] == "copy2")
    right = next(entry for entry in entries if entry[2]["name"] == "练习_copy2")
    chosen = {left[0]: True, right[0]: True}
    saved = project_backup(result, chosen, "跨页保存备注")
    restored = import_backup(saved, "paged-isolation")
    progress, notes = read_project_state(saved, restored)
    state = {}
    install_progress(restored, "result", progress, state)
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = restored
    at.session_state["project_notes_paged-isolation"] = notes
    for key, value in state.items():
        at.session_state[key] = value
    captured = []
    monkeypatch.setattr("app.ui.project_save._download_project",
                        lambda payload, *args: captured.append(payload))
    at.run()
    restored_entries = list(progress_entries(restored, "result"))
    key_by_identity = {identity: key for identity, key, _ in restored_entries}
    at.selectbox(key="progress_part_paged-isolation").set_value(1).run()
    assert not at.exception and at.checkbox(key=key_by_identity[right[0]]).value
    assert _capture(restored, at) == chosen
    at.checkbox(key=key_by_identity[right[0]]).uncheck().run()
    at.selectbox(key="progress_part_paged-isolation").set_value(0).run()
    at.selectbox(key="progress_page_paged-isolation_0").set_value(6).run()
    assert not at.exception and at.checkbox(key=key_by_identity[left[0]]).value
    at.button(key="project_save_paged-isolation").click().run()
    assert not at.exception
    data = json.loads(captured[-1])
    assert data["project_state"]["completed_rounds"] == {left[0]: True}
    assert data["project_state"]["notes"] == "跨页保存备注"


def test_paged_bulk_controls_and_resume_preserve_other_work_and_notes():
    result = _result(rows=171)
    entries = list(progress_entries(result, "result"))
    other = next(entry for entry in entries if entry[2]["name"] == "练习_copy2")
    state = {}
    install_progress(result, "result", {other[0]: True}, state)
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = result
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    at.text_area(key="project_notes_key-isolation").input("翻页与批量操作保留备注").run()
    at.button(key="all_key-isolation_练习").click().run()
    expected = {identity: True for identity, _, part in entries if part["name"] == "练习"}
    expected[other[0]] = True
    assert not at.exception and _capture(result, at) == expected
    at.button(key="clear_key-isolation_练习").click().run()
    assert not at.exception and _capture(result, at) == {other[0]: True}
    at.selectbox(key="progress_page_key-isolation_0").set_value(3).run()
    at.button(key="progress_next_key-isolation_0").click().run()
    at.run()
    assert not at.exception
    assert at.selectbox(key="progress_page_key-isolation_0").value == 0
    assert _capture(result, at) == {other[0]: True}
    assert at.text_area(key="project_notes_key-isolation").value == "翻页与批量操作保留备注"


def test_sidebar_restores_a_project_with_similar_names_without_adding_completions():
    result = _result()
    entry = next(entry for entry in progress_entries(result, "result") if entry[2]["name"] == "练习_copy2")
    saved = project_backup(result, {entry[0]: True}, "恢复我的备注")
    at = AppTest.from_file(_APP, default_timeout=30).run()
    at.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    at.text_area(key="open_backup_text").input(json.dumps(saved, ensure_ascii=False)).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception
    restored = at.session_state["result"]
    assert _capture(restored, at) == {entry[0]: True}
    assert at.text_area(key=f"project_notes_{restored['result_id']}").value == "恢复我的备注"
