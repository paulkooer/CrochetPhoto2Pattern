"""Result renderer: analysis / structure / pattern / progress / edit-regenerate.

被照片 Tab 与手动 Tab 复用。widget key 全部以 result_id 为命名空间，
保证两份结果同屏渲染不冲突、重新生成后进度不串档。
"""
from __future__ import annotations

import html
import json
import re
import uuid

import streamlit as st

from app.models.colors import YARN_COLORS
from app.schemas import PART_NAMES
from app.ui import result_logic
from app.ui.result_logic import rebuild_params, result_profile
from app.utils.exporters import export_markdown
from app.utils.share import _BACKUP_KEYS

# 以 result_id 为命名空间的 widget key 前缀（chk_/all_/clear_ 后跟 `rid_…`，
# 其余后跟 `rid` 本体）。旧结果被替换时用 purge_result_state 清理。
_WIDGET_KEY_PREFIXES = (
    "chk_", "all_", "clear_", "json_edit_", "regen_", "dl_json_", "dl_md_",
    "dl_backup_", "import_", "importbtn_", "sz_head_", "sz_height_", "sz_go_",
    "pdf_", "dl_pdf_", "hist_save_", "pdf_gen_", "sz_", "share_",
    "hist_title_", "struct_edit_", "struct_go_", "struct_",
    # share_token_ 不是 widget key，但替换结果时同样应随 rid 清理
    "share_token_",
)

_RGB_BY_NAME = {name: rgb for rgb, name in YARN_COLORS}

# 备份导入的粘贴长度门禁（与 share.py 的 2MB 解压上限同源）
_MAX_IMPORT_CHARS = 2 << 20


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


def _yarn_chip_html(name: str) -> str:
    """毛线色名 → 带真实色样的胶囊 HTML。

    色样圆点用色表 RGB（用户看颜色选线，而不是只读名字）；色表外
    （LLM 自造色名）退化为中性胶囊。名字经 html.escape 后才进
    unsafe_allow_html（prompt-injection 防线，与旧实现同口径）。
    """
    dot = ""
    rgb = _RGB_BY_NAME.get(name)
    if rgb is not None:
        hex_bg = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        dot = (f"<span style='display:inline-block;width:11px;height:11px;"
               f"border-radius:50%;background:{hex_bg};"
               f"border:1px solid rgba(0,0,0,0.25);margin-right:6px;"
               f"vertical-align:-1px;'></span>")
    return (
        "<span style='background:#f4f4f4;padding:4px 14px;border-radius:20px;"
        "font-size:0.85rem;border:1px solid #ccc;display:inline-flex;"
        f"align-items:center;'>{dot}🧶 {html.escape(_strip_invisible(str(name)))}</span>"
    )


def purge_result_state(result: dict) -> None:
    """Drop widget state namespaced to a result that is about to be replaced.

    result_id 每次生成都不同，若不清理，逐圈 checkbox 等几十个 key 会在
    session_state 中随使用次数无限累积。
    """
    rid = result.get("result_id")
    if not rid:
        return
    for key in list(st.session_state.keys()):
        if str(key).startswith(tuple(p + rid for p in _WIDGET_KEY_PREFIXES)):
            del st.session_state[key]


