"""Independent checks for a manually specified two-leg chain bridge."""
import json
from copy import deepcopy
from io import BytesIO
from xml.etree import ElementTree

import pytest
from streamlit.testing.v1 import AppTest

from app.models.leg_join import (
    MAX_LEG_JOIN_PLAN_BYTES,
    compare_leg_join,
    decode_leg_join_plan,
    leg_join_advisories,
    leg_join_plan,
)
from app.models.leg_join_diagram import leg_join_svg
from app.schemas import MAX_ROUND_STITCHES, PatternResult
from tests.test_app_smoke import _mock_result
from tests.test_project_backup import RENDER


def _inputs():
    return dict(left_row=7, left_stitches=12, left_marker=3,
                right_row=9, right_stitches=15, right_marker=15, chain=4)


def _select_part(at, label):
    return next(widget for widget in at.selectbox if widget.label == label)


def test_plan_counts_both_sides_of_bridge_and_preserves_references():
    plan = leg_join_plan(**_inputs())
    assert plan["result_stitches"] == 35
    assert plan["left"] == {"row": 7, "stitches": 12, "marker": 3}
    assert plan["right"] == {"row": 9, "stitches": 15, "marker": 15}
    assert plan["chain_sides"] == 2 and plan["sc_per_base_stitch"] == 1


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "12", None, float("nan")])
def test_invalid_values_are_not_coerced(value):
    data = _inputs()
    data["chain"] = value
    with pytest.raises(ValueError):
        leg_join_plan(**data)


@pytest.mark.parametrize("field,value", [("left_marker", 13), ("right_marker", 16),
                                         ("left_row", 0), ("right_stitches", -1),
                                         ("chain", MAX_ROUND_STITCHES)])
def test_invalid_reference_or_total_is_rejected(field, value):
    data = _inputs()
    data[field] = value
    with pytest.raises(ValueError):
        leg_join_plan(**data)


def test_exact_total_limit_is_allowed():
    data = _inputs()
    data.update(left_stitches=MAX_ROUND_STITCHES - 4, right_stitches=2,
                left_marker=1, right_marker=1, chain=1)
    assert leg_join_plan(**data)["result_stitches"] == MAX_ROUND_STITCHES


def test_manual_plan_ui_does_not_change_pattern_and_download_matches_inputs(monkeypatch):
    result = _mock_result("join-example")
    original = deepcopy(result)
    downloads = []
    import streamlit as st
    original_download = st.download_button

    def capture(label, data, *args, **kwargs):
        if label == "下载并腿方案 JSON":
            downloads.append(json.loads(data))
        return original_download(label, data, *args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture)
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    prefix = "leg_join_result_join-example_"
    for field, value in _inputs().items():
        at.number_input(key=prefix + field).set_value(value)
    at.run()
    assert not at.exception
    assert downloads[-1] == leg_join_plan(**_inputs())
    assert any("35 针" in item.value for item in at.info)
    assert at.session_state["result"] == original
    at.number_input(key=prefix + "left_marker").set_value(13).run()
    assert any("记号针序号" in item.value for item in at.error)
    assert at.session_state["result"] == original


def _encoded():
    return json.dumps(leg_join_plan(**_inputs())).encode()


def test_restore_existing_plan_accepts_utf8_bom_and_recomputes_counts():
    assert decode_leg_join_plan(b"\xef\xbb\xbf" + _encoded()) == leg_join_plan(**_inputs())


@pytest.mark.parametrize("damage", ["total", "sides", "per_stitch", "bool_count", "bool_side",
                                     "marker", "missing", "unknown", "version", "wrong_type"])
def test_restore_rejects_mismatched_or_ambiguous_plan(damage):
    plan = leg_join_plan(**_inputs())
    if damage == "total":
        plan["result_stitches"] += 1
    elif damage == "sides":
        plan["chain_sides"] = 1
    elif damage == "per_stitch":
        plan["sc_per_base_stitch"] = 2
    elif damage == "bool_count":
        plan["left"]["row"] = True
    elif damage == "bool_side":
        plan["sc_per_base_stitch"] = True
    elif damage == "marker":
        plan["right"]["marker"] = 16
    elif damage == "missing":
        del plan["left"]["row"]
    elif damage == "unknown":
        plan["left"]["other"] = 1
    elif damage == "version":
        plan["schema_version"] = "2"
    else:
        plan["right"] = []
    with pytest.raises(ValueError):
        decode_leg_join_plan(json.dumps(plan).encode())


