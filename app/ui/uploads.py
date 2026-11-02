"""Streamlit upload helpers built on the shared, Streamlit-free decoder in app.utils.images."""
from __future__ import annotations

import logging
import warnings

import streamlit as st
from PIL import Image

# 通过模块属性读取上限与解码流程，测试或部署对 images 的调整对上传同样生效
from app.utils import images

logger = logging.getLogger(__name__)


def load_uploaded_image(uploaded_file) -> Image.Image | None:
    """Decode an upload eagerly; surface corrupt/oversized files with a
    friendly message instead of a raw traceback mid-pipeline.

    Applies EXIF orientation — 手机照片的方向信息在 JPEG 元数据里，
    不转置的话竖拍照片会以横向进入 Vision API / 网格生成。
    Transparent PNGs are flattened onto white — 透明区底层 RGB 任意
    （常见黑色），不合成的话会以实色黑污染配色/网格（剪贴画、像素画）。
    Returns None (and renders an st.error) when the file is unusable.
    """
    if uploaded_file.size > images.MAX_UPLOAD_MB * 1024 * 1024:
        st.error(
            f"图片过大（{uploaded_file.size / 1024 / 1024:.1f}MB），"
            f"请上传 {images.MAX_UPLOAD_MB}MB 以内的文件"
        )
        return None
    try:
        # Pillow 默认只警告部分超大图片；上传边界应确定性拒绝，而不能继续
        # 分配内存。先将其警告升级为异常，再执行更严格的产品像素上限。
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(uploaded_file, formats=images.ALLOWED_UPLOAD_FORMATS) as image:
                return images._prepare_image(image)
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


def load_uploaded_image_cached(uploaded_file) -> Image.Image | None:
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
