"""Review yarn changes without mutation; unchanged saves must retain redo."""
import json
import math
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.services.progress_state import capture_progress
from app.services.result_logic import import_backup
from app.ui.edit_history import metrics
from app.ui.pattern_editor import edit_yarn
from app.utils.project import project_backup, read_project_state
from app.utils.trial_bundle import create_trial_bundle
from tests.test_project_backup import RENDER
from tests.test_swatch_provenance import FIXTURE, source


def start():
    current=edit_yarn(source(),{"ball_weight_g":50,"ball_length_m":125})
    current["history_id"]="stored-pattern"
    current["title"]="保存的名称"
    at=AppTest.from_string(RENDER,default_timeout=30)
    at.session_state["result"]=current
    at.run()
    return at


def rid(at):
    return at.session_state["result"]["result_id"]


def submit(at,label):
    next(b for b in at.button if b.label==label).click().run()
    assert not at.exception


def undo_to_base(at):
    at.number_input(key=f"edit_{rid(at)}_weight").set_value(60)
    submit(at,"更新材料估算")
    at.button(key=f"edit_{rid(at)}_undo").click().run()
    assert not at.exception and not at.button(key=f"edit_{rid(at)}_redo").disabled


@pytest.mark.parametrize("entry",["material","material-preview","rounds","head-preview","part-gauge",
                                  "size","size-preview","structure-json","params-json"])
def test_unchanged_edits_keep_id_redo_latest_progress_notes_and_storage_binding(entry):
    at=start()
    undo_to_base(at)
    before_id=rid(at)
    at.checkbox(key=f"chk_{before_id}_头部_0").check().run()
    at.text_area(key=f"project_notes_{before_id}").input("撤销后继续的进度").run()
    at.text_input(key=f"hist_title_{before_id}").input("尚未保存的名称").run()
    before=deepcopy(at.session_state["result"])
    history=deepcopy(at.session_state["edit_history_result"])
    progress=capture_progress(before,"result",at.session_state)
    if entry=="material":
        submit(at,"更新材料估算")
    elif entry=="material-preview":
        submit(at,"预览材料估算修改")
        at.button(key=f"edit_{before_id}_preview_apply").click().run()
    elif entry=="rounds":
        at.button(key=f"edit_{before_id}_roundapply").click().run()
    elif entry=="size":
        at.button(key=f"sz_go_{before_id}").click().run()
    elif entry=="size-preview":
        at.button(key=f"edit_{before_id}_size_preview").click().run()
        at.button(key=f"edit_{before_id}_preview_apply").click().run()
    elif entry in ("structure-json","params-json"):
        key=f"struct_go_{before_id}" if entry=="structure-json" else f"regen_{before_id}"
        at.button(key=key).click().run()
    else:
        key="head_open_preview" if entry=="head-preview" else "partgauge0_preview"
        at.button(key=f"edit_{before_id}_{key}").click().run()
        at.button(key=f"edit_{before_id}_preview_apply").click().run()
    assert not at.exception and rid(at)==before_id
    assert at.session_state["result"]==before
    assert at.session_state["edit_history_result"]==history
    assert capture_progress(before,"result",at.session_state)==progress
    assert at.text_area(key=f"project_notes_{before_id}").value=="撤销后继续的进度"
    assert at.text_input(key=f"hist_title_{before_id}").value=="尚未保存的名称"
    assert at.session_state["workspace_result"]["pending_preview"] is None
    assert any("设置与当前图解相同" in info.value for info in at.info)
    assert not any("已按新尺寸重新生成" in item.value or "已按修正后的部件结构重新生成" in item.value
                   or "已根据修正更新图解" in item.value for item in at.success)
    assert not at.button(key=f"edit_{before_id}_redo").disabled
    at.button(key=f"edit_{before_id}_redo").click().run()
    assert not at.exception
    assert at.session_state["result"]["params"]["yarn_spec"]["ball_weight_g"]==60
    assert at.session_state["result"]["history_id"]=="stored-pattern"


