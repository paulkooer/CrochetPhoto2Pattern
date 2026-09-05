"""Tests for PipelineOrchestrator.run_full_pipeline (mocked parser, no API)."""
from unittest.mock import patch

from PIL import Image

from app.models.image_parser import ImageParser
from app.models.orchestrator import PipelineOrchestrator
from app.schemas import ImageAnalysis


def _analysis():
    return ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=["大眼睛"], pose="站立", difficulty="easy",
        parts=["头部", "身体"],
    )


def test_full_pipeline_returns_three_stage_result():
    orch = PipelineOrchestrator()
    with patch.object(ImageParser, "parse_image", return_value=_analysis()):
        result = orch.run_full_pipeline(Image.new("RGB", (40, 40)))
    assert set(result.keys()) == {
        "analysis", "structure", "params", "usage", "vision_meta", "gauge",
        "style", "color_bands", "spans", "spans_measured", "preview",
        "sizing", "geometry",
    }
    assert result["analysis"]["body_type"] == "标准"
    assert len(result["structure"]["parts"]) == 2
    assert [p["name"] for p in result["params"]["parts"]] == ["头部", "身体"]
    # parse_image 被 mock → 无真实调用 → usage / vision_meta 均为空 dict
    assert result["usage"] == {}
    assert result["vision_meta"] == {}
    assert result["sizing"]["source"] == "default_reference"
    assert result["sizing"]["absolute_scale_from_photo"] is False
    assert result["geometry"]["schema_version"] == "1.0"


def test_full_pipeline_reports_progress():
    calls = []
    orch = PipelineOrchestrator()
    with patch.object(ImageParser, "parse_image", return_value=_analysis()):
        orch.run_full_pipeline(
            Image.new("RGB", (40, 40)),
            progress_cb=lambda pct, text: calls.append((pct, text)),
        )
    pcts = [p for p, _ in calls]
    assert pcts == [10, 40, 70]
    assert all("Step" in t for _, t in calls)


def test_full_pipeline_progress_cb_optional():
    """不传 progress_cb 时静默运行（模型层不依赖 Streamlit）。"""
    orch = PipelineOrchestrator()
    with patch.object(ImageParser, "parse_image", return_value=_analysis()):
        result = orch.run_full_pipeline(Image.new("RGB", (40, 40)))
    assert result["analysis"]["parts"] == ["头部", "身体"]


def test_full_pipeline_applies_user_target_to_parser_ratio():
    orch = PipelineOrchestrator()
    observed = ImageAnalysis(
        body_type="标准", head_diameter_cm=4.0, height_cm=20.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"])
    with patch.object(ImageParser, "parse_image", return_value=observed):
        result = orch.run_full_pipeline(
            Image.new("RGB", (40, 40)), target_height_cm=30.0,
            target_height_source="user_photo_target")
    assert result["analysis"]["height_cm"] == 30.0
    assert result["analysis"]["head_diameter_cm"] == 6.0
    assert result["sizing"]["source"] == "user_photo_target"
    assert result["sizing"]["photo_head_to_height_ratio"] == 0.2


def test_explicit_mock_mode_skips_api_and_photo_geometry():
    """vision_mode="mock"：即使配置了 Key 也不发起 API 调用、不读照片几何。

    旧设计里 Mock 只是"无 Key"的隐式副作用；显式三态后选择与行为一致。
    """
    from PIL import Image

    orch = PipelineOrchestrator(openai_key="sk-user-key-1234567890")
    result = orch.run_full_pipeline(Image.new("RGB", (40, 40)),
                                    vision_mode="mock")
    assert result["vision_meta"]["source"] == "mock"
    assert result["usage"] == {}
    assert result["geometry"]["silhouette"] is None
    assert result["geometry"]["used_for_generation"] is False


def test_invalid_vision_mode_rejected():
    """非三态值直接拒绝，不允许隐式回退。"""
    import pytest
    from PIL import Image

    orch = PipelineOrchestrator()
    with pytest.raises(ValueError, match="vision_mode"):
        orch.run_full_pipeline(Image.new("RGB", (40, 40)), vision_mode="yolo")
