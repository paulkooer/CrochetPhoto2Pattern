"""Shared helpers for handling user-uploaded images in the UI."""
from __future__ import annotations

import logging
import warnings
from typing import Optional

import streamlit as st
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_UPLOAD_MB = 20
MAX_UPLOAD_PIXELS = 40_000_000
MAX_UPLOAD_SIDE = 16_384


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


def load_image_file(path) -> Optional[Image.Image]:
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
            image = Image.open(path)
        _validate_upload_dimensions(image)
        image = ImageOps.exif_transpose(image)
        if _has_transparency(image):
            image = _flatten_alpha(image)
        image.load()
        return image
    except Exception as e:
        logger.warning("Failed to load image file %s: %s", path, e)
        return None


def load_uploaded_image(uploaded_file) -> Optional[Image.Image]:
    """Decode an upload eagerly; surface corrupt/oversized files with a
    friendly message instead of a raw traceback mid-pipeline.

    Applies EXIF orientation — 手机照片的方向信息在 JPEG 元数据里，
    不转置的话竖拍照片会以横向进入 Vision API / 网格生成。
    Transparent PNGs are flattened onto white — 透明区底层 RGB 任意
    （常见黑色），不合成的话会以实色黑污染配色/网格（剪贴画、像素画）。
    Returns None (and renders an st.error) when the file is unusable.
    """
    if uploaded_file.size > MAX_UPLOAD_MB * 1024 * 1024:
        st.error(
            f"图片过大（{uploaded_file.size / 1024 / 1024:.1f}MB），"
            f"请上传 {MAX_UPLOAD_MB}MB 以内的文件"
        )
        return None
    try:
        # Pillow 默认只警告部分超大图片；上传边界应确定性拒绝，而不能继续
        # 分配内存。先将其警告升级为异常，再执行更严格的产品像素上限。
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(uploaded_file)
        _validate_upload_dimensions(image)
        image = ImageOps.exif_transpose(image)
        if _has_transparency(image):
            image = _flatten_alpha(image)
        image.load()  # 强制立即解码，损坏/截断文件在此暴露而非流水线中途
        return image
    except Exception as e:
        logger.warning("Failed to open uploaded image: %s", e)
        st.error(f"无法读取图片文件（可能已损坏或格式不符）: {e}")
        return None


def _upload_cache_key(uploaded_file) -> tuple:
    file_id = getattr(uploaded_file, "file_id", None)
    if file_id:
        return ("id", file_id)
    return ("meta", uploaded_file.name, uploaded_file.size,
            getattr(uploaded_file, "type", ""))


def load_uploaded_image_cached(uploaded_file) -> Optional[Image.Image]:
    """Same as load_uploaded_image, but decode once per uploaded file.

    Streamlit 每次 rerun（拖滑块、勾 checkbox）都会重新执行脚本，若不缓存，
    最大 20MB 的文件每次都被完整解码。仅在真实 Streamlit 运行上下文中
    启用缓存；裸调用（单测）直接走无缓存路径。
    """
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return load_uploaded_image(uploaded_file)
    except Exception:
        return load_uploaded_image(uploaded_file)

    key = _upload_cache_key(uploaded_file)
    cache = st.session_state.get("_img_decode_cache")
    if cache is None:
        cache = st.session_state["_img_decode_cache"] = {}
    if key in cache:
        return cache[key]

    image = load_uploaded_image(uploaded_file)
    if image is not None:
        if len(cache) >= 4:  # 简单上限，防长期会话内存增长
            cache.clear()
        cache[key] = image
    return image
