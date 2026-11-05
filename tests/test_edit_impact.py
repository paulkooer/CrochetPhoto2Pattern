"""Keep only demonstrably unchanged work and review changes before applying."""
import json
from copy import deepcopy

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from streamlit.testing.v1 import AppTest

from app.services.progress_state import (
    has_color_change,
    progress_entries,
    progress_impact,
    reconcile_restored_progress,
    retained_progress,
)
from app.services.result_logic import import_backup
from app.utils.project import project_backup, read_project_state
from tests.progress_helpers import seed_progress
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
def test_changes_keep_only_the_exact_prefix_across_physical_copies(index):
    result = _flat()
    updated = deepcopy(result)
    arm = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")
    arm["rounds"][index]["notes"] = "6X；留线准备下一步"
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)
    assert kept == {identity: True for identity in progress
                    if json.loads(identity)[0] != "手臂" or json.loads(identity)[2] <= index}
    impact = next(p for p in progress_impact(result, updated, "result", progress) if p["部件"] == "手臂")
    assert impact["保留完成圈次"] == index * 2
    assert impact["清除完成圈次"] == (20 - index) * 2
    assert f"第 {index + 1} 圈" in impact["变化范围"]


# ── 纯颜色修改保留全部已完成圈次（规格 §7）──────────────────────────────
# 这是 2026-11-04 有意变更的契约：旧实现把颜色也算作"施工变化"，改一个圈的
# 颜色就从该圈起清除完成记录。针数、针法与人工文字都没变时，已钩的圈次依然
# 有效；界面另做"已钩出的旧颜色不会因为图解改色而改变"的提示。任何施工变化
# 同时出现时，仍按下面的保守规则处理。

@pytest.mark.parametrize("index", [0, 5, 19])
def test_colour_only_change_keeps_every_completed_round(index):
    result = _flat()
    updated = deepcopy(result)
    arm = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")
    arm["rounds"][index]["color"] = "红色"
    progress = _all(result)
    assert retained_progress(result, updated, "result", progress) == progress
    impact = next(p for p in progress_impact(result, updated, "result", progress) if p["部件"] == "手臂")
    assert impact == {"部件": "手臂", "变化范围": "原有圈次保持不变",
                      "保留完成圈次": 40, "清除完成圈次": 0}


def test_instance_colour_change_is_also_a_pure_colour_change():
    """逐份选色只写 instance_colors，针法未变，因此同样保留已完成圈次。"""
    result = _flat()
    updated = deepcopy(result)
    arm = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")
    arm["instance_colors"] = ["蓝色", None]
    progress = _all(result)
    assert retained_progress(result, updated, "result", progress) == progress


