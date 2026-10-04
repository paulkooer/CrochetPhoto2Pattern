"""Reviewed photo generation, reversible edits, single-count yarn, and request budgets."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import DEFAULT, ShapingStyle
from app.models.image_parser import ImageParser
from app.models.materials import YarnSpec, yarn_requirements
from app.models.orchestrator import PipelineOrchestrator
from app.models.photo_review import crop_photo, head_ratio, review_overlay, reviewed_analysis
from app.models.runtime import RunTrace, timed_export
from app.models.structure_designer import StructureDesigner
from app.models.subject import SubjectObservation
from app.schemas import PatternResult
from app.ui.edit_history import MAX_HISTORY_BYTES, MAX_SNAPSHOTS, trim_history
from app.ui.pattern_editor import edit_rounds, edit_structure_part, edit_yarn
from app.ui.result_logic import import_backup, regenerate_with_size
from app.utils.exporters import export_markdown


@pytest.fixture
def result():
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    return PatternResult(
        analysis=analysis.model_dump(),
        structure=structure,
        params=CrochetParamsGenerator.generate_params(analysis, structure),
        result_id="review-test",
    ).to_result_dict()


def test_crop_rejects_empty_and_uses_expected_pixels():
    image = Image.new("RGB", (100, 200), "red")
    cropped = crop_photo(image, (20, 80), (10, 90))
    assert cropped.size == (60, 160)
    assert image.size == (100, 200)
    with pytest.raises(ValueError):
        crop_photo(image, (50, 50), (0, 100))
    with pytest.raises(ValueError):
        crop_photo(image, (0, 1), (0, 100))


def test_review_overlay_does_not_modify_photo_and_ratio_uses_subject_height():
    image = Image.new("RGB", (100, 200), "white")
    subject = SubjectObservation(image)
    mask = np.zeros((200, 100), dtype=bool)
    mask[20:180, 20:80] = True
    subject.__dict__["segmentation"] = (mask, image)
    box = (0.3, 0.1, 0.7, 0.3)
    assert head_ratio(subject, box) == pytest.approx(0.25)
    overlay = review_overlay(subject, box)
    assert overlay.getpixel((30, 20)) == (255, 145, 0)
    assert image.getpixel((30, 20)) == (255, 255, 255)
    with pytest.raises(ValueError):
        head_ratio(subject, (0.2, 0.2, 0.2, 0.4))


def test_review_requires_parts_and_valid_ratio():
    analysis = ImageParser._mock_analysis()
    for parts, ratio in (([], 0.4), (["头部"], float("nan")), (["身体"], 1.1)):
        with pytest.raises(ValueError):
            reviewed_analysis(analysis, parts, ratio)
    revised = reviewed_analysis(analysis, ["头部"], 0.3)
    assert revised.parts == ["头部"]
    assert revised.head_diameter_cm / revised.height_cm == pytest.approx(0.3)
    assert len(analysis.parts) == 4


def test_draft_review_reuses_recognition_and_excludes_user_wait(monkeypatch):
    orch = PipelineOrchestrator()
    calls = []
    monkeypatch.setattr(
        orch.parser, "parse_image_mock", lambda: calls.append("recognize") or ImageParser._mock_analysis()
    )
    clock = [10.0]
    monkeypatch.setattr("app.models.runtime.time.monotonic", lambda: clock[0])
    draft = orch.prepare_photo(Image.new("RGB", (80, 160)), vision_mode="mock", budget_seconds=30)
    clock[0] += 3600  # User can inspect for an hour; active-time budget is still available.
    edited = reviewed_analysis(draft.analysis, ["头部", "身体"], 0.3)
    first = orch.generate_from_draft(draft, analysis=edited, target_height_cm=20)
    second = orch.generate_from_draft(draft, analysis=edited, target_height_cm=30)
    assert calls == ["recognize"]
    assert first["analysis"]["height_cm"] == 20
    assert second["analysis"]["height_cm"] == 30
    assert first["vision_meta"]["reviewed_by_user"] is True
    assert not hasattr(draft, "parser") and not hasattr(draft, "openai_key")
    assert len(draft.trace.stages) < len(first["diagnostics"]["stages"])


def test_budget_records_failed_stage_and_does_not_start_next(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.models.runtime.time.monotonic", lambda: clock[0])
    trace = RunTrace(1)
    with pytest.raises(TimeoutError), trace.stage("geometry"):
        clock[0] = 2
    assert trace.payload()["stages"] == [{"stage": "geometry", "seconds": 2, "status": "failed"}]
    with pytest.raises(TimeoutError), trace.stage("vision"):
        pytest.fail("must not start")


def test_export_failure_keeps_input_and_reports_duration(result):
    before = deepcopy(result)
    record = {}

    def fail():
        raise ValueError("export failed")

    with pytest.raises(ValueError):
        timed_export(record, "pdf", fail)
    assert result == before
    assert record["diagnostics"]["exports"]["pdf"]["stages"][0]["status"] == "failed"


def _response(provider, input_tokens=100, output_tokens=20):
    usage = (
        SimpleNamespace(prompt_tokens=input_tokens, completion_tokens=output_tokens)
        if provider == "openai"
        else SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    )
    return SimpleNamespace(usage=usage)


def test_request_ledger_counts_retry_refusal_and_fallback(monkeypatch, caplog):
    parser = ImageParser(openai_key="private-key", anthropic_key="private-key")
    tries = []

    class TransientError(Exception):
        status_code = 429

    def transient(**kwargs):
        tries.append(kwargs["timeout"])
        if len(tries) == 1:
            raise TransientError("private-key secret image base64")
        return _response("anthropic", 300, 60)

    parser._request("anthropic", transient, model="claude")
    parser._mark_attempt("refused")
    parser._request("openai", lambda **kw: _response("openai", 200, 40), model="gpt")
    parser._mark_attempt("success")
    usage = parser.last_usage
    assert len(usage["attempts"]) == 3
    assert [a["status"] for a in usage["attempts"]] == ["failed", "refused", "success"]
    assert usage["input_tokens"] == 500 and usage["output_tokens"] == 100
    assert usage["provider"] == "multiple" and usage["usage_complete"] is False
    assert usage["attempts"][0]["input_tokens"] is None
    assert "private-key" not in str(usage) + caplog.text
    assert "base64" not in str(usage) + caplog.text


def test_api_request_timeout_uses_remaining_budget_and_prevents_extra_calls(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.models.image_parser.time.monotonic", lambda: clock[0])
    parser = ImageParser(openai_key="x")
    parser._request_deadline = 3.0

    def late(**kwargs):
        assert kwargs["timeout"] == 3
        clock[0] = 4
        return _response("openai")

    with pytest.raises(TimeoutError):
        parser._request("openai", late, model="test")
    assert len(parser.last_usage["attempts"]) == 1
    assert parser.last_usage["input_tokens"] == 100  # Returned usage is retained, even for a late response.
    assert parser.last_usage["attempts"][0]["status"] == "failed"


def test_local_and_mock_clear_old_billing(monkeypatch):
    parser = ImageParser()
    parser._request("openai", lambda **kw: _response("openai"), model="test")
    parser.parse_image_mock()
    assert parser.last_usage == {}
    parser._request("openai", lambda **kw: _response("openai"), model="test")
    monkeypatch.setattr("app.models.local_vision.analyze", lambda *a, **k: (ImageParser._mock_analysis(), {}))
    parser.parse_image_local(Image.new("RGB", (40, 40)))
    assert parser.last_usage == {}


@pytest.mark.parametrize("one_piece", [False, True])
def test_yarn_single_count_even_for_one_piece(one_piece):
    analysis = ImageParser._mock_analysis()
    params = CrochetParamsGenerator.generate_params(
        analysis, StructureDesigner.design_3d_structure(analysis), style=ShapingStyle(one_piece=one_piece)
    )
    rows = [m for m in params["materials"] if "stitches" in m]
    assert sum(r["stitches"] for r in rows) == params["total_stitches"]
    assert len({r["color"] for r in rows}) == len(rows)
    assert params["material_summary"]["grams"] == pytest.approx(sum(r["grams"] for r in rows))
    assert not {"肤色系毛线", "主体色毛线"} & {r["item"] for r in params["materials"]}


def test_measured_yarn_and_ball_rounding():
    parts = [
        {
            "name": "身体",
            "quantity": 2,
            "color": "红色",
            "rounds": [{"stitches": 100}, {"stitches": 100, "color": "蓝色"}],
        }
    ]
    spec = {
        "ball_weight_g": 50,
        "ball_length_m": 100,
        "swatch_weight_g": 10,
        "swatch_stitches": 10,
        "swatch_rows": 10,
        "waste_percent": 10,
    }
    rows, summary = yarn_requirements(parts, DEFAULT, spec)
    assert [r["grams"] for r in rows] == [22, 22]
    assert summary["grams"] == 44 and summary["meters"] == 88
    assert summary["balls"] == 2 and summary["basis"] == "measured_swatch"


@pytest.mark.parametrize(
    "updates",
    [{"ball_length_m": float("inf")}, {"swatch_weight_g": 5}, {"ball_weight_g": 0}, {"swatch_rows": True}],
)
def test_invalid_yarn_spec_rejected(updates):
    with pytest.raises(ValueError):
        YarnSpec.model_validate({"ball_weight_g": 50, "ball_length_m": 100, **updates})


def test_yarn_spec_survives_resize_and_backup(result):
    original = deepcopy(result)
    updated = edit_yarn(
        result,
        {
            "ball_weight_g": 50,
            "ball_length_m": 100,
            "swatch_weight_g": 3,
            "swatch_stitches": 20,
            "swatch_rows": 10,
        },
    )
    resized = regenerate_with_size(updated, 10, 22)
    imported = import_backup(PatternResult.from_result(resized).to_backup(), "restored")
    assert imported["params"]["yarn_spec"] == updated["params"]["yarn_spec"]
    assert imported["params"]["material_summary"]["basis"] == "measured_swatch"
    assert result == original


def test_structure_quantity_position_and_attachment_edit(result):
    original = deepcopy(result)
    parts = result["structure"]["parts"]
    arm_idx = next(i for i, p in enumerate(parts) if p["name"] == "手臂")
    body_id = next(p["part_id"] for p in parts if p["name"] == "身体")
    attachment = [
        {"target_part_id": body_id, "self_anchor": "top", "target_anchor": "front", "method": "sewn"}
    ]
    updated = edit_structure_part(
        result,
        arm_idx,
        count=3,
        dimensions={"length_cm": 5},
        position={"x": 0.2, "y": 0.5, "z": 0.1},
        attachments=attachment,
    )
    arm = updated["structure"]["parts"][arm_idx]
    assert len(arm["instances"]) == arm["count"] == 3
    assert arm["instances"][0]["attachments"] == attachment
    assert arm["instances"][0]["position"]["x"] == 0.2
    assert next(p for p in updated["params"]["parts"] if p["name"] == "手臂")["quantity"] == 3
    shrunk = edit_structure_part(updated, arm_idx, count=1, dimensions={})
    assert len(shrunk["structure"]["parts"][arm_idx]["instances"]) == 1
    assert result == original


def test_bad_round_edit_does_not_modify_input(result):
    before = deepcopy(result)
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[1]["stitches"] += 5  # Violates increase/decrease arithmetic.
    with pytest.raises(ValueError):
        edit_rounds(result, 0, rounds)
    assert result == before
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[0]["color"] = "红色"
    updated = edit_rounds(result, 0, rounds)
    assert any(r.get("color") == "红色" for r in updated["params"]["materials"])


def test_history_bounded_by_count_and_total_bytes():
    history = {"undo": [{"i": i} for i in range(30)], "redo": []}
    trim_history(history)
    assert len(history["undo"]) == MAX_SNAPSHOTS
    assert history["undo"][-1]["i"] == 29
    history["redo"].append({"large": "x" * MAX_HISTORY_BYTES})
    trim_history(history)
    assert not history["undo"] and not history["redo"]


def test_undo_redo_ui_and_new_edit_discards_redo(result):
    script = """