@pytest.mark.parametrize("entry", ["size", "structure-json", "params-json"])
def test_actual_changes_still_regenerate_and_report_success(entry):
    at=start()
    undo_to_base(at)
    before_id=rid(at)
    if entry=="size":
        at.slider(key=f"sz_height_{before_id}").set_value(40.0)
        at.button(key=f"sz_go_{before_id}").click().run()
        assert at.session_state["result"]["analysis"]["height_cm"]==40
        assert at.session_state["result"]["sizing"]["source"]=="user_resize"
        expected="已按新尺寸重新生成"
    elif entry=="structure-json":
        key=f"struct_edit_{before_id}"
        structure=json.loads(at.text_area(key=key).value)
        structure["parts"][0]["instances"][0]["position"]["x"]=0.2
        at.text_area(key=key).input(json.dumps(structure,ensure_ascii=False)).run()
        at.button(key=f"struct_go_{before_id}").click().run()
        assert at.session_state["result"]["structure"]["parts"][0]["instances"][0]["position"]["x"]==0.2
        expected="已按修正后的部件结构重新生成"
    else:
        key=f"json_edit_{before_id}"
        params=json.loads(at.text_area(key=key).value)
        params["parts"][0]["rounds"][0]["notes"]+="；核对张力"
        at.text_area(key=key).input(json.dumps(params,ensure_ascii=False)).run()
        at.button(key=f"regen_{before_id}").click().run()
        assert "核对张力" in at.session_state["result"]["params"]["parts"][0]["rounds"][0]["notes"]
        expected="已根据修正更新图解"
    assert not at.exception and rid(at)!=before_id
    assert at.button(key=f"edit_{rid(at)}_redo").disabled
    assert any(expected in item.value for item in at.success)


def test_preview_cancel_apply_undo_redo_and_project_show_complete_material_changes():
    at=start()
    before=deepcopy(at.session_state["result"])
    before_id=rid(at)
    at.checkbox(key=f"chk_{before_id}_头部_0").check().run()
    at.text_area(key=f"project_notes_{before_id}").input("先核对线标，再购买").run()
    at.number_input(key=f"edit_{before_id}_weight").set_value(10)
    at.number_input(key=f"edit_{before_id}_length").set_value(200)
    at.number_input(key=f"edit_{before_id}_waste").set_value(20)
    at.checkbox(key=f"edit_{before_id}_measured").check()
    at.number_input(key=f"edit_{before_id}_swatchweight").set_value(5)
    at.number_input(key=f"edit_{before_id}_swatchst").set_value(10)
    at.number_input(key=f"edit_{before_id}_swatchrows").set_value(10)
    submit(at,"预览材料估算修改")
    assert at.session_state["result"]==before
    tables=[t.value for t in at.table if {"项目","修改前","修改后"} <= set(t.value.columns)]
    changes=tables[0].set_index("项目")
    expected_rows={"估算毛线（g）","估算毛线（m）","购线团数","预留比例（%）","线标（每团）","称重试片"}
    assert expected_rows <= set(changes.index)
    assert changes.loc["线标（每团）","修改前"]=="50g / 125m"
    assert changes.loc["线标（每团）","修改后"]=="10g / 200m"
    assert "30 针 × 32 行" in changes.loc["称重试片","修改后"]
    at.button(key=f"edit_{before_id}_preview_cancel").click().run()
    assert at.session_state["result"]==before
    assert at.checkbox(key=f"chk_{before_id}_头部_0").value
    submit(at,"预览材料估算修改")
    at.checkbox(key=f"chk_{before_id}_头部_1").check().run()
    at.button(key=f"edit_{before_id}_preview_apply").click().run()
    assert not at.exception
    updated=at.session_state["result"]
    assert updated["params"]["parts"]==before["params"]["parts"]
    summary=updated["params"]["material_summary"]
    assert summary["grams"]==round(summary["total_stitches"]*.05*1.2,2)
    assert summary["meters"]==round(summary["total_stitches"]*.05*1.2*20,2)
    yarn=[m for m in updated["params"]["materials"] if "color" in m]
    assert summary["balls"]==sum(math.ceil(m["stitches"]*.05*1.2/10) for m in yarn)
    for action in (None,"undo","redo"):
        if action:
            at.button(key=f"edit_{rid(at)}_{action}").click().run()
        assert not at.exception
        live=at.session_state["result"]
        assert at.checkbox(key=f"chk_{rid(at)}_头部_0").value
        assert at.checkbox(key=f"chk_{rid(at)}_头部_1").value
        assert at.text_area(key=f"project_notes_{rid(at)}").value=="先核对线标，再购买"
        assert live["params"]["yarn_spec"]["ball_weight_g"]==(50 if action=="undo" else 10)
    live=at.session_state["result"]
    progress=capture_progress(live,"result",at.session_state)
    saved=project_backup(live,progress,"先核对线标，再购买")
    restored=import_backup(json.loads(json.dumps(saved)),"fresh")
    assert read_project_state(saved,restored)==(progress,"先核对线标，再购买")
    assert restored["params"]["yarn_spec"]==live["params"]["yarn_spec"]


