"""Crochetability floors: block degenerate first generations, warn on existing work."""
import json

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app import cli
from app.models.crochet_params import CrochetParamsGenerator
from app.models.crochetability import (
    PatternCrochetabilityError,
    crochetability_advice,
    crochetability_findings,
    first_passing,
    require_crochetable,
    widest_rounds,
)
from app.models.gauge import PRESETS, Gauge, ShapingStyle
from app.models.orchestrator import PipelineOrchestrator
from app.models.parts import _ONE_PIECE_NAME, ONE_PIECE_NECK_MARKER
from app.models.photo_review import reviewed_analysis
from app.models.sizing import scale_analysis_to_target_height
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis

_DEFAULT_PARTS = ["头部", "身体", "手臂", "腿部"]


def _analysis(head_ratio: float, parts=None) -> ImageAnalysis:
    return ImageAnalysis(body_type="标准", head_diameter_cm=18 * head_ratio, height_cm=18,
                         main_features=[], pose="站立", difficulty="easy",
                         parts=parts or _DEFAULT_PARTS)


def _params(head_ratio: float, *, target: float = 18, gauge: Gauge = PRESETS["classic"], style=None):
    analysis, _ = scale_analysis_to_target_height(_analysis(head_ratio), target, source="test")
    structure = StructureDesigner.design_3d_structure(analysis, infer_missing_parts=False)
    return CrochetParamsGenerator.generate_params(analysis, structure, gauge=gauge,
                                                  style=style or ShapingStyle())


def _levels(params):
    return {(f.part, f.level, f.peak_stitches) for f in crochetability_findings(params)}


def test_default_settings_flag_photo_ratios_that_degenerate():
    # 默认 classic 密度、18 cm：Q 版比例无提示，写实比例生成 6–12 针的头和身体
    assert _levels(_params(1 / 2)) == set()
    assert _levels(_params(1 / 3)) == {("手臂", "note", 6), ("腿部", "note", 6)}
    assert {("头部", "warn", 18), ("身体", "warn", 18)} <= _levels(_params(1 / 4))
    assert {("头部", "block", 12), ("身体", "block", 12)} <= _levels(_params(1 / 5))
    eight = _params(1 / 8)
    assert {("头部", "block", 6), ("身体", "block", 6)} <= _levels(eight)
    with pytest.raises(PatternCrochetabilityError, match="头部最宽一圈只有 6 针"):
        require_crochetable(eight)


def test_denser_gauge_makes_the_same_proportions_crochetable():
    assert not [f for f in crochetability_findings(_params(1 / 5, gauge=PRESETS["fine"]))
                if f.level == "block"]


def test_one_piece_checks_head_section_above_neck_marker():
    wide_body = [{"row": i + 1, "stitches": n, "notes": "X"} for i, n in enumerate(
        [6, 12, 12, 6, 12, 18, 24, 30, 30, 24])]
    wide_body[3]["notes"] = f"A×6；{ONE_PIECE_NECK_MARKER}，不断线直接钩身体"
    part = {"name": _ONE_PIECE_NAME, "type": "onepiece", "rounds": wide_body}
    assert _levels({"parts": [part]}) == {(_ONE_PIECE_NAME, "block", 12)}
    assert widest_rounds({"parts": [part]}) == [(_ONE_PIECE_NAME, 30)]
    # 没有颈部标记（手写或旧数据）时退回整件最宽圈，不臆测头部段
    for row in wide_body:
        row["notes"] = "X"
    assert _levels({"parts": [part]}) == set()


def test_generated_one_piece_keeps_the_neck_marker():
    params = _params(1 / 5, style=ShapingStyle(one_piece=True))
    merged = next(p for p in params["parts"] if p["name"] == _ONE_PIECE_NAME)
    assert sum(ONE_PIECE_NECK_MARKER in r["notes"] for r in merged["rounds"]) == 1
    assert (_ONE_PIECE_NAME, "block", 12) in _levels(params)


