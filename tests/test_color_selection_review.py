"""Regression checks for color edits across construction and export boundaries."""

from copy import deepcopy

import pytest

from app.schemas import PatternResult
from app.services.color_selection import (
    MODE_INHERIT,
    MODE_KEEP_STRIPES,
    MODE_UNIFORM,
    apply_color_change,
    color_change_preview,
    color_origin_of,
)
from app.services.progress_state import color_only_change, progress_entries, retained_progress
from app.services.result_logic import (
    import_backup,
    rebuild_params,
    regenerate_with_gauge,
    regenerate_with_size,
    regenerate_with_structure,
)
from app.ui.pattern_editor import edit_rounds, edit_yarn
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report
from app.utils.project import project_backup, read_project_state
from tests.test_part_color_selection import _onepiece_result, _part, _result
from tests.test_progress_continuity import _chain


def _instance(result, color="蓝色", index=0):
    return apply_color_change(result, part_name="手臂", color=color,
                              instance_index=index, mode=MODE_UNIFORM)


def test_keep_mode_preserves_even_explicit_colors_matching_the_old_base():
    result = _result()
    part = _part(result, "身体")
    part["rounds"][0]["color"] = part["color"]  # Could be a previous manual choice.
    part["rounds"][2]["color"] = "红色"
    preview = color_change_preview(result, part_name="身体", color="蓝色", mode=MODE_KEEP_STRIPES)
    updated = apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_KEEP_STRIPES)
    body = _part(updated, "身体")
    assert body["color"] == "蓝色"
    assert body["rounds"][0]["color"] == "body"
    assert body["rounds"][1]["color"] is None
    assert body["rounds"][2]["color"] == "红色"
    assert {entry["圈号"] for entry in preview["kept"]} == {1, 3}
    assert preview["affected"][0]["旧色"] == "body"


def test_uniform_part_recolour_updates_preexisting_per_copy_overrides():
    result = _instance(_result())
    preview = color_change_preview(result, part_name="手臂", color="草绿色", mode=MODE_UNIFORM)
    first = next(row for row in preview["affected"] if row["实体"] == 1)
    second = next(row for row in preview["affected"] if row["实体"] == 2)
    assert first["旧色"] == "蓝色" and second["旧色"] == "skin"
    updated = apply_color_change(result, part_name="手臂", color="草绿色", mode=MODE_UNIFORM)
    assert "instance_colors" not in _part(updated, "手臂")
    assert "instance_color_ids" not in _part(updated, "手臂")
    assert "COLOR: #0078d7" not in export_parade_report(updated).text


