"""Q-style proportion mapping and the face-to-head box prior."""
import json

import pytest
from PIL import Image
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from app import cli
from app.models.crochetability import crochetability_findings
from app.models.local_vision import analyze, head_box_from_face
from app.models.orchestrator import PipelineOrchestrator
from app.models.photo_review import reviewed_analysis
from app.models.result_metadata import validate_result_metadata
from app.models.sizing import PROPORTION_STYLES, scale_analysis_to_target_height, styled_body_ratio
from app.schemas import ImageAnalysis

_PARTS = ["头部", "身体", "手臂", "腿部"]


def _analysis(body_ratio: float) -> ImageAnalysis:
    return ImageAnalysis(body_type="标准", head_diameter_cm=18 / body_ratio, height_cm=18,
                         main_features=[], pose="站立", difficulty="easy", parts=_PARTS)


@pytest.mark.parametrize("photo,q,balanced", [(8, 3.0, 4.5), (5, 2.5, 3.25), (2, 2.0, 2.0),
                                              (10, 3.0, 4.5), (1.5, 2.0, 2.0)])
def test_styles_compress_photo_ratios_into_doll_ranges(photo, q, balanced):
    assert styled_body_ratio(photo, "q") == pytest.approx(q)
    assert styled_body_ratio(photo, "balanced") == pytest.approx(balanced)
    assert styled_body_ratio(photo, "photo") == pytest.approx(min(max(photo, 2), 8))


def test_styles_are_monotone_and_ordered():
    ratios = [2 + i * 0.25 for i in range(25)]
    for style in PROPORTION_STYLES:
        mapped = [styled_body_ratio(r, style) for r in ratios]
        assert mapped == sorted(mapped)
    assert all(styled_body_ratio(r, "q") <= styled_body_ratio(r, "balanced") <= styled_body_ratio(r, "photo")
               for r in ratios)
    with pytest.raises(ValueError, match="头身比例风格"):
        styled_body_ratio(4, "chibi")


def test_scaling_records_photo_ratio_and_applied_style():
    q, q_meta = scale_analysis_to_target_height(_analysis(8), 18, source="t", proportion_style="q")
    assert q.head_diameter_cm == 6.0
    assert q_meta["photo_head_to_height_ratio"] == 0.125
    assert q_meta["applied_head_to_height_ratio"] == pytest.approx(1 / 3, abs=1e-4)
    assert q_meta["proportion_style"] == "q" and q_meta["ratio_clamped"] is False
    assert "Q 版" in q_meta["note"]
    photo, photo_meta = scale_analysis_to_target_height(_analysis(8), 18, source="t")
    assert photo.head_diameter_cm == 2.2 and photo_meta["proportion_style"] == "photo"
    assert "风格换算" not in photo_meta["note"]
    _, clamped = scale_analysis_to_target_height(_analysis(10), 18, source="t", proportion_style="q")
    assert clamped["ratio_clamped"] is True


def _draft():
    return PipelineOrchestrator().prepare_photo(Image.new("RGB", (80, 160)), vision_mode="local")


@pytest.mark.parametrize("head_ratio", [0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.125, 0.1])
def test_default_style_keeps_heads_crochetable_at_default_size(head_ratio):
    # 路线图验收：默认 classic 密度、18 cm 下，1:2–1:10 的照片比例都生成 ≥24 针的头部
    result = PipelineOrchestrator.generate_from_draft(
        _draft(), analysis=reviewed_analysis(_draft().analysis, _PARTS, head_ratio))
    head = next(p for p in result["params"]["parts"] if p["name"] == "头部")
    assert max(r["stitches"] for r in head["rounds"]) >= 24
    assert not [f for f in crochetability_findings(result["params"]) if f.level == "block"]
    assert result["sizing"]["proportion_style"] == "q"


def test_head_box_extends_face_upward_and_sideways_within_the_image():
    assert head_box_from_face((70, 100, 60, 60), 200, 400) == (64, 70, 72, 90)
    assert head_box_from_face((0, 10, 60, 60), 200, 400) == (0, 0, 66, 70)


