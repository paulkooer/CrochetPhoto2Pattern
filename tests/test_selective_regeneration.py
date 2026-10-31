"""Geometry edits replace affected constructions, retaining unrelated authored work."""
import json
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator, PatternGenerationError
from app.models.skirt_edit import move_skirt_join, unpin_skirt_waist, waist_rows
from app.models.validator import require_valid_pattern
from app.schemas import ImageAnalysis, PatternResult
from app.ui.pattern_editor import edit_yarn
from app.ui.progress_state import progress_entries, retained_progress
from app.ui.result_logic import (
    import_backup,
    rebuild_params,
    regenerate_with_gauge,
    regenerate_with_size,
    regenerate_with_structure,
)
from app.utils.exporters import export_markdown
from app.utils.project import project_backup, read_project_state
from tests.test_app_smoke import _mock_result
from tests.test_project_backup import RENDER
from tests.test_stitch_attachments import _check
from tests.test_stitch_attachments import _result as joined_result
from tests.test_waist_persistence import _source as profile_result


def part(result, name):
    return next(p for p in result["params"]["parts"] if p["name"] == name)


def authored(result=None):
    result = deepcopy(result or _mock_result("selective"))
    arm = part(result, "手臂")
    assert len(arm["rounds"]) == 8
    arm["rounds"].append({"row": 9, "stitches": 6, "notes": "6X；保留手改第九圈", "color": "红色"})
    arm["rounds"][2]["notes"] += "；保留特殊缝合备注"
    result["params"] = rebuild_params(result["params"])
    return result


def change(result, name, **dimensions):
    structure = deepcopy(result["structure"])
    next(p for p in structure["parts"] if p["name"] == name).update(dimensions)
    return regenerate_with_structure(result, structure)


@pytest.mark.parametrize("name,dimensions", [("头部", {"diameter_cm":12}), ("身体", {"height_cm":8})])
def test_dimension_edits_keep_nine_authored_arm_rounds_colors_and_notes(name, dimensions):
    current = authored()
    snapshot = deepcopy(current)
    updated = change(current, name, **dimensions)
    assert current == snapshot
    assert part(updated, "手臂") == part(current, "手臂")
    assert part(updated, name) != part(current, name)
    assert len(part(updated, "手臂")["rounds"]) == 9
    assert part(updated, "手臂")["rounds"][-1]["color"] == "红色"
    require_valid_pattern(updated["params"])
    if name == "头部":
        assert max(r["stitches"] for r in part(updated, name)["rounds"]) == 48


def test_size_change_replaces_changed_lengths_but_keeps_authored_head():
    current = authored()
    part(current, "头部")["rounds"][-1]["notes"] += "；头部个人备注"
    updated = regenerate_with_size(current, 9, 24)
    assert part(updated, "头部") == part(current, "头部")
    assert part(updated, "身体") != part(current, "身体")
    assert len(part(updated, "手臂")["rounds"]) != 9
    assert "保留手改第九圈" not in str(part(updated, "手臂"))
    require_valid_pattern(updated["params"])


def test_unchanged_size_keeps_all_parts_and_completed_work():
    current = authored()
    updated = regenerate_with_size(current, 9, 18)
    assert updated["params"]["parts"] == current["params"]["parts"]
    progress = {identity:True for identity, _, _ in progress_entries(current, "result")}
    assert retained_progress(current, updated, "result", progress) == progress


def test_gauge_change_still_rebuilds_all_authored_parts():
    current = authored()
    updated = regenerate_with_gauge(current, 20, 24)
    assert "保留手改第九圈" not in str(updated["params"])
    assert updated["params"]["gauge"] == {"stitches_per_10cm":20, "rows_per_10cm":24}
    require_valid_pattern(updated["params"])


