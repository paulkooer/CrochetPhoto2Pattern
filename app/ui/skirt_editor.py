"""Preview and move a declared waist join using actual pattern row numbers."""
import streamlit as st

from app.models.attachment_diagram import attachment_svg
from app.models.skirt_edit import move_skirt_join, skirt_connection, unpin_skirt_waist, waist_rows
from app.models.stitch_attachments import WAIST_POSITION_KEY
from app.ui.edit_history import preview_edit


def render_skirt_editor(result: dict, slot: str) -> None:
    from app.ui.result_renderer import md_safe

    params = result["params"]
    if params.get("skirt_style") != "attached":
        return
    rid = result.get("result_id") or slot
    with st.expander("🪡 接裙位置图示与调整"):
        try:
            connection = skirt_connection(params)
            st.markdown(attachment_svg(connection), unsafe_allow_html=True)
            st.download_button("下载接裙示意图 SVG", attachment_svg(connection),
                               file_name="skirt-join.svg", mime="image/svg+xml",
                               key=f"edit_{rid}_waist_svg")
            if WAIST_POSITION_KEY in params:
                st.caption(f"已固定腰位：候选圈序的 {params[WAIST_POSITION_KEY]:.1%}。"
                           "尺寸或部件重生成时会按此比例选择新圈号；这是圈序位置，不是实测腰高。")
                if st.button("预览取消腰位固定", key=f"edit_{rid}_waist_unpin"):
                    preview_edit(slot, result, unpin_skirt_waist(result))
                st.caption("取消固定只改变下次重生成的定位方式，当前针法与进度保持不变。")
            else:
                st.caption("当前为自动腰位；选择新腰位并应用后，将随工程保存相对位置。")
            rows = waist_rows(params)
            row_numbers = [r["row"] for r in rows]
            if connection["target_row"] not in row_numbers:
                st.info("当前基底圈不在可自动调整的身体范围内，请先核对身体段与接合记录。")
                return
            if WAIST_POSITION_KEY not in params and st.button(
                    "预览固定当前腰位", key=f"edit_{rid}_waist_pin"):
                preview_edit(slot, result, move_skirt_join(result, connection["target_row"]))
            labels = {r["row"]: f"第 {r['row']} 圈 · {r['stitches']} 针" for r in rows}
            selected = st.selectbox("接裙基底圈", row_numbers,
                                    index=row_numbers.index(connection["target_row"]),
                                    format_func=lambda row: labels[row], key=f"edit_{rid}_waist")
            st.caption("圈号沿用当前图解；头身一体从颈部后的身体段选择。"
                       "移动腰位会还原原预留圈并设置新预留圈；不同针数时重算生成的裙腰与过渡圈。"
                       "手改针法无法安全重算时会提示，实际腰位仍需试钩确认。")
            if selected != connection["target_row"]:
                candidate = move_skirt_join(result, selected)
                st.caption("拟调整后的接合关系（尚未应用）")
                st.markdown(attachment_svg(skirt_connection(candidate["params"])), unsafe_allow_html=True)
                if st.button("预览腰位修改影响", key=f"edit_{rid}_waist_preview"):
                    preview_edit(slot, result, candidate)
        except ValueError as exc:
            st.info(md_safe(exc))
