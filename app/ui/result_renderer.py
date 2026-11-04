"""Result renderer: analysis / structure / pattern / progress / edit-regenerate.

被照片 Tab 与手动 Tab 复用。widget key 全部以 result_id 为命名空间，
保证两份结果同屏渲染不冲突、重新生成后进度不串档。
"""
from __future__ import annotations

import html
import json
import re
from copy import deepcopy

import streamlit as st

from app.models.colors import YARN_COLORS
from app.models.gauge import gauge_for_part, gauge_from_result, has_independent_gauge, part_gauge_text
from app.models.stitches import PLACEMENT_GUIDANCE, ROUND_WORKING_GUIDANCE, STITCH_LEGEND_ZH
from app.schemas import (
    PART_NAMES,
    PartData,
    PatternResult,
    ResultData,
    RoundData,
    difficulty_label,
    strip_photo_derived,
)
from app.services import result_logic
from app.services.result_logic import rebuild_params, result_profile
from app.services.workspace import workspace
from app.ui.design_system import section_heading
from app.utils.color_labels import display_color_name, display_generated_color_note
from app.utils.exporters import export_markdown
from app.utils.share import _BACKUP_KEYS

_RGB_BY_NAME = {name: rgb for rgb, name in YARN_COLORS}

# 内部形状枚举 → 用户可读名称（结构表与部件圈序共用；未知值原样显示）
_SHAPE_LABELS: dict[str | None, str | None] = {
    "sphere": "球形", "cylinder": "圆柱", "cup": "开口杯形",
    "profile": "照片轮廓", "onepiece": "头身一体",
}

# E1：零宽/BiDi 控制符（显示欺骗面——同一字段可从 LLM 输出进来）
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


def _yarn_chip_html(name: str) -> str:
    """毛线色名 → 带真实色样的胶囊 HTML。

    色样圆点用色表 RGB（用户看颜色选线，而不是只读名字）；色表外
    （LLM 自造色名）退化为中性胶囊。名字经 html.escape 后才进
    unsafe_allow_html（prompt-injection 防线，与旧实现同口径）。
    """
    rgb = _RGB_BY_NAME.get(name)
    if rgb is not None:
        hex_bg = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        swatch = f"<i class='yarn-chip__swatch' style='background:{hex_bg};'></i>"
        variant = ""
    else:
        swatch = "<i class='yarn-chip__swatch'></i>"
        variant = " yarn-chip--unknown"
    return (
        f"<span class='yarn-chip{variant}'>{swatch}"
        f"{html.escape(_strip_invisible(str(name)))}</span>"
    )


def purge_result_state(result: ResultData) -> None:
    """Drop widget state namespaced to a result that is about to be replaced.

    result_id 每次生成都不同，若不清理，逐圈 checkbox 等几十个 key 会在
    session_state 中随使用次数无限累积。控件键把 result_id 作为以 ``_`` 分隔的
    一整段（``chk_<rid>_…``、``sz_head_<rid>``），而 result_id 是随机令牌，所以
    含这一段的键都属于该结果，新控件无需登记前缀。不是控件值的状态在标签页
    工作区里，随结果一起替换。
    """
    rid = result.get("result_id")
    if not rid:
        return
    for key in list(st.session_state.keys()):
        # A whole segment: another result whose ID begins with rid keeps its state.
        if rid in str(key).split("_"):
            del st.session_state[key]


def _live_record(result: ResultData, slot: str) -> dict[str, bool]:
    """The tab's completed rounds for ``result``; a record left by another result restarts empty."""
    from app.services.progress_state import progress_record_key, store_completed_rounds

    record = st.session_state.get(progress_record_key(slot))
    if isinstance(record, dict) and record.get("result_id") == (result.get("result_id") or slot):
        return record["completed"]
    return store_completed_rounds(result, slot, {}, st.session_state)


def _toggle_round(result: ResultData, slot: str, identity: str, key: str) -> None:
    completed = _live_record(result, slot)
    if st.session_state.get(key):
        completed[identity] = True
    else:
        completed.pop(identity, None)


def _set_rounds(result: ResultData, slot: str, entries: list[tuple[str, str]], value: bool) -> None:
    """Bulk update the record and any checkbox already showing these rounds."""
    completed = _live_record(result, slot)
    for identity, key in entries:
        if value:
            completed[identity] = True
        else:
            completed.pop(identity, None)
        if key in st.session_state:
            st.session_state[key] = value


def _round_checkbox(label: str, result: ResultData, slot: str, identity: str, key: str,
                    completed: dict[str, bool]) -> None:
    # The record is the source of truth; a checkbox is created from it and writes back.
    if key not in st.session_state:
        st.session_state[key] = bool(completed.get(identity))
    st.checkbox(label, key=key, on_change=_toggle_round, args=(result, slot, identity, key))


