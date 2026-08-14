"""Tab 2: manual parameter input (no photo / no API key required)."""
from __future__ import annotations

import logging
import uuid

import streamlit as st

from app.models.orchestrator import PipelineOrchestrator
from app.schemas import ImageAnalysis
from app.ui.result_renderer import render_results

logger = logging.getLogger(__name__)


def _run_pipeline_from_analysis(analysis: ImageAnalysis, openai_key=None, anthropic_key=None) -> dict:
    """Run structure + param stages given an already-parsed ImageAnalysis."""
    orchestrator = PipelineOrchestrator(openai_key=openai_key, anthropic_key=anthropic_key)
    structure = orchestrator.structure_designer.design_3d_structure(analysis)
    params = orchestrator.params_generator.generate_params(analysis, structure)
    return {
        "analysis": analysis.model_dump(),
        "structure": structure,
        "params": params,
        "result_id": uuid.uuid4().hex[:12],
    }


def render_tab_manual() -> None:
    st.subheader("✏️ 手动输入参数")
    st.info("无需上传照片，手动填写人物参数直接生成图解。")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        m_body_type = st.selectbox("体型", ["标准", "瘦", "胖"], key="m_body_type")
        m_head_d = st.slider("头部直径 (cm)", 4.0, 20.0, 9.0, 0.5, key="m_head_d")
        m_height = st.slider("整体高度 (cm)", 10.0, 60.0, 18.0, 0.5, key="m_height")
        m_difficulty = st.select_slider(
            "难度", options=["easy", "medium", "hard"], value="easy", key="m_difficulty"
        )

    with col_m2:
        m_pose = st.selectbox("姿态", ["站立", "坐姿", "其他"], key="m_pose")
        m_parts = st.multiselect(
            "包含部件",
            ["头部", "身体", "手臂", "腿部", "尾巴", "耳朵", "帽子"],
            default=["头部", "身体"],
            key="m_parts",
        )
        m_features = st.text_input(
            "主要特征（逗号分隔）",
            "大眼睛, 圆脸, 卡通风格",
            key="m_features",
        )

    if st.button("🚀 生成钉织图解", type="primary",
                 use_container_width=True, key="btn_manual"):
        if not m_parts:
            st.warning("请至少选择一个部件。")
        else:
            try:
                features = [f.strip() for f in m_features.split(",") if f.strip()]
                analysis = ImageAnalysis(
                    body_type=m_body_type,
                    head_diameter_cm=m_head_d,
                    height_cm=m_height,
                    main_features=features or ["卡通风格"],
                    pose=m_pose,
                    difficulty=m_difficulty,
                    parts=m_parts,
                )
                with st.spinner("生成图解中…"):
                    result = _run_pipeline_from_analysis(
                        analysis,
                        openai_key=st.session_state.get("openai_key"),
                        anthropic_key=st.session_state.get("anthropic_key"),
                    )
                st.session_state.manual_result = result
                st.success("✅ 图解已生成！")
            except Exception as e:
                st.error(f"生成失败: {e}")
                logger.exception("Manual pipeline failed")

    if "manual_result" in st.session_state:
        render_results(st.session_state.manual_result, "manual_result")