def test_preview_shows_ball_counts_for_new_and_removed_colors():
    result = edit_yarn(_result(), {"ball_weight_g": 50, "ball_length_m": 120})
    preview = color_change_preview(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    new_color = next(row for row in preview["materials"] if row["颜色"] == "蓝色")
    assert new_color["团数"].startswith("0 → ") and "未提供" not in new_color["团数"]


@pytest.mark.parametrize("change", ["size", "gauge"])
def test_geometry_regeneration_preserves_manual_part_and_copy_colors(change):
    result = apply_color_change(_result(), part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    result = _instance(result, "红色")
    updated = (regenerate_with_size(result, 10, 20) if change == "size"
               else regenerate_with_gauge(result, 16, 20))
    assert _part(updated, "身体")["color"] == "蓝色"
    assert _part(updated, "身体")["color_origin"] == "manual"
    assert {row.get("color") or "蓝色" for row in _part(updated, "身体")["rounds"]} == {"蓝色"}
    assert _part(updated, "手臂")["instance_colors"] == ["红色", None]
    assert _part(updated, "手臂")["instance_color_ids"] == ["arms_left", "arms_right"]


def test_resize_refuses_to_guess_how_to_remap_manual_stripes():
    result = _result()
    _part(result, "身体")["rounds"][2]["color"] = "红色"
    result = apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_KEEP_STRIPES)
    original = deepcopy(result)
    with pytest.raises(ValueError, match="无法安全对应原有逐圈配色"):
        regenerate_with_size(result, 10, 20)
    assert result == original


def test_reordering_graph_instances_preserves_color_identity_and_project_progress():
    result = _instance(_result())
    structure = deepcopy(result["structure"])
    arm = next(part for part in structure["parts"] if part["name"] == "手臂")
    arm["instances"].reverse()
    updated = regenerate_with_structure(result, structure)
    assert _part(updated, "手臂")["instance_color_ids"] == ["arms_right", "arms_left"]
    assert _part(updated, "手臂")["instance_colors"] == [None, "蓝色"]
    progress = {identity: True for identity, _, _ in progress_entries(updated, "result")}
    saved = project_backup(updated, progress, "备注")
    restored = import_backup(saved, "restored")
    assert _part(restored, "手臂")["instance_color_ids"] == ["arms_right", "arms_left"]
    assert read_project_state(saved, restored) == (progress, "备注")


@pytest.mark.parametrize("carrier", ["project", "share"])
@pytest.mark.parametrize("problem", ["order", "missing"])
def test_cannot_export_misaligned_copy_colors_as_a_recoverable_pattern(carrier, problem):
    from app.utils.share import encode_result

    result = _instance(_result())
    part = _part(result, "手臂")
    if problem == "order":
        part["instance_color_ids"].reverse()
    else:
        part["instance_color_ids"][0] = "missing_copy"
    original = deepcopy(result)
    with pytest.raises(ValueError, match="手臂.*逐份|手臂.*实体"):
        if carrier == "project":
            project_backup(result, {}, "保持备注")
        else:
            encode_result(result)
    assert result == original


@pytest.mark.parametrize("operation", ["colour", "rounds", "resize"])
def test_other_edits_do_not_silently_rebind_an_existing_misaligned_copy(operation):
    result = _instance(_result())
    _part(result, "手臂")["instance_color_ids"].reverse()
    original = deepcopy(result)
    with pytest.raises(ValueError, match="手臂.*逐份颜色"):
        if operation == "colour":
            apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
        elif operation == "rounds":
            index = next(i for i, part in enumerate(result["params"]["parts"]) if part["name"] == "身体")
            edit_rounds(result, index, deepcopy(_part(result, "身体")["rounds"]))
        else:
            regenerate_with_size(result, 10, 20)
    assert result == original


def test_removing_an_independently_colored_copy_requires_clearing_its_color_first():
    result = _instance(_result(), index=1)
    structure = deepcopy(result["structure"])
    arm = next(part for part in structure["parts"] if part["name"] == "手臂")
    arm["count"] = 1
    arm["instances"] = arm["instances"][:1]
    with pytest.raises(ValueError, match="移除带独立颜色的实体"):
        regenerate_with_structure(result, structure)
    cleared = apply_color_change(result, part_name="手臂", mode=MODE_INHERIT, instance_index=1)
    assert _part(regenerate_with_structure(cleared, structure), "手臂")["quantity"] == 1


def test_single_copy_can_return_to_shared_round_colors():
    striped = _result()
    _part(striped, "手臂")["rounds"][1]["color"] = "红色"
    result = _instance(striped)
    preview = color_change_preview(result, part_name="手臂", mode=MODE_INHERIT, instance_index=0)
    assert preview["affected"][0]["旧色"] == "蓝色"
    assert preview["affected"][0]["新色"] == "skin"
    assert preview["affected"][1]["新色"] == "红色"
    assert "沿用逐圈配色" in export_markdown(result["params"], result=result)
    updated = apply_color_change(result, part_name="手臂", mode=MODE_INHERIT, instance_index=0)
    assert "instance_colors" not in _part(updated, "手臂")
    assert "instance_color_ids" not in _part(updated, "手臂")


def test_unstable_legacy_copy_identity_cannot_be_silently_assigned_a_color():
    result = _result()
    result["structure"] = {"parts": []}
    with pytest.raises(ValueError, match="缺少稳定的实体身份"):
        _instance(result)


def test_legacy_color_origin_is_not_guessed():
    part = _part(_result(), "身体")
    part["color"] = "人工选过的颜色"
    assert color_origin_of(part) == "unrecorded"


@pytest.mark.parametrize("reserved", ["skin", "body"])
def test_reserved_placeholders_cannot_be_chosen_as_real_yarn_colors(reserved):
    with pytest.raises(ValueError, match="待选占位值"):
        apply_color_change(_result(), part_name="身体", color=reserved, mode=MODE_UNIFORM)


def test_one_piece_split_does_not_claim_monochrome():
    result = apply_color_change(_onepiece_result(), part_name="头身（一体）",
                                head_color="浅肤色", body_color="蓝色")
    assert "配色为整段单色" not in (_part(result, "头身（一体）").get("notes") or "")


@pytest.mark.parametrize("change", ["size", "gauge"])
def test_one_piece_section_colors_follow_the_new_neck_boundary(change):
    from app.services.color_selection import one_piece_neck_index

    result = apply_color_change(_onepiece_result(), part_name="头身（一体）",
                                head_color="浅肤色", body_color="蓝色")
    updated = (regenerate_with_size(result, 10, 20) if change == "size"
               else regenerate_with_gauge(result, 16, 20))
    part = _part(updated, "头身（一体）")
    neck = one_piece_neck_index(part)
    assert neck is not None and part["color_section_mode"] == "head_body"
    assert {row["color"] for row in part["rounds"][:neck + 1]} == {"浅肤色"}
    assert {row["color"] for row in part["rounds"][neck + 1:]} == {"蓝色"}
    assert "配色为整段单色" not in (part.get("notes") or "")


def test_unrepresentable_custom_color_is_not_claimed_as_complete_parade_export():
    result = _instance(_result(), "自定义测试色")
    report = export_parade_report(result)
    assert not report.complete
    assert any("自定义测试色" in failure and "已跳过" in failure for failure in report.failures)
    assert report.exported_parts < report.requested_parts


def test_unrepresentable_color_is_reported_when_no_copy_can_be_exported():
    result = _result()
    result["params"]["parts"] = [_part(result, "身体")]
    result = apply_color_change(result, part_name="身体", color="自定义测试色", mode=MODE_UNIFORM)
    with pytest.raises(ValueError, match="自定义测试色.*已跳过"):
        export_parade_report(result)


def test_untrusted_auto_fragment_cannot_hide_a_construction_change():
    result = _result()
    updated = deepcopy(result)
    row = _part(updated, "身体")["rounds"][1]
    row["notes"] += "；改挑后半针"
    row["auto_color_note"] = "改挑后半针"
    row["color"] = "蓝色"
    assert not color_only_change(result, updated)
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}
    assert retained_progress(result, updated, "result", progress) != progress