@st.fragment
def _render_part_progress(
    part: dict,
    part_data: dict,
    part_key: str,
    chk_keys_by_copy: list[list[str]],
    chk_keys: list[str],
    rounds_list: list[dict],
    quantity: int,
    n_rounds: int,
    result: dict,
    params: dict,
) -> None:
    """单个部件的进度区（fragment）。

    勾选/取消勾选只重跑本区块——几十个 checkbox 不再各自触发整页
    rerun（fable5.1 审核 P2）。「重置/全部完成」按钮与其它流程仍走
    st.rerun() 整页刷新，语义与旧版一致。
    """
    # Checkbox widget state is the single source of truth for progress.
    # It is updated by Streamlit before the rerun, so the counts below
    # already include the click that triggered this run (no one-step lag).
    n_done = sum(bool(st.session_state.get(k)) for k in chk_keys)
    physical_rounds = n_rounds * quantity
    pct = int(n_done / physical_rounds * 100) if physical_rounds else 0
    quantity_label = f" × {quantity} 个" if quantity > 1 else ""
    rounds_label = (f"{n_rounds} 圈/个，共 {physical_rounds} 圈次"
                    if quantity > 1 else f"{n_rounds} 圈")
    label_exp = (
        f"🧶 {part_data['name']}{quantity_label} ({rounds_label})"
        f"  —  ✅ {n_done}/{physical_rounds} 圈次"
    )
    with st.expander(label_exp):
        st.write(f"**形状**: {md_safe(part_data['type'])} | "
                 f"**颜色**: {md_safe(part_data['color'])}")
        if quantity > 1:
            st.info(f"此圈序需制作 {quantity} 份相同部件；总针数、材料和工时已按 {quantity} 份计算。")
        # T8：环形圈数图（球/一体件的顶视图；勾选列表上方的直观总览）
        if part_data.get("type") in ("sphere", "onepiece"):
            with st.expander("⭕ 顶视图（环形圈数图）", expanded=False):
                try:
                    from app.models.ring_chart import (
                        render_ring_svg,
                        render_symbol_strip,
                    )
                    from app.ui.design_system import html_box

                    _sw = (result.get("gauge") or params.get("gauge") or {})
                    _sw_cm = 10.0 / max(float(_sw.get(
                        "stitches_per_10cm", 13.0)), 1e-6)
                    st.html(html_box(
                        render_ring_svg(part, stitch_w_cm=_sw_cm), 330))
                    _strip = render_symbol_strip(part)
                    if _strip:
                        st.markdown("**逐圈符号条**（×=X · V=加针 · A=减针）")
                        st.html(html_box(_strip, min(
                            30 + 16 * min(len(part.get("rounds", [])), 24)
                            + 10, 560), scroll=True))
                except Exception as e:  # 可视化失败不影响主流程
                    st.caption(f"顶视图不可用: {md_safe(e)}")
        if part_data.get("notes"):
            st.info(md_safe(part_data["notes"]))
        st.progress(
            pct, text=f"钩织进度 {pct}%  ({n_done}/{physical_rounds} 圈次)")
        st.markdown("**逐圈进度** — 勾选已完成的圈：")
        col_clear, col_all = st.columns(2)
        with col_clear:
            if st.button("↩️ 重置进度", key=f"clear_{part_key}"):
                for k in chk_keys:
                    st.session_state[k] = False
                st.rerun()
        with col_all:
            if st.button("✅ 全部完成", key=f"all_{part_key}"):
                for k in chk_keys:
                    st.session_state[k] = True
                st.rerun()
        for copy, copy_keys in enumerate(chk_keys_by_copy, 1):
            if quantity > 1:
                st.markdown(f"**第 {copy} 个 {part_data['name']}**")
            for i, r in enumerate(rounds_list):
                rd = r
                inc_str = f"+{rd['increase']}" if rd.get("increase") else ""
                dec_str = f"-{rd['decrease']}" if rd.get("decrease") else ""
                change = f" ({inc_str}{dec_str})" if (inc_str or dec_str) else ""
                notes_str = f" — {rd['notes']}" if rd.get("notes") else ""
                color_str = f" · {rd['color']}" if rd.get("color") else ""
                lbl = (f"第 {rd.get('row', i + 1)} 圈："
                       f"{rd.get('stitches', '?')}针"
                       f"{change}{notes_str}{color_str}")
                st.checkbox(lbl, key=copy_keys[i])