def test_implicit_head_sizing_dependency_recalculates_legacy_limbs():
    current = _mock_result("legacy-fallback")
    current["structure"] = {"parts":[
        {"name":"头部", "shape":"sphere", "diameter_cm":9},
        {"name":"手臂", "shape":"cylinder", "length_cm":3},
    ]}
    current["params"] = CrochetParamsGenerator.generate_params(
        ImageAnalysis(**current["analysis"]), current["structure"])
    part(current, "手臂")["rounds"][-1]["notes"] += "；旧手改内容"
    assert max(r["stitches"] for r in part(current, "手臂")["rounds"]) == 12
    updated = regenerate_with_size(current, 12, 18)
    # The legacy arm has no explicit diameter: its circumference follows the head.
    assert max(r["stitches"] for r in part(updated, "手臂")["rounds"]) == 18
    assert "旧手改内容" not in str(part(updated, "手臂"))
    require_valid_pattern(updated["params"])


def test_preserved_rounds_drive_materials_exports_and_backup_restoration():
    current = edit_yarn(authored(), {"ball_weight_g":50,"ball_length_m":125,
                                   "swatch_weight_g":2,"swatch_stitches":10,"swatch_rows":10,
                                   "waste_percent":10})
    updated = change(current, "头部", diameter_cm=12)
    stitches = sum(sum(r["stitches"] for r in p["rounds"]) * p["quantity"]
                   for p in updated["params"]["parts"])
    assert updated["params"]["total_stitches"] == stitches
    # Measured 2g/100 stitches plus 10% waste, independent of material implementation.
    assert updated["params"]["material_summary"]["grams"] == pytest.approx(stitches * .022, abs=.02)
    assert "保留手改第九圈" in export_markdown(updated["params"], result=updated)
    restored = import_backup(PatternResult.from_result(updated).to_backup(), "restored")
    assert part(restored, "手臂") == part(updated, "手臂")
    again = change(restored, "头部", diameter_cm=15)
    assert part(again, "手臂") == part(updated, "手臂")
    assert max(r["stitches"] for r in part(again, "头部")["rounds"]) == 60


def test_pdf_receives_the_preserved_ninth_round(monkeypatch):
    platypus = pytest.importorskip("reportlab.platypus")
    from app.utils.pdf_export import export_pdf

    cells = []
    original = platypus.Table
    def table(data, *args, **kwargs):
        cells.extend(cell.getPlainText() if hasattr(cell, "getPlainText") else str(cell)
                     for row in data for cell in row)
        return original(data, *args, **kwargs)
    monkeypatch.setattr(platypus, "Table", table)
    updated = change(authored(), "头部", diameter_cm=12)
    pdf = export_pdf(updated["params"], result=updated)
    assert pdf.startswith(b"%PDF-")
    assert any("保留手改第九圈" in text for text in cells)


@pytest.mark.parametrize("one_piece", [False, True])
def test_attached_skirt_references_are_recomputed_while_arms_are_retained(one_piece):
    current = authored(joined_result(one_piece=one_piece))
    current = move_skirt_join(current, waist_rows(current["params"])[0]["row"])
    updated = change(current, "身体", height_cm=8, diameter_cm=7)
    _check(updated)
    assert part(updated, "手臂") == part(current, "手臂")
    assert updated["params"]["skirt_waist_position"] == current["params"]["skirt_waist_position"]
    target = "头身（一体）" if one_piece else "身体"
    assert part(updated, target) != part(current, target)
    assert part(updated, "裙子")["rounds"][0]["stitches"] != part(current, "裙子")["rounds"][0]["stitches"]


def test_onepiece_head_edit_rebuilds_merged_construction_but_keeps_arms():
    current = authored(joined_result(one_piece=True))
    updated = change(current, "头部", diameter_cm=12)
    _check(updated)
    assert part(updated, "头身（一体）") != part(current, "头身（一体）")
    assert part(updated, "头身（一体）")["head_diameter_cm"] == 12
    assert part(updated, "手臂") == part(current, "手臂")


