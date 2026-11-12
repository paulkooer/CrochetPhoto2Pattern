"""Tests for the no-LLM local vision path (app/models/local_vision.py)."""
import pytest
from PIL import Image

from app.models.image_parser import ImageParser
from app.models.local_vision import (
    _detect_face,
    analyze,
)
from app.models.orchestrator import PipelineOrchestrator
from app.schemas import ImageAnalysis


def _img(w=200, h=400) -> Image.Image:
    return Image.new("RGB", (w, h), (245, 194, 158))


# ── 比例推算（注入假检测结果，纯数学验证）───────────────────────────────────
# 人脸框按 HEAD_HEIGHT_PER_FACE=1.5 扩展为整头后再计算头身比。

def test_tiny_face_candidate_is_not_clamped_into_plausible_proportions(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (90, 20, 26, 26))
    analysis, meta = analyze(_img(200, 400))
    # 360/(26×1.5) ≈ 9.2 exceeds the supported ratio: do not silently clamp to 8.
    assert meta["source"] == "default"
    assert "过小" in meta["face_rejection_reason"]
    assert meta["rejected_face_box"] == [90, 20, 26, 26]
    assert "face_box" not in meta
    assert "body_ratio" not in meta
    assert analysis.height_cm == 18
    assert analysis.parts == ["头部", "身体", "手臂", "腿部"]


def test_mid_ratio_does_not_guess_body_type(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (70, 30, 60, 60))
    analysis, meta = analyze(_img(200, 400))
    # 360/(60×1.5) = 4.0, which says nothing about body fat.
    assert meta["body_ratio"] == 4.0
    assert analysis.body_type == "未评估"
    assert analysis.height_cm == 36.0


def test_big_head_does_not_imply_chubby_body(monkeypatch):
    """A large head-to-height ratio is not a body-type classification."""
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (50, 40, 100, 100))
    analysis, meta = analyze(_img(200, 400))
    assert meta["body_ratio"] == 2.4  # 360/(100×1.5)
    assert analysis.body_type == "未评估"


def test_body_type_label_does_not_change_generated_stitches(monkeypatch):
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.structure_designer import StructureDesigner

    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: (70, 30, 60, 60))
    analysis, _ = analyze(_img())
    structure = StructureDesigner.design_3d_structure(analysis)
    normal = CrochetParamsGenerator.generate_params(analysis, structure)
    relabeled = CrochetParamsGenerator.generate_params(
        analysis.model_copy(update={"body_type": "胖"}), structure)
    assert relabeled == normal


def test_min_ratio_clamped(monkeypatch):
    """极端大脸（几乎占满画面）也不得低于 MIN_BODY_RATIO=2。"""
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (0, 0, 190, 190))
    analysis, meta = analyze(_img(200, 400))
    assert meta["body_ratio"] == 2.0
    assert analysis.height_cm == 18.0


def test_no_face_falls_back_to_defaults(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: None)
    analysis, meta = analyze(_img())
    assert meta["source"] == "default"
    assert analysis.height_cm == 18.0
    assert analysis.body_type == "未评估"
    assert "未检出人脸" in analysis.main_features[0]


def test_colors_from_real_image_attached(monkeypatch):
    """推荐色板来自本地量化（肤色图 → 浅肤色），不走 LLM。"""
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: None)
    analysis, _ = analyze(_img())
    assert analysis.recommended_colors and analysis.recommended_colors[0] == "浅肤色"


# ── 真实 cv2 路径（合成图无人脸 → default；验证不崩）───────────────────────

def test_real_detector_on_synthetic_image():
    box = _detect_face(_img(100, 100))
    assert box is None  # 纯色图检不出人脸
    analysis, meta = analyze(_img(100, 100))
    assert isinstance(analysis, ImageAnalysis)
    assert meta["source"] in ("default", "opencv-face")


# ── parser / orchestrator 集成 ─────────────────────────────────────────────

def test_parse_image_local_records_meta(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (70, 30, 60, 60))
    parser = ImageParser()
    result = parser.parse_image_local(_img())
    assert result.body_type == "未评估"
    assert parser.last_local_meta["body_ratio"] == 4.0
    assert parser.last_local_meta["source"] == "opencv-face"


