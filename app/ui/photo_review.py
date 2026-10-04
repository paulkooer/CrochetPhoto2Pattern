"""Two-step photo workflow; expensive recognition is reused during review."""

from __future__ import annotations

from copy import copy, deepcopy

import streamlit as st

from app.models.orchestrator import PhotoDraft, PipelineOrchestrator
from app.models.photo_review import head_ratio, review_overlay, reviewed_analysis
from app.schemas import PART_NAMES


def render_photo_review(draft: PhotoDraft, key: str, *, gauge, style, target_height: float) -> dict | None:
    from app.ui.result_renderer import md_safe

    run_trace = None
    st.subheader("② 检查识别结果，再生成图解")
    st.caption("检查和调整不会再次调用 AI。修改裁剪范围或解析模式后需要重新识别。")
    meta = draft.vision_meta
    if meta.get("source") == "mock":
        st.warning("当前为 Mock 演示：比例与部件是模板值，请自行确认。")
    elif meta.get("source") == "default":
        st.warning("未检出人脸；当前比例来自默认模板，请调整头部框或比例。")
    box = meta.get("face_box")
    w, h = draft.image.size
    detected = (box[0] / w, box[1] / h, (box[0] + box[2]) / w, (box[1] + box[3]) / h) if box else None
    use_box = st.checkbox("手动框选头部范围", key=f"review_box_{key}")
    if use_box:
        initial = detected or (0.25, 0.05, 0.75, 0.4)
        hx = st.slider(
            "头部左右边界（%）",
            0,
            100,
            (round(initial[0] * 100), round(initial[2] * 100)),
            key=f"review_hx_{key}",
        )
        hy = st.slider(
            "头部上下边界（%）",
            0,
            100,
            (round(initial[1] * 100), round(initial[3] * 100)),
            key=f"review_hy_{key}",
        )
        detected = (hx[0] / 100, hy[0] / 100, hx[1] / 100, hy[1] / 100)
    try:
        st.image(
            review_overlay(draft.subject, detected),
            caption="绿色：估算的主体边界；橙色：头部范围（启发式，未经校准）",
        )
        if draft.subject.segmentation is None:
            st.caption("未取得可靠主体边界；头部框比例按裁剪图高度估算。")
        ratio = (
            head_ratio(draft.subject, detected)
            if use_box and detected is not None
            else draft.analysis.head_diameter_cm / draft.analysis.height_cm
        )
        if use_box:
            st.caption(f"头部框推算头径／主体高度：{ratio:.3f}")
        else:
            ratio = st.number_input(
                "头径／主体高度",
                min_value=0.01,
                max_value=1.0,
                value=min(1.0, max(0.01, float(ratio))),
                step=0.01,
                key=f"review_ratio_{key}",
            )
        options = list(dict.fromkeys([*PART_NAMES, *draft.analysis.parts]))
        parts = st.multiselect(
            "确认需要的部件", options, default=draft.analysis.parts, key=f"review_parts_{key}"
        )
        if st.button("确认并生成图解（不再调用 AI）", type="primary", key=f"review_generate_{key}"):
            analysis = reviewed_analysis(draft.analysis, parts, ratio)
            reviewed = copy(draft)
            reviewed.vision_meta = {**meta, "head_ratio_source": "user_box" if use_box else "user_review"}
            reviewed.vision_meta["body_ratio"] = round(1 / ratio, 3)
            reviewed.vision_meta["original_head_to_height_ratio"] = (
                draft.analysis.head_diameter_cm / draft.analysis.height_cm
            )
            if use_box and detected is not None:
                reviewed.vision_meta["review_head_box"] = list(detected)
            run_trace = deepcopy(draft.trace)
            with st.spinner("按确认后的比例与部件生成图解…"):
                return PipelineOrchestrator.generate_from_draft(
                    reviewed,
                    analysis=analysis,
                    gauge=gauge,
                    style=style,
                    target_height_cm=target_height,
                    target_height_source="user_photo_target",
                    run_trace=run_trace,
                )
    except Exception as exc:
        st.error(f"检查或生成失败：{md_safe(exc)}")
        if run_trace is not None:
            with st.expander("本次生成失败的诊断"):
                st.json({"diagnostics": run_trace.payload(), "usage": draft.usage})
    return None
