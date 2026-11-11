"""Subject-relative priors share the image frame with color and shape evidence."""
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from app.models.color_design import PART_SPAN, resolved_part_spans
from app.models.geometry import SilhouetteObservation, profile_extent
from app.models.image_parser import ImageParser
from app.models.orchestrator import PipelineOrchestrator
from app.models.subject import SubjectObservation
from app.schemas import ImageAnalysis, PatternResult
from app.services.result_logic import import_backup, regenerate_with_size


def _subject_at(top):
    pixels = np.full((160, 80, 3), 255, dtype=np.uint8)
    mask = np.zeros((160, 80), dtype=bool)
    for y in range(80):
        half = 14 if y < 24 else int(9 + (y - 24) / 26 * 7) if y < 50 else 15
        mask[top + y, 40 - half:40 + half] = True
        pixels[top + y, 40 - half:40 + half] = (
            (60, 40, 30) if y < 24 else (210, 25, 30) if y < 50 else (0, 80, 210))
    image = Image.fromarray(pixels)
    return image, SubjectObservation.from_reviewed_mask(image, mask, image)


def _analysis():
    return ImageAnalysis(body_type="标准", head_diameter_cm=7, height_cm=18,
                         main_features=[], pose="站立", difficulty="easy",
                         parts=["头部", "身体", "手臂", "腿部"])


def _generate(top):
    image, subject = _subject_at(top)
    with patch("app.models.pose.get_body_landmarks", return_value=None), patch.object(
            ImageParser, "parse_image_local", return_value=_analysis()):
        draft = PipelineOrchestrator().prepare_photo(image, subject=subject)
        result = PipelineOrchestrator.generate_from_draft(draft, enforce_crochetability=False)
    return draft, result


def test_translated_subject_keeps_round_colors_and_body_shaping():
    outputs = [_generate(top) for top in (0, 40, 80)]
    signatures, walls = [], []
    for draft, result in outputs:
        assert draft.geometry.silhouette.subject_extent is not None
        parts = {part["name"]: part for part in result["params"]["parts"]}
        signatures.append({name: [row["color"] for row in part["rounds"]]
                           for name, part in parts.items()})
        wall = [row["stitches"] for row in parts["身体"]["rounds"] if row["region"] == "wall"]
        assert wall[0] > wall[-1]  # The fixture is wider at the body's bottom.
        walls.append(wall)
    assert signatures[0] == signatures[1] == signatures[2]
    assert walls[0] == walls[1] == walls[2]
    assert len({tuple(signatures[0][name]) for name in ("头部", "身体", "腿部")}) == 3


def test_pose_measured_ranges_override_only_the_corresponding_mapped_prior(monkeypatch):
    image, subject = _subject_at(80)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda image: {"valid": True})
    monkeypatch.setattr("app.models.pose.measured_spans", lambda landmarks: {"头部": (0.52, 0.63)})
    with patch.object(ImageParser, "parse_image_local", return_value=_analysis()):
        draft = PipelineOrchestrator().prepare_photo(image, subject=subject)
    assert draft.spans_measured == ["头部"]
    assert draft.spans["头部"] == (0.52, 0.63)
    assert draft.spans["身体"] == (0.65, 0.81)
    assert draft.spans["腿部"] == (0.81, 1.0)


def test_mapped_ranges_survive_backup_and_regeneration():
    draft, result = _generate(80)
    restored = import_backup(PatternResult.from_result(result).to_backup(), "translated")
    resized = regenerate_with_size(restored, 8, 20)
    for value in (restored, resized):
        assert tuple(value["spans"]["身体"]) == draft.spans["身体"]
        assert value["geometry"]["silhouette"]["profile"] == draft.geometry.silhouette.profile
        assert "subject_extent" not in value["geometry"]["silhouette"]
    body = next(part for part in resized["params"]["parts"] if part["name"] == "身体")
    wall = [row["stitches"] for row in body["rounds"] if row["region"] == "wall"]
    assert wall[0] > wall[-1]


def test_absent_extent_preserves_legacy_defaults_and_stored_geometry():
    assert profile_extent([]) is None
    assert profile_extent([0.0] * 40) is None
    assert resolved_part_spans(None, None) is None
    assert resolved_part_spans({"头部": (0.1, 0.2)}, None) == {
        **PART_SPAN, "头部": (0.1, 0.2)}
    old = {"profile": [0.0] * 10 + [1.0] * 20 + [0.0] * 10, "flare": False}
    silhouette = SilhouetteObservation.model_validate(old)
    assert silhouette.subject_extent == pytest.approx((0.25, 0.75))
    assert "subject_extent" not in silhouette.model_dump()
