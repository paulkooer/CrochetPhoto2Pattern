"""Opt-in construction prototype; no changes to automatic photo-part selection."""
from __future__ import annotations

import hashlib
import importlib.util

import streamlit as st

from app.doll_cli import MAX_DESIGN_BYTES, read_design
from app.models.dressed_doll import DollDesign, DollPlan, build_doll_plan, starter_design
from app.models.dressed_doll.planner import STARTER_LABELS
from app.models.gauge import Gauge
from app.ui.result_renderer import md_safe
from app.utils.dressed_doll_export import export_doll_graph, export_doll_markdown, export_doll_pdf


def _design_inputs() -> DollDesign | None:
    source = st.radio("原型方案来源", ["从起始方案调整", "载入设计 JSON"], horizontal=True,
                      key="doll_design_source")
    if source == "载入设计 JSON":
        file = st.file_uploader("穿衣人偶设计 JSON", type=["json"], key="doll_design_upload")
        if file is None:
            return None
        if file.size > MAX_DESIGN_BYTES:
            raise ValueError("设计文件超过 512 KiB 上限")
        design = read_design(file.getvalue())
        st.caption("使用文件中记录的全部尺寸、部件选型与密度；修改后可重新载入。")
        st.json(design.model_dump())
        return design
    profile = st.selectbox("起始结构", list(STARTER_LABELS), format_func=STARTER_LABELS.__getitem__,
                           key="doll_design_starter")
    a, b = st.columns(2)
    with a:
        height = st.number_input("原型目标总高（不含帽子，cm）", 16.0, 60.0, 24.0, 0.5,
                                 key="doll_design_height")
        stitches = st.number_input("原型密度：每 10cm 针数", 6.0, 40.0, 22.0, 0.5,
                                   key="doll_design_stitches")
    with b:
        rows = st.number_input("原型密度：每 10cm 行/圈数", 8.0, 50.0, 28.0, 0.5,
                               key="doll_design_rows")
        layers = st.selectbox("裙层数量", [1, 2], index=1, key="doll_design_layers")
    base = starter_design(profile, height_cm=height, gauge=Gauge(stitches, rows))
    st.caption("这组密度单独用于结构原型，是输入假设；先分别实测片钩、圈钩与肋纹小样。")
    with st.expander("调整关键轮廓与构造"):
        left, right = st.columns(2)
        with left:
            head = st.number_input("原型头径（cm）", 2.0, 20.0, base.head_diameter_cm, 0.1,
                                   key=f"doll_design_head_{profile}")
            palm = st.number_input("手掌目标直径（cm）", 0.4, 6.0, base.palm_diameter_cm, 0.1,
                                   key=f"doll_design_palm_{profile}")
            wrist = st.number_input("手腕目标直径（cm）", 0.3, 4.0, base.wrist_diameter_cm, 0.1,
                                    key=f"doll_design_wrist_{profile}")
            hair = st.selectbox("发束构造", ["curls", "straight"],
                                index=int(base.hair == "straight"),
                                format_func=lambda x: "卷发回钩" if x == "curls" else "直发回钩",
                                key=f"doll_design_hair_{profile}")
        with right:
            foot_length = st.number_input("鞋底目标长度（cm）", 1.0, 10.0, base.foot_length_cm, 0.1,
                                          key=f"doll_design_foot_length_{profile}")
            foot_width = st.number_input("鞋底目标宽度（cm）", 0.5, 8.0, base.foot_width_cm, 0.1,
                                         key=f"doll_design_foot_width_{profile}")
            bodice = st.number_input("上衣片目标长度（cm）", 1.0, 30.0, base.bodice_length_cm, 0.1,
                                     key=f"doll_design_bodice_{profile}")
            hat = st.selectbox("帽子构造", ["wide_brim", "folded_band"],
                               index=int(base.hat == "folded_band"),
                               format_func=lambda x: "帽身＋宽帽檐" if x == "wide_brim" else "帽身＋片钩翻边",
                               key=f"doll_design_hat_{profile}")
            chains = st.number_input("每根长发束起针锁针数", 6, 120, base.hair_chain_count,
                                     key=f"doll_design_hair_chains_{profile}")
    values = base.model_dump() | {
        "head_diameter_cm": head, "palm_diameter_cm": palm, "wrist_diameter_cm": wrist,
        "foot_length_cm": foot_length, "foot_width_cm": foot_width, "hair": hair,
        "hat": hat, "skirt_layers": layers, "hair_chain_count": chains,
        "bodice_length_cm": bodice,
    }
    return DollDesign.model_validate(values)


