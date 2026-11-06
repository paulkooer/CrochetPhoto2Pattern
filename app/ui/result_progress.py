"""Chapter 3 of the result page: stitch reference, materials and round progress."""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

from app.models.gauge import gauge_for_part, gauge_from_result, has_independent_gauge, part_gauge_text
from app.models.stitches import PLACEMENT_GUIDANCE, ROUND_WORKING_GUIDANCE, STITCH_LEGEND_ZH
from app.schemas import PartData, ResultData, RoundData
from app.ui.design_system import section_heading
from app.ui.result_analysis import _RGB_BY_NAME, _yarn_chip_html, md_safe
from app.ui.result_structure import _SHAPE_LABELS
from app.utils.color_labels import display_color_name, display_generated_color_note


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



def render_pattern(result: ResultData, slot: str) -> dict[str, Any]:
    """钩织参数、材料与逐圈进度。返回自检结果，供装配和导出沿用同一次检查。"""
    params = result["params"]
    result_key = result.get("result_id") or slot
    # Section 3: Crochet Pattern  (with round progress tracking)
    section_heading(3, "钩织参数")
    physical_parts = sum(
        max(1, int(part.get("quantity", 1)))
        for part in params.get("parts", []))
    estimated_minutes = max(0, int(params.get("estimated_time_minutes") or 0))
    # T4：图解自检——代数矛盾直接暴露给用户（借鉴 CrochetPARADE 的
    # correctness checking；此前只有测试层知道）
    from app.models.validator import validate_pattern
    _v = validate_pattern(params)
    shaping_label = "默认密度" if _v["ok"] and has_independent_gauge(params) else "当前密度"
    from app.models.stitches import (
        glossary_table_markdown,
        symbol_strip_html,
    )

    # 2026-11-05 信息架构：针法图例/钩法/针位/工时/塑形说明收进「针法速查」，
    # 正文只留三个指标、自检徽章、材料与圈序。
    with st.expander("针法速查（五体系对照 · 含突尼斯针族）", expanded=False):
        st.caption(STITCH_LEGEND_ZH)
        st.caption(ROUND_WORKING_GUIDANCE)
        st.caption(PLACEMENT_GUIDANCE)
        st.caption(
            "工时为未校准的基础估算，仅计针数与每圈固定开销；"
            "不含缝合、填充、换色、刺绣、返工和休息，完整项目通常会更久。"
        )
        st.caption(
            f"塑形口径：{shaping_label}的连续几何变化率约 "
            f"{_v['shaping_continuous_delta']:.2f} 针/圈，按六等分针法向上量化为 "
            f"±{_v['max_stitch_change']} 针；较平缓轮廓仍可使用 6 针步长。")
        # 符号条走 markdown 通道（st.html 的净化器剥整个 <svg>，实测 1.60）
        st.markdown(symbol_strip_html(), unsafe_allow_html=True)
        st.markdown(glossary_table_markdown())
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

    return _v