@pytest.mark.parametrize("operation", ["rebuild", "recolour", "import"])
def test_untrusted_auto_markers_do_not_erase_maker_notes(operation):
    result = _result()
    part = _part(result, "身体")
    part["notes"] = "手缝纽扣"
    part["auto_color_summary"] = "手缝纽扣"
    row = part["rounds"][1]
    row["notes"] += "；保留长线尾"
    row["auto_color_note"] = "保留长线尾"
    original = deepcopy(result)

    if operation == "rebuild":
        updated = deepcopy(result)
        updated["params"] = rebuild_params(result["params"])
    elif operation == "recolour":
        updated = apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    else:
        updated = import_backup(PatternResult.from_result(result).to_backup(), "restored")

    assert _part(updated, "身体")["notes"] == "手缝纽扣"
    assert "保留长线尾" in _part(updated, "身体")["rounds"][1]["notes"]
    assert result == original


def test_untrusted_part_summary_cannot_hide_a_part_wide_instruction_change():
    result = _result()
    part = _part(result, "身体")
    part["notes"] = part["auto_color_summary"] = "手缝纽扣"
    updated = deepcopy(result)
    changed = _part(updated, "身体")
    changed["notes"] = changed["auto_color_summary"] = "必须缝上扣子"
    progress = {identity: True for identity, _, p in progress_entries(result, "result")
                if p["name"] == "身体"}

    assert not color_only_change(result, updated)
    assert not retained_progress(result, updated, "result", progress)


