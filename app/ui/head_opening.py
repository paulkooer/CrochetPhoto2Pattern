"""Review exact neck stitches before replacing a separate head construction."""
import streamlit as st

from app.models.head_opening import HEAD_OPENING_KEY, has_declared_head_opening, head_opening_target
from app.ui.edit_history import preview_edit
from app.ui.result_logic import regenerate_with_head_opening
from app.utils.counts import integer_count


def render_head_opening(result: dict, slot: str) -> None:
    parts = result["params"]["parts"]
    head = next((p for p in parts if p["name"] == "头部"), None)
    if head is None:
        return
    rid = result.get("result_id") or slot
    with st.expander("🪡 独立头部留口", expanded=False):
        try:
            maximum = max(integer_count(row["stitches"]) for row in head["rounds"])
            raw = result["params"].get(HEAD_OPENING_KEY)
            saved = head_opening_target(raw) if raw is not None else None
            if saved is not None and saved > maximum:
                raise ValueError("留口针数大于头围")
        except (ValueError, TypeError, KeyError):
            st.info("头部针数或留口设置无效，请先核对逐圈数据。")
            return
        if maximum < 6:
            st.caption("头部留口生成需要最大围不少于 6 针，请先调整尺寸或逐圈图解。")
            return
        manual_open = saved is None and has_declared_head_opening(head)
        st.caption(f"当前头部末圈：第 {head['rounds'][-1]['row']} 圈，"
                   f"{head['rounds'][-1]['stitches']} 针；最大围 {maximum} 针。")
        enabled = st.checkbox("保留颈部开口", value=saved is not None or manual_open,
                              key=f"edit_{rid}_head_open")
        initial = saved or (max(6, integer_count(head["rounds"][-1]["stitches"]))
                            if manual_open else min(16, maximum))
        target = st.number_input("颈部开口针数", min_value=6, max_value=maximum,
                                 value=initial, step=1,
                                 disabled=not enabled, key=f"edit_{rid}_head_open_stitches")
        st.caption("按当前尺寸和密度重算头部，保留冠部后在收针段结束；可指定 16 等非六倍数针数。"
                   "这会替换头部手改针法；关闭选项恢复闭合模板。请先预览圈序、进度和装配影响。"
                   "本选项适用于分件头部；开口大小、缝合分配与支撑仍需试钩核对。")
        if st.button("预览头部留口修改", key=f"edit_{rid}_head_open_preview"):
            from app.ui.result_renderer import md_safe

            try:
                preview_edit(slot, result, regenerate_with_head_opening(result, target if enabled else None))
            except Exception as exc:
                st.error(f"留口修改失败：{md_safe(exc)}")
