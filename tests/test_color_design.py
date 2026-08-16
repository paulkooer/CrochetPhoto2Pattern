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
    assert colors[0] in ("深棕色", "黑色")   # 顶部头发带（暗色系）
    assert colors[-1] == "蓝色"             # 底部衣服带
    # start/end 覆盖 0..1 且单调
    assert bands[0]["start"] == 0.0 and bands[-1]["end"] == 1.0


def test_part_span_slices_bands():
    bands = vertical_color_bands(_two_tone_image(), n_bands=10)
    head_blocks = color_blocks_for_part(bands, "头部")   # 0.05–0.30 → 深棕为主
    body_blocks = color_blocks_for_part(bands, "身体")   # 0.30–0.62 → 蓝
    assert head_blocks and head_blocks[0][2] in ("深棕色", "黑色")
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
