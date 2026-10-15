"""Recover visible foreground without mutating recognition or losing provenance."""
from copy import deepcopy

import numpy as np
import pytest
from PIL import Image, ImageDraw
from streamlit.testing.v1 import AppTest

from app.models.mask_review import MaskReview, mask_editor_input, with_reviewed_mask
from app.models.orchestrator import PipelineOrchestrator
from app.models.photo_review import with_reviewed_body
from app.schemas import PatternResult
from app.ui.result_logic import import_backup, regenerate_with_size
from app.utils.provenance import provenance_lines


@pytest.fixture
def draft(monkeypatch):
    image = Image.new("RGB", (80, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 50, 59, 139), fill="red")
    draw.rectangle((25, 10, 54, 44), fill=(0, 120, 215))
    mask = np.zeros((160, 80), dtype=bool)
    mask[50:140, 20:60] = True  # visible blue area was missed by segmentation
    monkeypatch.setattr("app.models.subject.extract_subject", lambda *a, **kw: (mask, image))
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _: None)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda _: None)
    return PipelineOrchestrator().prepare_photo(image, vision_mode="local")


def payload(draft, *, restore=False):
    small, mask, token = mask_editor_input(draft)
    edited = mask.copy()
    if not restore:
        edited[10:45, 25:55] = True
    return {"width": small.width, "height": small.height, "image_token": token,
            "pixels": "".join("1" if pixel else "0" for pixel in edited.flat)}


def test_recovered_foreground_updates_geometry_palette_and_generated_colors(draft, monkeypatch):
    original = draft.subject.segmentation[0].copy()
    old_palette = draft.analysis.recommended_colors.copy()
    # Populate the old color cache before editing to catch stale-cache reuse.
    old_colors = draft.subject.color_segmentation[0].copy()
    monkeypatch.setattr("app.models.subject.extract_subject",
                        lambda *a, **kw: pytest.fail("segmentation must not rerun"))
    edited = with_reviewed_mask(draft, payload(draft))
    assert draft.geometry.silhouette.profile[5] == 0
    assert edited.geometry.silhouette.profile[5] > 0
    assert "蓝色" in edited.analysis.recommended_colors
    assert "蓝色" not in old_palette
    assert edited.subject.color_segmentation[0][20, 40]
    np.testing.assert_array_equal(draft.subject.segmentation[0], original)
    np.testing.assert_array_equal(draft.subject.color_segmentation[0], old_colors)
    assert draft.analysis.recommended_colors == old_palette
    assert draft.geometry.mask_review is None
    generated = PipelineOrchestrator.generate_from_draft(edited)
    assert any(band["color"] == "蓝色" for band in generated["color_bands"])
    assert any("补选／擦除" in line for line in provenance_lines(generated))


def test_erasure_removes_foreground_from_both_geometry_and_colors(draft):
    data = payload(draft)
    data["pixels"] = "".join("1" if 10 <= y < 45 and 25 <= x < 55 else "0"
                             for y in range(160) for x in range(80))
    edited = with_reviewed_mask(draft, data)
    assert not edited.subject.segmentation[0][80, 40]
    assert edited.geometry.silhouette.profile[20] == 0
    assert edited.analysis.recommended_colors == ["蓝色"]


def test_correction_recovers_from_failed_segmentation_and_feeds_body_box(draft):
    correction = payload(draft)
    draft.subject.__dict__["segmentation"] = None
    edited = with_reviewed_mask(draft, correction)
    selected = with_reviewed_body(edited, (0.25, 0.3, 0.75, 0.88))
    assert selected.geometry.mask_review is not None
    assert selected.geometry.body_region is not None
    assert draft.subject.segmentation is None
    # Reapplying a correction to an already body-reviewed draft recomputes it.
    reedited = with_reviewed_mask(selected, correction)
    assert reedited.geometry.body_region == selected.geometry.body_region


def test_corrected_mask_survives_backup_and_resize_without_photo(draft):
    result = PipelineOrchestrator.generate_from_draft(with_reviewed_mask(draft, payload(draft)))
    restored = import_backup(PatternResult.from_result(result).to_backup(), "mask")
    resized = regenerate_with_size(restored, 9, 22)
    for output in (restored, resized):
        assert output["geometry"]["mask_review"] == result["geometry"]["mask_review"]
        assert output["geometry"]["silhouette"] == result["geometry"]["silhouette"]
        assert output["color_bands"] == result["color_bands"]


@pytest.mark.parametrize("change", [
    {"width": True}, {"height": 161}, {"pixels": "1" * 25601},
    {"pixels": "x" * 12800}, {"pixels": "0" * 12800}, {"pixels": "1"},
    {"image_token": "f" * 64}, {"width": 160, "height": 80},
])
def test_invalid_empty_or_stale_correction_is_rejected(draft, change):
    with pytest.raises(ValueError):
        with_reviewed_mask(draft, {**payload(draft), **change})


def test_mock_and_malformed_backup_cannot_claim_mask_review(draft):
    correction = payload(draft)
    draft.geometry.used_for_generation = False
    with pytest.raises(ValueError, match="Mock"):
        with_reviewed_mask(draft, correction)
    draft.geometry.used_for_generation = True
    result = PipelineOrchestrator.generate_from_draft(with_reviewed_mask(draft, correction))
    backup = deepcopy(PatternResult.from_result(result).to_backup())
    backup["geometry"]["mask_review"]["pixels"] = "1"
    with pytest.raises(ValueError, match="尺寸"):
        import_backup(backup, "bad")
    with pytest.raises(ValueError):
        MaskReview(**{**correction, "unexpected": 1})


def test_review_ui_uses_correction_and_can_restore_original(draft, monkeypatch):
    from app.ui import mask_editor

    pending = [{**payload(draft), "use_original": False}]
    monkeypatch.setattr(mask_editor, "_canvas", lambda **kwargs: pending[0])
    captured = []
    monkeypatch.setattr(PipelineOrchestrator, "generate_from_draft",
                        lambda reviewed, **kw: captured.append((reviewed, kw["analysis"])))
    at = AppTest.from_string('''
import streamlit as st
from app.ui.photo_review import render_photo_review
from app.models.gauge import DEFAULT, DEFAULT_STYLE
render_photo_review(st.session_state.draft, "mask", gauge=DEFAULT,
                    style=DEFAULT_STYLE, target_height=18)
''', default_timeout=20)
    at.session_state["draft"] = draft
    at.run()
    at.radio(key="review_subject_mask").set_value("单个玩偶，所需部件可用下方列表表达").run()
    at.checkbox(key="review_mask_enabled_mask").check().run()
    at.button(key="review_generate_mask").click().run()
    assert not at.error and not at.exception
    assert captured[0][0].geometry.mask_review is not None
    assert "蓝色" in captured[0][1].recommended_colors
    pending[0] = {**payload(draft), "pixels": "0" * 12800, "use_original": False}
    at.run()
    assert at.error and len(captured) == 1
    pending[0] = {**payload(draft, restore=True), "use_original": True}
    at.run()
    at.button(key="review_generate_mask").click().run()
    assert not at.error
    assert captured[-1][0].geometry.mask_review is None
    assert "蓝色" not in captured[-1][1].recommended_colors
    # An empty baseline after failed automatic segmentation is not permission
    # to silently revert when the user erases their entire manual selection.
    draft.subject.__dict__["segmentation"] = None
    pending[0] = {**payload(draft, restore=True), "use_original": False}
    at.run()
    assert at.error and len(captured) == 2
