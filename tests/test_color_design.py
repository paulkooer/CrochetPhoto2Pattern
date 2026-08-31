"""Tests for photo-driven colorwork design (app/models/color_design.py)."""
from PIL import Image, ImageDraw

from app.models.color_design import (
    PART_SPAN,
    blocks_summary_text,
    color_blocks_for_part,
    round_color,
    vertical_color_bands,
)


def _two_tone_image(top=(60, 40, 30), bottom=(0, 120, 215), bg=(245, 245, 245)):
    """浅色背景上的竖直人形：上半（头发）深棕，下半（衣服）蓝。"""
    img = Image.new("RGB", (200, 400), bg)
    d = ImageDraw.Draw(img)
    d.ellipse([70, 20, 130, 80], fill=top)                       # 头（上 15%）
    d.rounded_rectangle([75, 85, 125, 260], radius=20, fill=bottom)  # 上衣
    d.rounded_rectangle([60, 265, 140, 390], radius=20, fill=bottom)  # 下装
    return img


def test_bands_extract_two_tones_and_merge():
    bands = vertical_color_bands(_two_tone_image(), n_bands=10)
    assert 2 <= len(bands) <= 4  # 相邻同色已合并
    colors = [b["color"] for b in bands]
    assert colors[0] in ("深棕色", "黑色", "暗肤色", "深褐肤色", "咖啡肤色")  # 暗色系
    assert colors[-1] == "蓝色"             # 底部衣服带
    # start/end 覆盖 0..1 且单调
    assert bands[0]["start"] == 0.0 and bands[-1]["end"] == 1.0


def test_part_span_slices_bands():
    bands = vertical_color_bands(_two_tone_image(), n_bands=10)
    head_blocks = color_blocks_for_part(bands, "头部")   # 0.05–0.30 → 深棕为主
    body_blocks = color_blocks_for_part(bands, "身体")   # 0.30–0.62 → 蓝
    assert head_blocks and head_blocks[0][2] in (
        "深棕色", "黑色", "暗肤色", "深褐肤色", "咖啡肤色")  # 暗色系
    assert body_blocks and body_blocks[-1][2] == "蓝色"


def test_round_color_lookup_and_summary():
    blocks = [(0.0, 0.4, "深棕色"), (0.4, 1.0, "蓝色")]
    assert round_color(0.1, blocks) == "深棕色"
    assert round_color(0.9, blocks) == "蓝色"
    text = blocks_summary_text(["深棕色", "深棕色", "蓝色", "蓝色", "蓝色"])
    assert text == "R1–R2 深棕色；R3–R5 蓝色"


def test_unknown_part_has_no_span():
    assert "未知部件" not in PART_SPAN
    bands = vertical_color_bands(_two_tone_image())
    assert color_blocks_for_part(bands, "未知部件") == []


def test_bands_fail_safe_on_degenerate_image():
    assert vertical_color_bands(Image.new("RGB", (2, 2))) == []


def test_background_estimate_is_mode_not_mean():
    """双色背景（左上/右上白，左下/右下深灰）必须命中其中一色（fable5 F4：
    旧"量化后均值"落在两色中间，背景剔除会整体失效）。"""
    import numpy as np

    from app.models.color_design import estimate_background
    px = np.zeros((40, 40, 3), dtype=np.int16)
    px[:20, :] = 250          # 上半白
    px[20:, :] = 40           # 下半深灰
    r, g, b = estimate_background(px)
    # 命中白色桶或深灰桶之一，绝不能是两者的中间值（~145）
    assert (r > 200) or (r < 80), (r, g, b)


def test_background_mode_tolerates_jpeg_noise():
    import numpy as np

    from app.models.color_design import estimate_background
    rng = np.random.default_rng(7)
    px = np.full((40, 40, 3), 245, dtype=np.int16)
    px += rng.integers(-3, 4, px.shape)  # ±3 噪声
    r, g, b = estimate_background(px)
    assert abs(r - 245) <= 16 and abs(g - 245) <= 16