def test_analysis_uses_head_box_for_ratio_span_and_size_rule(monkeypatch):
    # 人脸占主体 1/11.25（旧规则会因“过小”拒绝）；整头 1/7.5 在支持范围内
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: (84, 20, 32, 32))
    analysis, meta = analyze(Image.new("RGB", (200, 400)))
    assert meta["source"] == "opencv-face"
    assert meta["face_box"] == [84, 20, 32, 32]
    assert meta["head_box"] == [81, 4, 38, 48]
    assert meta["body_ratio"] == 7.5
    assert meta["head_span"] == (0.01, 0.13)
    assert analysis.height_cm == 67.5


def test_review_head_box_starts_from_expanded_head(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: (28, 30, 24, 24))
    draft = _draft()
    head = draft.vision_meta["head_box"]
    at = AppTest.from_string('''
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
render_photo_review(st.session_state.draft, "box", gauge=DEFAULT, style=DEFAULT_STYLE, target_height=18)
''')
    at.session_state["draft"] = draft
    at.run()
    at.checkbox(key="review_box_box").check().run()
    assert at.slider(key="review_hy_box").value == (round(head[1] / 160 * 100),
                                                    round((head[1] + head[3]) / 160 * 100))
    assert at.slider(key="review_hy_box").value[0] < round(30 / 160 * 100)


def _photo(tmp_path):
    source = tmp_path / "photo.png"
    Image.new("RGB", (80, 160)).save(source)
    return source


def test_cli_photo_defaults_to_q_style_and_photo_style_stays_available(tmp_path, monkeypatch, capsys):
    # 头部框 18 px、主体 144 px：照片 1:8
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: (34, 10, 12, 12))
    output = tmp_path / "q.json"
    assert cli.main(["--image", str(_photo(tmp_path)), "--out", str(output), "--quiet"]) == 0
    sizing = json.loads(output.read_text(encoding="utf-8"))["sizing"]
    assert sizing["proportion_style"] == "q" and sizing["target_head_diameter_cm"] == 6.0
    capsys.readouterr()
    assert cli.main(["--image", str(_photo(tmp_path)), "--proportion-style", "photo",
                     "--out", str(tmp_path / "photo.json"), "--quiet"]) == 2
    err = capsys.readouterr().err
    assert "改用 --proportion-style q" in err and not (tmp_path / "photo.json").exists()


def test_imported_sizing_keeps_known_styles_and_rejects_unknown():
    data = {"sizing": {"photo_head_to_height_ratio": 0.2, "proportion_style": "balanced"}}
    validate_result_metadata(data)
    assert data["sizing"]["proportion_style"] == "balanced"
    with pytest.raises(ValidationError):
        validate_result_metadata({"sizing": {"proportion_style": "chibi"}})


def test_result_page_explains_the_applied_style():
    from tests.test_app_smoke import _APP

    draft = _draft()
    result = PipelineOrchestrator.generate_from_draft(
        draft, analysis=reviewed_analysis(draft.analysis, _PARTS, 0.2))
    result["result_id"] = "styled"
    at = AppTest.from_file(_APP, default_timeout=60)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert any("按「Q 版（推荐）」风格换算为玩偶约 1:2.5" in c.value for c in at.caption)


def test_default_evaluation_runner_records_its_proportion_style(tmp_path):
    import hashlib

    from app.evaluation import evaluate_dataset

    image = tmp_path / "one.png"
    Image.new("RGB", (32, 48), (200, 200, 200)).save(image)
    rights = {"copyright_basis": "self_owned", "author_or_rightsholder": "fixture-owner",
              "source_url": None, "license_identifier": None, "license_url": None,
              "permission_reference": "fixture-owner-attestation", "verified_on": "2026-11-02",
              "depicts_identifiable_person": False, "subject_authorization": "not_applicable",
              "evaluation_use_approved": True, "redistribution_allowed": False}
    manifest = {"schema_version": 2,
                "dataset": {"name": "styled", "version": "1", "rights_basis": "self_owned",
                            "evaluation_use_approved": True, "contains_personal_data": False,
                            "retention_policy": "Delete after the run."},
                "thresholds": {"min_cases": 1},
                "cases": [{"id": "one", "file": "one.png",
                           "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                           "rights": rights, "tags": ["fixture"],
                           "expected": {"parts": _PARTS, "flare": False, "dominant_colors": []}}]}
    (tmp_path / "eval_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    assert evaluate_dataset(tmp_path)["evaluator"]["proportion_style"] == "q"
    custom = evaluate_dataset(tmp_path, runner=PipelineOrchestrator().run_full_pipeline)
    assert custom["evaluator"]["proportion_style"] is None
