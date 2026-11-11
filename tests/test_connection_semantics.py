"""Structured joins and neck boundaries survive prose edits and old backups."""
from dataclasses import asdict

import pytest

from app.models.assembly import _openings_by_part
from app.models.crochet_params import CrochetParamsGenerator, _ideal_sphere_rounds
from app.models.crochetability import _core_peak
from app.models.gauge import Gauge, ShapingStyle
from app.models.instruction_checks import round_expression
from app.models.parts import ONE_PIECE_NECK_MARKER, one_piece_neck_index
from app.models.structure_designer import StructureDesigner
from app.models.validator import require_valid_pattern
from app.schemas import ImageAnalysis, PatternResult
from app.services.color_selection import apply_color_change
from app.services.result_logic import import_backup, regenerate_with_size
from app.utils.project import pattern_revision, project_backup, read_project_state


def _result(one_piece=False):
    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=8, height_cm=18,
                             main_features=[], pose="站立", difficulty="easy",
                             parts=["头部", "身体", "手臂", "腿部"])
    structure = StructureDesigner.design_3d_structure(analysis)
    style = ShapingStyle(one_piece=one_piece)
    params = CrochetParamsGenerator.generate_params(analysis, structure, style=style)
    return PatternResult(analysis=analysis.model_dump(), structure=structure, params=params,
                         gauge=params["gauge"], style=asdict(style)).to_result_dict()


def test_open_and_closed_joins_do_not_depend_on_round_prose():
    result = _result()
    parts = {p["name"]: p for p in result["params"]["parts"]}
    arm, head = parts["手臂"], parts["头部"]
    expected = _openings_by_part(result["params"]["parts"])
    arm["rounds"][-1]["notes"] += "；作者备注：先收口一半再缝"
    head["rounds"][-1]["notes"] = "作者备注：装饰"
    assert arm["connection_state"] == "open" and head["connection_state"] == "closed"
    assert _openings_by_part(result["params"]["parts"]) == expected
    assert expected["手臂"] == arm["rounds"][-1]["stitches"]
    assert "头部" not in expected
    restored = import_backup(PatternResult.from_result(result).to_backup(), "join")
    assert _openings_by_part(restored["params"]["parts"]) == expected


def test_one_piece_neck_remains_usable_after_editing_its_notes():
    result = _result(one_piece=True)
    part = next(p for p in result["params"]["parts"] if p["name"] == "头身（一体）")
    index = one_piece_neck_index(part)
    assert index is not None and part["neck_row"] == part["rounds"][index]["row"]
    part["rounds"][index]["notes"] = part["rounds"][index]["notes"].replace(
        f"；{ONE_PIECE_NECK_MARKER}，不断线直接钩身体", "")
    colored = apply_color_change(result, part_name="头身（一体）", head_color="浅肤色", body_color="蓝色")
    resized = regenerate_with_size(colored, 9, 20)
    restored = import_backup(PatternResult.from_result(colored).to_backup(), "neck")
    for output in (colored, restored, resized):
        current = next(p for p in output["params"]["parts"] if p["name"] == "头身（一体）")
        neck = one_piece_neck_index(current)
        assert neck is not None
        assert {r["color"] for r in current["rounds"][:neck + 1]} == {"浅肤色"}
        assert {r["color"] for r in current["rounds"][neck + 1:]} == {"蓝色"}


def test_crochetability_uses_neck_field_before_any_legacy_marker():
    part = {"name": "头身（一体）", "neck_row": "2", "rounds": [
        {"row": 1, "stitches": 18, "notes": ""},
        {"row": 2, "stitches": 12, "notes": "edited"},
        {"row": 3, "stitches": 36, "notes": ONE_PIECE_NECK_MARKER},
        {"row": 4, "stitches": 6, "notes": ""},
    ]}
    assert one_piece_neck_index(part) == 1
    assert _core_peak(part) == 18
    del part["neck_row"]
    assert one_piece_neck_index(part) == 2  # Legacy fallback remains available.
    assert _core_peak(part) == 36


def test_numeric_string_opening_reference_follows_validation_rules():
    result = _result()
    arm = next(p for p in result["params"]["parts"] if p["name"] == "手臂")
    expected = arm["rounds"][-1]["stitches"]
    arm["opening_row"] = str(arm["opening_row"])
    require_valid_pattern(result["params"])
    assert _openings_by_part(result["params"]["parts"])["手臂"] == expected


def test_opening_with_explicit_full_closure_instruction_is_rejected():
    result = _result()
    arm = next(p for p in result["params"]["parts"] if p["name"] == "手臂")
    arm["rounds"][-1]["notes"] += "；拉紧收口"
    with pytest.raises(ValueError, match="不能同时要求完全收口"):
        require_valid_pattern(result["params"])


@pytest.mark.parametrize("damage", ["state", "opening", "neck"])
def test_inconsistent_structural_references_are_rejected(damage):
    result = _result(one_piece=damage == "neck")
    part = result["params"]["parts"][0]
    if damage == "state":
        part["connection_state"] = "open"  # Closed head has no opening row.
    elif damage == "opening":
        part["connection_state"] = "closed"
        part["opening_row"] = part["rounds"][-1]["row"]
    else:
        part["neck_row"] = part["rounds"][-1]["row"]
    with pytest.raises(ValueError):
        require_valid_pattern(result["params"])
    with pytest.raises(ValueError):
        import_backup(result, "invalid")


def test_v2_project_keeps_progress_without_guessing_new_fields():
    legacy = _result()
    for part in legacy["params"]["parts"]:
        part.pop("connection_state", None)
        part.pop("neck_row", None)
        if part["name"] in ("身体", "手臂", "腿部"):
            part["opening_row"] = None
    project = project_backup(legacy, {}, "legacy notes")
    project["schema_version"] = "2"
    restored = import_backup(project, "legacy")
    assert read_project_state(project, restored) == ({}, "legacy notes")
    assert pattern_revision(project) == pattern_revision(restored)
    assert all("connection_state" not in p for p in restored["params"]["parts"])


@pytest.mark.parametrize("egg", [False, True])
@pytest.mark.parametrize("gauge", [Gauge(13, 16), Gauge(30, 8)])
def test_ideal_sphere_finish_warning_matches_its_actual_last_round(egg, gauge):
    rounds = _ideal_sphere_rounds(9, gauge, egg=egg)
    last = rounds[-1]
    if last["stitches"] == 6:
        assert "末圈已为6针" in last["notes"]
        assert "勿再减针收成6针" not in last["notes"]
    else:
        assert "勿再减针收成6针" in last["notes"]
    expression = round_expression(last["notes"])
    assert expression is not None and expression.counts.produced == last["stitches"]
