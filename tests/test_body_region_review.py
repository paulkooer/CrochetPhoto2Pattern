"""Body-region selection survives the complete reviewed-photo lifecycle."""
from copy import deepcopy

import numpy as np
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.models.geometry import SilhouetteObservation
from app.models.orchestrator import PipelineOrchestrator
from app.models.photo_review import with_reviewed_body
from app.schemas import PatternResult
from app.ui.result_logic import import_backup, regenerate_with_size, result_profile
from app.utils.provenance import provenance_lines
from app.utils.share import decode_result, encode_result


@pytest.fixture
def draft(monkeypatch):
    image = Image.new("RGB", (100, 160), "white")
    mask = np.zeros((160, 100), dtype=bool)
    mask[10:35, 35:65] = True
    mask[40:80, 40:60] = True
    mask[80:128, 35:65] = True
    mask[85:100, 10:90] = True  # touching arms contaminate whole-subject widths
    monkeypatch.setattr("app.models.subject.extract_subject", lambda *a, **k: (mask, image))
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda image: None)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda image: None)
    original = PipelineOrchestrator().prepare_photo(image, vision_mode="local")
    original.spans = {"头部": (0.05, 0.22), "身体": (0.3, 0.7)}
    original.spans_measured = ["头部", "身体"]
    return original


def body_stitches(result):
    return [r["stitches"] for p in result["params"]["parts"] if p["name"] == "身体" for r in p["rounds"]]


def test_selected_region_is_independent_and_controls_generation(draft):
    before = draft.subject.segmentation[0].copy()
    reviewed = with_reviewed_body(draft, (0.35, 0.25, 0.65, 0.8))
    assert draft.geometry.body_region is None
    assert reviewed.geometry.silhouette == draft.geometry.silhouette
    assert reviewed.geometry.body_region.profile[12] == pytest.approx(2 / 3)
    assert reviewed.geometry.body_region.profile[22] == 1.0
    assert reviewed.spans["身体"] == (0.25, 0.8)
    assert reviewed.spans_measured == ["头部"]
    assert draft.spans_measured == ["头部", "身体"]
    assert draft.spans["身体"] == (0.3, 0.7)
    np.testing.assert_array_equal(before, draft.subject.segmentation[0])
    generated = PipelineOrchestrator.generate_from_draft(reviewed)
    reviewed.geometry.silhouette = SilhouetteObservation(profile=[1.0] * 40)
    alternate = PipelineOrchestrator.generate_from_draft(reviewed)
    assert body_stitches(generated) == body_stitches(alternate)
    assert body_stitches(generated) != body_stitches(PipelineOrchestrator.generate_from_draft(draft))


def test_body_region_survives_backup_share_and_resize(draft, monkeypatch):
    reviewed = with_reviewed_body(draft, (0.35, 0.25, 0.65, 0.8))
    result = PipelineOrchestrator.generate_from_draft(reviewed)
    restored = import_backup(PatternResult.from_result(result).to_backup(), "body")
    # Regeneration must not require the source image or segment it again.
    monkeypatch.setattr("app.models.subject.extract_subject",
                        lambda *a, **k: pytest.fail("unexpected segmentation"))
    resized = regenerate_with_size(restored, 9, 22)
    # Full photo results may exceed the existing URL limit; backup remains
    # lossless. Exercise sharing with a compact body-only design below.
    for output in (result, restored, resized):
        assert result_profile(output) == reviewed.geometry.body_region.profile
        assert tuple(output["spans"]["身体"]) == (0.25, 0.8)
        assert tuple(output["geometry"]["body_region"]["box"]) == (0.35, 0.25, 0.65, 0.8)
        assert any("用户框选" in line for line in provenance_lines(output))
    assert body_stitches(restored) == body_stitches(result)
    assert body_stitches(resized) != body_stitches(result)


def test_compact_share_preserves_body_region(draft):
    reviewed = with_reviewed_body(draft, (0.35, 0.25, 0.65, 0.8))
    chosen = draft.analysis.model_copy(update={"parts": ["身体"]})
    result = PipelineOrchestrator.generate_from_draft(reviewed, analysis=chosen)
    # Optional run diagnostics and palette evidence are irrelevant to this
    # transport contract. Production sharing never strips them to force fit.
    result["diagnostics"] = {}
    result["vision_meta"] = {"source": "default"}
    token = encode_result(result)
    assert token is not None
    shared = import_backup(decode_result(token), "shared")
    assert result_profile(shared) == reviewed.geometry.body_region.profile
    assert tuple(shared["spans"]["身体"]) == (0.25, 0.8)


@pytest.mark.parametrize("box", [(0.5, 0.25, 0.5, 0.8), (-0.1, 0.25, 0.65, 0.8),
                                 (0.35, 0.5, 0.65, 0.51), (0.01, 0.25, 0.08, 0.8),
                                 (float("nan"), 0.25, 0.65, 0.8)])
def test_invalid_small_or_empty_boxes_are_rejected(draft, box):
    with pytest.raises(ValueError):
        with_reviewed_body(draft, box)
    assert draft.geometry.body_region is None


def test_mock_and_failed_segmentation_cannot_claim_reviewed_shape(draft):
    draft.geometry.used_for_generation = False
    with pytest.raises(ValueError, match="Mock"):
        with_reviewed_body(draft, (0.35, 0.25, 0.65, 0.8))
    draft.geometry.used_for_generation = True
    draft.subject.__dict__["segmentation"] = None
    with pytest.raises(ValueError, match="掩码"):
        with_reviewed_body(draft, (0.35, 0.25, 0.65, 0.8))


def test_import_rejects_body_box_span_mismatch(draft):
    result = PipelineOrchestrator.generate_from_draft(with_reviewed_body(draft, (0.35, 0.25, 0.65, 0.8)))
    backup = deepcopy(PatternResult.from_result(result).to_backup())
    backup["spans"]["身体"] = [0.1, 0.9]
    with pytest.raises(ValueError, match="分段不一致"):
        import_backup(backup, "invalid")


def test_ui_combines_head_and_body_review_without_mutating_draft(draft, monkeypatch):
    captured = []
    monkeypatch.setattr(PipelineOrchestrator, "generate_from_draft",
                        lambda reviewed, **kw: captured.append(reviewed))
    at = AppTest.from_string('''
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
render_photo_review(st.session_state.draft, "body", gauge=DEFAULT,
                    style=DEFAULT_STYLE, target_height=18)
''', default_timeout=20)
    at.session_state["draft"] = draft
    at.run()
    at.radio(key="review_subject_body").set_value("单个玩偶，所需部件可用下方列表表达").run()
    at.checkbox(key="review_body_box_body").check().run()
    at.slider(key="review_bx_body").set_value((35, 65)).run()
    at.slider(key="review_by_body").set_value((25, 80)).run()
    at.checkbox(key="review_box_body").check().run()
    at.slider(key="review_hy_body").set_value((5, 22)).run()
    at.button(key="review_generate_body").click().run()
    assert not at.exception and not at.error
    assert len(captured) == 1
    reviewed = captured[0]
    assert reviewed.spans["头部"] == (0.05, 0.22)
    assert reviewed.spans["身体"] == (0.25, 0.8)
    assert reviewed.spans_measured == []
    assert draft.geometry.body_region is None
    at.slider(key="review_bx_body").set_value((35, 35)).run()
    assert at.error and len(captured) == 1
