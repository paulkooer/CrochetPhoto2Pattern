"""Provider-neutral, versioned geometry observations."""
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from app.models.geometry import (
    GeometryObservation,
    SilhouetteObservation,
    _mask_width_profile,
    mock_geometry,
    observe_geometry,
    silhouette_profile,
)
from app.models.image_parser import ImageParser
from app.models.orchestrator import PipelineOrchestrator
from app.schemas import ImageAnalysis


def _analysis():
    return ImageAnalysis(
        body_type="标准", head_diameter_cm=6.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"],
    )


def test_geometry_observation_is_versioned_and_dimensionless(monkeypatch):
    profile = [0.2 + i / 50 for i in range(40)]
    monkeypatch.setattr("app.models.geometry.silhouette_profile",
                        lambda _image, **kwargs: profile)
    observation = observe_geometry(Image.new("RGB", (40, 80)))
    assert observation.schema_version == "1.0"
    assert observation.view_mode == "single_front_assumed"
    assert observation.silhouette is not None
    assert observation.silhouette.profile == [round(value, 3) for value in profile]
    assert observation.silhouette.confidence is None
    assert all("cm" not in key for key in observation.silhouette.model_dump())


def test_ai_pipeline_consumes_same_geometry_profile_as_local(monkeypatch):
    profile = [0.3] * 12 + [0.5] * 12 + [1.0] * 16
    monkeypatch.setattr("app.models.geometry.silhouette_profile",
                        lambda _image, **kwargs: profile)
    orchestrator = PipelineOrchestrator()
    with patch.object(ImageParser, "parse_image_local", return_value=_analysis()):
        result = orchestrator.run_full_pipeline(Image.new("RGB", (80, 160)))
    body = next(part for part in result["params"]["parts"] if part["name"] == "身体")
    assert body["type"] == "profile"
    assert result["geometry"]["used_for_generation"] is True
    assert result["geometry"]["silhouette"]["profile"] == profile


def test_mock_geometry_never_claims_photo_observation():
    observation = mock_geometry()
    assert observation.used_for_generation is False
    assert observation.silhouette is None
    assert "不读取照片" in observation.limitations[0]


def test_local_pipeline_reuses_one_geometry_observation(monkeypatch):
    observation = GeometryObservation(silhouette=SilhouetteObservation(
        profile=[0.5] * 40, flare=False))
    calls = []

    def _observe(_image, **kwargs):
        calls.append(1)
        return observation

    monkeypatch.setattr("app.models.orchestrator.observe_geometry", _observe)
    monkeypatch.setattr(
        "app.models.local_vision._silhouette_profile",
        lambda _image: (_ for _ in ()).throw(AssertionError("重复提取轮廓")),
    )
    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (80, 160)), local_vision=True)
    assert len(calls) == 1
    assert result["geometry"]["silhouette"]["profile"] == [0.5] * 40


def test_mock_pipeline_skips_geometry_extraction(monkeypatch):
    monkeypatch.setattr(
        "app.models.orchestrator.observe_geometry",
        lambda _image: (_ for _ in ()).throw(AssertionError("Mock 不应读取几何")),
    )
    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 40)), vision_mode="mock")
    assert result["vision_meta"]["source"] == "mock"
    assert result["geometry"]["used_for_generation"] is False


def test_disconnected_foreground_is_not_added_to_torso_width():
    centered = np.zeros((80, 100), dtype=bool)
    centered[:40, 40:60] = True
    centered[40:, 30:70] = True
    split = centered.copy()
    split[:40] = False
    split[:40, 10:20] = True
    split[:40, 80:90] = True
    assert np.array_equal(centered.sum(axis=1), split.sum(axis=1))
    assert _mask_width_profile(centered, 40) == [0.5] * 20 + [1.0] * 20
    assert _mask_width_profile(split, 40) == [0.25] * 20 + [1.0] * 20


def test_detached_arms_do_not_widen_profile_and_translation_is_invariant():
    mask = np.zeros((80, 100), dtype=bool)
    mask[10:30, 40:60] = True
    mask[30:70, 30:70] = True
    expected = _mask_width_profile(mask, 40)
    mask[35:60, 10:20] = True
    mask[35:60, 80:90] = True
    assert _mask_width_profile(mask, 40) == expected
    assert _mask_width_profile(np.roll(mask, 5, axis=1), 40) == expected
    assert expected[:5] == [0.0] * 5
    assert expected[5:15] == [0.5] * 10


@pytest.mark.parametrize("segmented", [True, False])
def test_segmented_and_fallback_paths_measure_same_uneroded_widths(monkeypatch, segmented):
    mask = np.zeros((80, 100), dtype=bool)
    mask[10:30, 45:55] = True
    mask[30:70, 25:75] = True
    mask[40:60, 10:15] = True
    pixels = np.full((80, 100, 3), 255, dtype=np.uint8)
    pixels[mask] = 0
    image = Image.fromarray(pixels)
    monkeypatch.setattr("app.models.subject.extract_subject",
                        lambda *a, **kw: (mask, image) if segmented else None)
    profile = silhouette_profile(image)
    assert profile == [0.0] * 5 + [0.2] * 10 + [1.0] * 20 + [0.0] * 5


def test_empty_and_tiny_width_profiles_are_unavailable():
    assert _mask_width_profile(np.zeros((80, 100), dtype=bool), 40) is None
    assert _mask_width_profile(np.ones((10, 100), dtype=bool), 40) is None
