"""Two-step photo workflow; expensive recognition is reused during review."""

from __future__ import annotations

from copy import copy, deepcopy

import streamlit as st

from app.models.crochet_params import PatternGenerationError
from app.models.orchestrator import PhotoDraft, PipelineOrchestrator
from app.models.photo_review import head_ratio, review_overlay, reviewed_analysis, with_reviewed_body
from app.models.sizing import (
    DEFAULT_PROPORTION_STYLE,
    PROPORTION_STYLE_LABELS,
    PROPORTION_STYLES,
    styled_body_ratio,
)
from app.schemas import PART_NAMES, ImageAnalysis, ResultData
from app.utils.provenance import CONFIRMED_SUBJECT_SCOPE


def _confirmed_draft(draft: PhotoDraft, body_reviewed: PhotoDraft, ratio: float,
                     head_box: tuple[float, float, float, float] | None) -> PhotoDraft:
    """The reviewed draft used for both the stitch preview and generation."""
    reviewed = copy(body_reviewed)
    reviewed.vision_meta = {**draft.vision_meta,
                            "head_ratio_source": "user_box" if head_box is not None else "user_review",
                            "subject_scope_review": CONFIRMED_SUBJECT_SCOPE,
                            "requires_subject_review": False, "parts_source": "user_review"}
    reviewed.vision_meta["body_ratio"] = round(1 / ratio, 3)
    reviewed.vision_meta["original_head_to_height_ratio"] = (
        draft.analysis.head_diameter_cm / draft.analysis.height_cm
    )
    if head_box is not None:
        reviewed.vision_meta["review_head_box"] = list(head_box)
        from app.models.color_design import PART_SPAN

        # Same cropped-image coordinates as the extracted color bands.
        reviewed.spans = {**PART_SPAN, **(reviewed.spans or {}),
                          "头部": (head_box[1], head_box[3])}
        # User annotation is not a pose-model measurement.
        reviewed.spans_measured = [name for name in reviewed.spans_measured if name != "头部"]
    return reviewed


def _render_preview(reviewed: PhotoDraft, analysis: ImageAnalysis, *, gauge, style,
                    target_height: float, head_box: bool, proportion_style: str) -> bool:
    """Exact per-part counts before generation; True keeps generation disabled."""
    from app.models.crochetability import at_or_above, crochetability_advice, crochetability_findings
    from app.models.sizing import MAX_PHOTO_TARGET_HEIGHT_CM, MIN_BODY_TO_HEAD_RATIO
    from app.ui.result_renderer import md_safe
    from app.ui.stitch_preview import preset_option, render_stitch_preview

    def build(height, ratio, selected_gauge, selected_style=proportion_style):
        return PipelineOrchestrator.preview_params(
            reviewed, analysis=reviewed_analysis(analysis, analysis.parts, ratio),
            gauge=selected_gauge, style=style, target_height_cm=height, proportion_style=selected_style)

    ratio = analysis.head_diameter_cm / analysis.height_cm
    try:
        params = build(target_height, ratio, gauge)
    except (ValueError, PatternGenerationError) as exc:
        st.warning(f"暂不能生成：{md_safe(exc)}")
        return True

    def suggest(level):
        options = []
        if proportion_style != DEFAULT_PROPORTION_STYLE:
            styled = build(target_height, ratio, gauge, DEFAULT_PROPORTION_STYLE)
            if not at_or_above(crochetability_findings(styled), level):
                options.append(f"把头身比例风格改为「{PROPORTION_STYLE_LABELS[DEFAULT_PROPORTION_STYLE]}」")
        advice = crochetability_advice(
            build, gauge=gauge, level=level, size=target_height, size_max=MAX_PHOTO_TARGET_HEIGHT_CM,
            ratio=ratio, ratio_max=1 / MIN_BODY_TO_HEAD_RATIO)
        if advice.size is not None:
            options.append(f"把目标成品高度提高到 {advice.size:g} cm")
        if advice.ratio is not None:
            options.append(f"扩大头部框，使头径／主体高度达到 {advice.ratio:.2f}" if head_box
                           else f"把头径／主体高度提高到 {advice.ratio:.2f}")
        return options + preset_option(advice)

    return render_stitch_preview(params, suggest)