@pytest.mark.parametrize("marker_kind", ["summary", "round"])
@pytest.mark.parametrize("operation", ["rebuild", "recolour", "import", "project"])
def test_generated_looking_untrusted_markers_never_erase_instructions(marker_kind, operation):
    result = _result()
    part = _part(result, "身体")
    if marker_kind == "summary":
        marker = " 配色（按钩织圈序，自下而上）：R1–R15 body。手缝纽扣。"
        part["notes"] = part["auto_color_summary"] = marker
    else:
        marker = "换线：保留长线尾（前一针最后一次挂线改用新色；螺旋圈仍可能出现台阶）"
        part["rounds"][1]["notes"] = marker
        part["rounds"][1]["auto_color_note"] = marker
    original = deepcopy(result)

    with pytest.raises(ValueError, match="身体.*自动配色说明"):
        if operation == "rebuild":
            rebuild_params(result["params"])
        elif operation == "recolour":
            apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
        elif operation == "import":
            import_backup(PatternResult.from_result(result).to_backup(), "restored")
        else:
            progress = {identity: True for identity, _, p in progress_entries(result, "result")
                        if p["name"] == "身体"}
            project = project_backup(result, progress, "制作笔记")
            import_backup(project, "restored")
    assert result == original


def test_verified_previous_markers_refresh_after_editing_a_round_color():
    result = _result()
    _part(result, "身体")["rounds"][2]["color"] = "红色"
    result = apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_KEEP_STRIPES)
    index = next(i for i, part in enumerate(result["params"]["parts"]) if part["name"] == "身体")
    original = _part(result, "身体")
    old_summary = original["auto_color_summary"]
    old_transition = original["rounds"][2]["auto_color_note"]
    rounds = deepcopy(original["rounds"])
    rounds[2]["color"] = "绿色"
    updated = edit_rounds(result, index, rounds)
    body = _part(updated, "身体")

    assert old_summary not in body["notes"]
    assert "绿色" in body["auto_color_summary"]
    assert old_transition not in body["rounds"][2]["notes"]
    assert "换线：绿色" in body["rounds"][2]["auto_color_note"]
    assert color_only_change(result, updated)


@pytest.mark.parametrize("marker_kind", ["summary", "round"])
def test_color_edit_cannot_reclassify_an_old_manual_note_as_generated(marker_kind):
    from app.models.color_design import _expected_color_texts

    result = _result()
    body = _part(result, "身体")
    index = next(i for i, part in enumerate(result["params"]["parts"]) if part["name"] == "身体")
    candidate = deepcopy(body)
    candidate["rounds"][2]["color"] = "红色"
    summary, transitions = _expected_color_texts(candidate)
    if marker_kind == "summary":
        body["notes"] = body["auto_color_summary"] = summary
    else:
        row = body["rounds"][2]
        row["notes"] = row["auto_color_note"] = transitions[row["row"]]
    original = deepcopy(result)
    rounds = deepcopy(body["rounds"])
    rounds[2]["color"] = "红色"

    with pytest.raises(ValueError, match="身体.*自动配色说明"):
        edit_rounds(result, index, rounds)
    assert result == original


