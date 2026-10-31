"""Exact separate-head neck openings, with immutable preview and portable state."""
import json
from copy import deepcopy
from dataclasses import asdict

import pytest
from streamlit.testing.v1 import AppTest

from app.models.assembly import _CLOSING_RE, _openings_by_part
from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import Gauge, ShapingStyle
from app.models.head_opening import HEAD_OPENING_KEY
from app.models.instruction_checks import round_expression
from app.models.structure_designer import StructureDesigner
from app.models.validator import require_valid_pattern
from app.schemas import ImageAnalysis, PatternResult
from app.ui.progress_state import capture_progress
from app.ui.result_logic import (
    import_backup,
    rebuild_params,
    regenerate_with_gauge,
    regenerate_with_head_opening,
    regenerate_with_size,
    regenerate_with_structure,
)
from app.utils.exporters import export_markdown
from app.utils.pdf_export import export_pdf
from app.utils.project import project_backup, read_project_state
from app.utils.trial_bundle import create_trial_bundle, decode_trial_bundle, encode_trial_bundle
from tests.test_project_backup import RENDER
from tests.test_selective_regeneration import authored, part
from tests.test_stitch_attachments import _result as joined_result


def reference(mode="ladder"):
    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=5.7, height_cm=36,
                             main_features=[], pose="站立", difficulty="medium",
                             parts=["头部", "身体", "手臂"])
    structure = StructureDesigner.design_3d_structure(analysis)
    gauge = Gauge(30, 32)
    style = ShapingStyle(sphere_mode=mode)
    params = CrochetParamsGenerator.generate_params(analysis, structure, gauge=gauge, style=style)
    return PatternResult(analysis=analysis.model_dump(), structure=structure, params=params,
                         gauge=asdict(gauge), style=asdict(style), result_id="opening").to_result_dict()


def test_reference_head_opens_at_exact_sixteen_with_executable_transition():
    current = reference()
    snapshot = deepcopy(current)
    assert len(part(current, "头部")["rounds"]) == 26
    updated = regenerate_with_head_opening(current, 16)
    head = part(updated, "头部")
    assert current == snapshot
    assert max(row["stitches"] for row in head["rounds"]) == 54
    assert len(head["rounds"]) == 25  # A generated variant, not a copy of a 26-round source pattern.
    assert head["opening_row"] == head["rounds"][-1]["row"] == 25
    previous, last = head["rounds"][-2:]
    assert (previous["stitches"], last["stitches"], last["decrease"]) == (18, 16, 2)
    assert last["notes"].startswith("(7X,A)×2")
    expression = round_expression(last["notes"])
    assert (expression.counts.consumed, expression.counts.produced) == (18, 16)
    assert not _CLOSING_RE.search(last["notes"])
    assert _openings_by_part(updated["params"]["parts"])["头部"] == 16
    assert part(updated, "手臂") == part(current, "手臂")
    assert updated["params"]["total_stitches"] == current["params"]["total_stitches"] - 2
    require_valid_pattern(updated["params"])


@pytest.mark.parametrize("mode", ["ladder", "ideal", "egg"])
@pytest.mark.parametrize("target", [6, 7, 16, 18, "maximum"])
def test_shape_modes_keep_exact_opening_and_executable_round_counts(mode, target):
    current = reference(mode)
    maximum = max(row["stitches"] for row in part(current, "头部")["rounds"])
    requested = maximum if target == "maximum" else target
    updated = regenerate_with_head_opening(current, requested)
    rows = part(updated, "头部")["rounds"]
    assert rows[-1]["stitches"] == requested
    assert part(updated, "头部")["opening_row"] == rows[-1]["row"]
    assert max(row["stitches"] for row in rows) == maximum
    for before, row in zip(rows, rows[1:], strict=False):
        expression = round_expression(row["notes"])
        assert expression is not None
        assert expression.counts.consumed == before["stitches"]
        assert expression.counts.produced == row["stitches"]
    require_valid_pattern(updated["params"])


