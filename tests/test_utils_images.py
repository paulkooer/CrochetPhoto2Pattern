"""Tests for safe uploaded-image loading (app/utils/images.py)."""
import io

from PIL import Image

from app.utils.images import MAX_UPLOAD_MB, load_uploaded_image, load_uploaded_image_cached


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
