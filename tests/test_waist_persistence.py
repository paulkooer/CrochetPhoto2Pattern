"""A chosen waist must survive regeneration and portable project recovery."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import refresh_derived
from app.models.skirt_edit import move_skirt_join, skirt_connection, unpin_skirt_waist, waist_rows
from app.models.stitch_attachments import WAIST_POSITION_KEY, prepare_attached_skirt
from app.models.validator import require_valid_pattern
from app.schemas import PatternResult
from app.ui.progress_state import progress_entries, retained_progress
from app.ui.result_logic import import_backup, regenerate_with_size, regenerate_with_structure
from app.utils.exporters import export_markdown
from app.utils.project import project_backup, read_project_state
from tests.test_project_backup import RENDER
from tests.test_skirt_editor import _shaped
from tests.test_stitch_attachments import _check


def _source(one_piece=False):
    result = _shaped(one_piece)
    # Carry the observed profile as real results do, so regeneration sees the
    # same geometry instead of falling back to a different body template.
    result["vision_meta"] = {"silhouette": {"profile": [.8, .7, .6, .5, .7, .9, 1.0]}}
    return result


def _regenerate(result, mode):
    if mode == "size":
        return regenerate_with_size(result, result["analysis"]["head_diameter_cm"], 25)
    structure = deepcopy(result["structure"])
    next(p for p in structure["parts"] if p["name"] == "身体")["height_cm"] += 3
    return regenerate_with_structure(result, structure)


@pytest.mark.parametrize("one_piece", [False, True])
@pytest.mark.parametrize("mode", ["size", "structure"])
@pytest.mark.parametrize("choice", ["first", "middle", "last"])
def test_regeneration_keeps_chosen_relative_waist_and_rebuilds_exact_connection(one_piece, mode, choice):
    source = _source(one_piece)
    rows = waist_rows(source["params"])
    index = {"first": 0, "middle": len(rows) // 2, "last": len(rows) - 1}[choice]
    pinned = move_skirt_join(source, rows[index]["row"])
    snapshot = deepcopy(pinned)
    position = pinned["params"][WAIST_POSITION_KEY]
    automatic = _regenerate(unpin_skirt_waist(pinned), mode)
    generated = _regenerate(pinned, mode)
    candidates = waist_rows(automatic["params"])
    expected = candidates[round(position * (len(candidates) - 1))]
    actual = _check(generated)
    assert actual["target_row"] == expected["row"]
    assert actual["end_stitch"] == expected["stitches"]
    assert generated["params"][WAIST_POSITION_KEY] == position
    assert WAIST_POSITION_KEY not in automatic["params"]
    assert pinned == snapshot
    assert WAIST_POSITION_KEY not in source["params"]


@pytest.mark.parametrize("one_piece", [False, True])
def test_repeated_resizing_does_not_round_the_saved_intent_each_time(one_piece):
    source = _source(one_piece)
    choices = waist_rows(source["params"])
    pinned = move_skirt_join(source, choices[1]["row"])
    position = pinned["params"][WAIST_POSITION_KEY]
    candidate = pinned
    for height in (24, 14, 30, 21, source["analysis"]["height_cm"]):
        candidate = regenerate_with_size(candidate, source["analysis"]["head_diameter_cm"], height)
        assert candidate["params"][WAIST_POSITION_KEY] == position
        _check(candidate)
    assert skirt_connection(candidate["params"])["target_row"] == choices[1]["row"]


@pytest.mark.parametrize("one_piece", [False, True])
@pytest.mark.parametrize("project", [False, True])
def test_restored_backup_or_project_keeps_waist_policy_before_regenerating(one_piece, project):
    source = _source(one_piece)
    pinned = move_skirt_join(source, waist_rows(source["params"])[0]["row"])
    progress = {identity: True for identity, _, _ in progress_entries(pinned, "result")}
    payload = (project_backup(pinned, progress, "保留腰位") if project
               else PatternResult.from_result(pinned).to_backup())
    restored = import_backup(payload, "restored")
    assert restored["params"][WAIST_POSITION_KEY] == 0
    if project:
        assert read_project_state(payload, restored) == (progress, "保留腰位")
    regenerated = _regenerate(restored, "size")
    assert _check(regenerated)["target_row"] == waist_rows(regenerated["params"])[0]["row"]


@pytest.mark.parametrize("value", [True, False, None, "0.5", -0.1, 1.1, float("nan"), float("inf"), {}, []])
def test_invalid_waist_preferences_are_rejected_by_edit_import_and_export(value):
    result = _source()
    result["params"][WAIST_POSITION_KEY] = value
    for operation in (lambda: require_valid_pattern(result["params"]),
                      lambda: import_backup(PatternResult.from_result(result).to_backup(), "bad"),
                      lambda: export_markdown(result["params"])):
        with pytest.raises(ValueError, match="固定腰位"):
            operation()


@pytest.mark.parametrize("damage", ["ring", "missing_plan", "missing_skirt"])
def test_fixed_position_requires_a_declared_attached_skirt(damage):
    result = _source()
    result["params"][WAIST_POSITION_KEY] = .5
    if damage == "ring":
        result["params"]["skirt_style"] = "ring"
    elif damage == "missing_plan":
        result["params"].pop("stitch_attachments")
    else:
        result["params"]["parts"] = [p for p in result["params"]["parts"] if p["name"] != "裙子"]
    with pytest.raises(ValueError, match="固定腰位"):
        require_valid_pattern(result["params"])


def test_unpin_changes_only_the_next_regeneration_policy_and_keeps_progress():
    source = _source()
    fixed = move_skirt_join(source, waist_rows(source["params"])[0]["row"])
    progress = {identity: True for identity, _, _ in progress_entries(fixed, "result")}
    unpinned = unpin_skirt_waist(fixed)
    assert {**unpinned["params"], WAIST_POSITION_KEY: 0} == fixed["params"]
    assert retained_progress(fixed, unpinned, "result", progress) == progress
    automatic = _regenerate(unpinned, "size")
    assert WAIST_POSITION_KEY not in automatic["params"]
    assert _check(automatic)["target_row"] != waist_rows(automatic["params"])[0]["row"]


def test_explicitly_removing_skirt_drops_its_preference():
    result = _source()
    fixed = move_skirt_join(result, waist_rows(result["params"])[0]["row"])
    structure = deepcopy(fixed["structure"])
    structure["parts"] = [p for p in structure["parts"] if p["name"] != "裙子"]
    updated = regenerate_with_structure(fixed, structure)
    assert WAIST_POSITION_KEY not in updated["params"]
    assert not any(p["name"] == "裙子" for p in updated["params"]["parts"])


def test_fixed_waist_ui_survives_resize_and_unpin_can_be_undone():
    source = _source()
    pinned = move_skirt_join(source, waist_rows(source["params"])[0]["row"])
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = pinned
    at.session_state["project_notes_joined"] = "腰位保持靠近身体起始端"
    at.run()
    assert not at.exception and any("已固定腰位" in c.value for c in at.caption)
    at.slider(key="sz_height_joined").set_value(24).run()
    at.button(key="edit_joined_size_preview").click().run()
    assert at.session_state["result"] == pinned
    at.button(key="edit_joined_preview_apply").click().run()
    updated = at.session_state["result"]
    rid = updated["result_id"]
    assert _check(updated)["target_row"] == waist_rows(updated["params"])[0]["row"]
    assert updated["params"][WAIST_POSITION_KEY] == 0
    at.checkbox(key=f"chk_{rid}_身体_0").check().run()
    at.button(key=f"edit_{rid}_waist_unpin").click().run()
    assert any("自动定位" in str(t.value) and "固定候选" in str(t.value) for t in at.table)
    at.button(key=f"edit_{rid}_preview_apply").click().run()
    rid = at.session_state["result"]["result_id"]
    assert WAIST_POSITION_KEY not in at.session_state["result"]["params"]
    assert at.checkbox(key=f"chk_{rid}_身体_0").value
    assert at.text_area(key=f"project_notes_{rid}").value == "腰位保持靠近身体起始端"
    at.button(key=f"edit_{rid}_undo").click().run()
    assert not at.exception and at.session_state["result"]["params"][WAIST_POSITION_KEY] == 0


def test_current_waist_can_be_pinned_without_changing_rounds():
    source = _source()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = source
    at.run()
    at.button(key="edit_joined_waist_pin").click().run()
    at.button(key="edit_joined_preview_apply").click().run()
    assert not at.exception
    updated = at.session_state["result"]
    assert WAIST_POSITION_KEY in updated["params"]
    assert updated["params"]["parts"] == source["params"]["parts"]


def test_unavailable_current_waist_still_has_a_diagram_and_actionable_message():
    result = _source()
    result["params"]["stitch_attachments"] = prepare_attached_skirt(result["params"]["parts"], target_row=1)
    refresh_derived(result["params"])
    require_valid_pattern(result["params"])
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception and any("不在可自动调整" in info.value for info in at.info)
    assert any(b.label == "下载接裙示意图 SVG" for b in at.get("download_button"))