@pytest.mark.parametrize("one_piece", [False, True])
@pytest.mark.parametrize("where", ["middle", "last"])
def test_unpin_then_resize_uses_new_actual_join_and_keeps_unrelated_arms(one_piece, where):
    current = authored(profile_result(one_piece))
    choices = waist_rows(current["params"])
    index = len(choices) // 2 if where == "middle" else -1
    current = move_skirt_join(current, choices[index]["row"])
    current = unpin_skirt_waist(current)
    height = next(p["height_cm"] for p in current["structure"]["parts"] if p["name"] == "身体")
    updated = change(current, "身体", height_cm=height + 3)
    _check(updated)
    assert "skirt_waist_position" not in updated["params"]
    assert part(updated, "手臂") == part(current, "手臂")


def test_quantity_color_and_deletion_are_still_authoritative():
    current = authored()
    structure = deepcopy(current["structure"])
    head = next(p for p in structure["parts"] if p["name"] == "头部")
    head["color"] = "蓝色"
    arm = next(p for p in structure["parts"] if p["name"] == "手臂")
    arm["count"] = 1
    arm["instances"] = arm["instances"][:1]
    updated = regenerate_with_structure(current, structure)
    assert part(updated, "手臂")["quantity"] == 1
    assert len(part(updated, "手臂")["rounds"]) == 8
    assert all(r["color"] == "蓝色" for r in part(updated, "头部")["rounds"])
    # Removing a graph leaf must not reinsert it from preserved params.
    structure["parts"] = [p for p in structure["parts"] if p["name"] != "手臂"]
    updated = regenerate_with_structure(current, structure)
    assert not any(p["name"] == "手臂" for p in updated["params"]["parts"])
    require_valid_pattern(updated["params"])


def test_unreproducible_legacy_template_keeps_full_regeneration_fallback(monkeypatch):
    current = authored()
    original = CrochetParamsGenerator.generate_params
    def generate(analysis, structure, **kwargs):
        if next(p for p in structure["parts"] if p["name"] == "头部")["diameter_cm"] == 9:
            raise PatternGenerationError("legacy template unavailable")
        return original(analysis, structure, **kwargs)
    monkeypatch.setattr(CrochetParamsGenerator, "generate_params", generate)
    updated = change(current, "头部", diameter_cm=12)
    assert len(part(updated, "手臂")["rounds"]) == 8
    require_valid_pattern(updated["params"])


def test_invalid_preserved_instructions_reject_candidate_without_mutating_current():
    current = authored()
    part(current, "手臂")["rounds"][-1]["notes"] = "7X"
    snapshot = deepcopy(current)
    with pytest.raises(ValueError, match="图解自检失败"):
        change(current, "头部", diameter_cm=12)
    assert current == snapshot


def test_preview_apply_undo_redo_and_project_save_keep_unrelated_work():
    current = authored()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = current
    at.run()
    at.checkbox(key="chk_selective_手臂_8").check().run()
    at.checkbox(key="chk_selective_手臂_copy2_8").check().run()
    at.checkbox(key="chk_selective_头部_0").check().run()
    at.text_area(key="project_notes_selective").input("保留两条手臂的完成进度").run()
    at.number_input(key="edit_selective_part0_diameter_cm").set_value(12)
    next(b for b in at.button if b.label == "预览部件修改影响").click().run()
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
        assert part(saved, "手臂") == part(current, "手臂")
        assert at.checkbox(key=f"chk_{rid}_手臂_8").value
        assert at.checkbox(key=f"chk_{rid}_手臂_copy2_8").value
        assert at.checkbox(key=f"chk_{rid}_头部_0").value == (action == "undo")
        assert at.text_area(key=f"project_notes_{rid}").value == "保留两条手臂的完成进度"
    from app.ui.progress_state import capture_progress
    progress = capture_progress(saved, "result", at.session_state)
    project = project_backup(saved, progress, "保留两条手臂的完成进度")
    restored = import_backup(json.loads(json.dumps(project)), "new-session")
    assert read_project_state(project, restored) == (progress, "保留两条手臂的完成进度")