def render_dressed_doll_designer() -> None:
    with st.expander("穿衣人偶结构原型（新增）"):
        st.caption("目前适用于简化的拼装人偶；复杂衣物构造和立体花纹尚不支持。")
        st.caption("包含发型、帽檐或翻边、掌腕、鞋底鞋面、衣片袖筒、裙层和包袋。"
                   "人工选型与尺寸驱动，尚未验证合身、实际可钩性或照片还原度。")
        try:
            design = _design_inputs()
        except ValueError as exc:
            st.error(f"设计参数需要调整：{md_safe(exc)}")
            design = None
        if st.button("生成穿衣人偶结构原型", key="doll_design_generate", disabled=design is None):
            try:
                assert design is not None
                plan = build_doll_plan(design)
                st.session_state["doll_design_plan"] = plan.model_dump()
                st.session_state.pop("doll_design_pdf", None)
            except ValueError as exc:
                st.error(f"暂不能生成该结构：{md_safe(exc)}")
        stored = st.session_state.get("doll_design_plan")
        if stored is not None:
            _render_plan(DollPlan.model_validate(stored), design)


def _render_plan(plan: DollPlan, design: DollDesign | None) -> None:
    stale = design is None or plan.design != design
    if stale:
        st.info("参数已改变，下方仍是上一份原型；请重新生成后再下载。")
    st.markdown("**结构原型 · 未实钩验证**")
    st.dataframe([{"部件": p.name, "数量": p.quantity,
                   "钩法": "片钩" if p.work == "rows" else "圈钩",
                   "分段": "、".join(dict.fromkeys(s.section for s in p.steps))}
                  for p in plan.components], hide_index=True, width="stretch")
    with st.expander("查看部件连接图"):
        st.caption("显示真实部件与装配去向；不是成品外观或物理仿真。")
        st.graphviz_chart(export_doll_graph(plan))
    markdown = export_doll_markdown(plan)
    st.download_button("下载设计参数 JSON", plan.design.model_dump_json(indent=2),
                       "doll-design.json", "application/json", key="doll_design_download_spec",
                       disabled=stale)
    st.download_button("下载结构方案 JSON", plan.model_dump_json(indent=2),
                       "doll-plan.json", "application/json", key="doll_design_download_plan", disabled=stale)
    st.download_button("下载逐部件说明 Markdown", markdown, "doll-plan.md", "text/markdown",
                       key="doll_design_download_md", disabled=stale)
    if importlib.util.find_spec("reportlab") is not None:
        if st.button("准备结构原型 PDF", key="doll_design_prepare_pdf", disabled=stale):
            try:
                st.session_state["doll_design_pdf"] = {
                    "source": hashlib.sha256(plan.model_dump_json().encode()).hexdigest(),
                    "bytes": export_doll_pdf(plan),
                }
            except (ValueError, ImportError):
                st.error("PDF 暂时未能生成；原型仍已保留，可先下载 Markdown。")
        pdf = st.session_state.get("doll_design_pdf")
        if pdf and pdf["source"] == hashlib.sha256(plan.model_dump_json().encode()).hexdigest():
            st.download_button("下载结构原型 PDF", pdf["bytes"], "doll-plan.pdf", "application/pdf",
                               key="doll_design_download_pdf", disabled=stale)
    with st.expander("阅读逐部件步骤与试合检查点"):
        st.markdown(markdown)