def test_full_pipeline_local_vision_mode(monkeypatch):
    """local_vision=True：全程无 LLM，vision_meta 透传到结果。"""
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (70, 30, 60, 60))
    orch = PipelineOrchestrator()
    result = orch.run_full_pipeline(_img(), local_vision=True)
    assert set(result.keys()) == {
        "analysis", "structure", "params", "usage", "vision_meta", "gauge",
        "style", "color_bands", "spans", "spans_measured", "preview",
        "sizing", "geometry", "generator_version", "diagnostics",
    }
    assert result["gauge"]["stitches_per_10cm"] > 0  # gauge 透传（M4.15）
    assert result["analysis"]["body_type"] == "未评估"
    assert [p["name"] for p in result["params"]["parts"]] == ["头部", "身体", "手臂", "腿部"]
    assert result["vision_meta"]["source"] == "opencv-face"
    assert result["usage"] == {}  # 无 LLM 调用
    assert result["analysis"]["height_cm"] == 18.0
    assert result["sizing"]["absolute_scale_from_photo"] is False
    assert result["geometry"]["schema_version"] == "1.0"


def test_stubbed_local_parser_has_no_vision_meta():
    """替身不提供元数据时不编造来源。"""
    from unittest.mock import patch

    orch = PipelineOrchestrator()
    with patch.object(ImageParser, "parse_image_local", return_value=ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"],
    )):
        result = orch.run_full_pipeline(Image.new("RGB", (40, 40)))
    assert result["vision_meta"] == {}


# ── 轮廓剖面：下摆展开 → 自动加裙子 ────────────────────────────────────────

def _person(dress: bool) -> Image.Image:
    """浅背景人形剪影：dress=True 下摆展开（A 字裙），否则直筒。"""
    from PIL import ImageDraw
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([75, 10, 125, 60], fill=(230, 180, 150))          # 头
    d.rounded_rectangle([80, 65, 120, 150], radius=15, fill=(0, 120, 215))  # 上衣
    if dress:
        d.polygon([(70, 150), (130, 150), (155, 390), (45, 390)], fill=(220, 50, 50))
    else:
        d.rounded_rectangle([78, 150, 122, 390], radius=15, fill=(70, 130, 180))
    return img


def test_silhouette_flare_is_review_hint_not_automatic_skirt(monkeypatch):
    from app.models import local_vision as lv
    monkeypatch.setattr(lv, "_detect_face", lambda _i: None)  # 关闭人脸路径
    analysis, meta = lv.analyze(_person(dress=True))
    assert "裙子" not in analysis.parts
    assert analysis.parts == ["头部", "身体", "手臂", "腿部"]
    assert meta["possible_skirt"] is True
    assert meta["possible_ears"] is False
    assert meta["possible_tail"] is False
    assert meta["parts_source"] == "default_template"
    assert meta["requires_subject_review"] is True
    assert "silhouette" not in meta  # 几何数据已移至独立 geometry IR
    assert lv._has_bottom_flare(lv._silhouette_profile(_person(dress=True)))


def test_straight_silhouette_no_skirt(monkeypatch):
    from app.models import local_vision as lv
    monkeypatch.setattr(lv, "_detect_face", lambda _i: None)
    analysis, meta = lv.analyze(_person(dress=False))
    assert "裙子" not in analysis.parts
    assert meta["possible_skirt"] is False
    assert meta["possible_ears"] is False
    assert meta["possible_tail"] is False
    assert "silhouette" not in meta
    assert meta["source"] == "silhouette-head"
    assert meta["parts_source"] == "default_template"
    _x, y, _w, h = meta["head_box"]
    assert y + h / 2 < _person(dress=False).height / 2


def test_silhouette_profile_normalized():
    from app.models.local_vision import _has_bottom_flare, _silhouette_profile
    prof = _silhouette_profile(_person(dress=True))
    assert prof is not None and len(prof) == 40
    assert all(0.0 <= x <= 1.0001 for x in prof)
    assert _has_bottom_flare(prof) is True
    prof2 = _silhouette_profile(_person(dress=False))
    assert _has_bottom_flare(prof2) is False


# ── 照片驱动的逐圈配色（color_bands 贯穿 generate_params）─────────────────

