"""Tab 1: photo upload + AI pipeline."""
from __future__ import annotations

import hashlib
import logging
import uuid

import streamlit as st

from app.models.gauge import gauge_from_ui
from app.models.image_parser import env_api_key
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
    .env.example 的占位值（sk-your-key-here）不算已配置——否则应用会
    带着占位符发真实请求。
    """
    return bool(
        st.session_state.get("openai_key")
        or st.session_state.get("anthropic_key")
        or env_api_key("OPENAI_API_KEY")
        or env_api_key("ANTHROPIC_API_KEY")
    )


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
                   "本地估算／Mock 不向模型服务商发送照片；AI 模式会发送至所选服务商或中转站。"
                   "历史记录默认关闭，启用后保存于部署主机的磁盘。")
        with st.expander("➕ 多角度照片（规划中）", expanded=False):
            st.caption("上传侧面/背面照片以辅助 3D 结构推理——尚未开放；"
                       "当前可用结果页的「快速调整尺寸」与姿态实测分段弥补部分场景。")

        # 解析模式显式选择（放在上传之前：先选模式再传照片更顺）。
        # vision_mode 是显式三态（"ai"/"local"/"mock"）：Mock 不再是
        # "无 Key"的隐式副作用——有 Key 时选 Mock 也绝不发起 API 调用。
        if _has_effective_keys():
            mode_options = ["🤖 AI 视觉解析", "🧮 本地视觉估算（免费）",
                            "🎬 Mock 演示数据"]
            mode_help = ("AI：视觉模型语义解析（按 token 计费）；"
                         "本地：人脸检测推算比例，零 API 成本；"
                         "Mock：固定演示数据（配色来自照片），零 API 成本")
        else:
            mode_options = ["🧮 本地视觉估算（推荐）", "🎬 Mock 演示数据"]
            mode_help = ("本地估算：人脸检测推算相对头身比例，零 API 成本；"
                         "Mock：体型与部件为演示数据，配色来自照片，零 API 成本")
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
        vision_mode = {"🤖": "ai", "🧮": "local", "🎬": "mock"}[mode[0]]

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
                st.caption("预算在阶段边界检查，并约束 API 请求超时；本地计算无法中途强制终止。")
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
