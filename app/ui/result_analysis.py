"""Chapter 1 of the result page: proportions, provenance and colour swatches."""
from __future__ import annotations

import html
import re

import streamlit as st

from app.models.gauge import gauge_for_part, gauge_from_result
from app.schemas import PART_NAMES, ResultData, difficulty_label
from app.services.result_logic import result_profile
from app.ui.design_system import section_heading

_INVISIBLE_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069]")


def _strip_invisible(text: str) -> str:
    return _INVISIBLE_RE.sub("", text)


def _plain_text(value) -> str:
    """模型可控文本 → 安全展示字符串（去零宽/BiDi 控制符）。

    凡是 LLM/结构 JSON 可写的自由文本，一律经 st.text 纯文本渲染或
    html.escape 后才进入输出——st.write/st.markdown 会渲染链接与图片
    语法，是图片内文字注入的展示面。
    """
    return _strip_invisible(str(value))


def md_safe(value) -> str:
    """他人备份/模型可控文本 → 可安全放进 Markdown 渲染的字符串。

    st.info/st.warning/st.write 会渲染 Markdown：链接、图片与内联 HTML
    都能生效（fable5.1 第二轮审视：分享 token/备份导入是"他人内容"
    入口）。三道处理：剥零宽/BiDi → 反斜杠转义 [ ]（链接/图片语法
    失效）→ HTML 转义（<script> 等字面显示）。
    """
    text = _strip_invisible(str(value))
    text = text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    return html.escape(text)


def _confidence_text(silhouette: dict) -> str:
    """Historical numeric confidence values are not calibrated probabilities."""
    return "启发式估算（未经校准）"


def _ratio_text(sizing: dict) -> str:
    """照片头身比仅是展示性溯源数据——备份可控的非法值不得崩掉渲染。"""
    raw = sizing["photo_head_to_height_ratio"]
    try:
        return f"{float(raw):.3f}"
    except (TypeError, ValueError, OverflowError):
        return md_safe(raw)


def _silhouette_verifications(result: ResultData) -> list[tuple[str, str]]:
    """照片驱动（type="profile"）部件 → (部件名, 侧影 SVG) 列表。

    params["parts"] 在双态收敛后是纯 dict 形态；旧的 getattr 过滤器永远
    匹配不上，整个「轮廓对应验证」区域被静默禁用。
    """
    params = result.get("params") or {}
    profile_parts = [p for p in params.get("parts", [])
                     if isinstance(p, dict) and p.get("type") == "profile"]
    if not profile_parts:
        return []
    from app.models.color_design import PART_SPAN
    from app.models.profile_shaping import render_silhouette_svg, strip_dome

    gauge = gauge_from_result(result)
    photo = result_profile(result)
    spans = result.get("spans") or PART_SPAN
    return [
        (str(part.get("name", "?")),
         render_silhouette_svg(
             strip_dome([r.get("stitches", 0) for r in part.get("rounds", [])
                         if isinstance(r, dict)]),
             gauge_for_part(part, gauge), photo, spans.get("身体")))
        for part in profile_parts
    ]


def _yarn_chip_html(name: str, displays: dict | None = None) -> str:
    """毛线色名 → 带色样的胶囊 HTML。

    色样来自统一解析：色表、十六进制，或该名称登记的显示色。
    没有显示色的自定义名退化为中性胶囊，不借用别的毛线色。
    名字经 html.escape 后才进 unsafe_allow_html。
    """
    from app.models.colors import resolve_display_color

    hex_bg = resolve_display_color(name, displays, placeholders=False)
    if hex_bg is not None:
        swatch = f"<i class='yarn-chip__swatch' style='background:{hex_bg};'></i>"
        variant = ""
    else:
        swatch = "<i class='yarn-chip__swatch'></i>"
        variant = " yarn-chip--unknown"
    return (
        f"<span class='yarn-chip{variant}'>{swatch}"
        f"{html.escape(_strip_invisible(str(name)))}</span>"
    )