def test_unknown_parts_and_malformed_rounds_are_not_guessed():
    params = {"parts": [{"name": "翅膀", "rounds": [{"row": 1, "stitches": 6}]},
                        {"name": "头部", "rounds": [{"row": 1, "stitches": "6"}]}, "bad"]}
    assert crochetability_findings(params) == []


def test_first_passing_returns_the_smallest_checked_value():
    checked = []

    def passes(value):
        checked.append(value)
        return value >= 7

    assert first_passing(list(range(1, 11)), passes) == 7
    assert 7 in checked and len(checked) <= 5
    assert first_passing([1, 2, 3], lambda _: False) is None
    assert first_passing([], lambda _: True) is None


def _photo_build(draft, analysis):
    def build(height, ratio, gauge):
        return PipelineOrchestrator.preview_params(
            draft, analysis=reviewed_analysis(analysis, analysis.parts, ratio), gauge=gauge,
            style=ShapingStyle(), target_height_cm=height)
    return build


def _draft():
    return PipelineOrchestrator().prepare_photo(Image.new("RGB", (80, 160)), vision_mode="local")


def _blocked(params):
    return any(f.level == "block" for f in crochetability_findings(params))


def test_advice_values_are_exact_single_change_boundaries():
    draft = _draft()
    analysis = reviewed_analysis(draft.analysis, _DEFAULT_PARTS, 1 / 5)
    build = _photo_build(draft, analysis)
    classic = PRESETS["classic"]
    assert _blocked(build(18, 0.2, classic))
    advice = crochetability_advice(build, gauge=classic, level="block", size=18, size_max=60,
                                   ratio=0.2, ratio_max=0.5)
    assert advice.size is not None and advice.ratio is not None
    assert not _blocked(build(advice.size, 0.2, classic))
    assert _blocked(build(advice.size - 0.5, 0.2, classic))
    assert not _blocked(build(18, advice.ratio, classic))
    assert _blocked(build(18, round(advice.ratio - 0.01, 2), classic))
    assert advice.presets == ("dk", "fine")
    # 提示级别的建议要求连警告也消失
    warn = crochetability_advice(build, gauge=classic, level="warn", size=18, size_max=60,
                                 ratio=0.2, ratio_max=0.5)
    assert warn.size is not None and advice.size is not None and warn.size > advice.size
    assert crochetability_advice(build, gauge=PRESETS["fine"], level="block", size=60, size_max=60,
                                 ratio=0.5, ratio_max=0.5).presets == ()


def test_preview_matches_generation_and_generation_enforces_the_gate():
    draft = _draft()
    feasible = reviewed_analysis(draft.analysis, _DEFAULT_PARTS, 0.45)
    preview = PipelineOrchestrator.preview_params(draft, analysis=feasible, target_height_cm=20)
    result = PipelineOrchestrator.generate_from_draft(draft, analysis=feasible, target_height_cm=20)
    assert ([[r["stitches"] for r in p["rounds"]] for p in preview["parts"]]
            == [[r["stitches"] for r in p["rounds"]] for p in result["params"]["parts"]])

    tiny = reviewed_analysis(draft.analysis, _DEFAULT_PARTS, 0.125)
    with pytest.raises(PatternCrochetabilityError, match="低于 18 针下限"):
        PipelineOrchestrator.generate_from_draft(draft, analysis=tiny)
    unchecked = PipelineOrchestrator.generate_from_draft(draft, analysis=tiny, enforce_crochetability=False)
    assert _blocked(unchecked["params"])


def test_cli_rejects_degenerate_manual_dimensions_before_writing(tmp_path, capsys):
    output = tmp_path / "pattern.json"
    assert cli.main(["--parts", "头部,身体", "--head", "3", "--height", "18",
                     "--out", str(output), "--quiet"]) == 2
    err = capsys.readouterr().err
    assert "可钩性检查未通过" in err and "可增大 --head、" in err and "--gauge dk / fine" in err
    assert "--height" not in err and "Traceback" not in err
    assert not output.exists()