def render_photo_review(draft: PhotoDraft, key: str, *, gauge, style,
                        target_height: float) -> ResultData | None:
    from app.ui.result_renderer import md_safe

    run_trace = None
    st.subheader("② 检查识别结果，再生成图解")
    st.caption("检查和调整在本地完成。修改裁剪范围或解析模式后需要重新识别。")
    meta = draft.vision_meta
    if meta.get("source") == "mock":
        st.warning("当前为 Mock 演示：比例与部件是模板值，请自行确认。")
    elif meta.get("source") == "default":
        st.warning("没有可用的头部检测结果；当前比例来自默认模板，请调整头部框或比例。")
    if meta.get("parts_source") == "default_template":
        st.info("本地模式不能识别动物种类或完整部件。下方是初始模板，请补选耳朵、尾巴、帽子，"
                "并移除照片中没有的部件。")
    if meta.get("face_rejection_reason"):
        st.warning(f"已忽略头部候选框：{meta['face_rejection_reason']}。可手动框选头部。")
    if meta.get("possible_skirt"):
        st.caption("轮廓下方较宽，可能由腿、底座、背景或裙摆造成；若确有裙子，请在部件列表中添加。")
    subject_choice = st.radio(
        "确认照片主体", ["单个玩偶，所需部件可用下方列表表达", "多个主体，需要先裁剪",
                   "食品或其他无法用现有部件表达的作品"],
        index=None, key=f"review_subject_{key}",
    )
    if subject_choice == "多个主体，需要先裁剪":
        st.info("请返回裁剪区，只保留一个目标后重新识别。")
    elif subject_choice == "食品或其他无法用现有部件表达的作品":
        st.info("当前照片流程不支持该结构。翅膀、象鼻、触角、打结长管等不能用人形部件直接替代。")
    subject_supported = subject_choice == "单个玩偶，所需部件可用下方列表表达"
    # 头部框由人脸框按经验比例扩展（含额头与头发）；旧草稿只有人脸框时沿用人脸框
    box = meta.get("head_box") or meta.get("face_box")
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
    body_box = None
    use_body_box = st.checkbox(
        "手动限定身体轮廓范围", key=f"review_body_box_{key}",
        disabled=not draft.geometry.used_for_generation,
        help="蓝框内测量身体轮廓，尽量排除手臂、腿和背景。框选不会补回分割遗漏的像素。",
    )
    if use_body_box and draft.geometry.used_for_generation:
        bx = st.slider("身体左右边界（%）", 0, 100, (25, 75), key=f"review_bx_{key}")
        by = st.slider("身体上下边界（%）", 0, 100, (35, 70), key=f"review_by_{key}")
        body_box = (bx[0] / 100, by[0] / 100, bx[1] / 100, by[1] / 100)
        st.caption("蓝框仅限定轮廓测量；成品尺寸仍由目标高度和部件比例决定。"
                   "身体色带使用框的上下范围，左右范围不用于重新采样颜色。")
    try:
        from app.ui.mask_editor import render_mask_editor

        corrected = render_mask_editor(draft, key)
        st.image(
            review_overlay(corrected.subject, detected, body_box),
            caption="绿色：估算主体边界；橙色：头部范围；蓝色：人工身体范围（未经实物校准）",
        )
        body_reviewed = with_reviewed_body(corrected, body_box) if body_box is not None else corrected
        if corrected.subject.segmentation is None:
            st.caption("未取得可靠主体边界；头部框比例按裁剪图高度估算。")
        ratio = (
            head_ratio(corrected.subject, detected)
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
        proportion_style = st.radio(
            "头身比例风格", list(PROPORTION_STYLES), format_func=PROPORTION_STYLE_LABELS.__getitem__,
            index=list(PROPORTION_STYLES).index(DEFAULT_PROPORTION_STYLE), horizontal=True,
            key=f"review_proportion_{key}",
            help="照片保留被摄者的写实比例；常见玩偶约 1:2–1:3。Q 版把照片比例压缩到 1:2–1:3，"
                 "适中压缩到 1:2–1:4.5，写实直接使用照片比例。",
        )
        st.caption(f"照片约 1:{1 / ratio:.1f} → 玩偶约 1:{styled_body_ratio(1 / ratio, proportion_style):.1f}"
                   "（身高 : 头径）")
        options = list(dict.fromkeys([*PART_NAMES, *draft.analysis.parts]))
        parts = st.multiselect(
            "确认需要的部件", options, default=draft.analysis.parts, key=f"review_parts_{key}"
        )
        unsupported = [name for name in parts if name not in PART_NAMES]
        if unsupported:
            st.warning("暂不支持自动生成：" + "、".join(md_safe(name) for name in unsupported)
                       + "。请移除误识别项并选择对应的受支持部件；真实特殊结构需另行设计。")
        can_generate = subject_supported and bool(parts) and not unsupported
        if body_box is not None and "身体" not in parts:
            st.warning("已限定身体轮廓，请选择身体部件，或关闭身体框。")
            can_generate = False
        confirmed = None
        if parts and not unsupported:
            analysis = reviewed_analysis(body_reviewed.analysis, parts, ratio)
            reviewed = _confirmed_draft(draft, body_reviewed, ratio, detected if use_box else None)
            confirmed = (reviewed, analysis)
            if _render_preview(reviewed, analysis, gauge=gauge, style=style, target_height=target_height,
                               head_box=use_box, proportion_style=proportion_style):
                can_generate = False
        if st.button("确认并生成图解", type="primary", key=f"review_generate_{key}",
                     disabled=not can_generate) and can_generate and confirmed is not None:
            reviewed, analysis = confirmed
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
                    proportion_style=proportion_style,
                )
    except Exception as exc:
        st.error(f"检查或生成失败：{md_safe(exc)}")
        if run_trace is not None:
            with st.expander("本次生成失败的诊断"):
                st.json({"diagnostics": run_trace.payload(), "usage": draft.usage})
    return None
