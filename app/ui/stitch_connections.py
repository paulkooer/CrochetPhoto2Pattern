"""Opt-in inspection of one adjacent-round connection window."""
import json
import math

import streamlit as st

from app.models.stitch_connection_diagram import connection_svg
from app.models.stitch_connections import CONNECTION_PAGE_SIZE, round_connections
from app.ui.design_system import html_box
from app.utils.project import pattern_revision


def _span(numbers: tuple[int, ...]) -> str:
    return str(numbers[0]) if len(numbers) == 1 else f"{numbers[0]}–{numbers[-1]}"


def render_stitch_connections(result: dict, slot: str) -> None:
    rid = result.get("result_id") or slot
    prefix = f"edit_{rid}_connections_"
    with st.expander("🔗 逐针连接核对", expanded=False):
        st.caption("查看本圈每个操作使用上一圈的哪些针目。仅展开明确的完整操作式，"
                   "不按总针数推测排针，也不表示实物形状或线股路径。")
        enabled = st.checkbox("显示逐针连接", key=prefix + "enabled")
        content = st.empty()
        if not enabled:
            return
        with content.container():
            _render_window(result, prefix)


def _render_window(result: dict, prefix: str) -> None:
    from app.ui.result_renderer import md_safe

    parts = result.get("params", {}).get("parts", [])
    if not parts:
        st.info("当前图解没有可查看的部件。")
        return
    index = st.selectbox("连接图部件", range(len(parts)),
                         format_func=lambda i: parts[i]["name"], key=prefix + "part")
    part = parts[index]
    rounds = part.get("rounds", [])
    if not rounds:
        st.info("所选部件没有圈记录。")
        return
    row_index = st.selectbox(
        "连接图圈次", range(len(rounds)), index=min(1, len(rounds) - 1),
        format_func=lambda i: f"第 {rounds[i].get('row', i + 1)} 圈",
        key=prefix + f"part{index}_row",
    )
    try:
        view = round_connections(part, row_index)
        pages = math.ceil(view.operation_count / CONNECTION_PAGE_SIZE)
        page = st.number_input("连接图页码", 1, pages, 1, 1,
                               key=prefix + f"part{index}_row{row_index}_page")
        if page > 1:
            view = round_connections(part, row_index, start=(page - 1) * CONNECTION_PAGE_SIZE)
    except ValueError as exc:
        st.info(md_safe(exc))
        return
    st.code(view.formula, language=None)
    first, last = view.operations[0].index, view.operations[-1].index
    st.caption(f"第 {page}/{pages} 页：操作 {first}–{last} / {view.operation_count}。"
               "每页最多 24 个操作；针序为各圈内的 1 起始编号，多份部件分别使用同一圈序。")
    svg = connection_svg(view)
    st.markdown(html_box(svg, 340, scroll=True), unsafe_allow_html=True)
    st.dataframe([
        {"操作序号": op.index, "针法": op.symbol, "来源圈针序": _span(op.sources),
         "本圈针序": _span(op.targets),
         "挑针": {"both": "双半针", "FLO": "前半针", "BLO": "后半针"}[op.loop]}
        for op in view.operations
    ], hide_index=True)
    st.caption("只核对所示操作式的针目关联；附加说明、实物起点、朝向及跨部件接合"
               "仍需人工核对。未运行张力仿真，也不代表成品已验证。")
    st.download_button("下载本页连接图 SVG", svg, file_name="stitch-connections.svg",
                       mime="image/svg+xml", key=prefix + "svg")
    payload = {**view.to_dict(), "pattern_revision": pattern_revision(result)}
    st.download_button("下载本页连接记录 JSON", json.dumps(payload, ensure_ascii=False, indent=2),
                       file_name="stitch-connections.json", mime="application/json",
                       key=prefix + "json")
    st.caption("下载只包含当前窗口，JSON 标明是否覆盖全圈；此记录不能作为图解或工程导入。")
