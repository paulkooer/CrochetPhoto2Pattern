"""Cross-boundary regressions for reviewed intent and printable instructions."""
from copy import deepcopy

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.models.orchestrator import PipelineOrchestrator
from app.models.photo_review import reviewed_analysis
from app.models.structure_designer import StructureDesigner
from app.models.validator import validate_pattern
from app.schemas import PatternResult
from app.ui.pattern_editor import edit_rounds
from app.ui.result_logic import import_backup, regenerate_with_size
from app.utils.exporters import export_markdown


def draft():
    return PipelineOrchestrator().prepare_photo(Image.new("RGB", (100, 200)), vision_mode="mock")


def test_reviewed_removal_survives_generation_export_and_resize():
    original = draft()
    original.analysis.clothing_type = "连衣裙"
    chosen = reviewed_analysis(original.analysis, ["头部", "身体"], 0.5)
    assert "裙子" in [p["name"] for p in StructureDesigner.design_3d_structure(chosen)["parts"]]
    result = PipelineOrchestrator.generate_from_draft(original, analysis=chosen)
    restored = import_backup(PatternResult.from_result(result).to_backup(), "reviewed")
    resized = regenerate_with_size(restored, 10, 20)
    for output in (result, restored, resized):
        assert {p["name"] for p in output["structure"]["parts"]} == {"头部", "身体"}
        assert {p["name"] for p in output["params"]["parts"]} == {"头部", "身体"}
        assert "裙子" not in export_markdown(output["params"], result=output)
    assert original.analysis.clothing_type == "连衣裙"


@pytest.mark.parametrize("note", ["不加不减，共 999 针", "不加不减，共 12 针", "999 短针"])
def test_contradictory_notes_rejected_at_edit_import_and_export(note):
    result = PipelineOrchestrator.generate_from_draft(draft())
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[1]["notes"] = note
    with pytest.raises(ValueError, match="说明"):
        edit_rounds(result, 0, rounds)
    result["params"]["parts"][0]["rounds"] = rounds
    assert not validate_pattern(result["params"])["ok"]
    with pytest.raises(ValueError, match="说明"):
        import_backup(PatternResult.from_result(result).to_backup(), "invalid")
    with pytest.raises(ValueError, match="说明"):
        export_markdown(result["params"], result=result)


def test_custom_finishing_note_is_not_interpreted_as_stitch_total():
    result = PipelineOrchestrator.generate_from_draft(draft())
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[1]["notes"] = "按自己的记号安排加针；留线 999 cm，后续共 999 针"
    updated = edit_rounds(result, 0, rounds)
    assert validate_pattern(updated["params"])["ok"]
    assert updated["params"]["parts"][0]["rounds"][1]["notes"] == rounds[1]["notes"]


def test_head_box_updates_color_span_without_mutating_recognition(monkeypatch):
    original = draft()
    original.spans = {"头部": (0.05, 0.3), "身体": (0.3, 0.6)}
    original.spans_measured = ["头部", "身体"]
    monkeypatch.setattr("app.models.color_design.vertical_color_bands", lambda *args, **kwargs: [
        {"start": 0.0, "end": 0.2, "color": "蓝色"},
        {"start": 0.2, "end": 0.5, "color": "红色"},
        {"start": 0.5, "end": 1.0, "color": "蓝色"},
    ])
    captured = []
    generate = PipelineOrchestrator.generate_from_draft

    def capture(reviewed, **kwargs):
        captured.append(generate(reviewed, **kwargs))
        return None

    monkeypatch.setattr(PipelineOrchestrator, "generate_from_draft", capture)
    at = AppTest.from_string('''
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
render_photo_review(st.session_state.draft, "box", gauge=DEFAULT,
                    style=DEFAULT_STYLE, target_height=18)
''', default_timeout=20)
    at.session_state["draft"] = original
    at.run()
    at.radio(key="review_subject_box").set_value("单个玩偶，所需部件可用下方列表表达").run()
    at.checkbox(key="review_box_box").check().run()
    at.slider(key="review_hy_box").set_value((20, 50)).run()
    at.button(key="review_generate_box").click().run()
    assert not at.exception
    assert len(captured) == 1
    result = captured[0]
    head = next(p for p in result["params"]["parts"] if p["name"] == "头部")
    assert {r["color"] for r in head["rounds"]} == {"红色"}
    assert result["spans"]["头部"] == (0.2, 0.5)
    assert result["spans"]["身体"] == (0.3, 0.6)
    assert "头部" not in result["spans_measured"]
    assert original.spans["头部"] == (0.05, 0.3)
    restored = import_backup(PatternResult.from_result(result).to_backup(), "box")
    assert tuple(restored["spans"]["头部"]) == (0.2, 0.5)
    assert tuple(regenerate_with_size(restored, 9, 20)["spans"]["头部"]) == (0.2, 0.5)