@pytest.mark.parametrize("legacy", [False, True])
def test_repeated_generated_phrases_preserve_the_extra_maker_copy(legacy):
    result = _result()
    _part(result, "身体")["rounds"][1]["color"] = "红色"
    result["params"] = rebuild_params(result["params"])
    part = _part(result, "身体")
    row = part["rounds"][1]
    transition, summary = row["auto_color_note"], part["auto_color_summary"]
    row["notes"] += "；" + transition
    part["notes"] = (part["notes"] or "") + summary
    if legacy:
        row.pop("auto_color_note")
        part.pop("auto_color_summary")

    result["params"] = rebuild_params(result["params"])
    result["params"] = rebuild_params(result["params"])
    updated = apply_color_change(result, part_name="身体", color="蓝色", mode=MODE_UNIFORM)
    assert _part(updated, "身体")["notes"].count(summary) == 1
    assert _part(updated, "身体")["rounds"][1]["notes"].count(transition) == 1


def test_generated_fragments_support_custom_color_names_with_punctuation():
    result = _result()
    _part(result, "身体")["rounds"][2]["color"] = "蓝；绿"
    striped = apply_color_change(result, part_name="身体", color="浅。粉（嫩）",
                                 mode=MODE_KEEP_STRIPES)
    part = _part(striped, "身体")
    summary = part["auto_color_summary"]
    assert part["notes"].count(summary) == 1
    transitions = [(index, row["auto_color_note"]) for index, row in enumerate(part["rounds"])
                   if row["auto_color_note"]]
    assert transitions
    assert all(part["rounds"][index]["notes"].count(note) == 1 for index, note in transitions)

    updated = apply_color_change(striped, part_name="身体", color="白色", mode=MODE_UNIFORM)
    body = _part(updated, "身体")
    assert summary not in (body["notes"] or "")
    assert all(note not in (body["rounds"][index]["notes"] or "") for index, note in transitions)
    progress = {identity: True for identity, _, _ in progress_entries(striped, "result")}
    assert color_only_change(striped, updated)
    assert retained_progress(striped, updated, "result", progress) == progress


@pytest.mark.parametrize("empty_note", [None, ""])
def test_adding_a_color_transition_to_an_empty_note_preserves_progress(empty_note):
    result = _result()
    _part(result, "身体")["rounds"][2]["notes"] = empty_note
    updated = deepcopy(result)
    _part(updated, "身体")["rounds"][2]["color"] = "红色"
    updated["params"] = rebuild_params(updated["params"])
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}

    assert "换线：红色" in _part(updated, "身体")["rounds"][2]["notes"]
    assert color_only_change(result, updated)
    assert retained_progress(result, updated, "result", progress) == progress


def test_joined_part_copy_color_keeps_existing_conservative_progress_rule():
    result = _chain((0, 1, 2))
    updated = deepcopy(result)
    _part(updated, "base")["instance_colors"] = ["红色"]
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}
    kept = retained_progress(result, updated, "result", progress)
    assert all('"independent"' in identity for identity in kept)
    assert kept


def test_new_color_assignments_use_new_pattern_version():
    result = _instance(_result())
    data = project_backup(result, {})
    assert data["schema_version"] == "2"
    assert _part(import_backup(data, "restored"), "手臂")["instance_colors"] == ["蓝色", None]


def test_legacy_custom_round_color_is_not_silently_exported():
    result = _result()
    body = _part(result, "身体")
    body["rounds"][1]["color"] = "旧图解自定义色"
    assert "color_origin" not in body
    report = export_parade_report(result)
    assert not report.complete
    assert any("旧图解自定义色" in failure and "颜色未忠实表达" in failure
               for failure in report.failures)


def test_known_copy_override_can_export_when_other_copy_has_unknown_round_color():
    result = _result()
    _part(result, "手臂")["rounds"][1]["color"] = "旧图解自定义色"
    result = _instance(result, "蓝色")
    report = export_parade_report(result)
    assert not report.complete
    assert any("手臂 第 2 份" in failure and "旧图解自定义色" in failure
               for failure in report.failures)
    assert report.exported_parts == report.requested_parts - 1
    assert "COLOR: #0078d7" in report.text