def test_color_bands_drive_round_colors():
    from app.models.orchestrator import PipelineOrchestrator as Orch
    from tests.test_color_design import _two_tone_image
    img = _two_tone_image()
    orch = Orch()
    result = orch.run_full_pipeline(img, local_vision=True)
    head = [p for p in result["params"]["parts"] if p["name"] == "头部"][0]
    body = [p for p in result["params"]["parts"] if p["name"] == "身体"][0]
    # 头部圈色来自照片顶部（暗色系），身体来自中段（蓝系）
    assert head["rounds"][0]["color"] in ("黑色", "深棕色", "暗肤色", "深褐肤色", "咖啡肤色")
    assert body["rounds"][-1]["color"] == "蓝色"
    # 换线说明出现在颜色变化圈（头部黑→蓝）
    changes = [r for r in head["rounds"] if r.get("notes") and "换线" in r.get("notes")]
    assert changes, "头部应有换线圈"
    # 部件 notes 带配色摘要（多色部件才有）
    assert "配色" in (head.get("notes") or "")


def test_no_image_no_colorwork():
    """手动模式（无照片）：圈色为 None、notes 无换线（单色降级）。"""
    from unittest.mock import patch as _patch

    from app.models.orchestrator import PipelineOrchestrator as Orch
    orch = Orch()
    with _patch.object(ImageParser, "parse_image_local", return_value=ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["头部"],
    )):
        # 纯色 40x40 无主体 → bands 空 → 降级
        result = orch.run_full_pipeline(Image.new("RGB", (40, 40), (255, 255, 255)))
    head = result["params"]["parts"][0]
    assert all(r["color"] is None for r in head["rounds"])
    assert "换线" not in (head.get("notes") or "")


def test_photo_driven_profile_body_end_to_end():
    """照片剖面 → 身体轮廓驱动（M1.2 端到端）：梨形剪影产出的身体逐圈针数
    随剖面变化，而非等粗圆柱；且结果带 gauge 供渲染层使用。"""
    from PIL import Image, ImageDraw

    from app.models.orchestrator import PipelineOrchestrator as Orch

    img = Image.new("RGB", (200, 400), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([75, 5, 125, 55], fill=(230, 180, 150))                    # 头
    d.polygon([(85, 60), (115, 60), (150, 250), (50, 250)], fill=(0, 120, 215))  # 梨形身
    d.rounded_rectangle([55, 255, 90, 395], radius=12, fill=(70, 130, 180))
    d.rounded_rectangle([110, 255, 145, 395], radius=12, fill=(70, 130, 180))
    result = Orch().run_full_pipeline(img, local_vision=True)
    body = [p for p in result["params"]["parts"] if p["name"] == "身体"][0]
    assert body["type"] == "profile"
    wall = [r["stitches"] for r in body["rounds"]]
    n_dome = wall[0] // 6
    wall_st = wall[n_dome:]
    assert len(set(wall_st)) > 1, f"剖面驱动身体不应是等粗筒: {wall_st}"
    assert "照片驱动轮廓身体" in body.get("notes")
    assert result["gauge"]["stitches_per_10cm"] > 0
    assert result["geometry"]["silhouette"]["profile"]


def _eared_doll() -> Image.Image:
    from PIL import ImageDraw
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.ellipse([40, 28, 78, 78], fill=(230, 180, 150))
    draw.ellipse([122, 28, 160, 78], fill=(230, 180, 150))
    draw.ellipse([55, 40, 145, 140], fill=(230, 180, 150))
    draw.rounded_rectangle([78, 150, 122, 370], radius=12, fill=(0, 120, 215))
    return img


def _tailed_doll() -> Image.Image:
    from PIL import ImageDraw
    img = Image.new("RGB", (200, 400), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.ellipse([70, 16, 130, 76], fill=(230, 180, 150))
    draw.rounded_rectangle([78, 90, 122, 300], radius=12, fill=(0, 120, 215))
    draw.ellipse([108, 240, 142, 275], fill=(0, 120, 215))
    return img


def test_ear_and_tail_hints_do_not_enter_the_part_list(monkeypatch):
    from app.models import local_vision as lv
    monkeypatch.setattr(lv, "_detect_face", lambda _i: None)
    eared, eared_meta = lv.analyze(_eared_doll())
    assert eared_meta["possible_ears"] is True
    assert "耳朵" not in eared.parts
    assert eared.parts == ["头部", "身体", "手臂", "腿部"]
    tailed, tailed_meta = lv.analyze(_tailed_doll())
    assert tailed_meta["possible_tail"] is True
    assert tailed_meta["possible_ears"] is False
    assert tailed_meta["possible_skirt"] is False
    assert "尾巴" not in tailed.parts


def test_missing_contour_observations_are_unavailable_not_negative(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: None)
    _, meta = analyze(_img(), geometry_profile=None, geometry_observed=True)
    assert meta["possible_ears"] is None
    assert meta["possible_skirt"] is None
    assert meta["possible_tail"] is None


@pytest.mark.parametrize(("image_factory", "flag", "part"), [
    (lambda: _person(dress=True), "possible_skirt", "裙子"),
    (_eared_doll, "possible_ears", "耳朵"),
    (_tailed_doll, "possible_tail", "尾巴"),
])
def test_headless_pipeline_delivers_automatic_contour_candidates(monkeypatch, image_factory, flag, part):
    """Automatic delivery and the review draft share evidence, not review status."""
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: None)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda _img: None)
    image = image_factory()
    pipeline = PipelineOrchestrator()
    draft = pipeline.prepare_photo(image)
    assert draft.vision_meta[flag] is True
    assert part not in draft.analysis.parts  # interactive review remains explicit

    result = pipeline.run_full_pipeline(image, enforce_crochetability=False)
    assert part in result["analysis"]["parts"]
    assert part in {item["name"] for item in result["structure"]["parts"]}
    assert part in {item["name"] for item in result["params"]["parts"]}
    assert result["vision_meta"]["parts_source"] == "automatic_contour"
    assert part in result["vision_meta"]["automatic_parts"]
    assert result["vision_meta"]["requires_subject_review"] is True
    assert not result["vision_meta"].get("reviewed_by_user")
    from app.utils.provenance import provenance_lines

    provenance = provenance_lines(result)
    assert any("未经校准" in line and "轮廓" in line for line in provenance)
    assert not any("用户已确认" in line for line in provenance)