import streamlit as st
from app.ui.pattern_editor import render_pattern_editor
render_pattern_editor(st.session_state.result, "result")
"""
    at = AppTest.from_string(script, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert at.button(key="edit_review-test_undo").disabled
    at.number_input(key="edit_review-test_part0_diameter_cm").set_value(11)
    next(b for b in at.button if b.label == "应用部件修改").click().run()
    assert not at.exception
    changed = at.session_state["result"]
    assert changed["structure"]["parts"][0]["diameter_cm"] == 11
    rid = changed["result_id"]
    at.button(key=f"edit_{rid}_undo").click().run()
    assert at.session_state["result"]["structure"] == result["structure"]
    restored_id = at.session_state["result"]["result_id"]
    at.button(key=f"edit_{restored_id}_redo").click().run()
    assert at.session_state["result"]["structure"] == changed["structure"]
    rid = at.session_state["result"]["result_id"]
    at.button(key=f"edit_{rid}_undo").click().run()
    rid = at.session_state["result"]["result_id"]
    at.number_input(key=f"edit_{rid}_part0_diameter_cm").set_value(12)
    next(b for b in at.button if b.label == "应用部件修改").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert at.button(key=f"edit_{rid}_redo").disabled


def test_invalid_diagnostics_are_rejected_on_import(result):
    result["diagnostics"] = {"stages": [{"stage": "vision", "seconds": float("nan"), "status": "failed"}]}
    with pytest.raises(ValueError):
        import_backup(result, "bad")


def test_export_lists_yarn_once_with_summary(result):
    md = export_markdown(result["params"], result["analysis"], result=result)
    assert "肤色系毛线" not in md and "主体色毛线" not in md
    assert "小计已含" in md


def test_photo_review_ui_generates_without_new_recognition(monkeypatch):
    draft = PipelineOrchestrator().prepare_photo(Image.new("RGB", (80, 160)), vision_mode="mock")

    def forbidden(*a, **kw):
        pytest.fail("review must never call a vision provider")

    monkeypatch.setattr(ImageParser, "parse_image", forbidden)
    monkeypatch.setattr(ImageParser, "parse_image_mock", forbidden)
    script = """
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
result = render_photo_review(st.session_state.draft, "draft", gauge=DEFAULT,
                             style=DEFAULT_STYLE, target_height=24)
