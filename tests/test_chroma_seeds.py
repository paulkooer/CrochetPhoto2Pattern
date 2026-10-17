"""色度种子档（subject.extract_subject 的 YCrCb 分档）。

背景与半透明阴影/水印是"同一表面按比例变暗"，色度几乎不变；浅粉/浅棕这类
浅色主体亮度与阴影重叠、色度却高出一个量级。所以亮度档抓不到、色度档能抓。

本档**只做加法**：不把任何像素降级成背景（实测把"比背景暗的中性像素"降级
会让深灰/中灰玩偶整只判没，而半透明水印照样留在掩码里——色度不负责去水印）。
"""
import pytest
from PIL import Image, ImageDraw

from app.models.subject import extract_subject


def _pale_subject_with_darker_neutral_mark() -> Image.Image:
    """中性背景 + 左中一块更深的**中性**污渍 + 浅粉主体。

    到背景的亮度 L1：主体 ~102（< 强制前景下限 144 → 旧口径直接丢成背景），
    污渍 ~174（> 144 → 旧口径反而钉成确定前景）。到背景的色度：主体 ~15
    （> 确定前景下限 12），污渍 ~0——真实照片正是"亮度分不开、色度分得开"。
    """
    image = Image.new("RGB", (120, 200), (168, 168, 164))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 60, 45, 190), fill=(110, 110, 106))   # 深中性块
    draw.ellipse((40, 75, 90, 125), fill=(216, 196, 190))     # 浅粉头
    draw.rectangle((45, 125, 85, 185), fill=(214, 195, 189))  # 浅粉身体
    return image


def test_pale_chromatic_subject_is_seeded_by_chroma():
    """浅色主体的亮度距背景低于强制前景下限时，色度档必须把它锚进掩码。"""
    result = extract_subject(_pale_subject_with_darker_neutral_mark(), max_side=120)
    assert result is not None, "浅色主体图不应回退启发式"
    mask, _small = result
    h, w = mask.shape
    assert mask[int(100 * h / 200), int(65 * w / 120)]   # 头部中心
    assert mask[int(155 * h / 200), int(65 * w / 120)]   # 身体中心


@pytest.mark.parametrize("subject", [(60, 60, 60), (150, 150, 150), (74, 58, 46)])
def test_neutral_and_dark_subjects_still_segment(subject):
    """中性/深色主体色度≈0，色度档不动它们，只能靠亮度档锚定——不能回归。"""
    image = Image.new("RGB", (140, 220), (235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.ellipse((45, 40, 95, 90), fill=subject)      # 头
    draw.rectangle((50, 90, 90, 175), fill=subject)   # 身体
    result = extract_subject(image, max_side=120)
    assert result is not None, f"{subject} 主体不应回退启发式"
    mask, _small = result
    h, w = mask.shape
    assert mask[int(65 * h / 220), int(70 * w / 140)]    # 头
    assert mask[int(130 * h / 220), int(70 * w / 140)]   # 身体