def test_headless_explicit_parts_override_contour_candidates(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: None)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda _img: None)
    result = PipelineOrchestrator().run_full_pipeline(
        _person(dress=True), parts=["头部", "身体"], enforce_crochetability=False)
    assert result["analysis"]["parts"] == ["头部", "身体"]
    assert [part["name"] for part in result["params"]["parts"]] == ["头部", "身体"]
    assert result["vision_meta"]["parts_source"] == "cli_explicit"
    assert not result["vision_meta"].get("reviewed_by_user")


def test_automatic_parts_and_unreviewed_provenance_survive_backup_and_resize(monkeypatch):
    from app.schemas import PatternResult
    from app.services.result_logic import import_backup, regenerate_with_size

    monkeypatch.setattr("app.models.local_vision._detect_face", lambda _img: None)
    monkeypatch.setattr("app.models.pose.get_body_landmarks", lambda _img: None)
    result = PipelineOrchestrator().run_full_pipeline(_person(dress=True), enforce_crochetability=False)
    restored = import_backup(PatternResult.from_result(result).to_backup(), "automatic")
    resized = regenerate_with_size(restored, 8, 20)
    for value in (restored, resized):
        assert "裙子" in value["analysis"]["parts"]
        assert "裙子" in {part["name"] for part in value["params"]["parts"]}
        assert value["vision_meta"]["parts_source"] == "automatic_contour"
        assert value["vision_meta"]["requires_subject_review"] is True
        assert not value["vision_meta"].get("reviewed_by_user")


def test_accepted_face_stays_ahead_of_the_contour_head(monkeypatch):
    from app.models import local_vision as lv
    monkeypatch.setattr(lv, "_detect_face", lambda _i: (70, 30, 60, 60))
    _analysis, meta = lv.analyze(_person(dress=False))
    assert meta["source"] == "opencv-face"
    assert meta["face_box"] == [70, 30, 60, 60]
    assert "裙子" not in _analysis.parts


def test_flare_detection_composition_invariant():
    """裙摆悬空（主体不贴图底）时下摆展开仍可检出（O2 配套改进）。

    旧版按整图高度取下摆窗口——主体下方有留白的构图里窗口落到背景，
    A 字裙漏检。现在窗口取在主体纵向范围内（首/末超阈行之间）。
    """
    from PIL import ImageDraw

    from app.models.local_vision import _has_bottom_flare, _silhouette_profile
    img = Image.new("RGB", (800, 1200), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([350, 60, 450, 160], fill=(230, 180, 150))
    d.rounded_rectangle([360, 170, 440, 330], radius=20, fill=(0, 120, 215))
    d.polygon([340, 340, 460, 340, 500, 700, 300, 700], fill=(220, 50, 50))
    prof = _silhouette_profile(img)
    assert prof is not None
    assert _has_bottom_flare(prof), "悬空裙摆漏检"