if result is not None:
    st.session_state.generated = result
"""
    at = AppTest.from_string(script, default_timeout=30)
    at.session_state["draft"] = draft
    at.run()
    assert not at.exception
    at.number_input(key="review_ratio_draft").set_value(0.3).run()
    at.multiselect(key="review_parts_draft").set_value(["头部", "身体"]).run()
    at.button(key="review_generate_draft").click().run()
    assert not at.exception
    generated = at.session_state["generated"]
    assert generated["analysis"]["parts"] == ["头部", "身体"]
    assert generated["analysis"]["height_cm"] == 24
    assert generated["vision_meta"]["source"] == "mock"
    assert generated["vision_meta"]["reviewed_by_user"] is True
    assert generated["vision_meta"]["body_ratio"] == pytest.approx(3.333)
    at.checkbox(key="review_box_draft").check().run()
    at.slider(key="review_hx_draft").set_value((40, 40)).run()
    assert not at.exception
    assert at.error
    assert at.session_state["generated"] == generated


def test_one_piece_preserves_matching_quantities_and_rejects_mismatch():
    from app.models.onepiece import merge_head_body
    from app.schemas import CrochetPart

    analysis = ImageParser._mock_analysis()
    params = CrochetParamsGenerator.generate_params(analysis, StructureDesigner.design_3d_structure(analysis))
    parts = [CrochetPart(**p) for p in params["parts"]]
    for part in parts:
        if part.name in ("头部", "身体"):
            part.quantity = 3
    merged = merge_head_body(parts, DEFAULT)
    assert merged[0].quantity == 3
    next(p for p in parts if p.name == "身体").quantity = 2
    with pytest.raises(ValueError, match="数量相同"):
        merge_head_body(parts, DEFAULT)


def test_yarn_form_applies_measured_inputs_and_undo(result):
    script = """
