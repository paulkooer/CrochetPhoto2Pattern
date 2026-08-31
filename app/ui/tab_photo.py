"""Tab 1: photo upload + AI pipeline."""
from __future__ import annotations

import logging
import os
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
        openai_base_url=st.session_state.get("openai_base_url"),
        anthropic_base_url=st.session_state.get("anthropic_base_url"),
    )


def _has_effective_keys() -> bool:
    """输入框或 .env（环境变量）任一处配置了 Key 即视为已配置。

    只看输入框会把 .env 用户误判为"无 Key"：ImageParser 的空串 key 会
    回退 os.getenv，旧版在此时选择"Mock 演示数据"实际发起的是真实计费
    调用（Mock 只是"无 key"的隐式副作用），选项与行为完全脱节。
    """
    return bool(
        st.session_state.get("openai_key")
        or st.session_state.get("anthropic_key")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
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
        target_height = st.slider(
            "目标成品高度 (cm)", 10.0, 60.0, 18.0, 0.5,
            key="photo_target_height",
            help="单张照片无法测出真实厘米尺寸；系统保留照片头身比例，"
                 "再按这个目标高度生成图解。",
        )
        st.caption("📏 照片只用于估算相对比例，绝对尺寸由上面的目标高度决定。")
        st.caption("🔒 隐私说明：选择 AI 解析时照片会发送至对应的模型服务商"
                   "（OpenAI/Anthropic 或你的中转站）；本地估算/Mock 模式照片"
                   "不离开本机。本工具自身没有服务器，图解历史只存在你的电脑上。")
        with st.expander("➕ 多角度照片（规划中）", expanded=False):
            st.caption("上传侧面/背面照片以辅助 3D 结构推理——尚未开放；"
                       "当前可用结果页的「快速调整尺寸」与姿态实测分段弥补部分场景。")

        # 解析模式显式选择（放在上传之前：先选模式再传照片更顺）。
        # Mock 选项只在"真正无 Key（输入框与 .env 都没有）"时提供——
        # 它靠"无 key"的隐式副作用生效，有 Key 时选它会变成真实计费调用。
        if _has_effective_keys():
            mode_options = ["🤖 AI 视觉解析", "🧮 本地视觉估算（免费）"]
            mode_help = ("AI：视觉模型语义解析（按 token 计费）；"
                         "本地：人脸检测推算比例，零 API 成本")
        else:
            mode_options = ["🧮 本地视觉估算（推荐）", "🎬 Mock 演示数据"]
            mode_help = ("本地估算：人脸检测推算相对头身比例，零 API 成本；"
                         "Mock：固定演示数据，与照片无关")
        # options 随 Key 状态切换：残留旧值不在新 options 时先清掉，
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
        use_local = mode.startswith("🧮")

    with col_preview:
        if uploaded_file is None:
            st.markdown(
                "<div class='crochet-empty'>🧶<br>上传照片后，这里会显示预览，"
                "生成结果将出现在下方。</div>",
                unsafe_allow_html=True,
            )

    if uploaded_file:
        image = load_uploaded_image_cached(uploaded_file)
        if image is not None:
            with col_preview:
                st.image(image, caption="上传的照片", width="stretch")

            if st.button("🚀 生成钩织图解", type="primary",
                         width="stretch", key="btn_photo"):
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
                        target_height_cm=target_height,
                        target_height_source="user_photo_target",
                    )
                    # 替换旧结果前清掉它命名空间下的 widget 状态，防累积
                    if "result" in st.session_state:
                        purge_result_state(st.session_state.result)
                    result["result_id"] = uuid.uuid4().hex[:12]
                    st.session_state.result = result
                    # 结果区本身即完成反馈：清掉进度条，避免"100% 完成条"
                    # 常驻在页面上方造成 clutter
                    progress.empty()
                except Exception as e:
                    progress.empty()  # 失败时移除进度条，避免"40% + 报错"同屏矛盾
                    st.error(f"生成失败: {e}")
                    logger.exception("Pipeline failed")

    # Render outside the `if uploaded_file` block so the last result stays
    # visible even after the uploader is cleared.
    if "result" in st.session_state:
        render_results(st.session_state.result, "result")
