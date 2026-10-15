"""Local photo parser and palette regression tests."""
from PIL import Image

from app.models.colors import nearest_yarn
from app.models.image_parser import ImageParser, extract_color_palette
from app.schemas import ImageAnalysis


def test_mock_analysis_returns_valid_schema():
    result = ImageParser._mock_analysis()
    assert isinstance(result, ImageAnalysis)
    assert result.difficulty in ("easy", "medium", "hard")
    assert result.head_diameter_cm > 0
    assert len(result.parts) > 0


def test_color_palette_white_image():
    """Pure white image → 白色 in palette."""
    img = Image.new("RGB", (80, 80), (255, 255, 255))
    colors = extract_color_palette(img, n_colors=3)
    assert "白色" in colors


def test_color_palette_red_image():
    """Pure red image → 红色 in palette."""
    img = Image.new("RGB", (80, 80), (255, 0, 0))
    colors = extract_color_palette(img, n_colors=3)
    assert "红色" in colors


def test_color_palette_skin_tone():
    """Skin-tone image → 浅肤色 in palette."""
    img = Image.new("RGB", (80, 80), (245, 194, 158))
    colors = extract_color_palette(img, n_colors=3)
    assert "浅肤色" in colors


def test_color_palette_rgba_no_crash():
    """RGBA image should not crash and return at least one color."""
    img = Image.new("RGBA", (80, 80), (70, 130, 180, 200))
    colors = extract_color_palette(img, n_colors=3)
    assert len(colors) >= 1


def test_color_palette_sorted_by_dominance_and_dedup():
    """占比高的颜色排在前；映射到同名毛线色的簇应去重。"""
    img = Image.new("RGB", (100, 100))
    px = img.load()
    for y in range(100):
        for x in range(100):
            px[x, y] = (255, 0, 0) if x < 70 else (0, 0, 255)
    colors = extract_color_palette(img, n_colors=3)
    assert colors[0] == "红色"  # 70% 占比必须排第一
    assert len(colors) >= 2  # 蓝色区域也应被提取
    assert len(colors) == len(set(colors))  # 同名毛线色去重


def test_nearest_yarn_black():
    assert nearest_yarn(0, 0, 0)[0] == "黑色"


def test_nearest_yarn_white():
    assert nearest_yarn(255, 255, 255)[0] == "白色"


def test_mock_analysis_has_no_colors_by_default():
    """Mock analysis without image has no recommended_colors."""
    result = ImageParser._mock_analysis()
    assert result.recommended_colors is None


def test_color_palette_excludes_background():
    """O2：白底+红色主体 → 推荐色板应来自主体，背景白色不入板。"""
    img = Image.new("RGB", (160, 160), (255, 255, 255))
    from PIL import ImageDraw
    ImageDraw.Draw(img).rectangle([40, 40, 120, 120], fill=(255, 0, 0))
    colors = extract_color_palette(img, n_colors=3)
    assert colors, "应有推荐色"
    assert colors[0] == "红色"
    assert "白色" not in colors, f"背景白色混进推荐色板: {colors}"