import streamlit as st
from app.ui.pattern_editor import render_pattern_editor
render_pattern_editor(st.session_state.result, "result")
"""
    at = AppTest.from_string(script, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.checkbox(key="edit_review-test_measured").check()
    at.number_input(key="edit_review-test_swatchweight").set_value(2)
    next(b for b in at.button if b.label == "更新材料估算").click().run()
    assert not at.exception
    changed = at.session_state["result"]
    assert changed["params"]["yarn_spec"]["swatch_weight_g"] == 2
    assert changed["params"]["material_summary"]["basis"] == "measured_swatch"
    rid = changed["result_id"]
    at.button(key=f"edit_{rid}_undo").click().run()
    assert not at.exception
    assert at.session_state["result"]["params"] == result["params"]


def test_photo_tab_crop_mode_invalidation_and_failure_preserves_result(monkeypatch, result):
    import io

    from app.ui import tab_photo

    uploaded = io.BytesIO(b"synthetic-photo-upload")
    monkeypatch.setattr(tab_photo.st, "file_uploader", lambda *a, **k: uploaded)
    monkeypatch.setattr(tab_photo, "load_uploaded_image_cached", lambda _: Image.new("RGB", (100, 200)))
    orch = PipelineOrchestrator()
    calls = []
    prepare = orch.prepare_photo

    def prepare_record(image, **kwargs):
        calls.append(image.size)
        return prepare(image, **kwargs)

    monkeypatch.setattr(orch, "prepare_photo", prepare_record)
    monkeypatch.setattr(tab_photo, "_build_orchestrator", lambda: orch)
    # Keep this test focused on upload/review transitions; result rendering is tested separately.
    monkeypatch.setattr(tab_photo, "render_results", lambda *a, **kw: None)
    at = AppTest.from_string(
        "from app.ui.tab_photo import render_tab_photo\nrender_tab_photo()", default_timeout=30
    )
    at.session_state["result"] = deepcopy(result)
    at.run()
    at.radio(key="vision_mode").set_value("🎬 Mock 演示数据").run()
    at.slider(key="crop_x").set_value((20, 80)).run()
    at.button(key="btn_photo").click().run()
    assert not at.exception
    assert calls == [(60, 200)]
    draft_id = at.session_state["photo_draft"][2]
    at.slider(key="photo_target_height").set_value(24).run()
    assert at.session_state["photo_draft"][2] == draft_id
    assert len(calls) == 1
    at.button(key=f"review_generate_{draft_id}").click().run()
    assert not at.exception
    generated = deepcopy(at.session_state["result"])
    assert generated["analysis"]["height_cm"] == 24
    at.slider(key="crop_y").set_value((10, 90)).run()
    assert "photo_draft" not in at.session_state
    assert at.session_state["result"] == generated

    def fail_build():
        raise ValueError("configuration rejected")

    monkeypatch.setattr(tab_photo, "_build_orchestrator", fail_build)
    at.button(key="btn_photo").click().run()
    assert not at.exception and at.error
    assert at.session_state["result"] == generated


def test_numeric_round_edit_refreshes_obsolete_instructions(result):
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[0]["stitches"] = 12
    rounds[1]["increase"] = 0
    updated = edit_rounds(result, 0, rounds)
    changed = updated["params"]["parts"][0]["rounds"]
    assert "12" in changed[0]["notes"]
    assert changed[1]["notes"] == "12X（不加不减）"
    assert changed[2]["notes"] == rounds[2]["notes"]