@pytest.mark.parametrize("raw", [b'{"x": 1, "x": 2}', b"{", b"\xff", b"[]",
                                  b'{"x":NaN}', b" " * (MAX_LEG_JOIN_PLAN_BYTES + 1)])
def test_restore_rejects_malformed_duplicate_nonfinite_or_oversized_data(raw):
    with pytest.raises(ValueError):
        decode_leg_join_plan(raw)


def test_restore_form_is_atomic_and_keeps_current_pattern():
    result = _mock_result("join-restore")
    original = deepcopy(result)
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    prefix = "leg_join_result_join-restore_"
    at.radio(key=prefix + "source").set_value("粘贴 JSON").run()
    at.text_area(key=prefix + "paste").input(_encoded().decode()).run()
    at.button(key=prefix + "restore").click().run()
    assert not at.exception
    assert at.number_input(key=prefix + "left_row").value is None
    at.button(key=prefix + "restore_apply").click().run()
    assert all(at.number_input(key=prefix + key).value == value for key, value in _inputs().items())
    assert any("方案已恢复" in item.value for item in at.success)
    assert any("35 针" in item.value for item in at.info)
    assert at.session_state["result"] == original
    at.number_input(key=prefix + "left_row").set_value(8).run()
    bad = json.loads(_encoded())
    bad["result_stitches"] += 1
    at.text_area(key=prefix + "paste").input(json.dumps(bad)).run()
    at.button(key=prefix + "restore").click().run()
    assert any("不一致" in item.value for item in at.error)
    assert at.number_input(key=prefix + "left_row").value == 8
    assert at.session_state["result"] == original


def test_file_restore_reads_from_start_and_can_be_repeated(monkeypatch):
    import streamlit as st

    uploaded = BytesIO(_encoded())
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: uploaded)
    at = AppTest.from_string('''
from app.ui.leg_join import render_leg_join
render_leg_join("test")
''', default_timeout=30)
    at.session_state["leg_join_test_upload"] = uploaded
    at.run()
    for _ in range(2):
        at.button(key="leg_join_test_restore").click().run()
        at.button(key="leg_join_test_restore_apply").click().run()
        assert not at.exception
        assert at.number_input(key="leg_join_test_left_row").value == 7
        assert any("方案已恢复" in item.value for item in at.success)


@pytest.mark.parametrize("change", ["form", "source", "mode"])
def test_restore_preview_rejects_stale_input_and_keeps_current_work(change):
    result = _mock_result("join-stale")
    original = deepcopy(result)
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    prefix = "leg_join_result_join-stale_"
    at.radio(key=prefix + "source").set_value("粘贴 JSON").run()
    at.number_input(key=prefix + "left_row").set_value(3).run()
    at.text_area(key=prefix + "paste").input(_encoded().decode()).run()
    at.button(key=prefix + "restore").click().run()
    assert at.number_input(key=prefix + "left_row").value == 3
    assert any("尚未应用" in text.value for text in at.markdown)
    if change == "form":
        at.number_input(key=prefix + "left_row").set_value(4).run()
    elif change == "source":
        plan = json.loads(_encoded())
        plan["left"]["row"] = 8
        at.text_area(key=prefix + "paste").input(json.dumps(plan)).run()
    else:
        at.radio(key=prefix + "source").set_value("上传 JSON 文件").run()
    at.button(key=prefix + "restore_apply").click().run()
    assert not at.exception
    assert any("重新预览" in item.value for item in at.error)
    assert at.number_input(key=prefix + "left_row").value == (4 if change == "form" else 3)
    assert at.session_state["result"] == original
    assert not any(button.key == prefix + "restore_apply" for button in at.button)


def test_restore_preview_can_be_cancelled_without_replacing_inputs():
    at = AppTest.from_string('''
from app.ui.leg_join import render_leg_join
render_leg_join("cancel")
''', default_timeout=30).run()
    prefix = "leg_join_cancel_"
    at.radio(key=prefix + "source").set_value("粘贴 JSON").run()
    at.number_input(key=prefix + "left_row").set_value(3).run()
    at.text_area(key=prefix + "paste").input(_encoded().decode()).run()
    at.button(key=prefix + "restore").click().run()
    at.button(key=prefix + "restore_cancel").click().run()
    assert not at.exception
    assert at.number_input(key=prefix + "left_row").value == 3
    assert not any(button.key == prefix + "restore_apply" for button in at.button)


