"""Bounded, Streamlit-free image decoding shared by the UI, CLI and evaluation."""
from __future__ import annotations

import logging
import warnings
from io import BytesIO

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_UPLOAD_MB = 20
MAX_UPLOAD_PIXELS = 40_000_000
MAX_UPLOAD_SIDE = 16_384
# 解码后立即降采样到此边长：管线实际消费 ≤1024px（Vision API/网格/配色），
# 更大的像素只会在缓存（最多 4 张）、st.image 全帧传输和白底合成时放大
# 内存——39.7MP RGBA 合成实测峰值 +650MB。2048 给预览留一档余量。
MAX_DECODED_SIDE = 2048
# 只允许解码与上传控件 type=["jpg","jpeg","png"] 一致的格式。Pillow 默认会
# 嗅探全部已注册解码器（TIFF/BMP/GIF/JPEG2000/XBM…），把以 .png 结尾的
# 任意格式文件送进对应解码器，扩大了不可信输入的攻击面。传 formats= 后
# Pillow 只尝试这两种解码器，其余格式直接报错。
ALLOWED_UPLOAD_FORMATS = ("JPEG", "PNG")


def load_image_bytes(data: bytes) -> Image.Image | None:
    """Decode a bounded immutable snapshot, including the normal image guards."""
    try:
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError(f"图片超过 {MAX_UPLOAD_MB}MB 上限")
        with BytesIO(data) as source, warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source, formats=ALLOWED_UPLOAD_FORMATS) as original:
                return _prepare_image(original)
    except Exception as exc:
        logger.warning("Failed to decode image snapshot: %s", exc)
        return None


def _validate_upload_dimensions(image: Image.Image) -> None:
    """Reject resource-exhausting dimensions before pixel data is decoded."""
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("图片尺寸无效")
    pixels = width * height
    if width > MAX_UPLOAD_SIDE or height > MAX_UPLOAD_SIDE:
        raise ValueError(
            f"图片边长过大（{width}×{height}），单边不得超过 {MAX_UPLOAD_SIDE} 像素")
    if pixels > MAX_UPLOAD_PIXELS:
        raise ValueError(
            f"图片像素过多（{width}×{height}，共 {pixels:,} 像素），"
            f"上限为 {MAX_UPLOAD_PIXELS:,} 像素")


def _apply_jpeg_draft(image: Image.Image) -> Image.Image:
    """JPEG 按 2 的幂降采样解码（其余格式 no-op）。

    必须在 exif_transpose 之前调用：transpose 会强制解码并返回丢失
    format 属性的副本，之后再 draft 已太晚。39.7MP 的 JPEG 不再全量
    解出 650MB 像素缓冲再缩到 2048。
    """
    if image.format == "JPEG":
        image.draft("RGB", (MAX_DECODED_SIDE, MAX_DECODED_SIDE))
    return image


def _downsample(image: Image.Image) -> Image.Image:
    """解码后立即降采样到 MAX_DECODED_SIDE。

    先于白底合成执行：全尺寸 RGBA 合成是超清抠图 PNG 的主要内存尖峰
    （合成需整幅 RGBA×2 副本）。LANCZOS 直采样 RGBA 会在透明边缘混入
    底层 RGB，对配色量化/网格取色无感，换 40× 的内存峰值值得。
    """
    if max(image.size) > MAX_DECODED_SIDE:
        image.thumbnail((MAX_DECODED_SIDE, MAX_DECODED_SIDE),
                        Image.Resampling.LANCZOS)
    return image


def _flatten_alpha(image: Image.Image) -> Image.Image:
    """透明像素合成到白底。

    抠图/像素画 PNG 透明区的底层 RGB 任意（常见黑色）——下游一律
    convert("RGB") 丢 alpha，透明区会变成实色黑混进配色与网格。
    白底是唯一无偏的合成色（与毛线色表中的"白色"语义一致）。
    """
    rgba = image.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, rgba).convert("RGB")


def _has_transparency(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA", "PA"):
        return True
    return image.mode == "P" and "transparency" in image.info


def _prepare_image(image: Image.Image) -> Image.Image:
    """Detach only after scaling, avoiding an unconditional full-size copy."""
    _validate_upload_dimensions(image)
    image = _apply_jpeg_draft(image)
    ImageOps.exif_transpose(image, in_place=True)
    image = _downsample(image)
    # The caller owns/closes the decoder. Alpha composition returns a new image;
    # other modes need a detached copy, now bounded to MAX_DECODED_SIDE.
    result = _flatten_alpha(image) if _has_transparency(image) else image.copy()
    result.load()
    return result


def load_image_file(path) -> Image.Image | None:
    """从磁盘路径加载图片（CLI/无头模式用）。

    与 load_uploaded_image 同一套防线：文件大小、像素/边长、解压炸弹、
    EXIF 转置 + 透明合成白底；失败返回 None（不渲染 UI 错误）。
    """
    try:
        if getattr(path, "stat", None) is not None:
            size = path.stat().st_size
        else:
            from pathlib import Path
            size = Path(path).stat().st_size
        if size > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError(f"图片超过 {MAX_UPLOAD_MB}MB 上限")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path, formats=ALLOWED_UPLOAD_FORMATS) as image:
                return _prepare_image(image)
    except Exception as e:
        logger.warning("Failed to load image file %s: %s", path, e)
        return None


def thumbnail_data_url(image: Image.Image, max_side: int = 96,
                       quality: int = 70) -> str | None:
    """RGB JPEG 缩略图 data URL（历史列表/分享预览用）；失败返回 None。

    从 orchestrator 抽出的展示层关注点：缩略图只进 preview 字段，不参与
    图解生成；输入可能是共享缓存图，必须 copy 后再做原地 thumbnail。
    """
    try:
        import base64
        import io

        thumb = image.convert("RGB").copy()
        thumb.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=quality)
        return ("data:image/jpeg;base64,"
                + base64.b64encode(buf.getvalue()).decode())
    except Exception as e:
        logger.debug("preview thumbnail failed: %s", e)
        return None
