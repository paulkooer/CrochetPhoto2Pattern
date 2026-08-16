"""Shared helpers for handling user-uploaded images in the UI."""
from __future__ import annotations

import logging
from typing import Optional

import streamlit as st
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_UPLOAD_MB = 20


def load_uploaded_image(uploaded_file) -> Optional[Image.Image]:
    """Decode an upload eagerly; surface corrupt/oversized files with a
    friendly message instead of a raw traceback mid-pipeline.

    Applies EXIF orientation — 手机照片的方向信息在 JPEG 元数据里，
    不转置的话竖拍照片会以横向进入 Vision API / 网格生成。
    Returns None (and renders an st.error) when the file is unusable.
    """
    if uploaded_file.size > MAX_UPLOAD_MB * 1024 * 1024:
        st.error(
            f"图片过大（{uploaded_file.size / 1024 / 1024:.1f}MB），"
            f"请上传 {MAX_UPLOAD_MB}MB 以内的文件"
        )
        return None
    try:
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image)
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