@st.fragment
def _render_paged_progress(result: ResultData, slot: str) -> None:
    """Bound widget creation; the record keeps progress for rounds on hidden pages."""
    from app.services.progress_state import PROGRESS_PAGE_SIZE, progress_entries

    rid = result.get("result_id") or slot
    parts = result["params"]["parts"]
    completed = _live_record(result, slot)
    st.caption("圈次较多，按部件分页显示；切换页面会保留进度。全部完成/重置仅作用于所选部件。")
    index = st.selectbox("进度部件", range(len(parts)),
                         format_func=lambda i: parts[i]["name"], key=f"progress_part_{rid}")
    part = parts[index]
    entries = [(identity, key) for identity, key, _ in progress_entries(result, slot, part_index=index)]

    def set_completed(value: bool) -> None:
        _set_rounds(result, slot, entries, value)

    done = sum(bool(completed.get(identity)) for identity, _ in entries)
    st.progress(done / len(entries) if entries else 0,
                text=f"{md_safe(part['name'])}：已完成 {done}/{len(entries)} 圈次")
    with st.container(horizontal=True):
        st.button("重置进度", key=f"clear_{rid}_{part['name']}",
                  on_click=set_completed, args=(False,))
        st.button("全部完成", key=f"all_{rid}_{part['name']}",
                  on_click=set_completed, args=(True,))
    pages = max(1, (len(entries) + PROGRESS_PAGE_SIZE - 1) // PROGRESS_PAGE_SIZE)
    next_offset = next((i for i, (identity, _) in enumerate(entries) if not completed.get(identity)), None)
    if next_offset is not None:
        next_copy, next_row = divmod(next_offset, len(part["rounds"]))
        st.caption(f"下一未完成圈：第 {next_copy + 1} 个 {md_safe(part['name'])} · "
                   f"第 {part['rounds'][next_row]['row']} 圈")
    else:
        st.caption("此部件的所有实体圈次均已完成。")

    def go_to_next() -> None:
        if next_offset is not None:
            st.session_state[f"progress_page_{rid}_{index}"] = next_offset // PROGRESS_PAGE_SIZE

    st.button("▶ 前往下一未完成圈", key=f"progress_next_{rid}_{index}",
              disabled=next_offset is None, on_click=go_to_next)
    page = st.selectbox("进度页", range(pages), format_func=lambda n: f"{n + 1} / {pages}",
                        key=f"progress_page_{rid}_{index}")
    for offset in range(page * PROGRESS_PAGE_SIZE, min((page + 1) * PROGRESS_PAGE_SIZE, len(entries))):
        identity, key = entries[offset]
        copy, row = divmod(offset, len(part["rounds"]))
        rd = part["rounds"][row]
        shown_notes = display_generated_color_note(rd.get("notes") or "", rd.get("auto_color_note"))
        _round_checkbox(f"第 {copy + 1} 个 · 第 {rd['row']} 圈 · {rd['stitches']} 针　"
                        f"{md_safe(display_color_name(rd.get('color') or ''))}　"
                        f"{md_safe(shown_notes)}",
                        result, slot, identity, key, completed)


@st.fragment
def _render_part_progress(
    part: PartData,
    part_data: PartData,
    part_key: str,
    entries_by_copy: list[list[tuple[str, str]]],
    rounds_list: list[RoundData],
    quantity: int,
    n_rounds: int,
    result: ResultData,
    slot: str,
) -> None:
    """单个部件的进度区（fragment）。

    勾选和批量更新只重跑本区块。进度记录是唯一真源：勾选回调和批量按钮先更新
    记录，再同步已经显示的复选框。
    """
    entries = [entry for copy_entries in entries_by_copy for entry in copy_entries]

    def set_completed(value: bool) -> None:
        _set_rounds(result, slot, entries, value)

    # Callbacks run before the rerun, so counts include the click that triggered it.
    completed = _live_record(result, slot)
    n_done = sum(bool(completed.get(identity)) for identity, _ in entries)
    physical_rounds = n_rounds * quantity
    pct = int(n_done / physical_rounds * 100) if physical_rounds else 0
    quantity_label = f" × {quantity} 个" if quantity > 1 else ""
    rounds_label = (f"{n_rounds} 圈/个，共 {physical_rounds} 圈次"
                    if quantity > 1 else f"{n_rounds} 圈")
    # 标签必须稳定：st.expander 没有 key，元素 id 由标签派生。带实时完成数的
    # 标签会在每次勾选（fragment 重跑）后让面板重新挂载为折叠态——"边钩边勾选"
    # 每勾一圈就得重新展开（浏览器实测）。完成数由面板内的进度条承载。
    label_exp = f"{md_safe(part_data['name'])}{quantity_label}（{rounds_label}）"
    with st.expander(label_exp):
        shape = part_data.get("type")
        shape_text = _SHAPE_LABELS.get(shape, shape) if isinstance(shape, str) else "—"
        st.write(f"**形状**: {md_safe(shape_text)} | "
                 f"**颜色**: {md_safe(display_color_name(part_data['color']))}")
        if caption := part_gauge_text(part_data, gauge_from_result(result)):
            st.caption(caption)
        if quantity > 1:
            st.info(f"此圈序需制作 {quantity} 份相同部件；总针数、材料和工时已按 {quantity} 份计算。")
        # T8：环形圈数图（球/一体件的顶视图；勾选列表上方的直观总览）
        if part_data.get("type") in ("sphere", "onepiece"):
            with st.expander("顶视图（环形圈数图）", expanded=False):
                try:
                    from app.models.ring_chart import (
                        render_ring_svg,
                        render_symbol_strip,
                    )
                    from app.ui.design_system import html_box

                    _sw_cm = gauge_for_part(part_data, gauge_from_result(result)).stitch_w_cm
                    # 不用 st.html：其 DOMPurify 净化器剥掉整个 <svg>；
                    # st.markdown unsafe_allow_html 不净化（内联 SVG 无空行
                    # 时不经 markdown 重排）
                    st.markdown(html_box(
                        render_ring_svg(part, stitch_w_cm=_sw_cm), 330),
                        unsafe_allow_html=True)
                    _strip = render_symbol_strip(part)
                    if _strip:
                        st.markdown("**逐圈符号条**（×=短针，V=加针，A=减针，W=一放三，M=三并一；F/B=前/后半针）")
                        st.caption("可识别操作式按原顺序显示；只有总针数时为均匀分布示意，文字错位提示需另行核对。")
                        st.markdown(html_box(_strip, min(
                            30 + 16 * min(len(part.get("rounds", [])), 24)
                            + 10, 560), scroll=True), unsafe_allow_html=True)
                except Exception as e:  # 可视化失败不影响主流程
                    st.caption(f"顶视图不可用: {md_safe(e)}")
        if part_data.get("notes"):
            shown_notes = display_generated_color_note(
                part_data["notes"], part_data.get("auto_color_summary"))
            st.info(md_safe(shown_notes))
        st.progress(
            pct, text=f"钩织进度 {pct}%  ({n_done}/{physical_rounds} 圈次)")
        st.markdown("**逐圈进度**：勾选已完成的圈")
        # Two content-width buttons side by side; st.columns(2) spread them half a panel apart.
        with st.container(horizontal=True):
            st.button("重置进度", key=f"clear_{part_key}",
                      on_click=set_completed, args=(False,))
            st.button("全部完成", key=f"all_{part_key}",
                      on_click=set_completed, args=(True,))
        for copy, copy_entries in enumerate(entries_by_copy, 1):
            if quantity > 1:
                st.markdown(f"**第 {copy} 个 {md_safe(part_data['name'])}**")
            for i, (rd, (identity, key)) in enumerate(zip(rounds_list, copy_entries, strict=True)):
                inc_str = f"+{rd['increase']}" if rd.get("increase") else ""
                dec_str = f"-{rd['decrease']}" if rd.get("decrease") else ""
                change = f"（{inc_str}{dec_str}）" if (inc_str or dec_str) else ""
                # notes/color 为模型或 JSON 编辑器可写字段；checkbox 标签会
                # 渲染 Markdown，先经 md_safe 再拼进标签
                shown_notes = display_generated_color_note(rd.get("notes"), rd.get("auto_color_note"))
                notes_str = f"　{md_safe(shown_notes)}" if rd.get("notes") else ""
                color_str = f"　{md_safe(display_color_name(rd['color']))}" if rd.get("color") else ""
                lbl = (f"**第 {rd.get('row', i + 1)} 圈**　"
                       f"{rd.get('stitches', '?')} 针"
                       f"{change}{color_str}{notes_str}")
                _round_checkbox(lbl, result, slot, identity, key, completed)


def render_results(result: ResultData, slot: str) -> None:
    """Render the result UI. `slot` is the st.session_state key holding `result`,
    so edits/regeneration write back to the tab that owns this result."""
    analysis = result["analysis"]
    structure = result["structure"]
    params = result["params"]
    # Widget-key namespace: unique per generated result, stable across reruns.
    # Fallback to the stable slot name — id(result) may be reused across reruns.
    result_key = result.get("result_id") or slot

    from app.ui.edit_history import get_history
    get_history(slot, result)

    st.divider()
    st.markdown(
        "<p class='sheet-note'>下面是这份图解：先核对比例与结构，"
        "再按部件逐圈勾选进度；需要时局部修正，并下载备份。</p>",
        unsafe_allow_html=True,
    )
    if notice := workspace(result, slot, st.session_state)["recovery_notice"]:
        st.warning(notice)

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

    # 导入的旧图解或显式自定义结构可以保留非规范名，不重新猜测其形状。
    unknown = [p for p in analysis.get("parts", []) if p not in PART_NAMES]
    if unknown:
        st.caption("⚠️ 未识别的部件 "
                   + "、".join(md_safe(p) for p in unknown)
                   + " 使用已有结构与图解，请人工核对形状；不支持从该名称自动推断")

    color_evidence = (result.get("vision_meta") or {}).get("color_observation")
    if color_evidence:
        from app.models.color_observation import ColorObservation

        observation = ColorObservation.model_validate(color_evidence)
        if observation.requires_review:
            st.warning("照片中的局部色块需要复核：当前图解只有整圈配色，"
                       "眼斑等局部颜色尚未转换成圈内换色或附着装饰。")
        with st.expander("照片局部配色观测"):
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
        with st.expander("运行耗时与回退原因"):
            st.caption("耗时只计运行阶段，不含人工确认停留时间；预算在阶段边界检查。")
            st.json({"diagnostics": result.get("diagnostics", {}), "api_usage": usage})

    # 解析来源透明展示：AI（LLM）/ 本地估算 / Mock 三类（vision_meta）
    vmeta = result.get("vision_meta") or {}
    from app.utils.provenance import (
        confirmed_analysis_review,
        has_consistent_head_box,
        unrecognized_review_record,
    )

    if confirmed_analysis_review(vmeta):
        st.caption("✓ 比例与部件已经过人工确认；原始解析来源保留如下。")
    elif unrecognized_review_record(vmeta):
        st.warning("复核记录无法识别，请重新核对主体、头部与部件。")
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

    # Section 2: Structure
    section_heading(2, "部件结构设计（基础形状）")
    try:
        _verifications = _silhouette_verifications(result)
    except Exception as e:  # 可视化失败不影响主流程
        _verifications = None
        st.caption(f"轮廓可视化不可用：{md_safe(e)}")
    if _verifications:
        with st.expander("轮廓对应验证（生成侧影 vs 照片剖面）", expanded=False):
            from app.ui.design_system import html_box

            for _name, _svg in _verifications:
                st.markdown(html_box(_svg, 320), unsafe_allow_html=True)
                st.caption(f"{md_safe(_name)}：逐圈针数反渲染的侧影（蓝）"
                           "与照片剖面（橙虚线）")
    rows = []
    id_to_name = {
        part_id: part.get("name", "?")
        for part in structure.get("parts", [])
        if isinstance(part_id := part.get("part_id"), str) and part_id
    }
    shape_labels = _SHAPE_LABELS
    for structure_part in structure.get("parts", []):
        dims = []
        if structure_part.get("diameter_cm"):
            dims.append(f"直径 {structure_part['diameter_cm']}cm")
        if structure_part.get("height_cm"):
            dims.append(f"高 {structure_part['height_cm']}cm")
        if structure_part.get("length_cm"):
            dims.append(f"长 {structure_part['length_cm']}cm")
        poses = []
        connections = []
        for instance in structure_part.get("instances", []):
            position = instance.get("position") or {}
            rotation = instance.get("rotation_deg") or {}
            poses.append(
                f"{instance.get('instance_id', '?')}: "
                f"({float(position.get('x', 0)):+.2f},"
                f" {float(position.get('y', 0)):.2f},"
                f" {float(position.get('z', 0)):+.2f}); "
                f"旋转({float(rotation.get('x', 0)):+.0f},"
                f"{float(rotation.get('y', 0)):+.0f},"
                f"{float(rotation.get('z', 0)):+.0f})°"
            )
            for attachment in instance.get("attachments", []):
                target_id = attachment.get("target_part_id", "?")
                target = id_to_name.get(target_id, target_id)
                connections.append(
                    f"{instance.get('instance_id', '?')} → "
                    f"{target}.{attachment.get('target_anchor', '?')}"
                    f"（{attachment.get('method', 'sewn')}）"
                )
        shape = structure_part.get("shape", "—")
        rows.append({
            "部件": structure_part.get("name", "?"),
            "数量": structure_part.get("count", 1),
            # shape 正常是字符串；非标量（旧备份注入的 dict/list）会让 dict.get
            # 抛 unhashable TypeError，这里降级为「—」而非崩溃（import 侧已拦截，
            # 此为渲染层兜底）。
            "形状": shape_labels.get(shape, shape) if isinstance(shape, (str, type(None))) else "—",
            "尺寸": "，".join(dims) or "—",
            "位置 / 旋转": "；".join(poses) or "旧版未记录",
            "连接": "；".join(connections) or "独立部件 / 未记录",
            "基准色": display_color_name(structure_part.get("color", "—")),
        })
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
        if structure.get("schema_version") == "2.0":
            st.caption(
                "结构 v2 坐标：x 左−右+，y 底部0→顶部1，z 后−前+；"
                "位置、旋转和连接来自模板推断，并非单张照片的三维测量。")
        with st.expander("3D 结构预览（示意）", expanded=False):
            from app.ui.preview3d import structure_preview_html

            _pv = structure_preview_html(result)
            if _pv:
                from app.ui.design_system import html_box

                # 静态等距 SVG——st.html 的净化器剥 <svg>/<script>，交互
                # canvas 无可用脚本通道，与其他图形同走 markdown
                st.markdown(html_box(_pv, 420), unsafe_allow_html=True)
                if any(part.get("color") in ("skin", "body")
                       for part in (result.get("params") or {}).get("parts", [])):
                    st.caption("待选色使用示意颜色，请根据实际毛线选色。")
                from app.models.parts import _part_instance_colors

                _params_parts = (result.get("params") or {}).get("parts", [])
                _striped = any(
                    any((rd.get("color") or part.get("color")) != part.get("color")
                        for rd in (part.get("rounds") or []))
                    for part in _params_parts)
                _per_copy = any(_part_instance_colors(part) is not None
                                for part in _params_parts)
                if _striped or _per_copy:
                    st.caption("3D 预览按部件主色示意：不显示逐圈条纹，也不显示各份实体"
                               "各自的颜色；请以逐圈图解与材料清单为准。")
            else:
                st.caption("当前结构无可预览的实体部件。")
        with st.expander("查看结构 JSON"):
            for structure_part in structure.get("parts", []):
                st.json(structure_part)

    # Section 3: Crochet Pattern  (with round progress tracking)
    section_heading(3, "钩织参数")
    st.caption(STITCH_LEGEND_ZH)
    st.caption(ROUND_WORKING_GUIDANCE)
    st.caption(PLACEMENT_GUIDANCE)
    from app.models.stitches import (
        glossary_table_markdown,
        symbol_strip_html,
    )

    with st.expander("针法速查（五体系对照 · 含突尼斯针族）", expanded=False):
        # 符号条走 markdown 通道（st.html 的净化器剥整个 <svg>，实测 1.60）
        st.markdown(symbol_strip_html(), unsafe_allow_html=True)
        st.markdown(glossary_table_markdown())
    physical_parts = sum(
        max(1, int(part.get("quantity", 1)))
        for part in params.get("parts", []))
    estimated_minutes = max(0, int(params.get("estimated_time_minutes") or 0))
    summary_a, summary_b, summary_c = st.columns(3)
    with summary_a:
        st.metric("实体部件", f"{physical_parts} 个")
    with summary_b:
        st.metric("总针数", f"{int(params.get('total_stitches') or 0):,} 针")
    with summary_c:
        time_label = (f"{estimated_minutes / 60:.1f} 小时"
                      if estimated_minutes >= 60 else f"{estimated_minutes} 分钟")
        st.metric(
            "基础操作估时",
            time_label,
            help="低置信度经验模型：只按针数和实体圈次计算。",
        )
    st.caption(
        "工时为未校准的基础估算，仅计针数与每圈固定开销；"
        "不含缝合、填充、换色、刺绣、返工和休息，完整项目通常会更久。"
    )
    # T4：图解自检——代数矛盾直接暴露给用户（借鉴 CrochetPARADE 的
    # correctness checking；此前只有测试层知道）
    from app.models.validator import validate_pattern
    _v = validate_pattern(params)
    if _v["ok"]:
        st.success(
            f"✅ 针数代数与相邻圈跳变检查通过（已检查 {_v['checked']} 圈）")
        st.caption("自检覆盖针数代数及可识别操作式的消耗、产出与加减针；自定义工艺说明仍需人工复核。"
                   "已声明的预留半针连接也会核对圈号、针数及挑针范围；其他连接和实际成形仍需试钩确认。")
    else:
        st.warning("⚠️ 图解自检发现问题（可在局部修正中修复）：\n"
                   + "\n".join(md_safe(issue) for issue in _v["issues"]))
    if _v.get("notes"):
        st.caption("ℹ️ " + "；".join(md_safe(n) for n in _v["notes"]))
    # 已有图解（导入、编辑或重算）只提示；首次生成时的阻断见 app/models/crochetability.py
    from app.models.crochetability import crochetability_findings
    _crochetability = crochetability_findings(params)
    if _concerns := [f for f in _crochetability if f.level != "note"]:
        st.warning("⚠️ 可钩性提示：" + "；".join(md_safe(f.message) for f in _concerns)
                   + "。可在「局部修正 → 快速调整尺寸」增大尺寸后重新生成。")
    if _small := [f for f in _crochetability if f.level == "note"]:
        st.caption("ℹ️ " + "；".join(md_safe(f.message) for f in _small) + "。")
    shaping_label = "默认密度" if _v["ok"] and has_independent_gauge(params) else "当前密度"
    st.caption(
        f"塑形口径：{shaping_label}的连续几何变化率约 "
        f"{_v['shaping_continuous_delta']:.2f} 针/圈，按六等分针法向上量化为 "
        f"±{_v['max_stitch_change']} 针；较平缓轮廓仍可使用 6 针步长。")

    st.write("**所需材料**:")
    st.caption("克重/米数为估算值（请以实际线标为准）；品牌色号仅收录已核实条目")
    from app.models.materials import material_summary_text
    if summary := material_summary_text(params):
        st.caption(md_safe(summary))
    for mat in params.get("materials", []):
        # JSON 编辑器可能把材料改坏（如纯字符串）——渲染层降级显示而非崩溃
        if isinstance(mat, dict):
            item = str(mat.get("item", "?"))
            qty = str(mat.get("quantity", "?"))
            # T2 逐色材料：item 形如"毛线 · <色名>"且色在色表 → 真实色样胶囊
            if item.startswith("毛线 · ") and mat.get("color") in _RGB_BY_NAME:
                st.markdown(
                    _yarn_chip_html(item.replace("毛线 · ", ""))
                    + f"<span class='yarn-qty'>{html.escape(qty)}</span>",
                    unsafe_allow_html=True)
            else:
                st.text(f"  - {item}: {qty}")
        else:
            st.text(f"  - {mat}")

    # 按完整图解为每份实体分配勾选编号；历史坏结果中的重名部件仍用
    # 序号区分批量按钮。正常未冲突的编号保持稳定。
    from app.services.progress_state import MAX_INLINE_ROUNDS, physical_rounds, progress_entries
    if physical_rounds(result) > MAX_INLINE_ROUNDS:
        _render_paged_progress(result, slot)
    else:
        # Widget keys come from the full-pattern mapping shared with paging, project
        # save and restore, so similar custom names never alias another copy's keys.
        valid_keys = {key for _, key, _ in progress_entries(result, slot)}
        for key in list(st.session_state):
            if str(key).startswith(f"chk_{result_key}_") and key not in valid_keys:
                del st.session_state[key]
        seen_names: dict = {}
        for part_index, part in enumerate(params.get("parts", [])):
            part_data = part
            name = part_data.get("name", "?")
            seen_names[name] = seen_names.get(name, 0) + 1
            suffix = "" if seen_names[name] == 1 else f"_{seen_names[name]}"
            part_key = f"{result_key}_{name}{suffix}"
            rounds_list = part_data.get("rounds", [])
            n_rounds = len(rounds_list)
            quantity = max(1, int(part_data.get("quantity", 1)))
            entries = [(identity, key)
                       for identity, key, _ in progress_entries(result, slot, part_index=part_index)]
            entries_by_copy = [entries[i:i + n_rounds] for i in range(0, len(entries), n_rounds or 1)]
            # 带 key 的容器获得 CSS 类 st-key-sheet_part_…；design_system 据此把
            # 这一部件的圈序渲染成"图解纸"（宋体行，勾选后记号扣高亮）
            with st.container(key=f"sheet_part_{result_key}_{part_index}"):
                _render_part_progress(
                    part, part_data, part_key, entries_by_copy,
                    rounds_list, quantity, n_rounds, result, slot)

    from app.ui.project_save import render_project_save

    render_project_save(result, slot)
    from app.ui.trial_editor import render_trial_editor

    render_trial_editor(result, slot)

    # Section 4: Assembly
    section_heading(4, "装配说明")
    # 装配文本内嵌部件名（模型/结构 JSON 可写）——纯文本渲染，
    # 不经 Markdown（链接/图片语法不生效）
    from app.models.assembly import assembly_for_pattern

    asm = assembly_for_pattern(params) if _v["ok"] else params.get("assembly_instructions") or ""
    st.text(asm if isinstance(asm, str) else str(asm))

    # Section 5: Edit & Re-generate
    section_heading(5, "局部修正")
    # A5: st.success 后立即 st.rerun() 的话消息会被 rerun 丢弃（用户看不见），
    # 改为记在新结果的工作区，下一次 rerun 渲染时弹出。
    ws = workspace(result, slot, st.session_state)
    if success := ws["success"]:
        ws["success"] = None
        st.success(success)
    from app.ui.edit_history import preview_edit
    from app.ui.pattern_editor import apply_edit_with_notice, render_pattern_editor

    # Undo/redo first, then the common editors in order of use (size → parts and
    # rounds → materials). Raw JSON editing is the advanced layer below them.
    render_pattern_editor(result, slot)

    serializable_params = json.loads(
        json.dumps(params, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
                   ensure_ascii=False, indent=2)
    )
    applied_params_json = json.dumps(serializable_params, ensure_ascii=False, indent=2)

    # ── 高级编辑：输出 JSON 与结构 JSON 共用一个默认折叠的面板 ──────────────
    # 两段编辑器始终同时渲染，不用单选切换：Streamlit 会丢弃未渲染控件的状态，
    # 切换会让尚未应用的草稿消失。
    with st.expander("高级编辑（JSON）", expanded=False):
        st.caption("直接编辑生成结果或部件结构的 JSON；建议先预览影响再应用。"
                   "尺寸、部件、逐圈与材料的常用修正请使用上方面板。")
        correction_json = st.text_area(
            "编辑 JSON 输出",
            applied_params_json,
            height=300,
            key=f"json_edit_{result_key}",
        )
        draft_pending = correction_json != applied_params_json
        if draft_pending:
            st.caption("JSON 草稿尚未应用。请点击「重新生成」应用修改；"
                       "下载、分享和存入历史使用当前已应用的图解。")
        with st.container(horizontal=True):
            preview_json = st.button("预览 JSON 修改影响", key=f"edit_{result_key}_json_preview")
            apply_json = st.button("重新生成", key=f"regen_{result_key}")
        if apply_json or preview_json:
            try:
                corrected = json.loads(correction_json)
                candidate = deepcopy(result)
                candidate["params"] = rebuild_params(corrected)
                candidate["gauge"] = candidate["params"].get("gauge")
                if preview_json:
                    preview_edit(slot, result, candidate)
                else:
                    apply_edit_with_notice(slot, result, candidate, "✅ 已根据修正更新图解，向上查看结果！")
            except Exception as e:
                st.error(f"解析/应用失败: {md_safe(e)}")

        # ── StructureGeometry 修正：严格校验后本地重生成，不重新调用 AI ──────
        st.caption(
            "部件结构 JSON：可修改部件尺寸、形状、数量、位置和连接节点。结构 v2 会严格检查 "
            "part_id、实例数量、镜像引用与 attachment 目标；修改数量时也要同步 "
            "instances。位置/旋转用于结构表达，连接节点影响装配说明；"
            "针数主要由形状和尺寸决定。")
        structure_json = st.text_area(
            "编辑结构 JSON",
            json.dumps(structure, ensure_ascii=False, indent=2),
            height=360,
            key=f"struct_edit_{result_key}",
        )
        with st.container(horizontal=True):
            preview_structure = st.button("预览结构 JSON 修改影响",
                                          key=f"edit_{result_key}_structure_preview")
            apply_structure = st.button("校验结构并重新生成", key=f"struct_go_{result_key}")
        if apply_structure or preview_structure:
            try:
                # 校验 + 重生成在 result_logic（纯函数，可离线单测）
                _updated = result_logic.regenerate_with_structure(
                    result, json.loads(structure_json))
                if preview_structure:
                    preview_edit(slot, result, _updated)
                else:
                    apply_edit_with_notice(slot, result, _updated,
                                           "✅ 已按修正后的部件结构重新生成图解与装配说明！")
            except Exception as e:
                st.error(f"结构校验或重生成失败: {md_safe(e)}")

    from app.models.runtime import timed_export
    from app.ui.export_cache import EXPORT_CACHE_VERSION, cached_export, parade_payload
    export_record = ws["export_trace"]
    export_cache = ws["export_cache"]
    # Bind portable text to all inputs its exporter consumes, including source
    # labels. Widget edits and unrelated diagnostics do not invalidate it.
    from app import software_version
    markdown_source = {
        "params": serializable_params, "analysis": analysis,
        "vision_meta": result.get("vision_meta"), "sizing": result.get("sizing"),
        "generator_version": result.get("generator_version"), "export_version": software_version(),
    }
    md_content = ""
    md_ready = False
    if _v["ok"]:
        try:
            md_content = cached_export(
                export_cache, "markdown", markdown_source,
                lambda: timed_export(
                    export_record, "markdown", lambda: export_markdown(params, analysis, result=result)))
            md_ready = True
        except Exception as exc:
            st.error(f"Markdown 生成失败：{md_safe(exc)}")

    # ── 下载与保存：常用出口始终可见，不进折叠面板 ─────────────────────────
    st.markdown("**下载与保存**")
    if draft_pending:
        st.caption("「高级编辑」中有尚未应用的 JSON 草稿；以下下载、分享和存入历史使用当前已应用的图解。")

    # ── 完整结果备份/导入（刷新会丢 session，备份 JSON 可跨会话恢复）───────
    # F24：备份键集走 _BACKUP_KEYS 与分享同构——旧版只写三键，导入后
    # 快速调尺寸会把一体件拆回分件、egg 退化 ladder（style/spans 全丢）
    # 下载的备份也可能被转发分享（分享链接过大时本就建议改用它），因此剔除
    # 照片衍生数据（preview 缩略图 + mask_review 主体剪影），与文档“只携带图解”
    # 的声明一致。本机历史缩略图另走 history 列保存，不受影响。
    backup_json = json.dumps(strip_photo_derived(PatternResult.from_result({
        **result, "params": serializable_params,
    }).to_backup()), ensure_ascii=False)
    col_bk1, col_bk2, col_bk3 = st.columns(3)
    with col_bk1:
        st.download_button(
            "备份完整结果",
            backup_json,
            file_name="amigurumi_backup.json",
            mime="application/json",
            key=f"dl_backup_{result_key}",
            help="含解析/结构/参数的完整结果，可稍后在任意会话导入恢复",
        )
        st.download_button(
            "下载 JSON",
            applied_params_json,
            file_name="amigurumi_pattern.json",
            mime="application/json",
            key=f"dl_json_{result_key}",
        )
        st.download_button(
            "下载 Markdown 图解",
            md_content,
            file_name="amigurumi_pattern.md",
            mime="text/markdown",
            key=f"dl_md_{result_key}",
            disabled=not md_ready,
        )
    with col_bk2:
        # A live session must regenerate PDFs after printable guidance changes.
        if ws["pdf"] is not None and ws["pdf"]["format"] != EXPORT_CACHE_VERSION:
            ws["pdf"] = None
        # PDF（S4）：点"生成"才构建（避免每次 rerun 都渲染 PDF），
        # 字节缓存进工作区后出现下载按钮
        if st.button("生成 PDF 图解", key=f"pdf_gen_{result_key}", disabled=not _v["ok"]):
            try:
                from app.utils.pdf_export import export_pdf
                ws["pdf"] = {"format": EXPORT_CACHE_VERSION, "bytes": timed_export(
                    export_record, "pdf", lambda: export_pdf(params, analysis, result=result))}
            except ImportError:
                st.caption("PDF 导出需安装 reportlab："
                           "pip install crochet-photo2pattern[pdf]")
            except Exception as e:
                st.error(f"PDF 生成失败: {md_safe(e)}")
        _pdf_bytes = ws["pdf"]["bytes"] if ws["pdf"] is not None else None
        if _pdf_bytes and _v["ok"]:
            st.download_button("下载 PDF", _pdf_bytes,
                               file_name="amigurumi_pattern.pdf",
                               mime="application/pdf",
                               key=f"dl_pdf_{result_key}")
    with col_bk3:
        from app.ui.workspace import live_workspace, seed_widget, title_key

        seed_widget(title_key(result_key), live_workspace(result, slot)["title"])
        st.text_input("历史命名（可选）",
                      key=title_key(result_key),
                      placeholder="给这份图解起个名字", label_visibility="collapsed")
        # F23：分享入口。token 计算含全量 JSON + zlib，按需生成并缓存进
        # 工作区——不再每次 rerun 都压缩；编辑图解后需重新生成。
        from app.utils.share import encode_result
        if st.button("生成分享链接", key=f"share_{result_key}"):
            ws["share"] = {"token": encode_result({
                **{k: result.get(k) for k in _BACKUP_KEYS
                   if k not in ("params", "preview")},
                "params": serializable_params})}
        _share_token = ws["share"]["token"] if ws["share"] is not None else None
        if ws["share"] is not None and _share_token is None:
            st.info("图解超过分享链接大小上限，请使用「备份完整结果」文件分享。")
        elif _share_token is None:
            st.caption("🔗 点「生成分享链接」得到可分享的 URL 参数；"
                       "图解过大时会提示改用「备份完整结果」文件")
        else:
            st.caption(f"🔗 分享链接（{len(_share_token)}/6000 字符，"
                       f"复制下面整行拼到本应用域名后打开即载入；"
                       f"修改图解后请重新生成）：")
            with st.expander("展开分享链接", expanded=False):
                st.code(f"?p={_share_token}", language=None)
        # 历史持久化（S4）：SQLite 单文件，跨会话在侧栏"我的图解"恢复
        from app.utils import history

        if st.button("存入历史", key=f"hist_save_{result_key}",
                     disabled=not history.history_enabled() or not _v["ok"],
                     help="保存到部署主机的图解历史，可在侧栏随时载回"):
            try:
                saved = result.copy()
                saved["params"] = rebuild_params(serializable_params)
                saved["gauge"] = saved["params"].get("gauge")
                _title = (live_workspace(result, slot)["title"] or "").strip() or None
                saved_id = history.save_result(saved, title=_title)
                if saved_id:
                    result["history_id"] = saved_id
                    result["title"] = _title
                st.success("✅ 已存入历史（左侧栏「我的图解」可载回）")
            except Exception as e:
                st.error(f"存入历史失败: {md_safe(e)}")
        from app.ui.backup_import import render_backup_import

        render_backup_import(slot, result_key=result_key)

    # ── CrochetPARADE 导出（3D 验证）：独立 DSL 出口的差异化功能 ──────────
    with st.expander("导出 CrochetPARADE（3D 验证）", expanded=False):
        st.caption(
            "把图解翻译为 [CrochetPARADE](https://crochetparade.org) 的文本语法："
            "粘贴到其网页应用（本地计算、照片不外发）可得可旋转 3D 模型、"
            "\"过松/过紧针目\"物理分析与逐针动画——本应用代数自检之外的"
            "独立检查工具。语法映射基于其官方手册的已核对子集。")
        st.caption("本应用只检查导出完整性与文本语法，尚未运行外部仿真；仿真结果也不能替代实体试钩。")
        st.caption("可识别操作式保留针法顺序及明确的 FLO/BLO；挑针范围不清时停止该部件导出。"
                   "仅文字描述的错位和收口动作需对照原图解核对。")
        try:
            if not _v["ok"]:
                raise ValueError("请先修复图解自检错误")
            _parade = cached_export(
                export_cache, "parade", {"params": serializable_params, "export_version": software_version()},
                lambda: parade_payload(result))
            _parade_text = _parade["text"]
            if _parade["inferred_rounds"]:
                st.caption(f"{_parade['inferred_rounds']} 个实体圈次仅按数值均匀安排针位；"
                           "其余可识别操作式保留针法顺序，特殊工艺及文字错位提示仍需核对。")
            if not _parade["complete"]:
                st.warning("仅导出部分图解；不可视为完整验证："
                           f"{_parade['exported_rounds']}/{_parade['requested_rounds']} 圈次，"
                           f"{_parade['exported_parts']}/{_parade['requested_parts']} 个完整实体部件。")
            _parade_issues = _parade["issues"]
            if _parade_issues:
                st.warning("导出自检提示：\n" + "\n".join(md_safe(i)
                                                       for i in _parade_issues))
            st.code(_parade_text, language=None)
            st.download_button(
                "下载 CrochetPARADE DSL",
                _parade_text,
                file_name="amigurumi_parade.txt",
                mime="text/plain",
                key=f"dl_parade_{result_key}")
        except Exception as e:
            st.caption(f"CrochetPARADE 导出不可用: {md_safe(e)}")

    with st.expander("最近一次导出耗时"):
        st.json(export_record.get("diagnostics", {}))

    # Inline Markdown preview
    with st.expander("预览 Markdown 图解", expanded=False):
        st.markdown(md_content)
