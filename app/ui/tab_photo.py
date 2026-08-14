"""Tab 1: photo upload + AI pipeline."""
from __future__ import annotations

import logging
import uuid

import streamlit as st
from PIL import Image

from app.models.orchestrator import PipelineOrchestrator
from app.ui.result_renderer import render_results

logger = logging.getLogger(__name__)


def render_tab_photo() -> None:
    st.subheader("📷 照片上传")
    col_upload, col_preview = st.columns([1, 1])

    with col_upload:
        uploaded_file = st.file_uploader(
            "上传照片（正面为主）", type=["jpg", "jpeg", "png"],
            help="建议上传正面清晰照片",
            key="photo_uploader",
        )
        with st.expander("➕ 辅助角度照片（即将支持）", expanded=False):
            st.info("🚧 Coming Soon — 上传侧面/背面照片以提升 3D 结构推理准确度")

    if uploaded_file:
        image = Image.open(uploaded_file)
        with col_preview:
            st.image(image, caption="上传的照片", use_container_width=True)

        if st.button("🚀 生成钉织图解", type="primary",
                     use_container_width=True, key="btn_photo"):
            orchestrator = PipelineOrchestrator(
                openai_key=st.session_state.get("openai_key"),
                anthropic_key=st.session_state.get("anthropic_key"),
            )
            progress = st.progress(0, text="准备中...")
            try:
                progress.progress(10, text="Step 1/3: AI 视觉解析中...")
                analysis = orchestrator.parser.parse_image(image)

                progress.progress(40, text="Step 2/3: 3D 结构设计中...")
                structure = orchestrator.structure_designer.design_3d_structure(analysis)

                progress.progress(70, text="Step 3/3: 生成钉织参数...")
                params = orchestrator.params_generator.generate_params(analysis, structure)

                progress.progress(100, text="✅ 生成完成！")
                st.session_state.result = {
                    "analysis": analysis.model_dump(),
                    "structure": structure,
                    "params": params,
                    "result_id": uuid.uuid4().hex[:12],
                }
            except Exception as e:
                st.error(f"生成失败: {e}")
                logger.exception("Pipeline failed")

    # Render outside the `if uploaded_file` block so the last result stays
    # visible even after the uploader is cleared.
    if "result" in st.session_state:
        render_results(st.session_state.result, "result")
