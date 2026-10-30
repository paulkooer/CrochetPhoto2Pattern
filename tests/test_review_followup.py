"""Cross-workflow regressions from the October 9 system review."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.image_parser import ImageParser
from app.models.structure_designer import StructureDesigner
from app.schemas import PatternResult
from app.ui.pattern_editor import edit_rounds
from app.ui.result_logic import import_backup
from app.utils.exporters import export_markdown

RENDER = '''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state["result"], "result")
'''


@pytest.fixture
def result():
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    return PatternResult(
        analysis=analysis.model_dump(), structure=structure,
        params=CrochetParamsGenerator.generate_params(analysis, structure),
        result_id="followup",
    ).to_result_dict()


def test_yarn_edit_undo_redo_retains_progress(result):
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    next(c for c in at.checkbox if c.key.startswith("chk_")).check().run()
    for label in ("更新材料估算", "↶ 撤销修改", "↷ 重做修改"):
        next(b for b in at.button if b.label == label).click().run()
        assert not at.exception
        assert sum(c.value for c in at.checkbox if c.key.startswith("chk_")) == 1


def test_structure_edit_only_invalidates_changed_part_and_undo_restores(result):
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    for name in ("头部", "手臂"):
        next(c for c in at.checkbox if c.key == f"chk_followup_{name}_0").check().run()
    at.number_input(key="edit_followup_part0_diameter_cm").set_value(11)
    next(b for b in at.button if b.label == "应用部件修改").click().run()
    assert not at.exception
    checked = [c.key for c in at.checkbox if c.key.startswith("chk_") and c.value]
    assert len(checked) == 1 and "手臂" in checked[0]
    next(b for b in at.button if b.label == "↶ 撤销修改").click().run()
    assert not at.exception
    # AppTest can retain stale fragment nodes from the larger pre-undo pattern;
    # inspect only widgets belonging to the installed result.
    rid = at.session_state["result"]["result_id"]
    assert sum(c.value for c in at.checkbox if c.key.startswith(f"chk_{rid}_")) == 2


@pytest.mark.parametrize("instances", [[{"instance_id": "old"}], "broken", [None]])
def test_legacy_graph_fields_rejected_before_import(result, instances):
    result["structure"] = {"parts": [{"name": "头部", "instances": instances}]}
    with pytest.raises(ValueError, match="instances"):
        import_backup(result, "legacy")


def test_plain_legacy_backup_still_renders(result):
    result["structure"] = {"parts": [{"name": "头部"}]}
    restored = import_backup(result, "legacy")
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = restored
    at.run()
    assert not at.exception


@pytest.mark.parametrize("name,craft", [("头部", "无痕收口"), ("手臂", "断线留15cm用于缝合")])
def test_numeric_edit_preserves_finishing_in_export_and_roundtrip(result, name, craft):
    index = next(i for i, p in enumerate(result["params"]["parts"]) if p["name"] == name)
    rounds = deepcopy(result["params"]["parts"][index]["rounds"])
    rounds[-1].update(stitches=rounds[-2]["stitches"], increase=0, decrease=0)
    updated = edit_rounds(result, index, rounds)
    note = updated["params"]["parts"][index]["rounds"][-1]["notes"]
    assert "不加不减" in note and craft in note
    restored = import_backup(PatternResult.from_result(updated).to_backup(), "roundtrip")
    assert restored["params"]["assembly_instructions"] == updated["params"]["assembly_instructions"]
    assert craft in export_markdown(restored["params"], result=restored)


def test_numeric_edit_requires_confirmation_for_unrecognized_instructions(result):
    part = result["params"]["parts"][0]
    part["rounds"][-1]["notes"] = "在背面留开口，填充后用自己的方法缝合"
    rounds = deepcopy(part["rounds"])
    rounds[-1].update(stitches=rounds[-2]["stitches"], increase=0, decrease=0)
    with pytest.raises(ValueError, match="说明"):
        edit_rounds(result, 0, rounds)
    rounds[-1]["notes"] = "12 短针；留开口，填充后缝合"
    updated = edit_rounds(result, 0, rounds)
    assert updated["params"]["parts"][0]["rounds"][-1]["notes"] == rounds[-1]["notes"]


def test_progress_follows_instance_identity_and_gauge_changes_invalidate(result):
    from app.ui.progress_state import capture_progress, install_progress, retained_progress

    state = {"chk_followup_手臂_copy2_0": True}
    progress = capture_progress(result, "result", state)
    updated = deepcopy(result)
    arm = next(p for p in updated["structure"]["parts"] if p["name"] == "手臂")
    arm["instances"].reverse()
    updated["result_id"] = "reordered"
    kept = retained_progress(result, updated, "result", progress)
    destination = {}
    install_progress(updated, "result", kept, destination)
    assert destination == {"chk_reordered_手臂_0": True}
    arm["instances"].pop(0)
    arm["count"] = 1
    next(p for p in updated["params"]["parts"] if p["name"] == "手臂")["quantity"] = 1
    assert retained_progress(result, updated, "result", progress) == {}
    updated = deepcopy(result)
    updated["params"]["gauge"] = {"stitches_per_10cm": 20, "rows_per_10cm": 22}
    assert retained_progress(result, updated, "result", progress) == {}


def test_neighbor_staggering_tracks_preceding_increase_and_can_be_restored(result):
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    assert rounds[3]["notes"] == "(X,V,X)×6"
    rounds[0]["stitches"] = 12
    rounds[1]["stitches"] = 18
    rounds[2]["increase"] = 0
    updated = edit_rounds(result, 0, rounds)
    assert updated["params"]["parts"][0]["rounds"][3]["notes"] == "(2X,V)×6，隔2针加1针"
    restored_rounds = deepcopy(updated["params"]["parts"][0]["rounds"])
    restored_rounds[0]["stitches"] = 6
    restored_rounds[1]["stitches"] = 12
    restored_rounds[2]["increase"] = 6
    restored = edit_rounds(updated, 0, restored_rounds)
    assert restored["params"]["parts"][0]["rounds"][3]["notes"] == "(X,V,X)×6"


def test_neighbor_change_preserves_unchanged_custom_instructions(result):
    custom = "按自己设置的记号安排本圈加针"
    result["params"]["parts"][0]["rounds"][2]["notes"] = custom
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[0]["stitches"] = 12
    rounds[1]["increase"] = 0
    updated = edit_rounds(result, 0, rounds)
    assert updated["params"]["parts"][0]["rounds"][2]["notes"] == custom


@pytest.mark.parametrize("bad_json", [False, True])
def test_history_saves_applied_result_not_unapplied_json_draft(result, monkeypatch, bad_json):
    import json

    from app.ui import result_renderer
    from app.utils import history

    saved = []
    downloads = []
    download_button = result_renderer.st.download_button

    def capture_download(label, data, *args, **kwargs):
        if label == "📥 下载 JSON":
            downloads.append(json.loads(data))
        return download_button(label, data, *args, **kwargs)

    monkeypatch.setattr(result_renderer.st, "download_button", capture_download)
    monkeypatch.setattr(history, "history_enabled", lambda: True)
    monkeypatch.setattr(history, "save_result", lambda data, **kwargs: saved.append(deepcopy(data)))
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    draft = deepcopy(result["params"])
    draft["parts"][0]["rounds"][0]["color"] = "蓝色"
    at.text_area(key="json_edit_followup").input("{broken" if bad_json else json.dumps(draft)).run()
    at.button(key="hist_save_followup").click().run()
    assert not at.exception and not at.error
    assert len(saved) == 1
    assert saved[0]["params"]["parts"] == result["params"]["parts"]
    assert at.session_state["result"] == result
    assert all(data["parts"] == result["params"]["parts"] for data in downloads)
    if not bad_json:
        at.button(key="regen_followup").click().run()
        assert not at.exception and not at.error
        applied = at.session_state["result"]
        # A fresh view also checks persistence independently of stale AppTest
        # fragment nodes left behind when the editor changes result IDs.
        reloaded = AppTest.from_string(RENDER, default_timeout=30)
        reloaded.session_state["result"] = applied
        reloaded.run()
        reloaded.button(key=f"hist_save_{applied['result_id']}").click().run()
        assert not reloaded.exception and not reloaded.error
        assert applied["params"]["parts"][0]["rounds"][0]["color"] == "蓝色"
        assert saved[-1]["params"]["parts"] == applied["params"]["parts"]
        assert downloads[-1]["parts"] == applied["params"]["parts"]


@pytest.mark.parametrize("direction", ["commit", "undo", "redo"])
@pytest.mark.parametrize("failure", ["metrics", "trim_history", "install_progress"])
def test_edit_preparation_failure_preserves_session(result, monkeypatch, direction, failure):
    from app.ui import edit_history

    state = {"result": result, "chk_followup_头部_0": True,
             "export_cache_followup": {"sentinel": "cached"}}
    history = {"current_id": "followup", "undo": [{"result": deepcopy(result)}],
               "redo": [{"result": deepcopy(result)}], "comparison": None}
    state["edit_history_result"] = history
    monkeypatch.setattr(edit_history.st, "session_state", state)
    before = deepcopy(state)

    def fail(*args, **kwargs):
        raise ValueError("injected preparation failure")

    monkeypatch.setattr(edit_history, failure, fail)
    with pytest.raises(ValueError, match="injected"):
        if direction == "commit":
            edit_history.commit_edit("result", result, deepcopy(result))
        else:
            edit_history.restore_edit("result", result, direction)
    assert state == before


def test_accessories_follow_physical_counts(result):
    from app.ui.pattern_editor import edit_structure_part

    idx = next(i for i, p in enumerate(result["structure"]["parts"]) if p["name"] == "头部")
    updated = edit_structure_part(result, idx, count=3, dimensions={})
    materials = {m["item"]: m for m in updated["params"]["materials"]}
    assert materials["安全眼"]["count"] == 3
    assert materials["安全眼"]["quantity"].startswith("3 对")
    assert materials["缝合针"]["count"] == 1
    assert materials["缝合针"]["scope"] == "reusable"


def test_large_progress_has_bounded_widgets_and_survives_page_switch(result):
    from app.ui.progress_state import capture_progress

    part = deepcopy(result["params"]["parts"][0])
    part["quantity"] = 20
    part["rounds"] = [{"row": i + 1, "stitches": 6} for i in range(2000)]
    result["params"]["parts"] = [part]
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert len([c for c in at.checkbox if c.key.startswith("chk_")]) == 50
    first_key = at.checkbox[0].key
    at.checkbox[0].check().run()
    at.selectbox(key="progress_page_followup_0").select(1).run()
    assert not at.exception
    assert len([c for c in at.checkbox if c.key.startswith("chk_")]) == 50
    assert len(capture_progress(result, "result", at.session_state.to_dict())) == 1
    at.selectbox(key="progress_page_followup_0").select(0).run()
    assert at.checkbox(key=first_key).value
    at.checkbox(key=first_key).uncheck().run()
    assert not capture_progress(result, "result", at.session_state.to_dict())
    at.button(key=f"all_followup_{part['name']}").click().run()
    assert len(capture_progress(result, "result", at.session_state.to_dict())) == 40000
    at.button(key=f"clear_followup_{part['name']}").click().run()
    assert not capture_progress(result, "result", at.session_state.to_dict())
