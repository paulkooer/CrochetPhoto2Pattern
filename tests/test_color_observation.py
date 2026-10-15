"""Preserve photo patches without pretending they are stitch instructions."""
from copy import deepcopy

import numpy as np
import pytest
from PIL import Image, ImageDraw
from streamlit.testing.v1 import AppTest

from app.models.color_design import vertical_color_bands
from app.models.color_observation import ColorObservation, build_observation
from app.models.orchestrator import PipelineOrchestrator
from app.models.subject import SubjectObservation
from app.schemas import PatternResult
from app.ui.result_logic import import_backup, regenerate_with_size
from app.utils.exporters import export_markdown
from app.utils.share import decode_result, encode_result


def patches(two=True):
    image = Image.new("RGB", (160, 160), "white")
    draw = ImageDraw.Draw(image)
    for box in ([(30, 40, 45, 79), (110, 40, 125, 79)] if two else [(64, 40, 95, 79)]):
        draw.rectangle(box, fill="black")
    subject = SubjectObservation(image)
    subject.__dict__["segmentation"] = (np.ones((160, 160), dtype=bool), image)
    return image, subject


def observe(two=True):
    image, subject = patches(two)
    evidence = {}
    bands = vertical_color_bands(image, subject=subject, observation=evidence)
    return bands, evidence


def test_distinct_patch_positions_survive_identical_majority_bands():
    bands, two = observe()
    other_bands, one = observe(False)
    assert bands == other_bands == [{"start": 0.0, "end": 1.0, "color": "白色"}]
    assert two["coverage"] == one["coverage"]
    assert next(c["pixels"] for c in two["coverage"] if c["color"] == "黑色") == 1280
    black = [r for r in two["regions"] if r["color"] == "黑色"]
    assert len(black) == 2
    assert black[0]["box"][2] < black[1]["box"][0]
    assert len([r for r in one["regions"] if r["color"] == "黑色"]) == 1
    assert ColorObservation.model_validate(two).requires_review
    assert two == observe()[1]


def test_monochrome_does_not_need_local_color_review():
    image, subject = patches()
    image.paste("white", (0, 0, 160, 160))
    evidence = {}
    vertical_color_bands(image, subject=subject, observation=evidence)
    observation = ColorObservation.model_validate(evidence)
    assert not observation.requires_review
    assert observation.minority_fraction == 0
    assert len(observation.regions) == 1


def test_fallback_mask_is_labeled_and_failed_extraction_clears_old_evidence():
    image = Image.new("RGB", (160, 160), "white")
    ImageDraw.Draw(image).rectangle((40, 40, 119, 119), fill="blue")
    subject = SubjectObservation(image)
    subject.__dict__["segmentation"] = None
    evidence = {}
    vertical_color_bands(image, subject=subject, observation=evidence)
    assert evidence["mask_source"] == "background_distance"
    assert not ColorObservation.model_validate(evidence).requires_review
    assert vertical_color_bands(Image.new("RGB", (2, 2)), observation=evidence) == []
    assert evidence == {}


def test_many_regions_are_bounded_but_all_color_counts_survive():
    # 100 separated 10x10 regions, each above the size threshold.
    labels = np.zeros((160, 160), dtype=int)
    for y in range(0, 160, 16):
        for x in range(0, 160, 16):
            labels[y:y+10, x:x+10] = 1
    evidence = build_observation(np.ones((160, 160), bool), labels.ravel(), ["白色", "黑色"],
                                 10, "segmentation")
    observation = ColorObservation.model_validate(evidence)
    assert len(observation.regions) == 64
    assert observation.omitted_region_count > 0 and observation.omitted_pixels > 0
    assert sum(c.pixels for c in observation.coverage) == 25600


def photo_result(head_only=False):
    image, subject = patches()
    draft = PipelineOrchestrator().prepare_photo(image, vision_mode="mock", subject=subject)
    chosen = draft.analysis.model_copy(update={"parts": ["头部"]}) if head_only else None
    return PipelineOrchestrator.generate_from_draft(draft, analysis=chosen)


def test_photo_evidence_survives_backup_share_resize_and_export():
    result = photo_result(head_only=True)
    expected = result["vision_meta"]["color_observation"]
    restored = import_backup(PatternResult.from_result(result).to_backup(), "color-layout")
    token = encode_result(result)
    assert token is not None
    shared = import_backup(decode_result(token), "shared")
    resized = regenerate_with_size(restored, 10, 20)
    for record in (restored, shared, resized):
        assert record["vision_meta"]["color_observation"] == expected
        assert "局部配色待复核" in export_markdown(record["params"], result=record)
        assert "圈内换色或附着装饰" in export_markdown(record["params"], result=record)


def test_large_result_keeps_evidence_in_backup_when_share_is_too_long():
    result = photo_result()
    assert encode_result(result) is None
    restored = import_backup(PatternResult.from_result(result).to_backup(), "large")
    assert restored["vision_meta"]["color_observation"] == result["vision_meta"]["color_observation"]


@pytest.mark.parametrize("corruption", ["nan_box", "invalid_sum", "too_many_regions", "bad_band"])
def test_import_rejects_invalid_color_evidence(corruption):
    result = photo_result()
    evidence = result["vision_meta"]["color_observation"]
    if corruption == "nan_box":
        evidence["regions"][0]["box"][0] = float("nan")
    elif corruption == "invalid_sum":
        evidence["coverage"][0]["pixels"] += 1
    elif corruption == "too_many_regions":
        evidence["regions"] *= 65
    else:
        evidence["band_coverage"][0]["end"] = 0.95
    with pytest.raises(ValueError):
        import_backup(PatternResult.from_result(result).to_backup(), "invalid")


def test_ui_and_cached_markdown_reflect_patch_evidence():
    result = photo_result()
    result["result_id"] = "color-ui"
    at = AppTest.from_string('''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
''', default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert any("局部色块需要复核" in w.value for w in at.warning)
    cache = at.session_state["export_cache_color-ui"]
    assert "局部配色待复核" in cache["markdown"]["value"]
    # Metadata is in the export fingerprint; replacing it cannot reuse stale text.
    changed = deepcopy(result)
    changed["vision_meta"].pop("color_observation")
    at.session_state["result"] = changed
    at.run()
    assert not at.exception
    assert not any("局部色块需要复核" in w.value for w in at.warning)
    assert "局部配色待复核" not in at.session_state["export_cache_color-ui"]["markdown"]["value"]
