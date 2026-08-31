"""Tab 2: manual parameter input (no photo / no API key required)."""
from __future__ import annotations

import logging
import uuid

import streamlit as st

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import gauge_from_ui
from app.models.geometry import no_photo_geometry
from app.models.sizing import sizing_meta_for_analysis
from app.models.structure_designer import StructureDesigner
from app.schemas import PART_NAMES, ImageAnalysis
from app.ui.result_renderer import purge_result_state, render_results

logger = logging.getLogger(__name__)


def _style_from_session():
    import streamlit as _st

    from app.models.gauge import ShapingStyle

    return ShapingStyle(
        sphere_mode=_st.session_state.get("style_sphere", "ladder"),
        one_piece=bool(_st.session_state.get("style_onepiece", False)),
        skirt_style=_st.session_state.get("style_skirt", "ring"),
        ruffle_hem=bool(_st.session_state.get("style_ruffle", False)),
    )


def _gauge_values():
    import streamlit as st
    return (st.session_state.get("gauge_preset", "classic"),
            st.session_state.get("gauge_st_input"), st.session_state.get("gauge_rw_input"))


def _run_pipeline_from_analysis(analysis: ImageAnalysis) -> dict:
    """Run structure + param stages given an already-parsed ImageAnalysis.

    手动输入无需 Vision 解析，因此直接用后两个阶段类，不构造
    PipelineOrchestrator（那会连带初始化 ImageParser 并加载 prompt 文件）。
    """
    structure = StructureDesigner.design_3d_structure(analysis)
    style = _style_from_session()
    params = CrochetParamsGenerator.generate_params(
        analysis, structure,
        gauge=gauge_from_ui(*_gauge_values()),
        style=style)
    return {
        "analysis": analysis.model_dump(),
        "structure": structure,
        "params": params,
        "result_id": uuid.uuid4().hex[:12],
        # 与照片路径同构：结果页快速调整尺寸时复用（无照片 → 无色带）
        "style": {"sphere_mode": style.sphere_mode,
                  "one_piece": style.one_piece,
                  "skirt_style": style.skirt_style,
                  "ruffle_hem": style.ruffle_hem},
        "color_bands": None,
        "sizing": sizing_meta_for_analysis(analysis, "manual_dimensions"),
        "geometry": no_photo_geometry().model_dump(),
    }


def render_tab_manual() -> None:
    st.subheader("✏️ 手动设计玩偶")
    st.markdown(
        "<p class='crochet-section-note'>无需上传照片，填写人物比例、姿态与部件，"
        "就能直接生成专属钩织图解。</p>",
        unsafe_allow_html=True,
    )

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
            list(PART_NAMES),
            default=["头部", "身体"],
            key="m_parts",
        )
        m_features = st.text_input(
            "主要特征（逗号分隔）",
            "大眼睛, 圆脸, 卡通风格",
            key="m_features",
        )

    if st.button("🚀 生成钩织图解", type="primary",
                 width="stretch", key="btn_manual"):
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
                    result = _run_pipeline_from_analysis(analysis)
                # 替换旧结果前清掉它命名空间下的 widget 状态，防累积
                if "manual_result" in st.session_state:
                    purge_result_state(st.session_state.manual_result)
                st.session_state.manual_result = result
                st.success("✅ 图解已生成！")
            except Exception as e:
                st.error(f"生成失败: {e}")
                logger.exception("Manual pipeline failed")

    if "manual_result" in st.session_state:
        render_results(st.session_state.manual_result, "manual_result")