def test_mixed_copy_colour_and_construction_edit_rechecks_only_the_changed_copy():
    from app.services.progress_state import color_only_change

    result = _flat()
    updated = deepcopy(result)
    arm = next(part for part in updated["params"]["parts"] if part["name"] == "手臂")
    arm["instance_colors"] = ["蓝色", None]
    body = next(part for part in updated["params"]["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    progress = _all(result)

    assert not color_only_change(result, updated)
    kept = retained_progress(result, updated, "result", progress)
    left = {key for key in progress if json.loads(key)[:2] == ["手臂", "arms_left"]}
    right = {key for key in progress if json.loads(key)[:2] == ["手臂", "arms_right"]}
    assert left.isdisjoint(kept)
    assert right <= kept.keys()
    impact = next(row for row in progress_impact(result, updated, "result", progress)
                  if row["部件"] == "手臂")
    assert impact["保留完成圈次"] == 20 and impact["清除完成圈次"] == 20
    assert "第 1 份" in impact["变化范围"]


def test_mixed_edit_keeps_copy_progress_until_the_first_effective_colour_difference():
    result = _flat()
    arm = next(part for part in result["params"]["parts"] if part["name"] == "手臂")
    arm["color"] = "红色"
    arm["instance_colors"] = ["红色", None]
    arm["rounds"][4]["color"] = "蓝色"
    updated = deepcopy(result)
    updated_arm = next(part for part in updated["params"]["parts"] if part["name"] == "手臂")
    updated_arm["instance_colors"] = [None, None]
    body = next(part for part in updated["params"]["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)

    left_rows = {json.loads(key)[2] for key in kept if json.loads(key)[:2] == ["手臂", "arms_left"]}
    assert left_rows == set(range(1, 5))
    assert len([key for key in kept if json.loads(key)[:2] == ["手臂", "arms_right"]]) == 20
    impact = next(row for row in progress_impact(result, updated, "result", progress)
                  if row["部件"] == "手臂")
    assert "第 1 份" in impact["变化范围"] and "第 5 圈" in impact["变化范围"]


def test_copy_override_matching_inherited_yarn_does_not_clear_progress_in_a_mixed_edit():
    result = _flat()
    updated = deepcopy(result)
    arm = next(part for part in updated["params"]["parts"] if part["name"] == "手臂")
    arm["instance_colors"] = [arm["color"], None]
    body = next(part for part in updated["params"]["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)
    assert all(key in kept for key in progress if json.loads(key)[0] == "手臂")
    assert not has_color_change(result, updated)


def test_mixed_base_colour_change_keeps_a_copy_with_an_unchanged_override():
    result = _flat()
    arm = next(part for part in result["params"]["parts"] if part["name"] == "手臂")
    arm["instance_colors"] = ["蓝色", None]
    updated = deepcopy(result)
    next(part for part in updated["params"]["parts"] if part["name"] == "手臂")["color"] = "红色"
    body = next(part for part in updated["params"]["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)
    left = {key for key in progress if json.loads(key)[:2] == ["手臂", "arms_left"]}
    right = {key for key in progress if json.loads(key)[:2] == ["手臂", "arms_right"]}

    assert left <= kept.keys()
    assert right.isdisjoint(kept)
    impact = next(row for row in progress_impact(result, updated, "result", progress)
                  if row["部件"] == "手臂")
    assert impact["保留完成圈次"] == 20 and impact["清除完成圈次"] == 20
    assert "第 2 份" in impact["变化范围"]


def test_mixed_stripe_edit_keeps_a_uniform_copy_and_rechecks_the_other_from_the_change():
    from app.services.color_selection import MODE_UNIFORM, apply_color_change
    from app.services.result_logic import rebuild_params

    result = _flat()
    next(part for part in result["params"]["parts"] if part["name"] == "手臂")["rounds"][4]["color"] = "红色"
    result = apply_color_change(result, part_name="手臂", color="蓝色", instance_index=0, mode=MODE_UNIFORM)
    updated = deepcopy(result)
    arm = next(part for part in updated["params"]["parts"] if part["name"] == "手臂")
    arm["rounds"][4]["color"] = "绿色"
    body = next(part for part in updated["params"]["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    updated["params"] = rebuild_params(updated["params"], previous=result["params"],
                                       structure=result["structure"])
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)

    assert len([key for key in kept if json.loads(key)[:2] == ["手臂", "arms_left"]]) == 20
    right_rows = {json.loads(key)[2] for key in kept if json.loads(key)[:2] == ["手臂", "arms_right"]}
    assert right_rows == set(range(1, 5))
    impact = next(row for row in progress_impact(result, updated, "result", progress)
                  if row["部件"] == "手臂")
    assert "第 2 份" in impact["变化范围"] and "第 5 圈" in impact["变化范围"]


def test_reordering_copies_without_changing_their_yarn_keeps_progress():
    result = _flat()
    arm = next(part for part in result["params"]["parts"] if part["name"] == "手臂")
    arm["instance_colors"] = ["蓝色", "红色"]
    arm["instance_color_ids"] = ["arms_left", "arms_right"]
    updated = deepcopy(result)
    graph_arm = next(part for part in updated["structure"]["parts"] if part["name"] == "手臂")
    graph_arm["instances"].reverse()
    updated_arm = next(part for part in updated["params"]["parts"] if part["name"] == "手臂")
    updated_arm["instance_colors"].reverse()
    updated_arm["instance_color_ids"].reverse()
    progress = _all(result)

    assert not has_color_change(result, updated)
    assert retained_progress(result, updated, "result", progress) == progress


@settings(max_examples=80, deadline=None)
@given(
    st.lists(st.sampled_from(["红色", "蓝色", "绿色"]), min_size=5, max_size=5),
    st.lists(st.sampled_from(["红色", "蓝色", "绿色"]), min_size=5, max_size=5),
    st.tuples(st.sampled_from([None, "红色", "蓝色"]), st.sampled_from([None, "红色", "蓝色"])),
    st.tuples(st.sampled_from([None, "红色", "蓝色"]), st.sampled_from([None, "红色", "蓝色"])),
    st.booleans(),
)
def test_mixed_colour_progress_follows_effective_yarn_and_stable_copy_ids(
        old_rounds, new_rounds, old_overrides, new_overrides, reverse):
    result = _flat()
    arm = next(part for part in result["params"]["parts"] if part["name"] == "手臂")
    arm["rounds"] = arm["rounds"][:5]
    arm["instance_colors"] = list(old_overrides)
    arm["instance_color_ids"] = ["arms_left", "arms_right"]
    for row, color in zip(arm["rounds"], old_rounds, strict=True):
        row["color"] = color
    updated = deepcopy(result)
    new_arm = next(part for part in updated["params"]["parts"] if part["name"] == "手臂")
    new_arm["instance_colors"] = list(new_overrides)
    for row, color in zip(new_arm["rounds"], new_rounds, strict=True):
        row["color"] = color
    if reverse:
        next(part for part in updated["structure"]["parts"] if part["name"] == "手臂")["instances"].reverse()
        new_arm["instance_colors"].reverse()
        new_arm["instance_color_ids"].reverse()
    body = next(part for part in updated["params"]["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"

    kept = retained_progress(result, updated, "result", _all(result))
    any_change = False
    for index, copy_id in enumerate(("arms_left", "arms_right")):
        old_colors = [old_overrides[index] or color for color in old_rounds]
        new_colors = [new_overrides[index] or color for color in new_rounds]
        first = next((i for i, pair in enumerate(zip(old_colors, new_colors, strict=True))
                      if pair[0] != pair[1]), 5)
        any_change |= first < 5
        actual = {json.loads(key)[2] for key in kept if json.loads(key)[:2] == ["手臂", copy_id]}
        assert actual == set(range(1, first + 1))
    assert has_color_change(result, updated) is any_change


def test_undo_does_not_transfer_completed_work_across_a_mixed_copy_colour_change():
    restored = _flat()
    current = deepcopy(restored)
    arm = next(part for part in current["params"]["parts"] if part["name"] == "手臂")
    arm["instance_colors"] = ["蓝色", None]
    body = next(part for part in current["params"]["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    entries = {json.loads(key)[1]: key for key, _, part in progress_entries(restored, "result")
               if part["name"] == "手臂" and json.loads(key)[2] == 1}
    saved = {entries["arms_right"]: True}
    live = {entries["arms_left"]: True, entries["arms_right"]: True}

    assert reconcile_restored_progress(current, restored, live, saved) == (saved, 1)


def test_mixed_json_preview_warns_about_yarn_and_shows_copy_progress_impact():
    result = _flat()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.checkbox(key="chk_project_手臂_0").check().run()
    at.checkbox(key="chk_project_手臂_copy2_0").check().run()
    updated = deepcopy(result["params"])
    next(part for part in updated["parts"] if part["name"] == "手臂")["instance_colors"] = ["蓝色", None]
    body = next(part for part in updated["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    at.text_area(key="json_edit_project").input(json.dumps(updated, ensure_ascii=False)).run()
    at.button(key="edit_project_json_preview").click().run()

    assert not at.exception
    assert any("已钩出的旧颜色不会因为图解改色而改变" in item.value for item in at.warning)
    assert any("第 1 份" in str(table.value) and "手臂" in str(table.value) for table in at.table)
    at.button(key="edit_project_preview_apply").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert not at.checkbox(key=f"chk_{rid}_手臂_0").value
    assert at.checkbox(key=f"chk_{rid}_手臂_copy2_0").value
    assert any("已钩出的旧颜色不会因为图解改色而改变" in item.value for item in at.warning)


def test_direct_mixed_json_apply_warns_about_already_worked_yarn():
    result = _flat()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    updated = deepcopy(result["params"])
    next(part for part in updated["parts"] if part["name"] == "手臂")["instance_colors"] = ["蓝色", None]
    body = next(part for part in updated["parts"] if part["name"] == "身体")
    body["notes"] = (body.get("notes") or "") + "；手工缝合说明"
    at.text_area(key="json_edit_project").input(json.dumps(updated, ensure_ascii=False)).run()
    at.button(key="regen_project").click().run()
    assert not at.exception
    assert at.session_state["result"]["result_id"] != "project"
    assert any("已钩出的旧颜色不会因为图解改色而改变" in item.value for item in at.warning)


def test_colour_change_that_also_moves_stitches_stays_conservative():
    """颜色与针数同时变化＝施工变化：回到原有的首个受影响圈规则。"""
    result = _flat()
    updated = deepcopy(result)
    arm = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")
    arm["rounds"][5]["color"] = "红色"
    arm["rounds"][5].update(stitches=12, increase=6)
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)
    assert len([key for key in kept if json.loads(key)[0] == "手臂"]) == 5 * 2
    impact = next(p for p in progress_impact(result, updated, "result", progress) if p["部件"] == "手臂")
    assert impact["清除完成圈次"] == 15 * 2


def test_colour_change_that_edits_manual_prose_stays_conservative():
    """人工文字与颜色一起改时不是纯颜色修改，沿用保守规则。"""
    result = _flat()
    updated = deepcopy(result)
    arm = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")
    arm["rounds"][5]["color"] = "红色"
    arm["rounds"][5]["notes"] = "6X；这里改成先填棉"
    progress = _all(result)
    kept = retained_progress(result, updated, "result", progress)
    assert len([key for key in kept if json.loads(key)[0] == "手臂"]) == 5 * 2


def test_colour_only_detection_is_content_based_not_path_based():
    """选色面板与 JSON 编辑共用同一判定：不因编辑入口不同而改变进度结果。"""
    from app.services.progress_state import color_only_change

    result = _flat()
    recoloured = deepcopy(result)
    next(p for p in recoloured["params"]["parts"] if p["name"] == "手臂")["rounds"][3]["color"] = "红色"
    assert color_only_change(result, recoloured)
    restitched = deepcopy(recoloured)
    next(p for p in restitched["params"]["parts"] if p["name"] == "手臂")["rounds"][3]["stitches"] = 12
    assert not color_only_change(result, restitched)
    renamed = deepcopy(recoloured)
    next(p for p in renamed["params"]["parts"] if p["name"] == "手臂")["rounds"][3]["row"] = 99
    assert not color_only_change(result, renamed)
    assert not color_only_change(result, deepcopy(result))


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


def test_undo_only_carries_new_progress_for_rounds_with_unchanged_construction():
    restored = _flat()
    current = deepcopy(restored)
    next(part for part in current["params"]["parts"] if part["name"] == "手臂")["rounds"][5]["notes"] = (
        "6X；在此圈更换工艺")
    arm = [identity for identity, _, part in progress_entries(restored, "result")
           if part["name"] == "手臂"]
    by_row = {json.loads(identity)[2]: identity for identity in arm[:20]}
    saved = {by_row[3]: True, by_row[9]: True}
    live = {by_row[2]: True, by_row[6]: True}

    # Row 3 was unchecked after the edit; row 9 was invalidated by it.
    # Row 6 belongs to the changed construction and cannot be transferred back.
    assert reconcile_restored_progress(current, restored, live, saved) == (
        {by_row[2]: True, by_row[9]: True}, 1)


def test_preview_is_read_only_then_apply_undo_redo_keep_exact_progress_and_notes():
    result = _flat()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    for key in ("chk_project_手臂_2", "chk_project_手臂_copy2_8"):
        at.checkbox(key=key).check().run()
    at.text_area(key="project_notes_project").input("暂停在右臂").run()
    # A manual-prose edit (not a colour) keeps the exact-prefix rule this test
    # exists to pin; the pure-colour retention rule has its own tests above.
    changed = deepcopy(result["params"])
    arm = next(p for p in changed["parts"] if p["name"] == "手臂")
    arm["rounds"][5]["notes"] = "6X；留线准备下一步"
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
    seed_progress(at.session_state, result, {"chk_project_手臂_0"})
    at.session_state["project_notes_project"] = "保留此备注"
    at.run()
    at.button(key="edit_project_json_preview").click().run()
    at.button(key="edit_project_preview_cancel").click().run()
    assert not at.exception and at.session_state["result"] == result
    assert at.checkbox(key="chk_project_手臂_0").value
    assert at.text_area(key="project_notes_project").value == "保留此备注"
    assert at.session_state["workspace_result"]["pending_preview"] is None