def render_results(result: dict, slot: str) -> None:
    """Render the result UI. `slot` is the st.session_state key holding `result`,
    so edits/regeneration write back to the tab that owns this result."""
    analysis = result["analysis"]
    structure = result["structure"]
    params = result["params"]
    # Widget-key namespace: unique per generated result, stable across reruns.
    # Fallback to the stable slot name — id(result) may be reused across reruns.
    result_key = result.get("result_id") or slot

    st.divider()
    st.markdown(
        "<p class='crochet-section-note'>图解已生成。"
        "你可以查看结构、逐圈勾选进度、局部修正并下载备份。</p>",
        unsafe_allow_html=True,
    )

    # Section 1: Analysis
    st.subheader("1️⃣ 人物与比例")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("体型", analysis["body_type"])
        st.metric("难度", analysis["difficulty"])
    with col_b:
        st.metric("目标头部直径", f"{analysis['head_diameter_cm']} cm")
        st.metric("目标整体高度", f"{analysis['height_cm']} cm")
    sizing = result.get("sizing") or {}
    if sizing.get("photo_head_to_height_ratio") is not None:
        ratio = sizing["photo_head_to_height_ratio"]
        clamp_note = "（已限制到可生成范围）" if sizing.get("ratio_clamped") else ""
        st.caption(
            f"📏 照片头径/身高比例约 {ratio:.3f}{clamp_note}；"
            "照片不提供绝对厘米尺度，以上尺寸来自生成时选择的目标高度。")
    elif sizing.get("note"):
        st.caption(f"📏 {md_safe(sizing['note'])}")
    geometry = result.get("geometry") or {}
    silhouette = geometry.get("silhouette") or {}
    if silhouette:
        st.caption(
            f"📐 单图轮廓观测 · 置信度 {float(silhouette.get('confidence', 0)):.0%}"
            "；深度按旋转体假设补充，可在尺寸与结构区继续修正。")
    st.text("主要特征: "
            + ", ".join(_plain_text(f) for f in analysis["main_features"]))
    st.text("识别部件: "
            + ", ".join(_plain_text(p) for p in analysis["parts"]))

    # 规范名之外的部件会被降级为小球处理——只在日志里提示用户看不见，
    # 这里补一条 UI 内提示（部件名模型可写，caption 前先转义）
    unknown = [p for p in analysis.get("parts", []) if p not in PART_NAMES]
    if unknown:
        st.caption("⚠️ 未识别的部件 "
                   + "、".join(html.escape(_plain_text(p)) for p in unknown)
                   + " 将按小配件（球）处理")

    # Vision 调用的 token 用量（仅照片 Tab 的真实解析路径会有值）
    usage = result.get("usage") or {}
    if usage.get("input_tokens") is not None:
        st.caption(
            f"📊 Vision 用量（{usage.get('provider', '?')}）："
            f"输入 {usage['input_tokens']} tok · 输出 {usage.get('output_tokens', '?')} tok"
        )

    # 解析来源透明展示：AI（LLM）/ 本地估算 / Mock 三类（vision_meta）
    vmeta = result.get("vision_meta") or {}
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
        }.get(source, f"解析来源：{source}")
        ratio = vmeta.get("body_ratio")
        ratio_str = f"，身高/头径 ≈ {ratio}" if ratio else ""
        st.caption(f"{label}{ratio_str} — {md_safe(vmeta.get('note', ''))}")

    # S1/F15：分段来源诚实标注——实测覆盖的部件逐一列出，其余为先验
    measured = result.get("spans_measured") or []
    if measured:
        st.caption("📐 部件分段："
                   + "、".join(md_safe(m) for m in measured)
                   + " 来自姿态关键点实测；其余按常规比例先验")
    elif result.get("spans"):
        st.caption("📐 部件分段按常规比例先验（未检出姿态关键点）")

    # Color palette swatches (from extract_color_palette)
    colors = analysis.get("recommended_colors") or []
    if not isinstance(colors, list):
        colors = []
    if colors:
        st.write("**🎨 推荐毛线颜色**（按主色占比排序）:")
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
    st.subheader("2️⃣ 部件结构设计（基础形状）")
    profile_parts = [p for p in params.get("parts", [])
                     if getattr(p, "type", None) == "profile"]
    if profile_parts:
        with st.expander("📐 轮廓对应验证（生成侧影 vs 照片剖面）", expanded=False):
            try:
                from app.models.color_design import PART_SPAN as _SPAN
                from app.models.gauge import Gauge as _G
                from app.models.profile_shaping import render_silhouette_svg, strip_dome
                from app.ui.design_system import html_box

                # gauge 优先取 result 层（生成时写入）；导入的旧备份没有
                # result["gauge"]，回退 params 里随备份保存的 gauge
                _gd = result.get("gauge") or params.get("gauge") or {}
                _gauge = _G(_gd.get("stitches_per_10cm", 13.0),
                            _gd.get("rows_per_10cm", 16.0))
                _photo = result_profile(result)
                _spans = result.get("spans") or _SPAN
                for _pp in profile_parts:
                    _wall = [r.stitches for r in _pp.rounds]
                    # 跳过底部圆盘（水平圆盘不计筒壁；旧版误用
                    # _wall[0]//6——魔法环首圈 6 针 → 恒只跳 1 圈）
                    st.html(html_box(
                        render_silhouette_svg(
                            strip_dome(_wall), _gauge, _photo,
                            _spans.get("身体")), 320))
                    st.caption(f"{_pp.name}：逐圈针数反渲染的侧影（蓝）与照片剖面（橙虚线）")
            except Exception as e:  # 可视化失败不影响主流程
                st.caption(f"轮廓可视化不可用：{md_safe(e)}")
    rows = []
    id_to_name = {
        part.get("part_id"): part.get("name", "?")
        for part in structure.get("parts", []) if part.get("part_id")
    }
    for part in structure.get("parts", []):
        dims = []
        if part.get("diameter_cm"):
            dims.append(f"直径 {part['diameter_cm']}cm")
        if part.get("height_cm"):
            dims.append(f"高 {part['height_cm']}cm")
        if part.get("length_cm"):
            dims.append(f"长 {part['length_cm']}cm")
        poses = []
        connections = []
        for instance in part.get("instances", []):
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
        rows.append({
            "部件": part.get("name", "?"),
            "数量": part.get("count", 1),
            "形状": {"sphere": "球形", "cylinder": "圆柱", "cup": "开口杯形",
                     "profile": "照片轮廓"}.get(part.get("shape"), part.get("shape", "—")),
            "尺寸": "，".join(dims) or "—",
            "位置 / 旋转": "；".join(poses) or "旧版未记录",
            "连接": "；".join(connections) or "独立部件 / 未记录",
            "基准色": part.get("color", "—"),
        })
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
        if structure.get("schema_version") == "2.0":
            st.caption(
                "结构 v2 坐标：x 左−右+，y 底部0→顶部1，z 后−前+；"
                "位置、旋转和连接来自模板推断，并非单张照片的三维测量。")
        with st.expander("🧸 3D 结构预览（示意）", expanded=False):
            from app.ui.preview3d import structure_preview_html

            _pv = structure_preview_html(result)
            if _pv:
                from app.ui.design_system import html_box

                st.html(html_box(_pv, 400), unsafe_allow_javascript=True)
            else:
                st.caption("当前结构无可预览的实体部件。")
        with st.expander("查看结构 JSON"):
            for part in structure.get("parts", []):
                st.json(part)

    # Section 3: Crochet Pattern  (with round progress tracking)
    st.subheader("3️⃣ 钩织参数")
    st.caption(
        "记号：X=短针，V=加针（1针目钩2短针），A=减针（2针并1针）；"
        "(4X,V)×6 = “4短针+1加针”重复 6 次。"
        "螺旋钩法（不引拔不翻转），每圈第一针挂记号扣；减针建议隐形减针（只挑前半针）"
    )
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
        st.caption("该检查不等同于成品形状、部件连接或实际可钩性验证。")
    else:
        st.warning("⚠️ 图解自检发现问题（可在局部修正中修复）：\n"
                   + "\n".join(md_safe(issue) for issue in _v["issues"]))
    st.caption(
        f"塑形口径：当前密度的连续几何变化率约 "
        f"{_v['shaping_continuous_delta']:.2f} 针/圈，按六等分针法向上量化为 "
        f"±{_v['max_stitch_change']} 针；较平缓轮廓仍可使用 6 针步长。")

    st.write("**所需材料**:")
    st.caption("克重/米数为估算值（请以实际线标为准）；品牌色号仅收录已核实条目")
    for mat in params.get("materials", []):
        # JSON 编辑器可能把材料改坏（如纯字符串）——渲染层降级显示而非崩溃
        if isinstance(mat, dict):
            item = str(mat.get("item", "?"))
            qty = str(mat.get("quantity", "?"))
            # T2 逐色材料：item 形如"毛线 · <色名>"且色在色表 → 真实色样胶囊
            if item.startswith("毛线 · ") and mat.get("color") in _RGB_BY_NAME:
                st.markdown(
                    _yarn_chip_html(item.replace("毛线 · ", ""))
                    + f"&nbsp;<span style='color:#555;font-size:0.9rem;'>"
                      f"{html.escape(qty)}</span>",
                    unsafe_allow_html=True)
            else:
                st.text(f"  - {item}: {qty}")
        else:
            st.text(f"  - {mat}")

    # 同名部件（历史坏结果/JSON 编辑复制部件）会生成冲突 widget key → 整页
    # 崩溃；重名时追加序号后缀。正常结果首个部件不带后缀，key 保持稳定。
    seen_names: dict = {}
    for part in params.get("parts", []):
        part_data = part
        name = part_data.get("name", "?")
        seen_names[name] = seen_names.get(name, 0) + 1
        suffix = "" if seen_names[name] == 1 else f"_{seen_names[name]}"
        part_key = f"{result_key}_{name}{suffix}"
        rounds_list = part_data.get("rounds", [])
        n_rounds = len(rounds_list)
        quantity = max(1, int(part_data.get("quantity", 1)))
        # 第一份沿用历史 key，第二份起使用 copyN 命名；这样旧会话进度不丢，
        # 又能让成对部件的两份实体各自勾选。圈数/数量缩小时清掉越界状态。
        copy_prefixes = [
            f"chk_{part_key}_" if copy == 0 else f"chk_{part_key}_copy{copy + 1}_"
            for copy in range(quantity)
        ]
        stale = []
        all_part_prefix = f"chk_{part_key}_"
        for key in st.session_state:
            if not key.startswith(all_part_prefix):
                continue
            match = re.match(
                rf"^{re.escape(all_part_prefix)}(?:copy(\d+)_)?(\d+)$", key)
            if not match:
                continue
            copy_number = int(match.group(1) or 1)
            round_index = int(match.group(2))
            if copy_number > quantity or round_index >= n_rounds:
                stale.append(key)
        for k in stale:
            del st.session_state[k]
        # Checkbox widget state is the single source of truth for progress.
        # It is updated by Streamlit before the rerun, so the counts below
        # already include the click that triggered this run (no one-step lag).
        chk_keys_by_copy = [
            [f"{prefix}{i}" for i in range(n_rounds)]
            for prefix in copy_prefixes
        ]
        chk_keys = [key for keys in chk_keys_by_copy for key in keys]
        _render_part_progress(
            part, part_data, part_key, chk_keys_by_copy, chk_keys,
            rounds_list, quantity, n_rounds, result, params)

    # Section 4: Assembly
    st.subheader("4️⃣ 装配说明")
    # 装配文本内嵌部件名（模型/结构 JSON 可写）——纯文本渲染，
    # 不经 Markdown（链接/图片语法不生效）
    asm = params.get("assembly_instructions") or ""
    st.text(asm if isinstance(asm, str) else str(asm))

    # Section 5: Edit & Re-generate
    st.subheader("5️⃣ 局部修正")
    # A5: st.success 后立即 st.rerun() 的话消息会被 rerun 丢弃（用户看不见），
    # 改为 session 标志，下一次 rerun 渲染时弹出。
    _ok_flag = f"regen_{result_key}_ok"
    _sz_ok_flag = f"sz_{result_key}_ok"
    _struct_ok_flag = f"struct_{result_key}_ok"
    if st.session_state.pop(_ok_flag, False):
        st.success("✅ 已根据修正更新图解，向上查看结果！")
    if st.session_state.pop(_sz_ok_flag, False):
        st.success("✅ 已按新尺寸重新生成图解（配色与塑形选项保持不变）！")
    if st.session_state.pop(_struct_ok_flag, False):
        st.success("✅ 已按修正后的部件结构重新生成图解与装配说明！")
    st.info("可直接编辑下方 JSON，修改针数或比例后点击 '重新生成'")

    # ── 快速调整尺寸（不重新调用 AI）：改头径/身高 → 结构+参数层重算 ──────
    # 生成时的 style/gauge/色带随 result 透传，重生成与首次行为一致；
    # 纯本地计算，无 API 成本，比手改 JSON 快且不会改坏结构。
    with st.expander("📏 快速调整尺寸（不重新识别照片）", expanded=False):
        _sz_c1, _sz_c2 = st.columns(2)
        with _sz_c1:
            _new_head = st.slider(
                "头部直径 (cm)", 4.0, 20.0,
                float(analysis.get("head_diameter_cm") or 9.0), 0.5,
                key=f"sz_head_{result_key}")
        with _sz_c2:
            _new_height = st.slider(
                "整体高度 (cm)", 10.0, 60.0,
                float(analysis.get("height_cm") or 18.0), 0.5,
                key=f"sz_height_{result_key}")
        if st.button("📐 按新尺寸重新生成", key=f"sz_go_{result_key}"):
            try:
                # 业务逻辑在 result_logic（纯函数，可离线单测）
                _new_result = result_logic.regenerate_with_size(
                    result, _new_head, _new_height)
                _new_rid = uuid.uuid4().hex[:12]
                _new_result["result_id"] = _new_rid
                if slot in st.session_state:
                    purge_result_state(st.session_state[slot])
                st.session_state[slot] = _new_result
                # 成功标志必须以"新" result_id 为键：rerun 后 render_results
                # 按新 rid 组键弹出（旧 rid 已被替换，旧键永远弹不出来）
                st.session_state[f"sz_{_new_rid}_ok"] = True
                st.rerun()
            except Exception as e:
                st.error(f"尺寸重生成失败: {md_safe(e)}")

    # ── StructureGeometry 修正：严格校验后本地重生成，不重新调用 AI ──────
    with st.expander("🧩 调整部件结构（高级）", expanded=False):
        st.caption(
            "可修改部件尺寸、形状、数量、位置和连接节点。结构 v2 会严格检查 "
            "part_id、实例数量、镜像引用与 attachment 目标；修改数量时也要同步 "
            "instances。位置/旋转用于结构表达，连接节点影响装配说明；"
            "针数主要由形状和尺寸决定。")
        structure_json = st.text_area(
            "编辑结构 JSON",
            json.dumps(structure, ensure_ascii=False, indent=2),
            height=360,
            key=f"struct_edit_{result_key}",
        )
        if st.button("🧩 校验结构并重新生成", key=f"struct_go_{result_key}"):
            try:
                # 校验 + 重生成在 result_logic（纯函数，可离线单测）
                _updated = result_logic.regenerate_with_structure(
                    result, json.loads(structure_json))
                new_result_id = uuid.uuid4().hex[:12]
                _updated["result_id"] = new_result_id
                if slot in st.session_state:
                    purge_result_state(st.session_state[slot])
                st.session_state[slot] = _updated
                st.session_state[f"struct_{new_result_id}_ok"] = True
                st.rerun()
            except Exception as e:
                st.error(f"结构校验或重生成失败: {md_safe(e)}")

    serializable_params = json.loads(
        json.dumps(params, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
                   ensure_ascii=False, indent=2)
    )
    correction_json = st.text_area(
        "编辑 JSON 输出",
        json.dumps(serializable_params, ensure_ascii=False, indent=2),
        height=300,
        key=f"json_edit_{result_key}",
    )

    md_content = export_markdown(params, analysis)

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("🔄 重新生成", key=f"regen_{result_key}"):
            try:
                corrected = json.loads(correction_json)
                st.session_state[slot]["params"] = rebuild_params(corrected)
                st.session_state[_ok_flag] = True
                st.rerun()
            except Exception as e:
                st.error(f"解析/应用失败: {md_safe(e)}")
    with col_btn2:
        st.download_button(
            "📥 下载 JSON",
            correction_json,
            file_name="amigurumi_pattern.json",
            mime="application/json",
            key=f"dl_json_{result_key}",
        )
    with col_btn3:
        st.download_button(
            "📄 下载 Markdown 图解",
            md_content,
            file_name="amigurumi_pattern.md",
            mime="text/markdown",
            key=f"dl_md_{result_key}",
        )

    # ── CrochetPARADE 导出（3D 验证）：独立 DSL 出口的差异化功能 ──────────
    with st.expander("🧶 导出 CrochetPARADE（3D 验证）", expanded=False):
        st.caption(
            "把图解翻译为 [CrochetPARADE](https://crochetparade.org) 的文本语法："
            "粘贴到其网页应用（本地计算、照片不外发）可得可旋转 3D 模型、"
            "\"过松/过紧针目\"物理分析与逐针动画——本应用代数自检之外的"
            "独立验证层。语法映射基于其官方手册的已核对子集。")
        try:
            from app.utils.parade_export import export_parade_dsl, lint_parade_dsl
            _parade_text = export_parade_dsl(result)
            _parade_issues = lint_parade_dsl(_parade_text)
            if _parade_issues:
                st.warning("导出自检提示：\n" + "\n".join(md_safe(i)
                                                       for i in _parade_issues))
            st.code(_parade_text, language=None)
            st.download_button(
                "💾 下载 CrochetPARADE DSL",
                _parade_text,
                file_name="amigurumi_parade.txt",
                mime="text/plain",
                key=f"dl_parade_{result_key}")
        except Exception as e:
            st.caption(f"CrochetPARADE 导出不可用: {md_safe(e)}")

    # ── 完整结果备份/导入（刷新会丢 session，备份 JSON 可跨会话恢复）───────
    # F24：备份键集走 _BACKUP_KEYS 与分享同构——旧版只写三键，导入后
    # 快速调尺寸会把一体件拆回分件、egg 退化 ladder（style/spans 全丢）
    backup_json = json.dumps(
        {k: (serializable_params if k == "params" else result.get(k))
         for k in _BACKUP_KEYS},
        ensure_ascii=False,
    )
    col_bk1, col_bk2, col_bk3 = st.columns(3)
    with col_bk1:
        st.download_button(
            "💾 备份完整结果",
            backup_json,
            file_name="amigurumi_backup.json",
            mime="application/json",
            key=f"dl_backup_{result_key}",
            help="含解析/结构/参数的完整结果，可稍后在任意会话导入恢复",
        )
    with col_bk2:
        # PDF（S4）：点"生成"才构建（避免每次 rerun 都渲染 PDF），
        # 字节缓存进 session 后出现下载按钮
        if st.button("🖨 生成 PDF 图解", key=f"pdf_gen_{result_key}"):
            try:
                from app.utils.pdf_export import export_pdf
                st.session_state[f"pdf_{result_key}"] = export_pdf(
                    params, analysis)
            except ImportError:
                st.caption("PDF 导出需安装 reportlab："
                           "pip install crochet-photo2pattern[pdf]")
            except Exception as e:
                st.error(f"PDF 生成失败: {md_safe(e)}")
        _pdf_bytes = st.session_state.get(f"pdf_{result_key}")
        if _pdf_bytes:
            st.download_button("📄 下载 PDF", _pdf_bytes,
                               file_name="amigurumi_pattern.pdf",
                               mime="application/pdf",
                               key=f"dl_pdf_{result_key}")
    with col_bk3:
        st.text_input("历史命名（可选）",
                      value=result.get("title") or "",
                      key=f"hist_title_{result_key}",
                      placeholder="给这份图解起个名字", label_visibility="collapsed")
        # F23：分享入口。token 计算含全量 JSON + zlib，按需生成并缓存进
        # session——不再每次 rerun 都压缩；编辑图解后需重新生成。
        from app.utils.share import encode_result
        _share_state = f"share_token_{result_key}"
        if st.button("🔗 生成分享链接", key=f"share_{result_key}"):
            st.session_state[_share_state] = encode_result({
                **{k: result.get(k) for k in _BACKUP_KEYS
                   if k not in ("params", "preview")},
                "params": serializable_params})
        _share_token = st.session_state.get(_share_state)
        if _share_token is None:
            st.caption("🔗 点「生成分享链接」得到可分享的 URL 参数；"
                       "图解过大时会提示改用「备份完整结果」文件")
        else:
            st.caption(f"🔗 分享链接（{len(_share_token)}/6000 字符，"
                       f"复制下面整行拼到本应用域名后打开即载入；"
                       f"修改图解后请重新生成）：")
            with st.expander("📎 展开分享链接", expanded=False):
                st.code(f"?p={_share_token}", language=None)
        # 历史持久化（S4）：SQLite 单文件，跨会话在侧栏"我的图解"恢复
        if st.button("🗂 存入历史", key=f"hist_save_{result_key}",
                     help="保存到本机图解历史，可在侧栏随时载回"):
            try:
                from app.utils import history
                saved = dict(result)
                saved["params"] = rebuild_params(json.loads(correction_json))
                _title = (st.session_state.get(f"hist_title_{result_key}")
                          or "").strip() or None
                history.save_result(saved, title=_title)
                st.success("✅ 已存入历史（左侧栏「我的图解」可载回）")
            except Exception as e:
                st.error(f"存入历史失败: {md_safe(e)}")
        with st.expander("📂 导入结果备份"):
            pasted = st.text_area(
                "粘贴备份 JSON 内容", height=120, key=f"import_{result_key}"
            )
            if st.button("导入并替换当前结果", key=f"importbtn_{result_key}"):
                try:
                    if len(pasted) > _MAX_IMPORT_CHARS:
                        raise ValueError(
                            f"粘贴内容超过 {_MAX_IMPORT_CHARS // (1024 * 1024)}MB "
                            "上限，请分卷导入或改用历史/分享链接")
                    # 校验 + 回填在 result_logic（纯函数，与历史载入同口径）
                    imported = result_logic.import_backup(
                        json.loads(pasted), uuid.uuid4().hex[:12])
                    # 只替换当前槽位；另一个 Tab 的结果不受影响
                    if slot in st.session_state:
                        purge_result_state(st.session_state[slot])
                    st.session_state[slot] = imported
                    st.rerun()
                except Exception as e:
                    st.error(f"导入失败: {md_safe(e)}")

    # Inline Markdown preview
    with st.expander("📋 预览 Markdown 图解", expanded=False):
        st.markdown(md_content)
