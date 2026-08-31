"""Tests for safe uploaded-image loading (app/utils/images.py)."""
import io

from PIL import Image

from app.utils.images import (
    MAX_UPLOAD_MB,
    MAX_UPLOAD_PIXELS,
    MAX_UPLOAD_SIDE,
    load_uploaded_image,
    load_uploaded_image_cached,
)


class _FakeUpload(io.BytesIO):
    """Just enough of Streamlit's UploadedFile for load_uploaded_image."""

    def __init__(self, data: bytes, size: int):
        super().__init__(data)
        self.size = size


def _png_bytes(color=(255, 0, 0), size=(10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_valid_image_decoded():
    up = _FakeUpload(_png_bytes(), size=len(_png_bytes()))
    img = load_uploaded_image(up)
    assert img is not None
    assert img.size == (10, 10)


def test_corrupt_image_returns_none():
    data = b"this is definitely not an image"
    up = _FakeUpload(data, size=len(data))
    assert load_uploaded_image(up) is None


def test_oversized_image_returns_none():
    data = _png_bytes()
    up = _FakeUpload(data, size=MAX_UPLOAD_MB * 1024 * 1024 + 1)
    assert load_uploaded_image(up) is None


def test_excessive_pixel_dimensions_rejected_before_decode(monkeypatch):
    """压缩字节很小也不能绕过解码前的像素资源上限。"""
    class _HeaderOnlyImage:
        size = (8_000, MAX_UPLOAD_PIXELS // 8_000 + 1)

    monkeypatch.setattr("app.utils.images.Image.open", lambda _file: _HeaderOnlyImage())
    up = _FakeUpload(b"small-compressed-payload", size=24)
    assert load_uploaded_image(up) is None


def test_excessive_single_side_rejected_before_decode(monkeypatch):
    class _HeaderOnlyImage:
        size = (MAX_UPLOAD_SIDE + 1, 1)

    monkeypatch.setattr("app.utils.images.Image.open", lambda _file: _HeaderOnlyImage())
    up = _FakeUpload(b"small-compressed-payload", size=24)
    assert load_uploaded_image(up) is None


def test_truncated_image_returns_none():
    """声明尺寸正常但字节被截断的文件，image.load() 必须当场暴露。"""
    data = _png_bytes(size=(200, 200))[:200]
    up = _FakeUpload(data, size=len(data))
    assert load_uploaded_image(up) is None


def _jpeg_with_exif_orientation(orientation: int) -> bytes:
    img = Image.new("RGB", (400, 200), (255, 0, 0))
    exif = Image.Exif()
    exif[274] = orientation  # 274 = Orientation tag
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_exif_orientation_is_applied():
    """手机竖拍（Orientation=6）必须转置为竖向进入流水线（回归：旧版忽略 EXIF）。"""
    data = _jpeg_with_exif_orientation(6)
    img = load_uploaded_image(_FakeUpload(data, size=len(data)))
    assert img is not None
    assert img.size == (200, 400)


def test_exif_orientation_1_untouched():
    data = _jpeg_with_exif_orientation(1)  # 正常方向
    img = load_uploaded_image(_FakeUpload(data, size=len(data)))
    assert img is not None
    assert img.size == (400, 200)


def test_cached_loader_bare_mode_decodes():
    """无 Streamlit 运行上下文（单测/裸调用）时走直通路径，行为与直载一致。"""
    data = _png_bytes()
    img = load_uploaded_image_cached(_FakeUpload(data, size=len(data)))
    assert img is not None
    assert img.size == (10, 10)


def _transparent_png_bytes(size=(20, 20), subject=(255, 0, 0)) -> bytes:
    """黑底透明 PNG：透明区底层 RGB 为黑（抠图/像素画导出的常见形态）。"""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    w, h = size
    for y in range(h // 4, h * 3 // 4):
        for x in range(w // 4, w * 3 // 4):
            img.putpixel((x, y), (*subject, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_transparent_png_flattened_onto_white():
    """透明区（黑底）必须合成到白底而非变实色黑（N3）。

    下游一律 convert("RGB") 丢 alpha——不合成的话黑底透明 PNG 会把
    "黑色"混进推荐配色/网格（网格 Tab 的像素画用户高频踩中）。
    """
    data = _transparent_png_bytes()
    img = load_uploaded_image(_FakeUpload(data, size=len(data)))
    assert img is not None
    assert img.mode == "RGB"
    assert img.getpixel((1, 1)) == (255, 255, 255)  # 透明区 → 白
    assert img.getpixel((10, 10)) == (255, 0, 0)    # 不透明主体保留


def test_transparent_png_no_black_in_color_bands():
    """端到端：黑底透明 PNG 的纵向色带不得输出"黑色"（N3 回归）。"""
    from app.models.color_design import vertical_color_bands

    data = _transparent_png_bytes(size=(60, 100))
    img = load_uploaded_image(_FakeUpload(data, size=len(data)))
    bands = vertical_color_bands(img)
    colors = {b["color"] for b in bands}
    assert "黑色" not in colors, f"黑底透明污染了色带: {colors}"
    assert "红色" in colors


def test_palette_png_with_transparency_flattened():
    """P 模式（调色板+透明索引）PNG 同样合成白底。"""
    img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    img.putpixel((5, 5), (0, 128, 0, 255))
    buf = io.BytesIO()
    img.convert("P").save(buf, format="PNG")
    data = buf.getvalue()
    out = load_uploaded_image(_FakeUpload(data, size=len(data)))
    assert out is not None
    assert out.mode == "RGB"
    assert out.getpixel((0, 0)) == (255, 255, 255)
