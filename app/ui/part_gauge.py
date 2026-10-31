"""Independent swatches for hats and separate skirt tubes."""
import streamlit as st

from app.models.gauge import (
    INDEPENDENT_GAUGE_PARTS,
    Gauge,
    gauge_for_part,
    gauge_from_result,
)
from app.ui.edit_history import preview_edit
from app.ui.result_logic import regenerate_with_part_gauge


def render_part_gauge(result: dict, slot: str) -> None:
    parts = [p for p in result["params"]["parts"] if p["name"] in INDEPENDENT_GAUGE_PARTS
             and not (p["name"] == "裙子" and result["params"].get("skirt_style") == "attached")]
    if not parts:
        return
    rid = result.get("result_id") or slot
    with st.expander("🧵 帽子与独立裙筒密度", expanded=False):
        default = gauge_from_result(result)
        index = st.selectbox("选择独立密度部件", range(len(parts)),
                             format_func=lambda i:parts[i]["name"], key=f"edit_{rid}_gauge_part")
        part = parts[index]
        if part["name"] == "裙子" and result["params"].get("skirt_style") == "attached":
            st.caption("挑针接裙沿用身体密度；独立裙筒才可单独设置小样。")
            return
        try:
            selected = gauge_for_part(part, default)
        except ValueError:
            st.info("该部件密度无效，请先修正图解数据。")
            return
        prefix = f"edit_{rid}_partgauge{index}"
        st.caption(f"默认密度：10cm × {default.stitches_per_10cm:g} 针 × {default.rows_per_10cm:g} 行。"
                   "本设置重算所选部件，其他部件按各自密度和构造保留。")
        enabled = st.checkbox("使用独立小样密度", value=part.get("gauge") is not None,
                              key=prefix + "_enabled")
        stitches = st.number_input("本部件 10cm 针数", 6.0, 40.0, selected.stitches_per_10cm, .5,
                                   disabled=not enabled, key=prefix + "_stitches")
        rows = st.number_input("本部件 10cm 行数", 8.0, 50.0, selected.rows_per_10cm, .5,
                               disabled=not enabled, key=prefix + "_rows")
        st.caption("取消勾选可恢复沿用默认密度。有效密度不变时保留现有手改针法；"
                   "实际变化会重算本部件，请预览圈序和进度。默认试片克重仅用于有效密度等于默认值的部件，"
                   "其他密度的用量仍按经验估算。")
        if st.button("预览部件密度修改", key=prefix + "_preview"):
            from app.ui.result_renderer import md_safe

            try:
                candidate = regenerate_with_part_gauge(result, part["name"],
                                                       Gauge(stitches, rows) if enabled else None)
                preview_edit(slot, result, candidate)
            except Exception as exc:
                st.error(f"部件密度修改失败：{md_safe(exc)}")
