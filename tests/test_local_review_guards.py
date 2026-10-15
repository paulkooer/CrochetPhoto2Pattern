"""Reject unsafe proportion inference and require an explicit UI subject review."""
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.models.local_vision import analyze
from app.models.orchestrator import PipelineOrchestrator


@pytest.mark.parametrize("box", [(80, 240, 60, 60), (80, 330, 60, 60),
                                 (-2, 10, 60, 60), (180, 10, 60, 60)])
def test_unsuitable_face_is_rejected_before_proportion_inference(monkeypatch, box):
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _: box)
    analysis, meta = analyze(Image.new("RGB", (200, 400)), geometry_observed=True)
    assert meta["source"] == "default"
    assert meta["rejected_face_box"] == list(box)
    assert "face_box" not in meta
    assert "head_span" not in meta
    assert "body_ratio" not in meta
    assert analysis.height_cm == 18


def test_head_position_uses_subject_extent_not_whole_canvas(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _: (60, 220, 80, 80))
    profile = [0.0] * 20 + [0.5] * 18 + [0.0] * 2
    _, meta = analyze(Image.new("RGB", (200, 400)), geometry_profile=profile, geometry_observed=True)
    assert meta["source"] == "opencv-face"
    assert meta["body_ratio"] == 2.25
    assert meta["requires_subject_review"]


def test_subject_review_blocks_unknown_multiple_and_unsupported_subjects(monkeypatch):
    draft = PipelineOrchestrator().prepare_photo(Image.new("RGB", (80, 160)), vision_mode="local")
    calls = []

    def generate(draft, **kwargs):
        calls.append((draft.vision_meta.copy(), kwargs["analysis"].parts))
        return {"generated": True}

    monkeypatch.setattr(PipelineOrchestrator, "generate_from_draft", generate)
    script = '''
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
render_photo_review(st.session_state.draft, "test", gauge=DEFAULT,
                    style=DEFAULT_STYLE, target_height=18)
'''
    at = AppTest.from_string(script)
    at.session_state["draft"] = draft
    at.run()
    assert at.button(key="review_generate_test").disabled
    for choice in ("多个主体，需要先裁剪", "食品或其他无法用现有部件表达的作品"):
        at.radio(key="review_subject_test").set_value(choice).run()
        assert at.button(key="review_generate_test").disabled
        assert not calls
    at.radio(key="review_subject_test").set_value("单个玩偶，所需部件可用下方列表表达").run()
    at.multiselect(key="review_parts_test").set_value(["头部", "身体", "耳朵", "尾巴"]).run()
    at.button(key="review_generate_test").click().run()
    assert not at.exception
    assert len(calls) == 1
    meta, parts = calls[0]
    assert parts == ["头部", "身体", "耳朵", "尾巴"]
    assert meta["parts_source"] == "user_review"
    assert meta["requires_subject_review"] is False
    assert draft.vision_meta["requires_subject_review"] is True


def test_unreviewed_local_template_warning_survives_portable_export():
    from app.utils.provenance import provenance_lines

    unreviewed = {"vision_meta": {"source": "default", "requires_subject_review": True}}
    assert any("部件来自默认模板" in line for line in provenance_lines(unreviewed))
    reviewed = {"vision_meta": {"source": "default", "requires_subject_review": False,
                                "subject_scope_review": "single_representable_subject"}}
    assert any("用户已确认" in line for line in provenance_lines(reviewed))
    assert not any("尚未确认" in line for line in provenance_lines(reviewed))


def test_cli_local_template_warns_without_calling_provider(tmp_path, monkeypatch, capsys):
    from app import cli

    args = cli.build_parser().parse_args(["--mock"])
    result = cli.run(args)
    result["vision_meta"] = {"source": "default", "requires_subject_review": True}
    monkeypatch.setattr(cli, "run", lambda _: result)
    assert cli.main(["--mock", "--out", str(tmp_path / "p.json")]) == 0
    assert "主体类型未确认" in capsys.readouterr().err
