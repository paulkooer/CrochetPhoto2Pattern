"""Tab 1: photo upload + AI pipeline."""
from __future__ import annotations

import logging
import uuid

import streamlit as st

from app.models.gauge import gauge_from_ui
from app.models.orchestrator import PipelineOrchestrator
from app.ui.result_renderer import purge_result_state, render_results
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
    """每次点击新建（不缓存）。

    orchestrator 本身只是薄壳（prompt 文件读取 + dotenv，开销微小），而
    @st.cache_resource 会把用户输入过的每组 API key 进程级留存到重启，
    共享部署上是真实的密钥滞留面——权衡后放弃缓存。
    """
    return PipelineOrchestrator(
        openai_key=st.session_state.get("openai_key"),
        anthropic_key=st.session_state.get("anthropic_key"),
    )


def render_tab_photo() -> None:
    st.subheader("📷 从照片开始创作")
    st.markdown(
        "<p class='crochet-section-note'>上传一张轮廓清晰的正面照片，"
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
        with st.expander("➕ 辅助角度照片（即将支持）", expanded=False):
            st.info("🚧 Coming Soon — 上传侧面/背面照片以提升 3D 结构推理准确度")

        # 无 Key 时让用户显式选择：本地视觉估算（真实分析照片）或 Mock 演示。
        # 放在上传之前：先选模式再传照片更顺。
        has_keys = bool(
            st.session_state.get("openai_key") or st.session_state.get("anthropic_key")
        )
        use_local = False
        if not has_keys:
            mode = st.radio(
                "无 API Key 模式",
                ["🧮 本地视觉估算（推荐）", "🎬 Mock 演示数据"],
                key="nokey_mode",
                horizontal=True,
                help="本地估算：人脸检测推算头身比例，头径按 9cm 锚定，零 API 成本；"
                     "Mock：固定演示数据，与照片无关",
            )
            use_local = mode.startswith("🧮")

    if uploaded_file:
        image = load_uploaded_image_cached(uploaded_file)
        if image is not None:
            with col_preview:
                st.image(image, caption="上传的照片", use_container_width=True)

            if st.button("🚀 生成钩织图解", type="primary",
                         use_container_width=True, key="btn_photo"):
                orchestrator = _build_orchestrator()
                progress = st.progress(0, text="准备中...")
                try:
                    result = orchestrator.run_full_pipeline(
                        image, progress_cb=progress.progress, local_vision=use_local,
                        gauge=gauge_from_ui(
                            st.session_state.get("gauge_preset", "classic"),
                            st.session_state.get("gauge_st_input"),
                            st.session_state.get("gauge_rw_input"),
                        ),
                        style=_style_from_session(),
                    )
                    # 替换旧结果前清掉它命名空间下的 widget 状态，防累积
                    if "result" in st.session_state:
                        purge_result_state(st.session_state.result)
                    result["result_id"] = uuid.uuid4().hex[:12]
                    st.session_state.result = result
                    progress.progress(100, text="✅ 生成完成！")
                except Exception as e:
                    progress.empty()  # 失败时移除进度条，避免"40% + 报错"同屏矛盾
                    st.error(f"生成失败: {e}")
                    logger.exception("Pipeline failed")

    # Render outside the `if uploaded_file` block so the last result stays
    # visible even after the uploader is cleared.
    if "result" in st.session_state:
        render_results(st.session_state.result, "result")
