"""耳朵的本地推断：轮廓测量 → 部件表 → 图解里的长耳。

照片层原先写死 `["头部","身体","手臂","腿部"]`，耳朵只能靠人工补选；这里验证
"顶部窄段"测量能把耳朵自动测出来、并在图解里生成真正的长耳（而不是 6 针小球）。
"""
import numpy as np
import pytest
from PIL import Image

from app.models.crochet_params import CrochetParamsGenerator
from app.models.geometry import measure_ears
from app.models.local_vision import _CANONICAL_PARTS, analyze
from app.models.structure_designer import StructureDesigner
from app.models.subject import SubjectObservation
from app.schemas import ImageAnalysis

W, H = 60, 120


def _bunny_mask(ear_h: int = 45, ear_w: int = 7, gap: int = 8) -> np.ndarray:
    """长耳兔子剪影：两片窄长耳朵 + 圆头 + 直筒身体。"""
    mask = np.zeros((H, W), bool)
    cx = W // 2
    for x0 in (cx - gap // 2 - ear_w, cx + gap // 2):
        mask[:ear_h, x0:x0 + ear_w] = True
    head_h, head_w = 45, 40
    for i in range(head_h):
        half = int(head_w / 2 * np.sin(np.pi * (i + 0.5) / head_h) ** 0.35) or 1
        mask[ear_h + i, cx - half:cx + half] = True
    mask[ear_h + head_h:] = False
    mask[ear_h + head_h:ear_h + head_h + 30,
         cx - head_w // 2:cx + head_w // 2] = True
    return mask


def _doll_mask() -> np.ndarray:
    """圆头无耳娃娃剪影：宽度从顶部平滑长起来（不应被当成耳朵）。"""
    mask = np.zeros((H, W), bool)
    cx, head_h, head_w = W // 2, 55, 44
    for i in range(head_h):
        half = int(head_w / 2 * np.sin(np.pi * (i + 0.5) / head_h) ** 0.5) or 1
        mask[6 + i, cx - half:cx + half] = True
    mask[6 + head_h:6 + head_h + 45, cx - head_w // 3:cx + head_w // 3] = True
    return mask


def _splayed_bunny_mask(ear_h: int = 40, ear_w: int = 18, gap: int = 6,
                        head_h: int = 45, head_w: int = 40,
                        body_h: int = 30) -> np.ndarray:
    """外张长耳：两耳合计宽度已接近头宽，顶部并**不**窄——只有耳间缺口能
    说明这里分开过。窄带判据会有意漏掉它，分裂判据必须抓到（真实照片即此形）。"""
    mask = np.zeros((H, W), bool)
    cx = W // 2
    for x0 in (cx - gap // 2 - ear_w, cx + gap // 2):
        mask[:ear_h, x0:x0 + ear_w] = True
    for i in range(head_h):
        half = int(head_w / 2 * np.sin(np.pi * (i + 0.5) / head_h) ** 0.35) or 1
        mask[ear_h + i, cx - half:cx + half] = True
    mask[ear_h + head_h:ear_h + head_h + body_h,
         cx - head_w // 2:cx + head_w // 2] = True
    return mask


def test_splayed_ears_are_measured_from_the_split_not_the_width():
    """外张耳（真实照片形态）：顶部合计宽度 > 峰值一半 → 窄带判据失效，
    必须靠"分裂成两段"识别；且测出的耳宽是单耳宽而非合计宽度。"""
    got = measure_ears(_splayed_bunny_mask())
    assert got is not None
    length_ratio, width_ratio = got
    # 波段从耳尖到"头顶不再是窄/分裂"为止：耳 40 行 + 头顶前几行（也窄）
    assert 40 / 115 <= length_ratio <= 45 / 115
    assert width_ratio == pytest.approx(18 / 115, abs=0.02)
    assert length_ratio / width_ratio > 2.0


def test_long_ears_are_measured():
    got = measure_ears(_bunny_mask())
    assert got is not None
    length_ratio, width_ratio = got
    assert length_ratio == pytest.approx(0.40, abs=0.02)
    assert width_ratio < 0.10
    assert length_ratio / width_ratio > 2.0        # 长耳


def test_round_head_is_not_ears():
    assert measure_ears(_doll_mask()) is None


def test_noise_and_degenerate_masks_are_not_ears():
    assert measure_ears(np.random.default_rng(0).random((H, W)) > 0.7) is None
    assert measure_ears(np.zeros((H, W), bool)) is None
    assert measure_ears(np.zeros((5, W), bool)) is None
    # 掩码没分开主体/背景（窄段一路到底）→ 宁可不报，不当成长耳
    assert measure_ears(np.ones((H, W), bool)) is None


def test_measure_ears_rejects_non_2d():
    assert measure_ears(np.zeros((3, 4, 5), bool)) is None


def _analysis_for_mask(mask: np.ndarray):
    """把合成掩码当"用户已修正掩码"喂给本地视觉（不跑真分割）。"""
    image = Image.new("RGB", (W, H), (240, 238, 235))
    subject = SubjectObservation.from_reviewed_mask(image, mask, image)
    return analyze(image, subject=subject)


def test_local_vision_adds_ears_from_silhouette():
    analysis, meta = _analysis_for_mask(_bunny_mask())
    assert analysis.parts == [*_CANONICAL_PARTS, "耳朵"]
    assert meta["parts_source"] == "silhouette_ears"
    assert meta["requires_subject_review"] is True      # 仍需人工确认
    measured = meta["ears_measured"]
    assert measured["basis"] == "silhouette_top_band"
    assert analysis.ear_length_ratio == pytest.approx(
        measured["length_ratio"], abs=0.001)
    assert analysis.ear_width_ratio == pytest.approx(
        measured["width_ratio"], abs=0.001)


def test_local_vision_keeps_template_when_no_ears():
    analysis, meta = _analysis_for_mask(_doll_mask())
    assert analysis.parts == list(_CANONICAL_PARTS)
    assert analysis.ear_length_ratio is None
    assert analysis.ear_width_ratio is None
    assert meta["parts_source"] == "default_template"


def test_local_vision_without_subject_has_no_ears():
    """没有主体观测（未分割）时不得凭空加耳朵。"""
    analysis, meta = analyze(Image.new("RGB", (W, H), (240, 238, 235)))
    assert analysis.parts == list(_CANONICAL_PARTS)
    assert "ears_measured" not in meta
    assert analysis.ear_length_ratio is None


def test_photo_to_pattern_end_to_end_gives_a_long_ear():
    """照片（掩码）→ 部件 → 结构 → 图解：耳朵必须是长管，不是 6 针小球。"""
    analysis, _meta = _analysis_for_mask(_bunny_mask())
    structure = StructureDesigner.design_3d_structure(analysis)
    ear_spec = next(p for p in structure["parts"] if p["name"] == "耳朵")
    assert ear_spec["shape"] == "ear"
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    ear = next(p for p in params["parts"] if p["name"] == "耳朵")
    assert len(ear["rounds"]) >= 10                 # 长，不是球
    assert ear["height_cm"] > 2 * ear["diameter_cm"]   # 长宽比 > 2（耳不是球）
    assert max(r["stitches"] for r in ear["rounds"]) >= 6
    assert ear["rounds"][0]["stitches"] < ear["rounds"][1]["stitches"]  # 耳根加针
    assert ear["rounds"][-1]["stitches"] < ear["rounds"][-2]["stitches"]  # 耳尖收口


def test_round_lobe_ratio_still_makes_a_long_tube():
    """轮廓量到的耳长只是下界：圆形耳片也按长耳下限做管，不做成球。"""
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "耳朵"], ear_length_ratio=0.10, ear_width_ratio=0.09,
    )
    structure = StructureDesigner.design_3d_structure(analysis)
    ear_spec = next(p for p in structure["parts"] if p["name"] == "耳朵")
    assert ear_spec["shape"] == "ear"
    # dim() 按 0.1cm 取整，故留一个最小刻度容差
    assert ear_spec["length_cm"] >= 2.4 * ear_spec["diameter_cm"] - 0.1