def render_analysis(result: ResultData) -> None:
    """人物与比例。警告留在折叠面板外，来源说明默认折叠。"""
    analysis = result["analysis"]
    # Section 1: Analysis
    section_heading(1, "人物与比例")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("体型", analysis["body_type"])
        st.metric("难度", difficulty_label(analysis["difficulty"]),
                  help="难度档按 CYC（Craft Yarn Council）Project Levels 官方"
                       "定义对齐：Basic=基础针法+基础加减针；Easy=简单配色/"
                       "塑形；Intermediate=复杂塑形")
    with col_b:
        st.metric("目标头部直径", f"{analysis['head_diameter_cm']} cm")
        st.metric("目标整体高度", f"{analysis['height_cm']} cm")
    sizing = result.get("sizing") or {}
    if sizing.get("photo_head_to_height_ratio") is not None:
        ratio = _ratio_text(sizing)
        clamp_note = "（已限制到可生成范围）" if sizing.get("ratio_clamped") else ""
        from app.models.sizing import PROPORTION_STYLE_LABELS

        styled = ""
        applied, style_key = sizing.get("applied_head_to_height_ratio"), sizing.get("proportion_style")
        if style_key in ("q", "balanced") and isinstance(applied, int | float) and applied > 0:
            styled = f"按「{PROPORTION_STYLE_LABELS[style_key]}」风格换算为玩偶约 1:{1 / applied:.1f}；"
        st.caption(
            f"📏 照片头径/身高比例约 {ratio}{clamp_note}；{styled}"
            "照片不提供绝对厘米尺度，以上尺寸来自生成时选择的目标高度。")
    elif sizing.get("note"):
        st.caption(f"📏 {md_safe(sizing['note'])}")
    geometry = result.get("geometry") or {}
    vmeta = result.get("vision_meta") or {}
    from app.utils.provenance import (
        confirmed_analysis_review,
        has_consistent_head_box,
        unrecognized_review_record,
    )

    # 2026-11-05 信息架构：解析来源、掩码/轮廓置信、姿态先验、旧版用量与局部
    # 色块表收进「来源与限制」面板（默认折叠）；警告类信息留在面板外直接可见。
    if unrecognized_review_record(vmeta):
        st.warning("复核记录无法识别，请重新核对主体、头部与部件。")

    color_evidence = vmeta.get("color_observation")
    observation = None
    if color_evidence:
        from app.models.color_observation import ColorObservation

        observation = ColorObservation.model_validate(color_evidence)
        if observation.requires_review:
            st.warning("照片中的局部色块需要复核：当前图解只有整圈配色，"
                       "眼斑等局部颜色尚未转换成圈内换色或附着装饰。")

    # 导入的旧图解或显式自定义结构可以保留非规范名，不重新猜测其形状。
    unknown = [p for p in analysis.get("parts", []) if p not in PART_NAMES]
    if unknown:
        st.caption("⚠️ 未识别的部件 "
                   + "、".join(md_safe(p) for p in unknown)
                   + " 使用已有结构与图解，请人工核对形状；不支持从该名称自动推断")

    with st.expander("来源与限制", expanded=False):
        if geometry.get("mask_review"):
            st.caption("✓ 主体选区已经过人工补选／擦除；轮廓与配色来自修正后的掩码，部件仍需确认。")
        silhouette = geometry.get("silhouette") or {}
        if silhouette:
            st.caption(
                f"📐 单图轮廓观测 · {_confidence_text(silhouette)}"
                "；深度按旋转体假设补充，可在尺寸与结构区继续修正。")
        st.text("主要特征: "
                + ", ".join(_plain_text(f) for f in analysis["main_features"]))
        st.text("识别部件: "
                + ", ".join(_plain_text(p) for p in analysis["parts"]))
        if observation is not None:
            st.caption("色块按裁剪照片定位，不代表针目位置或制作方法。阴影、背景残留也可能形成色块。"
                       "修改图解不会改写这份照片观测。")
            st.dataframe([{"颜色": r.color, "占主体比例": f"{r.pixels / observation.foreground_pixels:.1%}",
                           "左边界": f"{r.box[0]:.1%}", "上边界": f"{r.box[1]:.1%}",
                           "右边界": f"{r.box[2]:.1%}", "下边界": f"{r.box[3]:.1%}"}
                          for r in observation.regions], hide_index=True)
            if observation.omitted_region_count:
                st.caption(f"另有 {observation.omitted_region_count} 个微小或超出展示上限的色块；"
                           "其颜色计数保留在备份中。")

        # Preserve billing provenance only for imported historical results.
        usage = result.get("usage") or {}
        if usage.get("input_tokens") is not None:
            st.caption(
                f"📊 旧版图解记录的 Vision 用量（{md_safe(usage.get('provider', '?'))}）："
                f"输入 {usage['input_tokens']} tok · 输出 {usage.get('output_tokens', '?')} tok"
            )

        if usage.get("usage_complete") is False:
            st.caption("部分请求未返回用量；以上合计不代表完整账单，失败与重试也可能计费。")
        if result.get("diagnostics") or usage.get("attempts"):
            st.caption("运行耗时与回退原因（耗时只计运行阶段，不含人工确认停留时间；预算在阶段边界检查）：")
            st.json({"diagnostics": result.get("diagnostics", {}), "api_usage": usage})

        # 解析来源透明展示：AI（LLM）/ 本地估算 / Mock 三类（vision_meta）
        if confirmed_analysis_review(vmeta):
            st.caption("✓ 比例与部件已经过人工确认；原始解析来源保留如下。")
        elif vmeta.get("parts_source") == "cli_explicit":
            st.caption("部件为 CLI 显式选择；主体类型、头部与比例仍待人工确认。")
        if vmeta.get("source") == "mock":
            st.caption("🎬 Mock 演示数据（体型与部件为固定演示值，"
                       "配色与分段参考照片，仅供体验流程）")
        elif vmeta.get("source"):
            source = vmeta["source"]
            label = {
                "anthropic": "🤖 Anthropic Vision（AI 语义解析）",
                "openai": "🤖 OpenAI Vision（AI 语义解析）",
                "opencv-face": "🧮 本地视觉估算（人脸检测）",
                "silhouette-head": "🧮 本地视觉估算（轮廓头部候选）",
                "default": "🧮 本地默认估算",
            }.get(source, f"解析来源：{md_safe(source)}")
            body_ratio = vmeta.get("body_ratio")
            ratio_str = f"，身高/头径 ≈ {body_ratio}" if body_ratio else ""
            st.caption(f"{label}{ratio_str} — {md_safe(vmeta.get('note', ''))}")

        # S1/F15：分段来源诚实标注——实测覆盖的部件逐一列出，其余为先验
        measured = result.get("spans_measured") or []
        manual_spans = []
        if geometry.get("body_region"):
            manual_spans.append("身体")
        head_box_consistent = has_consistent_head_box(vmeta, result.get("spans"))
        if head_box_consistent:
            manual_spans.append("头部")
        elif vmeta.get("review_head_box") is not None:
            st.caption("头部框记录无效或与分段不一致，无法确认人工框选来源。")
        if manual_spans:
            st.caption("📐 人工框选分段：" + "、".join(manual_spans)
                       + "；身体框仅限定轮廓范围，不代表实物尺寸校准。")
        if measured:
            st.caption("📐 部件分段："
                       + "、".join(md_safe(m) for m in measured)
                       + " 来自姿态关键点实测；未框选或实测的部件按常规比例先验")
        elif result.get("spans"):
            st.caption("📐 未人工框选的部件分段按常规比例先验（未检出姿态关键点）")

    # Color palette swatches (from extract_color_palette)
    colors = analysis.get("recommended_colors") or []
    if not isinstance(colors, list):
        colors = []
    if colors:
        st.write("**推荐毛线颜色**（按主色占比排序）:")
        # 胶囊带真实毛线色样（_yarn_chip_html 内做 html.escape +
        # 未知色名降级）；颜色名来自模型可写字段，转义后才进
        # unsafe_allow_html（图片内文字可能借 prompt injection 注入）。
        swatch_html = (
            "<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;'>"
            + "".join(_yarn_chip_html(c) for c in colors)
            + "</div>"
        )
        st.markdown(swatch_html, unsafe_allow_html=True)
        st.caption("颜色仅供参考，请根据实际毛线颜色调整")