def test_label_changes_with_same_estimate_are_real_edits_and_clear_redo():
    at=start()
    undo_to_base(at)
    before_id=rid(at)
    before=deepcopy(at.session_state["result"])
    at.number_input(key=f"edit_{before_id}_weight").set_value(60)
    at.number_input(key=f"edit_{before_id}_length").set_value(150)
    submit(at,"预览材料估算修改")
    candidate=at.session_state["workspace_result"]["pending_preview"]["candidate"]
    assert candidate["params"]["material_summary"]["grams"]==before["params"]["material_summary"]["grams"]
    at.button(key=f"edit_{before_id}_preview_apply").click().run()
    assert rid(at)!=before_id and at.button(key=f"edit_{rid(at)}_redo").disabled
    assert at.session_state["result"]["params"]["yarn_spec"]["ball_length_m"]==150


def test_instruction_changes_with_identical_metrics_are_not_treated_as_unchanged():
    at=start()
    undo_to_base(at)
    before=deepcopy(at.session_state["result"])
    before_id=rid(at)
    params=deepcopy(before["params"])
    params["parts"][0]["rounds"][0]["notes"]+="；这里放记号扣"
    candidate={**before,"params":params}
    assert metrics(before)==metrics(candidate)
    at.text_area(key=f"json_edit_{before_id}").input(json.dumps(params,ensure_ascii=False)).run()
    at.button(key=f"edit_{before_id}_json_preview").click().run()
    at.button(key=f"edit_{before_id}_preview_apply").click().run()
    assert not at.exception and rid(at)!=before_id
    assert at.button(key=f"edit_{rid(at)}_redo").disabled
    assert "这里放记号扣" in at.session_state["result"]["params"]["parts"][0]["rounds"][0]["notes"]


def test_legacy_swatch_preview_requires_confirmation_and_cancel_does_not_bind_it():
    current=import_backup(json.loads((FIXTURE/"project.json").read_text()),"legacy")
    at=AppTest.from_string(RENDER,default_timeout=30)
    at.session_state["result"]=current
    at.run()
    submit(at,"预览材料估算修改")
    assert at.session_state["result"]==current
    assert at.session_state["workspace_result"]["pending_preview"] is None
    assert any("核对并确认" in e.value for e in at.error)
    at.checkbox(key="edit_legacy_swatch_confirm").check()
    submit(at,"预览材料估算修改")
    tables=[t.value for t in at.table if {"项目","修改前","修改后"} <= set(t.value.columns)]
    row=tables[0].set_index("项目").loc["称重试片"]
    assert "密度待确认" in row["修改前"] and "30 针 × 32 行" in row["修改后"]
    at.button(key="edit_legacy_preview_cancel").click().run()
    assert at.session_state["result"]==current and "swatch_gauge" not in current["params"]["yarn_spec"]


def test_preview_and_application_do_not_rebind_existing_trial_evidence():
    at=start()
    current=at.session_state["result"]
    bundle=create_trial_bundle(current,trial_id="synthetic-preview",maker_id="synthetic")
    # Install through the app's normal restore boundary, retaining source bytes.
    script=RENDER.replace("render_results(st.session_state.result, \"result\")",'''
if "trial_workspace_result" not in st.session_state:
    from app.ui.trial_editor import _install
    _install("result", st.session_state.bundle)
render_results(st.session_state.result, "result")
''')
    at=AppTest.from_string(script,default_timeout=30)
    at.session_state["result"]=current
    at.session_state["bundle"]=bundle
    at.run()
    archive=at.session_state["trial_workspace_result"]["archive"]
    at.number_input(key=f"edit_{rid(at)}_weight").set_value(70)
    submit(at,"预览材料估算修改")
    assert at.session_state["trial_workspace_result"]["archive"]==archive
    at.button(key=f"edit_{rid(at)}_preview_apply").click().run()
    assert not at.exception and at.session_state["trial_workspace_result"]["archive"]==archive
    assert at.button(key="trial_gauge_preview_result").disabled


def test_comparison_handles_valid_legacy_numeric_spelling_without_mutation():
    current=source()
    current["params"]["yarn_spec"]={"ball_weight_g":"50","ball_length_m":"125"}
    before=deepcopy(current)
    assert metrics(current)["线标（每团）"]=="50g / 125m"
    assert current==before
