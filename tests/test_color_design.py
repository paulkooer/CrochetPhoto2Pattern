"""Tests for photo-driven colorwork design (app/models/color_design.py)."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.models import subject
from app.models.color_design import (
    PART_SPAN,
    _is_shading_look,
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


def _shaded_single_colour_subject():
    """浅背景上的单色主体，下半身在阴影里（行程照常见）——真实照片的样子。"""
    img = Image.new("RGB", (200, 400), (168, 168, 164))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([70, 20, 130, 390], radius=20, fill=(216, 200, 184))
    d.rectangle([70, 280, 130, 390], fill=(120, 120, 104))  # 下段阴影（少数）
    return img


def test_bands_read_lit_colour_so_shading_is_not_a_second_colour(monkeypatch):
    """单色玩偶不该因阴影被读成两色（真实照片里耳朵因此配成深灰色）。"""
    img = _shaded_single_colour_subject()
    colors = {b["color"] for b in vertical_color_bands(img, n_bands=10)}
    assert len(colors) == 1 and "深灰色" not in colors
    monkeypatch.setattr(subject, "shaded_area",
                        lambda m, i: np.zeros(m.shape, bool))
    plain = {b["color"] for b in vertical_color_bands(img, n_bands=10)}
    assert "深灰色" in plain        # 不做"只取受光面"就会凭空多出阴影色


def _gradient_mask():
    mask = np.zeros((160, 100), bool)
    mask[8:153, 30:71] = True
    return mask


def _shaded_gradient_subject(lit, dark, *, boundary=0.6, noise=18, seed=7):
    """浅背景上的单色主体：下半段只是受光更暗（照片里的常见样子）。

    主体内加确定性噪声，模拟照片里逐像素的颜色分布——正是这种分布让同一材质
    沿毛线色表边界移动，逐带投票因此可能把一只单色玩偶读成两色。
    """
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (100, 160), (168, 168, 164))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([30, 8, 70, 152], radius=8, fill=lit)
    d.rectangle([30, int(160 * boundary), 70, 152], fill=dark)
    arr = np.asarray(img, dtype=np.int16)
    inside = np.zeros(arr.shape[:2], bool)
    inside[10:150, 32:69] = True
    arr = np.where(inside[:, :, None],
                   arr + rng.integers(-noise, noise + 1, size=arr.shape), arr)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def _bands_with_given_mask(monkeypatch, image, **kwargs):
    """隔离分割：直接给出主体掩码，只考察配色判定本身。"""
    monkeypatch.setattr(subject, "extract_subject",
                        lambda image, **_: (_gradient_mask(), image))
    return vertical_color_bands(image, n_bands=10, **kwargs)


def test_shading_gradient_band_merges_into_lit_neighbour(monkeypatch):
    """同一材质下半段更暗：暗带并回受光带色号，不另立一色（真实照片的样子）。"""
    image = _shaded_gradient_subject((203, 193, 170), (152, 145, 128))
    assert [b["color"] for b in _bands_with_given_mask(monkeypatch, image)] == ["灰色"]
    plain = [b["color"] for b in
             _bands_with_given_mask(monkeypatch, image, unify_shading=False)]
    assert set(plain) == {"灰色", "小麦肤色"}   # 不并入时正是"凭空多出一色"


def test_uniform_dark_step_keeps_its_own_colour(monkeypatch):
    """均匀色块的暗带投票是决定性的，不并入——与保护真换色的是同一条判据。"""
    image = _shaded_gradient_subject((203, 193, 170), (152, 145, 128), noise=0)
    assert [b["color"] for b in _bands_with_given_mask(monkeypatch, image)] == \
        ["灰色", "小麦肤色"]


def test_clear_colour_change_is_not_unified(monkeypatch):
    """亮度接近但色度不同的真换色（暖橙）保持两色。"""
    image = _shaded_gradient_subject((203, 193, 170), (200, 150, 120))
    assert [b["color"] for b in _bands_with_given_mask(monkeypatch, image)] == \
        ["灰色", "棕肤色"]


def test_near_neutral_two_tone_keeps_both_colours(monkeypatch):
    """白 + 浅灰双色：色度与亮度比都落在受光窗口内，投票决定性仍然保住两色。"""
    image = _shaded_gradient_subject((245, 245, 245), (190, 190, 190), noise=6)
    assert [b["color"] for b in _bands_with_given_mask(monkeypatch, image)] == \
        ["浅灰色", "灰色"]


@pytest.mark.parametrize("darker,lighter,gap,expected", [
    ((152, 145, 128), (203, 193, 170), 0.20, True),    # 同色度、受光更暗、投票不牢靠
    ((60, 60, 60), (203, 193, 170), 0.20, False),      # 亮度比过低：更像另一种颜色
    ((200, 190, 168), (203, 193, 170), 0.20, False),   # 几乎同亮度：不是受光差异
    ((152, 145, 128), (203, 193, 170), 0.60, False),   # 投票决定性：不覆盖证据
    ((200, 150, 120), (203, 193, 170), 0.20, False),   # 亮度接近但色度不同＝真换色
    ((0, 0, 0), (245, 245, 245), 0.20, False),         # 极暗带色度崩掉（黑）
])
def test_shading_look_judgement(darker, lighter, gap, expected):
    """三条判据（亮度窗口、投票不牢靠、色度一致）逐条可分辨。"""
    assert _is_shading_look(darker, lighter, gap) is expected


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


def test_mixed_black_white_yarn_does_not_invent_grey(monkeypatch):
    import numpy as np

    image = Image.new("RGB", (100, 100), "black")
    ImageDraw.Draw(image).rectangle((60, 0, 99, 99), fill="white")
    monkeypatch.setattr("app.models.subject.extract_subject",
                        lambda image, **kw: (np.ones((100, 100), dtype=bool), image))
    assert vertical_color_bands(image) == [{"start": 0.0, "end": 1.0, "color": "黑色"}]


def test_fallback_empty_bands_do_not_introduce_background(monkeypatch):
    monkeypatch.setattr("app.models.subject.extract_subject", lambda *a, **kw: None)
    image = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((30, 30, 69, 69), fill=(0, 120, 215))
    assert vertical_color_bands(image) == [{"start": 0.0, "end": 1.0, "color": "蓝色"}]


def test_internal_empty_bands_use_nearest_observation(monkeypatch):
    import numpy as np

    image = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 10, 69, 19), fill="black")
    draw.rectangle((30, 70, 69, 79), fill=(0, 120, 215))
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:20, 30:70] = mask[70:80, 30:70] = True
    monkeypatch.setattr("app.models.subject.extract_subject", lambda *a, **kw: (mask, image))
    assert vertical_color_bands(image) == [
        {"start": 0.0, "end": 0.5, "color": "黑色"},
        {"start": 0.5, "end": 1.0, "color": "蓝色"},
    ]


def test_wrong_width_mask_falls_back(monkeypatch):
    import numpy as np

    image = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((30, 30, 69, 69), fill=(0, 120, 215))
    monkeypatch.setattr("app.models.subject.extract_subject",
                        lambda *a, **kw: (np.ones((100, 50), dtype=bool), image))
    assert vertical_color_bands(image) == [{"start": 0.0, "end": 1.0, "color": "蓝色"}]