def test_restore_preview_detects_replaced_uploaded_bytes(monkeypatch):
    import streamlit as st

    uploaded = BytesIO(_encoded())
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: uploaded)
    at = AppTest.from_string('''
from app.ui.leg_join import render_leg_join
render_leg_join("upload_change")
''', default_timeout=30)
    prefix = "leg_join_upload_change_"
    at.session_state[prefix + "upload"] = uploaded
    at.run()
    at.number_input(key=prefix + "left_row").set_value(3).run()
    at.button(key=prefix + "restore").click().run()
    uploaded.seek(0)
    uploaded.write(b"changed")
    uploaded.truncate()
    at.button(key=prefix + "restore_apply").click().run()
    assert not at.exception
    assert any("重新预览" in item.value for item in at.error)
    assert at.number_input(key=prefix + "left_row").value == 3


def test_compare_checks_both_parts_and_preserves_inputs():
    plan = leg_join_plan(**_inputs())
    parts = [{"name": "左腿", "quantity": 1, "rounds": [{"row": 7, "stitches": 12}]},
             {"name": "右腿", "quantity": 1, "rounds": [{"row": 9, "stitches": 15}]}]
    before = deepcopy((plan, parts))
    rows, issues = compare_leg_join(plan, parts, 0, 1)
    assert not issues
    assert [row["图解针数"] for row in rows] == [12, 15]
    assert (plan, parts) == before
    parts[1]["rounds"][0]["stitches"] = 14
    rows, issues = compare_leg_join(plan, parts, 0, 1)
    assert issues == ["右腿：针数不一致"]
    assert rows[1]["图解针数"] == 14


def test_compare_requires_two_copies_when_sharing_a_part():
    data = _inputs()
    data.update(right_row=7, right_stitches=12, right_marker=1)
    plan = leg_join_plan(**data)
    parts = [{"name": "腿", "quantity": 1, "rounds": [{"row": 7, "stitches": 12}]}]
    assert compare_leg_join(plan, parts, 0, 0)[1] == ["左右腿选择了同一部件，但该部件不足两份实体"]
    parts[0]["quantity"] = 2
    assert compare_leg_join(plan, parts, 0, 0)[1] == []


def test_compare_detects_invalid_quantity_even_for_separate_parts():
    plan = leg_join_plan(**_inputs())
    parts = [{"name": "左", "quantity": 0, "rounds": [{"row": 7, "stitches": 12}]},
             {"name": "右", "quantity": 1, "rounds": [{"row": 9, "stitches": 15}]}]
    assert compare_leg_join(plan, parts, 0, 1)[1] == ["左腿：部件实体数量无效"]


@pytest.mark.parametrize("rounds", [[], [{"row": 7, "stitches": 12}, {"row": 7, "stitches": 12}],
                                    [{"row": 7, "stitches": True}]])
def test_compare_rejects_missing_ambiguous_or_invalid_rounds(rounds):
    parts = [{"name": "腿", "quantity": 2, "rounds": rounds}]
    rows, issues = compare_leg_join(leg_join_plan(**_inputs()), parts, 0, 0)
    assert issues and rows[0]["图解针数"] == "—"


@pytest.mark.parametrize("index", [-1, 1, True, "0"])
def test_compare_rejects_invalid_selected_part(index):
    parts = [{"name": "腿", "quantity": 2, "rounds": []}]
    with pytest.raises(ValueError):
        compare_leg_join(leg_join_plan(**_inputs()), parts, index, 0)