@pytest.mark.parametrize("note", ["下一圈共 18 针", "两圈总计 24 针", "如果共 18 针则重新计数",
                                 "不加不减的圈完成后，下一圈共 18 针"])
def test_prose_about_other_rounds_does_not_block_valid_export(note):
    result = PipelineOrchestrator.generate_from_draft(draft())
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[1]["notes"] = note
    updated = edit_rounds(result, 0, rounds)
    assert note in export_markdown(updated["params"], result=updated)


@pytest.mark.parametrize("note", ["按记号加针；共 999 针", "魔法环起 999 针（X×999）",
                                 "共 " + "9" * 5000 + " 针"])
def test_explicit_contradictions_including_long_numbers_return_issues(note):
    params = {"parts": [{"name": "头部", "rounds": [{"stitches": 6, "notes": note}]}]}
    result = validate_pattern(params)
    assert not result["ok"]
    assert "说明" in result["issues"][0]


def test_unknown_semantics_require_review_but_existing_explicit_structure_survives():
    original = draft()
    original.analysis.parts = ["头部", "翅膀"]
    with pytest.raises(ValueError, match="翅膀"):
        PipelineOrchestrator.generate_from_draft(original)
    chosen = reviewed_analysis(original.analysis, ["头部"], 0.5)
    result = PipelineOrchestrator.generate_from_draft(original, analysis=chosen)
    # Previously authored custom geometry is not reinterpreted by the template designer.
    result["analysis"]["parts"] = ["自制附件"]
    result["structure"]["parts"][0]["name"] = "自制附件"
    result["params"]["parts"][0]["name"] = "自制附件"
    restored = import_backup(PatternResult.from_result(result).to_backup(), "custom")
    assert restored["params"]["parts"][0]["name"] == "自制附件"
    assert "自制附件" in export_markdown(restored["params"], result=restored)


def test_review_ui_blocks_unknown_and_empty_parts_until_corrected(monkeypatch):
    original = draft()
    original.analysis.parts = ["头部", "双手"]
    captured = []
    monkeypatch.setattr(PipelineOrchestrator, "generate_from_draft",
                        lambda reviewed, **kwargs: captured.append(kwargs["analysis"].parts))
    at = AppTest.from_string('''
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
render_photo_review(st.session_state.draft, "unknown", gauge=DEFAULT,
                    style=DEFAULT_STYLE, target_height=18)
''', default_timeout=20)
    at.session_state["draft"] = original
    at.run()
    at.radio(key="review_subject_unknown").set_value("单个玩偶，所需部件可用下方列表表达").run()
    assert at.button(key="review_generate_unknown").disabled
    assert any("双手" in warning.value for warning in at.warning)
    at.multiselect(key="review_parts_unknown").set_value([]).run()
    assert at.button(key="review_generate_unknown").disabled
    at.multiselect(key="review_parts_unknown").set_value(["头部", "手臂"]).run()
    assert not at.button(key="review_generate_unknown").disabled
    at.button(key="review_generate_unknown").click().run()
    assert not at.exception
    assert captured == [["头部", "手臂"]]
    assert original.analysis.parts == ["头部", "双手"]