@pytest.mark.parametrize("gauge", [Gauge(6, 8), Gauge(6, 50), Gauge(40, 8), Gauge(40, 50)])
@pytest.mark.parametrize("mode", ["ladder", "ideal", "egg"])
def test_density_boundaries_have_executable_opening_transitions(gauge, mode):
    source = reference(mode)
    params = CrochetParamsGenerator.generate_params(
        ImageAnalysis(**source["analysis"]), source["structure"], gauge=gauge,
        style=ShapingStyle(sphere_mode=mode), head_opening_stitches=6)
    assert params[HEAD_OPENING_KEY] == 6
    assert next(p for p in params["parts"] if p["name"] == "头部")["rounds"][-1]["stitches"] == 6
    require_valid_pattern(params)


@pytest.mark.parametrize("target", [True, False, 0, 5, -1, 16.5, "16.5", "nan", float("inf"), 100001, {}, []])
def test_invalid_requests_leave_authored_work_unchanged(target):
    current = authored()
    snapshot = deepcopy(current)
    with pytest.raises(ValueError):
        regenerate_with_head_opening(current, target)
    assert current == snapshot


def test_large_opening_or_onepiece_is_not_silently_clamped_or_split():
    current = reference()
    with pytest.raises(ValueError, match="最大"):
        regenerate_with_head_opening(current, 60)
    joined = joined_result(one_piece=True)
    snapshot = deepcopy(joined)
    with pytest.raises(ValueError, match="一体"):
        regenerate_with_head_opening(joined, 16)
    assert joined == snapshot


def test_close_again_and_noop_preserve_other_authored_parts():
    current = authored()
    opened = regenerate_with_head_opening(current, 16)
    assert part(opened, "手臂") == part(current, "手臂")
    assert regenerate_with_head_opening(opened, 16) == opened
    closed = regenerate_with_head_opening(opened, None)
    assert HEAD_OPENING_KEY not in closed["params"]
    assert part(closed, "头部")["opening_row"] is None
    assert _CLOSING_RE.search(part(closed, "头部")["rounds"][-1]["notes"])
    assert part(closed, "手臂") == part(current, "手臂")


@pytest.mark.parametrize("declared_row", [False, True])
def test_explicit_manual_opening_without_generation_flag_can_restore_closed_template(declared_row):
    current = regenerate_with_head_opening(reference(), 16)
    current["params"].pop(HEAD_OPENING_KEY)
    if not declared_row:
        part(current, "头部")["opening_row"] = None
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = current
    at.run()
    assert not at.exception
    assert at.checkbox(key="edit_opening_head_open").value
    closed = regenerate_with_head_opening(current, None)
    assert part(closed, "头部")["opening_row"] is None
    assert _CLOSING_RE.search(part(closed, "头部")["rounds"][-1]["notes"])


def test_resizing_regauging_structure_and_trial_restore_keep_saved_target():
    current = regenerate_with_head_opening(reference(), 16)
    backup = PatternResult.from_result(current).to_backup()
    restored = import_backup(backup, "restored")
    structure = deepcopy(restored["structure"])
    next(p for p in structure["parts"] if p["name"] == "头部")["diameter_cm"] = 8
    for updated in (regenerate_with_size(restored, 8, 40),
                    regenerate_with_gauge(restored, 26, 28),
                    regenerate_with_structure(restored, structure)):
        assert updated["params"][HEAD_OPENING_KEY] == 16
        assert part(updated, "头部")["rounds"][-1]["stitches"] == 16
        require_valid_pattern(updated["params"])
    bundle = create_trial_bundle(current, trial_id="open-head", maker_id="synthetic")
    reopened = decode_trial_bundle(encode_trial_bundle(bundle))
    assert reopened.source == bundle.source
    assert reopened.source_revision == bundle.source_revision


def test_smaller_head_rejects_incompatible_saved_neck_and_removal_drops_target():
    current = regenerate_with_head_opening(reference(), 16)
    snapshot = deepcopy(current)
    with pytest.raises(ValueError, match="留口"):
        regenerate_with_size(current, .5, 36)
    assert current == snapshot
    structure = deepcopy(current["structure"])
    structure["parts"] = [p for p in structure["parts"] if p["name"] != "头部"]
    updated = regenerate_with_structure(current, structure)
    assert HEAD_OPENING_KEY not in updated["params"]
    assert all(p["name"] != "头部" for p in updated["params"]["parts"])


