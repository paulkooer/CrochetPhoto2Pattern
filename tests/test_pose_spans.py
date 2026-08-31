"""S1 实测部件 span：姿态关键点 → spans → 配色/剖面接线（可选依赖+回退）。"""

import pytest
from PIL import Image

from app.models.color_design import PART_SPAN, color_blocks_for_part
from app.models.crochet_params import CrochetParamsGenerator
from app.models.pose import (
    _mediapipe_runtime_available,
    get_body_landmarks,
    measured_spans,
)
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis


def test_mediapipe_image_bridge_when_pose_extra_is_installed():
    """[pose] 必须能构造 Tasks Image；核心环境无 extra 时按设计跳过。"""
    if not _mediapipe_runtime_available():
        pytest.skip("MediaPipe Linux wheel requires libEGL.so.1")
    mp = pytest.importorskip("mediapipe")
    np = pytest.importorskip("numpy")

    image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=np.zeros((8, 12, 3), dtype=np.uint8),
    )
    assert image.width == 12
    assert image.height == 8


def test_pose_safely_falls_back_before_mediapipe_when_native_runtime_missing(
    monkeypatch,
):
    """缺 libEGL 时不得构造半初始化 Image，更不能由析构异常污染进程。"""
    monkeypatch.setattr(
        "app.models.pose._mediapipe_runtime_available", lambda: False
    )
    assert get_body_landmarks(Image.new("RGB", (8, 12), "white")) is None


def _standing_landmarks():
    """直立人形关键点（归一化 y，头在上）。"""
    return {
        "nose": 0.10, "eye_top": 0.07,
        "shoulder": 0.25, "hip": 0.50,
        "knee": 0.72, "ankle": 0.94, "wrist": 0.52,
    }


def test_measured_spans_anatomy_order():
    """实测 span 的纵向次序符合人体：头 < 身体 < 腿，帽子在头内。"""
    spans = measured_spans(_standing_landmarks())
    assert spans["头部"][1] <= spans["身体"][0]
    assert spans["身体"][1] <= spans["腿部"][0]
    assert spans["帽子"][1] <= spans["头部"][1]
    assert spans["耳朵"][0] >= spans["头部"][0]
    # 坐标净化在 0..1 且方向正确
    for s, e in spans.values():
        assert 0.0 <= s < e <= 1.0


def test_measured_spans_missing_knee_drops_leg_skirt():
    """膝盖不可见（坐姿特写）→ 腿/裙子无实测，交由调用方回退先验。"""
    lm = {k: v for k, v in _standing_landmarks().items()
          if k not in ("knee", "ankle")}
    lm["hip"] = 0.75
    spans = measured_spans(lm)
    assert "腿部" not in spans and "裙子" not in spans
    assert "头部" in spans and "身体" in spans


def test_color_blocks_use_measured_span():
    """实测 span 生效：身体 span 明显上移时，色带切块随之移动（M1.3 兑现）。"""
    bands = [{"start": 0.0, "end": 0.25, "color": "红色"},   # 照片顶部
             {"start": 0.25, "end": 0.55, "color": "蓝色"},
             {"start": 0.55, "end": 1.0, "color": "黑色"}]
    # 先验身体 0.30-0.62；实测身体 0.25-0.50
    prior = color_blocks_for_part(bands, "身体")
    measured = color_blocks_for_part(bands, "身体",
                                     spans={"身体": (0.25, 0.50)})
    assert prior[0][0] == PART_SPAN["身体"][0]
    assert measured[0][0] == 0.25 and measured[-1][1] == 0.50
    assert measured[-1][2] == "蓝色"      # 实测段不再包含黑色（0.55+）


def test_generate_params_uses_measured_spans():
    """generate_params(spans=...)：圈色按实测 span 铺设（端到端）。"""
    bands = [{"start": 0.0, "end": 0.25, "color": "红色"},
             {"start": 0.25, "end": 0.55, "color": "蓝色"},
             {"start": 0.55, "end": 1.0, "color": "黑色"}]
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体"])
    struct = StructureDesigner.design_3d_structure(a)
    spans = measured_spans(_standing_landmarks())
    params = CrochetParamsGenerator.generate_params(
        a, struct, color_bands=bands, spans=spans)
    by = {p.name: p for p in params["parts"]}
    # 实测身体 0.25-0.50 全在蓝色带内 → 身体整段蓝（先验会混入黑）
    assert {r.color for r in by["身体"].rounds} == {"蓝色"}
    # 无 spans 时保持旧行为（回退先验）
    params_prior = CrochetParamsGenerator.generate_params(
        a, struct, color_bands=bands)
    by_prior = {p.name: p for p in params_prior["parts"]}
    assert {r.color for r in by_prior["身体"].rounds} != {"蓝色"}


def test_orchestrator_pose_failure_falls_back(monkeypatch):
    """pose 全链路失败（无 mediapipe/模型）→ result["spans"] 为 None，正常出图解。"""
    import app.models.pose as pose_mod
    from app.models.orchestrator import PipelineOrchestrator

    monkeypatch.setattr(pose_mod, "get_body_landmarks", lambda _img: None)
    img = Image.new("RGB", (60, 60), (245, 194, 158))
    result = PipelineOrchestrator().run_full_pipeline(img, local_vision=True)
    assert result["spans"] is None
    assert result["params"]["parts"]


def test_orchestrator_pose_success_flows_to_result(monkeypatch):
    """pose 可用 → result["spans"] 为实测值，且 vision_meta 有据可查。"""
    import app.models.pose as pose_mod
    from app.models.orchestrator import PipelineOrchestrator

    monkeypatch.setattr(pose_mod, "get_body_landmarks",
                        lambda _img: _standing_landmarks())
    img = Image.new("RGB", (60, 60), (245, 194, 158))
    result = PipelineOrchestrator().run_full_pipeline(img, local_vision=True)
    assert result["spans"] is not None
    assert "腿部" in result["spans"]