def test_compare_ui_uses_current_pattern_and_updates_after_input_changes():
    result = _mock_result("compare-join")
    original = deepcopy(result)
    parts = result["params"]["parts"]
    leg_index = next(i for i, part in enumerate(parts) if part["name"] == "腿部")
    leg = parts[leg_index]
    leg["quantity"] = 2
    original["params"]["parts"][leg_index]["quantity"] = 2
    round_data = leg["rounds"][0]
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    prefix = "leg_join_result_compare-join_"
    values = dict(left_row=round_data["row"], right_row=round_data["row"],
                  left_stitches=round_data["stitches"], right_stitches=round_data["stitches"],
                  left_marker=1, right_marker=1, chain=3)
    for field, value in values.items():
        at.number_input(key=prefix + field).set_value(value)
    at.run()
    at.checkbox(key=prefix + "compare").check().run()
    _select_part(at, "左腿对应部件").set_value("腿部")
    _select_part(at, "右腿对应部件").set_value("腿部").run()
    assert not at.exception
    assert any("圈号、针数和实体数量" in item.value for item in at.info)
    assert any("后还有" in item.value for item in at.warning)
    at.number_input(key=prefix + "left_stitches").set_value(round_data["stitches"] + 1).run()
    assert any("左腿：针数不一致" in item.value for item in at.warning)
    assert at.session_state["result"] == original


def test_compare_advisories_report_later_rounds_and_finish_words_without_interpreting_them():
    data = _inputs()
    data.update(right_row=8, right_stitches=12, right_marker=1)
    plan = leg_join_plan(**data)
    parts = [{"name": "腿", "quantity": 2, "rounds": [
        {"row": 7, "stitches": 12, "notes": "普通短针"},
        {"row": 8, "stitches": 12, "notes": "勿收口；断线后留长线缝合"},
    ]}]
    before = deepcopy((plan, parts))
    warnings = leg_join_advisories(plan, parts, 0, 0)
    assert len(warnings) == 2
    assert "左腿" in warnings[0] and "后还有 1 圈" in warnings[0]
    assert "右腿" in warnings[1] and "提及" in warnings[1] and "是否仍有开口" in warnings[1]
    assert (plan, parts) == before


def test_compare_advisories_do_not_guess_for_ambiguous_or_missing_rounds():
    plan = leg_join_plan(**_inputs())
    parts = [{"name": "腿", "quantity": 2, "rounds": [
        {"row": 7, "stitches": 12, "notes": "断线"},
        {"row": 7, "stitches": 12, "notes": "断线"},
    ]}]
    assert leg_join_advisories(plan, parts, 0, 0) == []


def test_compare_ui_warns_on_generated_leg_finish_without_changing_pattern():
    result = _mock_result("join-finish")
    original = deepcopy(result)
    parts = result["params"]["parts"]
    index = next(i for i, part in enumerate(parts) if part["name"] == "腿部")
    last = parts[index]["rounds"][-1]
    assert "断线" in last["notes"]
    inputs = dict(left_row=last["row"], right_row=last["row"],
                  left_stitches=last["stitches"], right_stitches=last["stitches"],
                  left_marker=1, right_marker=1, chain=3)
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    prefix = "leg_join_result_join-finish_"
    for field, value in inputs.items():
        at.number_input(key=prefix + field).set_value(value)
    at.run()
    at.checkbox(key=prefix + "compare").check().run()
    _select_part(at, "左腿对应部件").set_value("腿部")
    _select_part(at, "右腿对应部件").set_value("腿部").run()
    assert not at.exception
    assert any("左腿：所选圈说明提及" in item.value for item in at.warning)
    assert any("右腿：所选圈说明提及" in item.value for item in at.warning)
    assert at.session_state["result"] == original


@pytest.mark.parametrize("change", ["removed", "renamed"])
def test_compare_selection_stays_with_part_on_reorder_and_clears_when_missing(change):
    at = AppTest.from_string('''
import streamlit as st
from app.ui.leg_join import render_leg_join
render_leg_join("reorder", st.session_state.result)
''', default_timeout=30)
    parts = [{"name": "甲腿", "quantity": 2, "rounds": [{"row": 7, "stitches": 12}]},
             {"name": "乙腿", "quantity": 2, "rounds": [{"row": 7, "stitches": 12}]}]
    at.session_state["result"] = {"params": {"parts": parts}}
    at.run()
    prefix = "leg_join_reorder_"
    values = dict(left_row=7, right_row=7, left_stitches=12, right_stitches=12,
                  left_marker=1, right_marker=1, chain=3)
    for field, value in values.items():
        at.number_input(key=prefix + field).set_value(value)
    at.run()
    at.checkbox(key=prefix + "compare").check().run()
    _select_part(at, "左腿对应部件").set_value("甲腿")
    _select_part(at, "右腿对应部件").set_value("甲腿").run()
    at.session_state["result"]["params"]["parts"] = list(reversed(parts))
    at.run()
    assert not at.exception
    assert _select_part(at, "左腿对应部件").value == "甲腿"
    assert _select_part(at, "右腿对应部件").value == "甲腿"
    assert any("圈号、针数和实体数量" in item.value for item in at.info)
    if change == "removed":
        at.session_state["result"]["params"]["parts"] = [parts[1]]
    else:
        at.session_state["result"]["params"]["parts"][1]["name"] = "丙腿"
    at.run()
    assert not at.exception
    assert _select_part(at, "左腿对应部件").value is None
    assert _select_part(at, "右腿对应部件").value is None
    assert any("之前选择的部件已不存在" in item.value for item in at.warning)
    assert not any("圈号、针数和实体数量" in item.value for item in at.info)