def test_cli_photo_mode_points_to_target_height(tmp_path, monkeypatch, capsys):
    source = tmp_path / "photo.png"
    Image.new("RGB", (80, 160)).save(source)
    # 默认比例 1:2；目标 10 cm、最粗密度时头部只有 12 针
    assert cli.main(["--image", str(source), "--height", "10", "--gauge", "custom",
                     "--stitches", "6", "--rows", "8", "--out", str(tmp_path / "p.json"), "--quiet"]) == 2
    err = capsys.readouterr().err
    assert "可增大 --height、" in err and "在界面确认头身比例" in err


def test_cli_prints_notes_for_thin_tubes(tmp_path, capsys):
    output = tmp_path / "pattern.json"
    assert cli.main(["--head", "6", "--height", "18", "--out", str(output)]) == 0
    assert "提示：手臂是 6 针细管" in capsys.readouterr().err
    assert json.loads(output.read_text(encoding="utf-8"))["params"]["parts"]


_REVIEW_SCRIPT = '''
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
render_photo_review(st.session_state.draft, "test", gauge=DEFAULT,
                    style=DEFAULT_STYLE, target_height=18)
'''


def test_photo_review_shows_counts_and_disables_degenerate_generation(monkeypatch):
    calls = []
    monkeypatch.setattr(PipelineOrchestrator, "generate_from_draft",
                        lambda draft, **kwargs: calls.append(kwargs) or {"generated": True})
    at = AppTest.from_string(_REVIEW_SCRIPT)
    at.session_state["draft"] = _draft()
    at.run()
    at.radio(key="review_subject_test").set_value("单个玩偶，所需部件可用下方列表表达").run()
    assert not at.button(key="review_generate_test").disabled
    assert any("各部件最宽一圈：头部 36 针" in c.value for c in at.caption)

    at.number_input(key="review_ratio_test").set_value(0.2).run()
    assert at.button(key="review_generate_test").disabled
    assert any("头部最宽一圈只有 12 针" in e.value for e in at.error)
    advice = " ".join(i.value for i in at.info)
    assert "目标成品高度提高到" in advice and "头径／主体高度提高到" in advice and "DK 中粗" in advice
    assert not calls

    at.number_input(key="review_ratio_test").set_value(0.5).run()
    at.button(key="review_generate_test").click().run()
    assert not at.exception and len(calls) == 1


_MANUAL_SCRIPT = '''
from app.ui.tab_manual import render_tab_manual
render_tab_manual()
'''


def test_manual_tab_disables_generation_until_dimensions_are_crochetable():
    at = AppTest.from_string(_MANUAL_SCRIPT)
    at.session_state["gauge_preset"] = "custom"
    at.session_state["gauge_st_input"] = 8.0
    at.session_state["gauge_rw_input"] = 10.0
    at.run()
    at.slider(key="m_head_d").set_value(4.0).run()
    assert at.button(key="btn_manual").disabled
    assert any("头部最宽一圈只有 12 针" in e.value for e in at.error)
    advice = " ".join(i.value for i in at.info)
    assert "头部直径提高到 6 cm" in advice and "经典图解(粗线)" in advice

    at.slider(key="m_head_d").set_value(6.0).run()
    assert not at.button(key="btn_manual").disabled
    at.button(key="btn_manual").click().run()
    assert not at.exception and "manual_result" in at.session_state


def test_existing_degenerate_pattern_renders_with_warning_not_error():
    from tests.test_app_smoke import _APP, _mock_result

    analysis, _ = scale_analysis_to_target_height(_analysis(1 / 5), 18, source="test")
    structure = StructureDesigner.design_3d_structure(analysis, infer_missing_parts=False)
    result = _mock_result("tiny-import")
    result.update(analysis=analysis.model_dump(), structure=structure,
                  params=CrochetParamsGenerator.generate_params(analysis, structure))
    at = AppTest.from_file(_APP, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert any("可钩性提示：头部最宽一圈只有 12 针" in w.value for w in at.warning)
