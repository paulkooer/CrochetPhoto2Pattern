"""部件级选色 V1 的行为测试（规格 docs/part-color-selection.md）。

覆盖：整件两种操作、实体级选色、一体件分段、材料按份拆分、导出一致性、
进度规则、兼容与校验、照片证据不被改写，以及结果页面板本身。
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, cast

import pytest
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import ShapingStyle
from app.models.image_parser import ImageParser
from app.models.materials import yarn_requirements
from app.models.parts import _part_instance_colors
from app.models.structure_designer import StructureDesigner
from app.schemas import PatternResult, ResultData
from app.services.color_selection import (
    MODE_KEEP_STRIPES,
    MODE_UNIFORM,
    apply_color_change,
    color_change_preview,
    color_origin_of,
    instance_color_rows,
    instance_labels,
    one_piece_neck_index,
)
from app.services.progress_state import progress_entries, retained_progress
from app.services.result_logic import import_backup, rebuild_params
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report, lint_parade_dsl
from app.utils.project import project_backup, read_project_state
from tests.test_app_smoke import _mock_result

RID = "color-v1"

_COLOR_UI = '''
import streamlit as st
from app.ui.color_editor import render_color_editor
from app.ui.edit_history import render_edit_preview
render_color_editor(st.session_state.result, "result")
render_edit_preview("result", st.session_state.result)
'''

_FULL_UI = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
'''


def _result() -> ResultData:
    return cast("ResultData", _mock_result(RID))


def _part(result: Any, name: str) -> dict[str, Any]:
    return next(p for p in result["params"]["parts"] if p["name"] == name)


def _all_progress(result: ResultData) -> dict[str, bool]:
    return {identity: True for identity, _key, _ in progress_entries(result, "result")}


def _skin_stitches(result: ResultData) -> int:
    rows = {row["color"]: row for row in yarn_requirements(result["params"]["parts"])[0]}
    return rows.get("肤色（待选色）", {}).get("stitches", 0)


def _striped(result: ResultData) -> ResultData:
    """身体的第 3 圈是一条与部件基础色不同的条纹。"""
    striped = deepcopy(result)
    _part(striped, "身体")["rounds"][2]["color"] = "红色"
    return striped


# ── 整件选色：两种操作 ───────────────────────────────────────────────────

def test_keep_stripes_changes_the_base_and_preserves_the_stripe_round():
    result = _striped(_result())
    updated = apply_color_change(result, part_name="身体", color="蓝色",
                                 mode=MODE_KEEP_STRIPES)
    part = _part(updated, "身体")
    assert part["rounds"][2]["color"] == "红色"          # 条纹保留
    assert {rd.get("color") or part["color"] for rd in part["rounds"][:2]} == {"蓝色"}
    assert part["color"] == "蓝色"
    assert part["color_origin"] == "manual"
    assert all(rd["stitches"] == old["stitches"]
               for rd, old in zip(part["rounds"], _part(result, "身体")["rounds"], strict=True))


def test_uniform_recolour_overwrites_stripes_and_the_preview_lists_every_round():
    result = _striped(_result())
    preview = color_change_preview(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    assert preview["kept"] == []
    assert {row["圈号"] for row in preview["affected"]} == {
        rd["row"] for rd in _part(result, "身体")["rounds"]}
    updated = apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    assert {rd["color"] for rd in _part(updated, "身体")["rounds"]} == {"蓝色"}


def test_keep_stripes_preview_lists_what_it_will_not_touch():
    result = _striped(_result())
    preview = color_change_preview(result, part_name="身体", color="蓝色",
                                   mode=MODE_KEEP_STRIPES)
    assert preview["kept"] == [{"圈号": 3, "颜色": "红色"}]
    assert 3 not in {row["圈号"] for row in preview["affected"]}
    assert preview["changed"] is True


def test_preview_is_read_only_and_reports_material_deltas():
    result = _striped(_result())
    before = deepcopy(result)
    preview = color_change_preview(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    assert result == before
    assert preview["materials"]
    colors = {row["颜色"] for row in preview["materials"]}
    assert "蓝色" in colors and "主体色（待选色）" in colors


@pytest.mark.parametrize("mode", [MODE_KEEP_STRIPES, MODE_UNIFORM])
def test_invalid_colour_and_mode_are_rejected(mode):
    result = _result()
    with pytest.raises(ValueError, match="颜色名称不能为空"):
        apply_color_change(result, part_name="身体", color="   ", mode=mode)
    with pytest.raises(ValueError, match="请选择操作"):
        apply_color_change(result, part_name="身体", color="蓝色", mode="typo")
    with pytest.raises(ValueError, match="没有部件"):
        apply_color_change(result, part_name="尾巴", color="蓝色", mode=mode)
    with pytest.raises(ValueError, match="40 个字符"):
        apply_color_change(result, part_name="身体", color="蓝" * 41, mode=mode)


def test_photo_evidence_is_never_rewritten_by_a_manual_colour():
    result = _result()
    result["vision_meta"]["color_observation"] = {"keep": True}
    result["analysis"]["recommended_colors"] = ["蓝色", "红色"]
    result["color_bands"] = [{"start": 0.0, "end": 1.0, "color": "蓝色"}]
    updated = apply_color_change(result, part_name="身体", color="草绿色", mode=MODE_UNIFORM)
    assert updated["vision_meta"] == result["vision_meta"]
    assert updated["analysis"]["recommended_colors"] == ["蓝色", "红色"]
    assert updated["color_bands"] == result["color_bands"]


def test_a_manual_choice_is_not_written_into_generated_photo_prose():
    result = _result()
    photo_note = " 主色按照片语义校正为 蓝色。"
    _part(result, "身体")["notes"] = "先填充再继续。" + photo_note
    updated = apply_color_change(result, part_name="身体", color="草绿色", mode=MODE_UNIFORM)
    assert photo_note in _part(updated, "身体")["notes"]
    assert "先填充再继续。" in _part(updated, "身体")["notes"]


def test_colour_edits_never_change_stitches_or_totals():
    result = _result()
    updated = apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    assert updated["params"]["total_stitches"] == result["params"]["total_stitches"]
    assert (updated["params"]["material_summary"]["total_stitches"]
            == result["params"]["material_summary"]["total_stitches"])
    assert (updated["params"]["estimated_time_minutes"]
            == result["params"]["estimated_time_minutes"])


def test_custom_colour_names_survive_and_are_escaped_in_markdown():
    result = _result()
    updated = apply_color_change(result, part_name="身体", color="蓝|<b>绿</b>",
                                 mode=MODE_UNIFORM)
    markdown = export_markdown(updated["params"], result=updated)
    assert r"蓝\|&lt;b&gt;绿&lt;/b&gt;" in markdown


# ── 实体级选色 ───────────────────────────────────────────────────────────

def test_instance_colour_only_touches_the_selected_copy():
    result = _result()
    assert _part(result, "手臂").get("quantity") == 2
    updated = apply_color_change(result, part_name="手臂", color="蓝色",
                                 instance_index=0, mode=MODE_UNIFORM)
    part = _part(updated, "手臂")
    assert part["instance_colors"] == ["蓝色", None]
    # 部件基础色不变：改的是「第 1 份」，不是整件。
    assert part["color"] == _part(result, "手臂")["color"]
    assert "color_origin" not in part
    assert _part(result, "手臂").get("instance_colors") is None  # 原结果未被修改


def test_instance_colour_splits_material_usage_by_copy():
    result = _result()
    arm_stitches = sum(rd["stitches"] for rd in _part(result, "手臂")["rounds"])
    before_skin = _skin_stitches(result)
    updated = apply_color_change(result, part_name="手臂", color="蓝色", instance_index=0, mode=MODE_UNIFORM)
    rows = {row["color"]: row for row in yarn_requirements(updated["params"]["parts"])[0]}
    assert rows["蓝色"]["stitches"] == arm_stitches
    assert before_skin - rows["肤色（待选色）"]["stitches"] == arm_stitches


def test_materials_stay_complete_when_both_copies_are_recoloured_differently():
    result = _result()
    once = apply_color_change(result, part_name="手臂", color="蓝色", instance_index=0, mode=MODE_UNIFORM)
    updated = apply_color_change(once, part_name="手臂", color="红色", instance_index=1, mode=MODE_UNIFORM)
    part = _part(updated, "手臂")
    assert part["instance_colors"] == ["蓝色", "红色"]
    rows = {row["color"]: row for row in yarn_requirements(updated["params"]["parts"])[0]}
    arm_stitches = sum(rd["stitches"] for rd in part["rounds"])
    assert rows["蓝色"]["stitches"] == rows["红色"]["stitches"] == arm_stitches


def test_instance_colour_reaches_markdown_pdf_and_the_dsl():
    result = _result()
    updated = apply_color_change(result, part_name="手臂", color="蓝色", instance_index=0, mode=MODE_UNIFORM)
    markdown = export_markdown(updated["params"], result=updated)
    assert "逐份配色" in markdown
    assert "第 1 份" in markdown and "蓝色" in markdown
    assert "同针法部件" in markdown          # 不再声称两份相同
    assert "整份使用自己的颜色" in markdown   # 换线说明的适用范围被写清
    report = export_parade_report(updated)
    assert "COLOR: #0078d7" in report.text   # 蓝色
    assert lint_parade_dsl(report.text) == []


def test_instance_labels_follow_the_recorded_instance_ids():
    result = _result()
    assert instance_labels(result, "手臂") == ["第 1 份（arms_left）", "第 2 份（arms_right）"]


def test_instance_colour_rows_lists_only_overridden_copies():
    result = apply_color_change(_result(), part_name="手臂", color="蓝色",
                                instance_index=1, mode=MODE_UNIFORM)
    assert instance_color_rows(_part(result, "手臂")) == [(2, "蓝色")]


def test_wrong_length_instance_colours_are_rejected_at_the_rebuild_boundary():
    result = _result()
    params = deepcopy(result["params"])
    _part({"params": params}, "手臂")["instance_colors"] = ["蓝色"]
    with pytest.raises(ValueError, match="必须与部件数量"):
        rebuild_params(params)


def test_instance_selector_rejects_an_out_of_range_copy():
    with pytest.raises(ValueError, match="实体序号超出"):
        apply_color_change(_result(), part_name="头部", color="蓝色", instance_index=1, mode=MODE_UNIFORM)


# ── 一体头身分段选色 ─────────────────────────────────────────────────────

def _onepiece_result() -> ResultData:
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure, style=ShapingStyle("ladder", True, "ring", False))
    result = cast("ResultData", _mock_result("onepiece"))
    result["params"] = params
    result["structure"] = structure
    result["gauge"] = params.get("gauge")
    result["style"] = {"sphere_mode": "ladder", "one_piece": True,
                       "skirt_style": "ring", "ruffle_hem": False}
    return result


def test_one_piece_split_colours_the_recorded_head_and_body_sections():
    result = _onepiece_result()
    part = _part(result, "头身（一体）")
    neck = one_piece_neck_index(part)
    assert neck is not None, "生成的一体件应带唯一的颈部标记"
    updated = apply_color_change(result, part_name="头身（一体）",
                                 head_color="浅肤色", body_color="蓝色")
    rounds = _part(updated, "头身（一体）")["rounds"]
    assert {rd["color"] for rd in rounds[:neck + 1]} == {"浅肤色"}
    assert {rd["color"] for rd in rounds[neck + 1:]} == {"蓝色"}
    assert "color_origin" not in _part(result, "头身（一体）")


def test_one_piece_split_preview_names_the_boundary_round():
    result = _onepiece_result()
    part = _part(result, "头身（一体）")
    neck = one_piece_neck_index(part)
    preview = color_change_preview(result, part_name="头身（一体）",
                                   head_color="浅肤色", body_color="蓝色")
    assert preview["scope"] == "sections"
    assert preview["neck_row"] == part["rounds"][neck]["row"]
    assert preview["affected"]


@pytest.mark.parametrize("damage", ["no_marker", "two_markers", "marker_on_last_round"])
def test_one_piece_split_refuses_an_unreliable_boundary(damage):
    result = _onepiece_result()
    part = _part(result, "头身（一体）")
    part.pop("neck_row")  # Legacy patterns have only the prose marker.
    rounds = part["rounds"]
    marker = "此处为颈部"
    for rd in rounds:
        rd["notes"] = (rd.get("notes") or "").replace(f"；{marker}，不断线直接钩身体", "")
    if damage == "two_markers":
        rounds[3]["notes"] = f"{rounds[3]['notes']}；{marker}"
        rounds[6]["notes"] = f"{rounds[6]['notes']}；{marker}"
    elif damage == "marker_on_last_round":
        rounds[-1]["notes"] = f"{rounds[-1]['notes']}；{marker}"
    with pytest.raises(ValueError, match="无法确认一体件"):
        apply_color_change(result, part_name="头身（一体）",
                           head_color="浅肤色", body_color="蓝色")


# ── 进度规则 ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", [MODE_KEEP_STRIPES, MODE_UNIFORM])
def test_pure_colour_change_keeps_every_completed_round(mode):
    result = _striped(_result())
    progress = _all_progress(result)
    updated = apply_color_change(result, part_name="身体", color="蓝色", mode=mode)
    assert retained_progress(result, updated, "result", progress) == progress


def test_instance_colour_change_also_keeps_every_completed_round():
    result = _result()
    progress = _all_progress(result)
    updated = apply_color_change(result, part_name="手臂", color="蓝色", instance_index=0, mode=MODE_UNIFORM)
    assert retained_progress(result, updated, "result", progress) == progress


def test_colour_change_together_with_a_stitch_change_stays_conservative():
    result = _result()
    updated = deepcopy(result)
    part = _part(updated, "身体")
    # 真正的施工变化：针数与加针数都改，不是把数值写成原来的值。
    part["rounds"][2]["color"] = "蓝色"
    part["rounds"][2]["stitches"] += 6
    part["rounds"][2]["increase"] += 6
    progress = _all_progress(result)
    kept = retained_progress(result, updated, "result", progress)
    assert kept != progress
    assert all(json.loads(identity)[0] != "身体"
               or json.loads(identity)[2] <= part["rounds"][1]["row"]
               for identity in kept)


# ── 兼容与往返 ───────────────────────────────────────────────────────────

def _coloured() -> ResultData:
    once = apply_color_change(_result(), part_name="手臂", color="蓝色", instance_index=0, mode=MODE_UNIFORM)
    return apply_color_change(once, part_name="身体", color="草绿色", mode=MODE_UNIFORM)


def test_new_fields_survive_backup_share_history_and_project_round_trips():
    from app.utils.share import decode_result, encode_result

    result = _coloured()
    backup = PatternResult.from_result(result).to_backup()
    restored = import_backup(backup, "restored")
    arm = _part(restored, "手臂")
    assert arm["instance_colors"] == ["蓝色", None]
    assert _part(restored, "身体")["color_origin"] == "manual"

    shared = decode_result(encode_result(result))
    assert _part(shared, "手臂")["instance_colors"] == ["蓝色", None]

    project = project_backup(result, _all_progress(result), "配色备注")
    saved, notes = read_project_state(project, import_backup(project, "new-session"))
    assert notes == "配色备注"
    assert _part(import_backup(project, "again"), "手臂")["instance_colors"] == ["蓝色", None]
    assert saved


def test_legacy_patterns_without_the_new_fields_still_load():
    result = _result()
    for part in result["params"]["parts"]:
        part.pop("instance_colors", None)
        part.pop("color_origin", None)
    restored = import_backup(PatternResult.from_result(result).to_backup(), "legacy")
    for part in restored["params"]["parts"]:
        assert "instance_colors" not in part and "color_origin" not in part
        assert _part_instance_colors(part) is None


def test_colour_origin_does_not_guess_whether_legacy_colors_are_manual():
    assert color_origin_of(_part(_result(), "身体")) == "unrecorded"
    assert color_origin_of(_part(_coloured(), "身体")) == "manual"
    assert color_origin_of(_part(_coloured(), "手臂")) == "instance"
    assert color_origin_of({"color": "红色", "color_origin": "weird"}) == "unrecorded"


def test_all_copies_share_one_colour_again_after_a_whole_part_recolour():
    """明确选择统一换色时，既有逐份覆盖也会在预览之后被覆盖。"""
    result = apply_color_change(_result(), part_name="手臂", color="蓝色",
                                instance_index=0, mode=MODE_UNIFORM)
    updated = apply_color_change(result, part_name="手臂", color="草绿色", mode=MODE_UNIFORM)
    part = _part(updated, "手臂")
    assert "instance_colors" not in part
    assert {rd["color"] for rd in part["rounds"]} == {"草绿色"}
    assert _part_instance_colors(part) is None


# ── 结果页面板 ───────────────────────────────────────────────────────────

def test_advanced_json_aligns_copy_colors_before_preview_and_backup():
    result = apply_color_change(_result(), part_name="手臂", color="蓝色",
                                instance_index=0, mode=MODE_UNIFORM)
    corrected = deepcopy(result["params"])
    arm = next(part for part in corrected["parts"] if part["name"] == "手臂")
    arm["instance_color_ids"].reverse()
    at = AppTest.from_string(_FULL_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    at.button(key=f"json_open_{RID}").click().run()
    at.text_area(key=f"json_edit_{RID}").set_value(json.dumps(corrected, ensure_ascii=False)).run()
    at.button(key=f"edit_{RID}_json_preview").click().run()
    assert not at.exception
    candidate = at.session_state["workspace_result"]["pending_preview"]["candidate"]
    preview_arm = _part(candidate, "手臂")
    assert preview_arm["instance_color_ids"] == ["arms_left", "arms_right"]
    assert preview_arm["instance_colors"] == [None, "蓝色"]
    assert any("arms_right" in str(table.value) and "蓝色" in str(table.value) for table in at.table)
    assert "第 1 份 沿用逐圈配色；第 2 份 蓝色" in export_markdown(candidate["params"], result=candidate)

    at.button(key=f"edit_{RID}_preview_apply").click().run()
    assert not at.exception
    updated = at.session_state["result"]
    restored = import_backup(PatternResult.from_result(updated).to_backup(), "restored")
    assert _part(restored, "手臂")["instance_colors"] == _part(updated, "手臂")["instance_colors"]
    assert _part(restored, "手臂")["instance_color_ids"] == _part(updated, "手臂")["instance_color_ids"]
    progress = _all_progress(updated)
    project = project_backup(updated, progress, "逐份配色")
    project_result = import_backup(project, "project-restored")
    assert read_project_state(project, project_result) == (progress, "逐份配色")
    assert _part(project_result, "手臂")["instance_colors"] == [None, "蓝色"]


@pytest.mark.parametrize("preview", [True, False])
def test_advanced_json_rejects_a_color_bound_to_a_missing_copy_without_losing_work(preview):
    result = apply_color_change(_result(), part_name="手臂", color="蓝色",
                                instance_index=0, mode=MODE_UNIFORM)
    corrected = deepcopy(result["params"])
    arm = next(part for part in corrected["parts"] if part["name"] == "手臂")
    arm["instance_color_ids"][0] = "missing_copy"
    at = AppTest.from_string(_FULL_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    at.button(key=f"json_open_{RID}").click().run()
    at.checkbox(key=f"chk_{RID}_手臂_0").check().run()
    at.text_area(key=f"json_edit_{RID}").set_value(json.dumps(corrected, ensure_ascii=False)).run()
    key = f"edit_{RID}_json_preview" if preview else f"regen_{RID}"
    at.button(key=key).click().run()
    assert not at.exception
    assert any("移除带独立颜色的实体" in item.value for item in at.error)
    assert at.session_state["result"] == result
    assert at.checkbox(key=f"chk_{RID}_手臂_0").value
    assert at.session_state["workspace_result"]["pending_preview"] is None


def test_direct_json_apply_reports_that_copy_colors_were_aligned():
    result = apply_color_change(_result(), part_name="手臂", color="蓝色",
                                instance_index=0, mode=MODE_UNIFORM)
    corrected = deepcopy(result["params"])
    next(part for part in corrected["parts"] if part["name"] == "手臂")["instance_color_ids"].reverse()
    at = AppTest.from_string(_FULL_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    at.button(key=f"json_open_{RID}").click().run()
    at.text_area(key=f"json_edit_{RID}").set_value(json.dumps(corrected, ensure_ascii=False)).run()
    at.button(key=f"regen_{RID}").click().run()
    assert not at.exception
    assert _part(at.session_state["result"], "手臂")["instance_colors"] == [None, "蓝色"]
    assert any("按实体 ID 对齐逐份颜色" in item.value for item in at.success)
    assert any("已钩出的旧颜色不会因为图解改色而改变" in item.value for item in at.warning)
    rid = at.session_state["result"]["result_id"]
    at.button(key=f"edit_{rid}_undo").click().run()
    assert any("已钩出的旧颜色不会因为图解改色而改变" in item.value for item in at.warning)


def test_existing_misaligned_session_warns_and_can_be_repaired_without_losing_progress():
    result = apply_color_change(_result(), part_name="手臂", color="蓝色",
                                instance_index=0, mode=MODE_UNIFORM)
    _part(result, "手臂")["instance_color_ids"].reverse()
    original = deepcopy(result)
    at = AppTest.from_string(_FULL_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    assert any("逐份配色待修正" in item.value for item in at.warning)
    at.button(key=f"json_open_{RID}").click().run()
    assert any(button.label == "备份完整结果" for button in at.get("download_button"))
    at.checkbox(key=f"chk_{RID}_手臂_0").check().run()
    at.button(key=f"share_{RID}").click().run()
    assert any("分享链接生成失败" in item.value for item in at.error)
    at.button(key=f"project_save_{RID}").click().run()
    assert any("工程保存失败" in item.value for item in at.error)
    assert at.session_state["result"] == original
    assert at.checkbox(key=f"chk_{RID}_手臂_0").value

    at.button(key=f"edit_{RID}_json_preview").click().run()
    pending = at.session_state["workspace_result"]["pending_preview"]["candidate"]
    assert _part(pending, "手臂")["instance_colors"] == [None, "蓝色"]
    assert any("arms_right" in str(table.value) and "蓝色" in str(table.value) for table in at.table)
    at.button(key=f"edit_{RID}_preview_apply").click().run()
    assert not at.exception
    updated = at.session_state["result"]
    assert _part(updated, "手臂")["instance_colors"] == [None, "蓝色"]
    assert at.checkbox(key=f"chk_{updated['result_id']}_手臂_0").value


def test_advanced_json_color_edit_refreshes_verified_previous_notes():
    result = apply_color_change(_striped(_result()), part_name="身体", color="蓝色",
                                mode=MODE_KEEP_STRIPES)
    corrected = deepcopy(result["params"])
    body = next(part for part in corrected["parts"] if part["name"] == "身体")
    old_transition = body["rounds"][2]["auto_color_note"]
    body["rounds"][2]["color"] = "绿色"
    at = AppTest.from_string(_FULL_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    at.button(key=f"json_open_{RID}").click().run()
    at.text_area(key=f"json_edit_{RID}").set_value(json.dumps(corrected, ensure_ascii=False)).run()
    at.button(key=f"regen_{RID}").click().run()
    assert not at.exception
    updated = _part(at.session_state["result"], "身体")
    assert updated["rounds"][2]["color"] == "绿色"
    assert "换线：绿色" in updated["rounds"][2]["auto_color_note"]
    assert old_transition not in updated["rounds"][2]["notes"]


def test_colour_panel_renders_and_previews_without_touching_the_pattern():
    result = _result()
    at = AppTest.from_string(_COLOR_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    at.selectbox(key=f"edit_{RID}_color_part").set_value(1).run()
    assert not at.exception
    assert any("颜色来源未记录" in c.value for c in at.caption)
    at.radio(key=f"edit_{RID}_color1_mode").set_value(MODE_UNIFORM).run()
    at.button(key=f"edit_{RID}_color1_preview").click().run()
    assert not at.exception
    assert at.session_state["result"] == result
    pending = at.session_state["workspace_result"]["pending_preview"]
    assert pending is not None and pending["detail"]["affected"]
    assert any("受影响的圈次" in c.value for c in at.caption)
    assert any("旧颜色不会因为图解改色而改变" in w.value for w in at.warning)


def test_colour_panel_never_prefills_an_internal_placeholder_as_a_choice():
    """占位值 skin/body 表示"还没选色"，面板必须让用户选真实毛线色。"""
    from app.ui.color_editor import _YARN_NAMES
    from app.utils.color_labels import is_reserved_placeholder

    assert _YARN_NAMES and not any(is_reserved_placeholder(name) for name in _YARN_NAMES)
    at = AppTest.from_string(_COLOR_UI, default_timeout=30)
    at.session_state["result"] = _result()          # 头部 color == "skin"
    at.run()
    assert not at.exception
    assert at.selectbox(key=f"edit_{RID}_color0_pick").value == _YARN_NAMES[0]
    assert not [w for w in at.text_input if w.key == f"edit_{RID}_color0_pick_custom"]

    # 已有的自定义颜色名仍然沿用，并可在自定义输入框里继续改。
    custom = _result()
    _part(custom, "头部")["color"] = "外婆家的藏青"
    at_custom = AppTest.from_string(_COLOR_UI, default_timeout=30)
    at_custom.session_state["result"] = custom
    at_custom.run()
    assert not at_custom.exception
    typed = [w for w in at_custom.text_input if w.key == f"edit_{RID}_color0_custom"]
    assert typed and typed[0].value == "外婆家的藏青"


def test_colour_panel_cancel_keeps_the_pattern():
    result = _result()
    at = AppTest.from_string(_COLOR_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.button(key=f"edit_{RID}_color0_preview").click().run()
    at.button(key=f"edit_{RID}_preview_cancel").click().run()
    assert not at.exception
    assert at.session_state["result"] == result
    assert at.session_state["workspace_result"]["pending_preview"] is None


def test_colour_panel_applies_then_undo_and_redo_restore_the_previous_colour():
    result = _result()
    at = AppTest.from_string(_FULL_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    at.selectbox(key=f"edit_{RID}_color_part").set_value(1).run()
    at.selectbox(key=f"edit_{RID}_color1_pick").select("蓝色").run()
    assert not any(button.key == f"edit_{RID}_color1_apply" for button in at.button)
    at.button(key=f"edit_{RID}_color1_preview").click().run()
    at.button(key=f"edit_{RID}_preview_apply").click().run()
    assert not at.exception
    new_id = at.session_state["result"]["result_id"]
    assert new_id != RID
    assert _part(at.session_state["result"], "身体")["color"] == "蓝色"
    at.button(key=f"edit_{new_id}_undo").click().run()
    reverted = at.session_state["result"]
    assert _part(reverted, "身体")["color"] == _part(result, "身体")["color"]
    at.button(key=f"edit_{reverted['result_id']}_redo").click().run()
    assert _part(at.session_state["result"], "身体")["color"] == "蓝色"


def test_colour_panel_offers_per_instance_scope_only_for_multi_copy_parts():
    at = AppTest.from_string(_COLOR_UI, default_timeout=30)
    at.session_state["result"] = _result()
    at.run()
    assert at.radio(key=f"edit_{RID}_color0_scope").options == ["整个部件"]
    at.selectbox(key=f"edit_{RID}_color_part").set_value(2).run()
    assert at.radio(key=f"edit_{RID}_color2_scope").options == ["整个部件", "仅所选实体（整份统一换色）"]
    at.radio(key=f"edit_{RID}_color2_scope").set_value("仅所选实体（整份统一换色）").run()
    assert not at.exception
    assert any("实体顺序与逐圈进度记录一致" in c.value for c in at.caption)


def test_colour_panel_explains_when_legacy_copies_cannot_be_selected_individually():
    result = _result()
    result["structure"] = {"parts": []}
    at = AppTest.from_string(_COLOR_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.selectbox(key=f"edit_{RID}_color_part").set_value(2).run()
    assert not at.exception
    assert at.radio(key=f"edit_{RID}_color2_scope").options == ["整个部件"]
    assert any("缺少稳定的实体身份" in c.value and "整个部件选色" in c.value for c in at.caption)
    assert any("旧实体的对应关系仍需核对" in c.value for c in at.caption)
    at.selectbox(key=f"edit_{RID}_color2_pick").select("蓝色").run()
    at.button(key=f"edit_{RID}_color2_preview").click().run()
    assert not at.exception and not at.error
    assert at.session_state["workspace_result"]["pending_preview"] is not None


def test_colour_panel_explains_when_all_existing_round_colours_are_preserved():
    result = _result()
    body = _part(result, "身体")
    body["color"] = "红色"
    for rd in body["rounds"]:
        rd["color"] = "红色"  # Explicit colours equal to the old base still stay unchanged.
    at = AppTest.from_string(_COLOR_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.selectbox(key=f"edit_{RID}_color_part").set_value(1).run()
    at.selectbox(key=f"edit_{RID}_color1_pick").select("蓝色").run()
    at.button(key=f"edit_{RID}_color1_preview").click().run()
    assert not at.exception
    pending = at.session_state["workspace_result"]["pending_preview"]
    assert not pending["detail"]["affected"]
    assert len(pending["detail"]["kept"]) == len(body["rounds"])
    assert {row["颜色"] for row in pending["detail"]["kept"]} == {"红色"}
    assert any("圈色来源无法可靠区分" in c.value for c in at.caption)
    assert any("没有改变任何圈的实际颜色" in w.value for w in at.warning)
    at.button(key=f"edit_{RID}_preview_apply").click().run()
    updated = _part(at.session_state["result"], "身体")
    assert updated["color"] == "蓝色"
    assert {rd["color"] for rd in updated["rounds"]} == {"红色"}


def test_colour_panel_labels_the_one_piece_sections_and_their_boundary():
    result = _onepiece_result()
    result["result_id"] = RID
    at = AppTest.from_string(_COLOR_UI, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    index = [p["name"] for p in result["params"]["parts"]].index("头身（一体）")
    options = at.radio(key=f"edit_{RID}_color{index}_scope").options
    assert "头部段与身体段分别选色" in options
    at.radio(key=f"edit_{RID}_color{index}_scope").set_value("头部段与身体段分别选色").run()
    assert not at.exception
    assert any("颈部" in c.value for c in at.caption)
