"""Local bidirectional canvas; component assets ship with the application."""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from app.models.mask_review import mask_editor_input, with_reviewed_mask
from app.models.orchestrator import PhotoDraft

_canvas = components.declare_component("subject_mask_editor", path=Path(__file__).with_name("mask_canvas"))


def render_mask_editor(draft: PhotoDraft, key: str) -> PhotoDraft:
    enabled = st.checkbox("补选／擦除主体区域", key=f"review_mask_enabled_{key}",
                          disabled=not draft.geometry.used_for_generation)
    if not enabled or not draft.geometry.used_for_generation:
        return draft
    st.caption("绿色为选中的主体。在漏掉的部分补选，在误选背景上擦除；每笔松开后生效。"
               "可撤销最近 20 笔或恢复自动分割。耳朵、尾巴等仍需在部件列表中确认。")
    small, mask, token = mask_editor_input(draft)
    base_pixels = "".join("1" if pixel else "0" for pixel in mask.flat)
    saved_key = f"review_mask_saved_{key}"
    saved = st.session_state.get(saved_key)
    if saved and saved.get("image_token") != token:
        saved = None
        st.session_state.pop(saved_key, None)
    preview = draft.image.convert("RGB")
    preview.thumbnail((640, 640))
    buffer = BytesIO()
    preview.save(buffer, format="PNG")
    image_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    value = _canvas(image_url=image_url, image_token=token, width=small.width, height=small.height,
                    base_pixels=base_pixels, current_pixels=saved["pixels"] if saved else base_pixels,
                    key=f"review_mask_canvas_{key}", default=saved)
    if value is None:
        return draft
    # Keep the last canvas value, including an empty mask, so undo remains
    # available after the server rejects generation. Bound input before caching.
    if (not isinstance(value, dict)
            or set(value) != {"image_token", "width", "height", "pixels", "use_original"}
            or type(value["use_original"]) is not bool
            or value["image_token"] != token or type(value["width"]) is not int
            or type(value["height"]) is not int or (value["width"], value["height"]) != small.size
            or not isinstance(value["pixels"], str) or len(value["pixels"]) != mask.size
            or set(value["pixels"]) - {"0", "1"}):
        raise ValueError("画布返回了无效或过期的修正，请重新打开主体修正")
    st.session_state[saved_key] = value
    if value["use_original"]:
        if value["pixels"] != base_pixels:
            raise ValueError("恢复自动分割的选区不一致，请重新打开主体修正")
        return draft
    return with_reviewed_mask(draft, {k: v for k, v in value.items() if k != "use_original"})