# ── O2：GrabCut 主体分割接入色带（Rother 2004）────────────────────────────

def _twobg_image():
    """双色背景（上白墙下深灰地板）+ 蓝色主体——旧启发式的痛点场景。"""
    img = Image.new("RGB", (200, 400), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 280, 200, 400], fill=(70, 70, 70))       # 地板
    d.rectangle([70, 60, 130, 350], fill=(0, 120, 215))      # 主体
    return img


def test_subject_mask_segments_subject_not_floor():
    """GrabCut 掩码应命中主体、剔除地板；纯背景图判退化返回 None。"""
    from app.models.subject import extract_subject
    res = extract_subject(_twobg_image(), max_side=120)
    assert res is not None, "GrabCut 应可用"
    mask, small = res
    h, w = mask.shape
    assert mask[h // 2, w // 2]            # 主体中心
    assert not mask[2, 2] and not mask[-3, -3]  # 角落（墙/地板）
    solid = extract_subject(Image.new("RGB", (120, 120), (200, 200, 200)),
                            max_side=120)
    assert solid is None                    # 纯背景 → 分割退化


def test_twobg_bands_exclude_floor_color():
    """端到端：地板色不得混进色带（旧启发式会把地板当主体）。"""
    bands = vertical_color_bands(_twobg_image(), n_bands=10)
    colors = {b["color"] for b in bands}
    assert "深灰色" not in colors and "灰色" not in colors, colors
    assert "蓝色" in colors


def test_empty_bands_propagate_nearest_subject_color():
    """主体未覆盖的横带延续最近主体色带，不落回背景均值。"""
    bands = vertical_color_bands(_twobg_image(), n_bands=10)
    colors = [b["color"] for b in bands]
    assert all(c == "蓝色" for c in colors[1:])  # 顶带之上无主体 → 延续
    assert all(c != "白色" for c in colors[1:])  # 白墙不得混入


# ── O-P1：Otsu 自适应阈值 + 人脸框种子（subject.py）───────────────────────

def test_otsu_threshold_bimodal_and_degenerate():
    """Otsu 对双峰距离分布给出峰间分割点；单峰/空分布返回 None。"""
    import numpy as np

    from app.models.subject import _otsu_threshold
    bimodal = np.array([0] * 500 + [200] * 500, dtype=np.int32)
    t = _otsu_threshold(bimodal)
    assert t is not None and 0 < t < 200
    assert _otsu_threshold(np.array([7] * 100, dtype=np.int32)) is None


def test_low_contrast_subject_still_segmented():
    """主体/背景 L1 距 30（< 旧固定阈 48）时 Otsu 下探仍能分割（O-P1）。"""
    from app.models.subject import extract_subject
    img = Image.new("RGB", (200, 300), (235, 235, 235))
    ImageDraw.Draw(img).rectangle([60, 80, 140, 260], fill=(245, 245, 245))
    res = extract_subject(img, max_side=120)
    assert res is not None, "低对比度图不应回退"
    mask, _small = res
    h, w = mask.shape
    assert mask[h // 2, w // 2] and not mask[3, 3]


def test_face_box_seed_forces_foreground(monkeypatch):
    """人脸框作为 GC_FGD 种子：颜色与背景一致的主体靠检测框锚定（O-P1）。

    框面积 >50% 图幅时弃用（防误检支配整图）。
    """
    import app.models.subject as subj_mod
    from app.models.subject import extract_subject

    img = Image.new("RGB", (120, 120), (200, 200, 200))  # 纯背景
    # 正常大小的框 → 中心被锚定为主体
    monkeypatch.setattr(subj_mod, "_face_box",
                        lambda _img: (30, 30, 60, 60))
    res = extract_subject(img, max_side=120)
    assert res is not None
    mask, _ = res
    assert mask[60, 60] and not mask[3, 3]

    # 过大的框（>50% 图幅）→ 弃用 → 全背景 → 分割退化 None
    monkeypatch.setattr(subj_mod, "_face_box",
                        lambda _img: (5, 5, 110, 110))
    assert extract_subject(img, max_side=120) is None