def test_compare_selection_rechecks_changed_copy_count():
    at = AppTest.from_string('''
import streamlit as st
from app.ui.leg_join import render_leg_join
render_leg_join("quantity", st.session_state.result)
''', default_timeout=30)
    at.session_state["result"] = {"params": {"parts": [
        {"name": "腿", "quantity": 2, "rounds": [{"row": 7, "stitches": 12}]},
    ]}}
    at.run()
    prefix = "leg_join_quantity_"
    for field, value in dict(left_row=7, right_row=7, left_stitches=12, right_stitches=12,
                             left_marker=1, right_marker=1, chain=3).items():
        at.number_input(key=prefix + field).set_value(value)
    at.run()
    at.checkbox(key=prefix + "compare").check().run()
    _select_part(at, "左腿对应部件").set_value("腿")
    _select_part(at, "右腿对应部件").set_value("腿").run()
    at.session_state["result"]["params"]["parts"][0]["quantity"] = 1
    at.run()
    assert not at.exception
    assert _select_part(at, "左腿对应部件").value == "腿"
    assert any("不足两份实体" in item.value for item in at.warning)


def test_count_diagram_is_valid_svg_and_displays_both_bridge_sides():
    svg = leg_join_svg(leg_join_plan(**_inputs()))
    root = ElementTree.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    text = " ".join(root.itertext())
    assert "左腿：第 7 圈 · 12 针" in text
    assert "右腿：第 9 圈 · 15 针" in text
    assert "锁针一侧钩 4 针；另一侧钩 4 针" in text
    assert "12 + 15 + 2 × 4 = 35 针" in text
    assert "不表示实物比例、起点、针位或钩织方向" in text


def test_count_diagram_refuses_inconsistent_or_untrusted_content():
    plan = leg_join_plan(**_inputs())
    plan["result_stitches"] = 1
    with pytest.raises(ValueError):
        leg_join_svg(plan)
    plan = leg_join_plan(**_inputs())
    plan["left"]["row"] = '<script>alert(1)</script>'
    with pytest.raises(ValueError):
        leg_join_svg(plan)


def test_diagram_download_updates_with_plan_and_does_not_change_result(monkeypatch):
    import streamlit as st

    result = _mock_result("join-svg")
    original = deepcopy(result)
    diagrams = []
    real_download = st.download_button

    def capture(label, data, *args, **kwargs):
        if label == "下载并腿数量示意图 SVG":
            diagrams.append(data)
        return real_download(label, data, *args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture)
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    prefix = "leg_join_result_join-svg_"
    for field, value in _inputs().items():
        at.number_input(key=prefix + field).set_value(value)
    at.run()
    assert not at.exception
    assert diagrams[-1] == leg_join_svg(leg_join_plan(**_inputs()))
    assert any(item.value == diagrams[-1] for item in at.markdown)
    at.number_input(key=prefix + "chain").set_value(5).run()
    assert "12 + 15 + 2 × 5 = 37 针" in diagrams[-1]
    assert at.session_state["result"] == original