@pytest.mark.parametrize("damage", ["target", "row", "closed", "no_head", "bool", "dangling_opening"])
def test_conflicting_saved_intent_is_rejected_at_import_and_print_boundaries(damage):
    current = regenerate_with_head_opening(reference(), 16)
    if damage == "target":
        current["params"][HEAD_OPENING_KEY] = 18
    elif damage == "row":
        part(current, "头部")["opening_row"] = 1
    elif damage == "closed":
        part(current, "头部")["rounds"][-1]["notes"] += "；拉紧收口"
    elif damage == "no_head":
        current["params"]["parts"] = [p for p in current["params"]["parts"] if p["name"] != "头部"]
    elif damage == "bool":
        current["params"][HEAD_OPENING_KEY] = True
    else:
        part(current, "手臂")["opening_row"] = 999
    for operation in (lambda: require_valid_pattern(current["params"]),
                      lambda: rebuild_params(current["params"]),
                      lambda: import_backup(current, "invalid"),
                      lambda: export_markdown(current["params"], result=current),
                      lambda: export_pdf(current["params"], result=current)):
        with pytest.raises(ValueError):
            operation()


def test_numeric_string_intent_normalizes_before_rendering_and_assembly_is_current():
    current = regenerate_with_head_opening(reference(), 16)
    current["params"][HEAD_OPENING_KEY] = "16"
    current["params"]["assembly_instructions"] = "stale closed head instructions"
    restored = import_backup(current, "opened")
    assert restored["params"][HEAD_OPENING_KEY] == 16
    assembly = restored["params"]["assembly_instructions"]
    assert "第 25 圈颈口（16 针）" in assembly
    body = part(restored, "身体")
    assert f"第 {body['rounds'][-1]['row']} 圈开口（{body['rounds'][-1]['stitches']} 针）" in assembly
    assert "两侧针数不同" in assembly
    markdown = export_markdown(current["params"], result=current)
    assert "stale closed" not in markdown
    assert "连接开口**：第 25 圈 · 16 针" in markdown
    assert "第 25 圈颈口（16 针）" in markdown


def test_pdf_uses_real_opening_row_and_count(monkeypatch):
    platypus = pytest.importorskip("reportlab.platypus")
    texts = []
    original = platypus.Paragraph
    def paragraph(text, *args, **kwargs):
        texts.append(str(text))
        return original(text, *args, **kwargs)
    monkeypatch.setattr(platypus, "Paragraph", paragraph)
    current = regenerate_with_head_opening(reference(), 16)
    assert export_pdf(current["params"], result=current).startswith(b"%PDF-")
    assert any("连接开口：第 25 圈 · 16 针" in text for text in texts)
    assert any("第 25 圈颈口（16 针）" in text for text in texts)


def test_preview_apply_undo_redo_and_project_restore_keep_unrelated_work():
    current = authored()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = current
    at.run()
    at.checkbox(key="chk_selective_手臂_8").check().run()
    at.text_area(key="project_notes_selective").input("颈口待试钩").run()
    at.checkbox(key="edit_selective_head_open").check().run()
    at.number_input(key="edit_selective_head_open_stitches").set_value(16).run()
    at.button(key="edit_selective_head_open_preview").click().run()
    assert not at.exception
    assert at.session_state["result"] == current
    at.button(key="edit_selective_preview_apply").click().run()
    for action in (None, "undo", "redo"):
        if action:
            rid = at.session_state["result"]["result_id"]
            at.button(key=f"edit_{rid}_{action}").click().run()
        assert not at.exception
        saved = at.session_state["result"]
        rid = saved["result_id"]
        assert (saved["params"].get(HEAD_OPENING_KEY) == 16) == (action != "undo")
        assert part(saved, "手臂") == part(current, "手臂")
        assert at.checkbox(key=f"chk_{rid}_手臂_8").value
        assert at.text_area(key=f"project_notes_{rid}").value == "颈口待试钩"
    progress = capture_progress(saved, "result", at.session_state)
    project = project_backup(saved, progress, "颈口待试钩")
    restored = import_backup(json.loads(json.dumps(project)), "new-session")
    assert read_project_state(project, restored) == (progress, "颈口待试钩")
    assert part(restored, "头部")["rounds"][-1]["stitches"] == 16
