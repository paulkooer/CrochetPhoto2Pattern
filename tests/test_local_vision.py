"""Tests for the no-LLM local vision path (app/models/local_vision.py)."""
from PIL import Image

from app.models.image_parser import ImageParser
from app.models.local_vision import (
    DEFAULT_HEAD_CM,
    MAX_BODY_RATIO,
    _detect_face,
    analyze,
)
from app.models.orchestrator import PipelineOrchestrator
from app.schemas import ImageAnalysis


def _img(w=200, h=400) -> Image.Image:
    return Image.new("RGB", (w, h), (245, 194, 158))


# ── 比例推算（注入假检测结果，纯数学验证）───────────────────────────────────

def test_face_box_drives_proportions(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (80, 20, 40, 40))
    analysis, meta = analyze(_img(200, 400))
    # subject_px = 400×0.9 = 360, head_px = 40 → ratio 9 → 钳到 8.0
    assert meta["source"] == "opencv-face"
    assert meta["body_ratio"] == MAX_BODY_RATIO
    assert analysis.height_cm == round(DEFAULT_HEAD_CM * 8.0, 1)
    assert analysis.body_type == "瘦"
    assert analysis.head_diameter_cm == DEFAULT_HEAD_CM
    assert analysis.parts == ["头部", "身体", "手臂", "腿部"]
    assert meta["head_cm_anchor"] == DEFAULT_HEAD_CM


def test_mid_ratio_is_standard_build(monkeypatch):
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (60, 30, 80, 80))
    analysis, meta = analyze(_img(200, 400))
    # 360/80 = 4.5 → 标准
    assert meta["body_ratio"] == 4.5
    assert analysis.body_type == "标准"
    assert analysis.height_cm == 40.5


def test_big_head_ratio_is_chubby(monkeypatch):
    """大头照（头占画面 1/3）→ 胖（Q 版）。"""
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (25, 40, 150, 150))
    analysis, meta = analyze(_img(200, 400))
    assert meta["body_ratio"] == 2.4  # 360/150
    assert analysis.body_type == "胖"


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
    assert analysis.body_type == "标准"
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
    monkeypatch.setattr("app.models.image_parser.load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (60, 30, 80, 80))
    parser = ImageParser()
    result = parser.parse_image_local(_img())
    assert result.body_type == "标准"
    assert parser.last_local_meta["body_ratio"] == 4.5
    assert parser.last_local_meta["source"] == "opencv-face"


def test_full_pipeline_local_vision_mode(monkeypatch):
    """local_vision=True：全程无 LLM，vision_meta 透传到结果。"""
    monkeypatch.setattr("app.models.local_vision._detect_face",
                        lambda _img: (60, 30, 80, 80))
    orch = PipelineOrchestrator()
    result = orch.run_full_pipeline(_img(), local_vision=True)
    assert set(result.keys()) == {
        "analysis", "structure", "params", "usage", "vision_meta", "gauge",
    }
    assert result["gauge"]["stitches_per_10cm"] > 0  # gauge 透传（M4.15）
    assert result["analysis"]["body_type"] == "标准"
    assert [p.name for p in result["params"]["parts"]] == ["头部", "身体", "手臂", "腿部"]
    assert result["vision_meta"]["source"] == "opencv-face"
    assert result["usage"] == {}  # 无 LLM 调用


def test_full_pipeline_llm_mode_has_no_vision_meta():
    """LLM 路径（mock 解析）vision_meta 应为空，不显示本地来源提示。"""
    from unittest.mock import patch

    orch = PipelineOrchestrator()
    with patch.object(ImageParser, "parse_image", return_value=ImageAnalysis(
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


def test_silhouette_flare_adds_skirt(monkeypatch):
    from app.models import local_vision as lv
    monkeypatch.setattr(lv, "_detect_face", lambda _i: None)  # 关闭人脸路径
    analysis, meta = lv.analyze(_person(dress=True))
    assert "裙子" in analysis.parts
    assert meta["silhouette"]["flare"] is True


def test_straight_silhouette_no_skirt(monkeypatch):
    from app.models import local_vision as lv
    monkeypatch.setattr(lv, "_detect_face", lambda _i: None)
    analysis, meta = lv.analyze(_person(dress=False))
    assert "裙子" not in analysis.parts
    # 剖面始终透传（M1.1），但无裙摆时不带 flare 标记
    assert not (meta.get("silhouette") or {}).get("flare")


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
    head = [p for p in result["params"]["parts"] if p.name == "头部"][0]
    body = [p for p in result["params"]["parts"] if p.name == "身体"][0]
    # 头部圈色来自照片顶部（暗色系），身体来自中段（蓝系）
    assert head.rounds[0].color in ("黑色", "深棕色")
    assert body.rounds[-1].color == "蓝色"
    # 换线说明出现在颜色变化圈（头部黑→蓝）
    changes = [r for r in head.rounds if r.notes and "换线" in r.notes]
    assert changes, "头部应有换线圈"
    # 部件 notes 带配色摘要（多色部件才有）
    assert "配色" in (head.notes or "")


def test_no_image_no_colorwork():
    """手动模式（无照片）：圈色为 None、notes 无换线（单色降级）。"""
    from unittest.mock import patch as _patch

    from app.models.orchestrator import PipelineOrchestrator as Orch
    orch = Orch()
    with _patch.object(ImageParser, "parse_image", return_value=ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["头部"],
    )):
        # 纯色 40x40 无主体 → bands 空 → 降级
        result = orch.run_full_pipeline(Image.new("RGB", (40, 40), (255, 255, 255)))
    head = result["params"]["parts"][0]
    assert all(r.color is None for r in head.rounds)
    assert "换线" not in (head.notes or "")


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
    body = [p for p in result["params"]["parts"] if p.name == "身体"][0]
    assert body.type == "profile"
    wall = [r.stitches for r in body.rounds]
    n_dome = wall[0] // 6
    wall_st = wall[n_dome:]
    assert len(set(wall_st)) > 1, f"剖面驱动身体不应是等粗筒: {wall_st}"
    assert "照片驱动轮廓身体" in body.notes
    assert result["gauge"]["stitches_per_10cm"] > 0
