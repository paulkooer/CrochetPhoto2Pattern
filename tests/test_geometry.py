"""Provider-neutral, versioned geometry observations."""
from unittest.mock import patch

from PIL import Image

from app.models.geometry import (
    GeometryObservation,
    SilhouetteObservation,
    mock_geometry,
    observe_geometry,
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
                        lambda _image: profile)
    observation = observe_geometry(Image.new("RGB", (40, 80)))
    assert observation.schema_version == "1.0"
    assert observation.view_mode == "single_front_assumed"
    assert observation.silhouette is not None
    assert observation.silhouette.profile == [round(value, 3) for value in profile]
    assert 0.0 < observation.silhouette.confidence < 1.0
    assert all("cm" not in key for key in observation.silhouette.model_dump())


def test_ai_pipeline_consumes_same_geometry_profile_as_local(monkeypatch):
    profile = [0.3] * 12 + [0.5] * 12 + [1.0] * 16
    monkeypatch.setattr("app.models.geometry.silhouette_profile",
                        lambda _image: profile)
    orchestrator = PipelineOrchestrator(openai_key="test-key")
    with patch.object(ImageParser, "parse_image", return_value=_analysis()):
        result = orchestrator.run_full_pipeline(Image.new("RGB", (80, 160)))
    body = next(part for part in result["params"]["parts"] if part.name == "身体")
    assert body.type == "profile"
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

    def _observe(_image):
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
        Image.new("RGB", (40, 40)), local_vision=False)
    assert result["vision_meta"]["source"] == "mock"
    assert result["geometry"]["used_for_generation"] is False
