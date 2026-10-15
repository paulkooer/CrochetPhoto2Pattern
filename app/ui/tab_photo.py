"""Tab 1: photo upload + local analysis."""
from __future__ import annotations

import hashlib
import logging
import uuid

import streamlit as st

from app.models.gauge import gauge_from_ui
from app.models.orchestrator import PipelineOrchestrator
from app.ui.result_renderer import md_safe, purge_result_state, render_results
from app.utils.images import load_uploaded_image_cached

logger = logging.getLogger(__name__)




def _style_from_session():
    from app.models.gauge import ShapingStyle

    return ShapingStyle(
        sphere_mode=st.session_state.get("style_sphere", "ladder"),
        one_piece=bool(st.session_state.get("style_onepiece", False)),
        skirt_style=st.session_state.get("style_skirt", "ring"),
        ruffle_hem=bool(st.session_state.get("style_ruffle", False)),
    )


def _build_orchestrator() -> PipelineOrchestrator:
    """Each preparation owns its local observations and diagnostics."""
    return PipelineOrchestrator()


def render_tab_photo() -> None:
    st.subheader("📷 从照片开始创作")
    st.markdown(
        "<p class='sheet-note'>上传一张轮廓清晰的正面照片，"
        "我们会整理人物比例、结构与逐圈针法。</p>",
        unsafe_allow_html=True,
    )
    col_upload, col_preview = st.columns([1, 1])

    with col_upload:
        uploaded_file = st.file_uploader(
            "上传照片（正面为主）", type=["jpg", "jpeg", "png"],
            help="建议上传正面清晰照片（JPG/PNG，20MB 以内）",
            key="photo_uploader",
        )
        target_height = st.slider(
            "目标成品高度 (cm)", 10.0, 60.0, 18.0, 0.5,
            key="photo_target_height",
            help="单张照片无法测出真实厘米尺寸；系统保留照片头身比例，"
                 "再按这个目标高度生成图解。",
        )
        st.caption("📏 照片只用于估算相对比例，绝对尺寸由上面的目标高度决定。")
        st.caption("🔒 上传的照片会传到运行此应用的主机；只有在自己电脑部署时才是本机处理。"
                   "照片通过本地算法处理，不调用云端视觉模型。"
                   "历史记录默认关闭，启用后保存于部署主机的磁盘。")
        with st.expander("➕ 多角度照片（规划中）", expanded=False):
            st.caption("上传侧面/背面照片以辅助 3D 结构推理——尚未开放；"
                       "当前可用结果页的「快速调整尺寸」与姿态实测分段弥补部分场景。")

        mode_options = ["🧮 本地视觉估算（推荐）", "🎬 Mock 演示数据"]
        mode_help = ("本地估算：轮廓与头部候选框推算比例，部件需人工确认；"
                     "Mock：固定演示数据，配色来自照片。")
        # 清理升级前的 AI 模式残留值，
        # 让 radio 确定性回到默认（不依赖 Streamlit 的隐式重置行为）
        if st.session_state.get("vision_mode") not in mode_options:
            st.session_state.pop("vision_mode", None)
        mode = st.radio(
            "解析模式",
            mode_options,
            key="vision_mode",
            horizontal=True,
            help=mode_help,
        )
        vision_mode = {"🧮": "local", "🎬": "mock"}[mode[0]]

    with col_preview:
        if uploaded_file is None:
            st.session_state.pop("photo_draft", None)
            st.session_state.pop("photo_fingerprint", None)
            st.markdown(
                "<div class='sheet-empty'>上传照片后，这里显示预览；"
                "生成的图解会出现在下方。</div>",
                unsafe_allow_html=True,
            )

    if uploaded_file:
        image = load_uploaded_image_cached(uploaded_file)
        if image is not None:
            from app.models.photo_review import crop_photo
            from app.ui.photo_review import render_photo_review
            fingerprint = hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:16]
            # One active crop/draft per session; replaced uploads do not accumulate.
            if st.session_state.get("photo_fingerprint") != fingerprint:
                for old_key in list(st.session_state):
                    if isinstance(old_key, str) and old_key.startswith(("review_", "crop_")):
                        del st.session_state[old_key]
                st.session_state.pop("photo_draft", None)
                st.session_state["photo_fingerprint"] = fingerprint
            with col_upload:
                horizontal = st.slider("裁剪左右范围（%）", 0, 100, (0, 100), key="crop_x")
                vertical = st.slider("裁剪上下范围（%）", 0, 100, (0, 100), key="crop_y")
                st.caption("保留完整主体；裁剪范围外的像素不会发送给视觉模型。")
            signature = (fingerprint, horizontal, vertical, vision_mode)
            cached = st.session_state.get("photo_draft")
            if cached and cached[0] != signature:
                st.session_state.pop("photo_draft", None)
                for old_key in list(st.session_state):
                    if isinstance(old_key, str) and old_key.startswith("review_"):
                        del st.session_state[old_key]
                cached = None
            try:
                cropped = crop_photo(image, horizontal, vertical)
                with col_preview:
                    st.image(cropped, caption="将用于识别的裁剪照片", width="stretch")
                budget = st.number_input("单次任务运行预算（秒，不含人工确认时间）", 15, 600, 180,
                                         key="photo_budget")
                st.caption("预算在阶段边界检查；本地计算无法中途强制终止。")
                if st.button("① 识别照片，进入确认", type="primary", width="stretch", key="btn_photo"):
                    progress = st.progress(0, text="识别中…")
                    orchestrator = None
                    try:
                        orchestrator = _build_orchestrator()
                        draft = orchestrator.prepare_photo(
                            cropped, progress_cb=progress.progress, vision_mode=vision_mode,
                            budget_seconds=float(budget))
                        # New recognition means a fresh review, including when the image is unchanged.
                        for old_key in list(st.session_state):
                            if isinstance(old_key, str) and old_key.startswith("review_"):
                                del st.session_state[old_key]
                        cached = (signature, draft, uuid.uuid4().hex[:12])
                        st.session_state["photo_draft"] = cached
                        st.session_state.pop("photo_failure", None)
                    except Exception as exc:
                        st.error(f"识别失败（{type(exc).__name__}），原有图解已保留。请检查配置后重试。")
                        logger.warning("Photo recognition failed (%s)", type(exc).__name__)
                        if orchestrator:
                            st.session_state["photo_failure"] = {
                                "diagnostics": orchestrator.last_diagnostics,
                                "usage": orchestrator.parser.last_usage}
                    finally:
                        progress.empty()
                if st.session_state.get("photo_failure"):
                    with st.expander("最近一次失败的诊断"):
                        st.json(st.session_state["photo_failure"])
                if cached:
                    result = render_photo_review(
                        cached[1], cached[2], target_height=target_height, style=_style_from_session(),
                        gauge=gauge_from_ui(st.session_state.get("gauge_preset", "classic"),
                                            st.session_state.get("gauge_st_input"),
                                            st.session_state.get("gauge_rw_input")))
                    if result is not None:
                        if "result" in st.session_state:
                            purge_result_state(st.session_state.result)
                        result["result_id"] = uuid.uuid4().hex[:12]
                        st.session_state.result = result
            except ValueError as exc:
                st.warning(md_safe(exc))

    # Render outside the `if uploaded_file` block so the last result stays
    # visible even after the uploader is cleared.
    if "result" in st.session_state:
        render_results(st.session_state.result, "result")