def _stage_join_preview(at, slot):
    rid = at.session_state[slot]["result_id"]
    prefix = f"leg_join_{slot}_{rid}_"
    for field, value in _inputs().items():
        at.number_input(key=prefix + field).set_value(value)
    at.radio(key=prefix + "source").set_value("粘贴 JSON").run()
    at.text_area(key=prefix + "paste").input(_encoded().decode()).run()
    at.checkbox(key=prefix + "compare").check().run()
    _select_part(at, "左腿对应部件").set_value("腿部")
    _select_part(at, "右腿对应部件").set_value("腿部").run()
    at.button(key=prefix + "restore").click().run()
    assert not at.exception
    assert prefix + "pending" in at.session_state
    assert at.session_state[prefix + "left_selection"] == "腿部"
    return prefix


@pytest.mark.parametrize("slot", ["result", "manual_result"])
def test_edit_and_undo_release_old_join_preview_without_touching_other_tab(slot):
    result = _mock_result("join-lifecycle")
    other_slot = "manual_result" if slot == "result" else "result"
    other_prefix = f"leg_join_{other_slot}_other_"
    other_plan = {"plan": leg_join_plan(**_inputs())}
    at = AppTest.from_string('''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state[st.session_state.active_slot], st.session_state.active_slot)
''', default_timeout=30)
    at.session_state["active_slot"] = slot
    at.session_state[slot] = result
    at.session_state[other_slot] = _mock_result("other")
    at.session_state[other_prefix + "pending"] = deepcopy(other_plan)
    at.session_state[other_prefix + "left_selection"] = "手臂"
    at.run()
    prefix = _stage_join_preview(at, slot)
    progress = next(widget for widget in at.checkbox if widget.key.startswith("chk_"))
    suffix = progress.key.removeprefix("chk_join-lifecycle_")
    progress.check().run()
    at.text_area(key="project_notes_join-lifecycle").input("保留钩织备注").run()
    next(button for button in at.button if button.label == "更新材料估算").click().run()

    assert not at.exception
    new_rid = at.session_state[slot]["result_id"]
    assert new_rid != result["result_id"]
    assert prefix + "pending" not in at.session_state
    assert prefix + "left_selection" not in at.session_state
    assert prefix + "right_selection" not in at.session_state
    assert at.checkbox(key=f"chk_{new_rid}_{suffix}").value
    assert at.text_area(key=f"project_notes_{new_rid}").value == "保留钩织备注"

    # Undo creates another result namespace; a newly staged preview must be freed too.
    prefix = _stage_join_preview(at, slot)
    at.button(key=f"edit_{new_rid}_undo").click().run()
    assert not at.exception
    assert prefix + "pending" not in at.session_state
    assert prefix + "left_selection" not in at.session_state
    assert at.session_state[slot]["params"] == result["params"]
    assert at.session_state[other_prefix + "pending"] == other_plan
    assert at.session_state[other_prefix + "left_selection"] == "手臂"
    restored_rid = at.session_state[slot]["result_id"]
    assert at.checkbox(key=f"chk_{restored_rid}_{suffix}").value
    assert at.text_area(key=f"project_notes_{restored_rid}").value == "保留钩织备注"


def test_pattern_import_preserves_join_preview_on_failure_and_clears_it_on_success():
    result = _mock_result("join-import-failure")
    original = deepcopy(result)
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    prefix = _stage_join_preview(at, "result")
    pending = deepcopy(at.session_state[prefix + "pending"])
    at.text_area(key="import_join-import-failure").input("{").run()
    at.button(key="importbtn_join-import-failure").click().run()

    assert not at.exception
    assert any("导入失败" in item.value for item in at.error)
    assert at.session_state["result"] == original
    assert at.session_state[prefix + "pending"] == pending
    assert _select_part(at, "左腿对应部件").value == "腿部"
    assert _select_part(at, "右腿对应部件").value == "腿部"
    assert all(at.number_input(key=prefix + field).value == value for field, value in _inputs().items())

    backup = PatternResult.from_result(original).to_backup()
    at.text_area(key="import_join-import-failure").input(json.dumps(backup)).run()
    at.button(key="importbtn_join-import-failure").click().run()
    assert not at.exception
    assert prefix + "pending" not in at.session_state
    assert prefix + "left_selection" not in at.session_state
    assert prefix + "right_selection" not in at.session_state
    assert not any(widget.key == prefix + "compare" for widget in at.checkbox)
    assert not any(button.key == prefix + "restore_apply" for button in at.button)
    rid = at.session_state["result"]["result_id"]
    at.number_input(key=f"leg_join_result_{rid}_left_row").set_value(7).run()
    assert not at.exception
