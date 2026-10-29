"""Manual bridge planning, deliberately separate from generated pattern state."""
import hashlib
import json
from typing import cast

import streamlit as st

from app.models.leg_join import (
    MAX_LEG_JOIN_PLAN_BYTES,
    compare_leg_join,
    decode_leg_join_plan,
    leg_join_advisories,
    leg_join_plan,
)
from app.models.leg_join_diagram import leg_join_svg
from app.schemas import MAX_ROUND_STITCHES

_FIELDS = (("left_row", "左腿开口圈号"), ("left_stitches", "左腿开口针数"),
           ("left_marker", "左腿记号针"), ("right_row", "右腿开口圈号"),
           ("right_stitches", "右腿开口针数"), ("right_marker", "右腿记号针"),
           ("chain", "连接锁针数"))


def _source_bytes(prefix: str) -> bytes:
    if st.session_state[prefix + "source"] == "上传 JSON 文件":
        uploaded = st.session_state.get(prefix + "upload")
        if uploaded is None:
            raise ValueError("请先选择并腿方案文件")
        uploaded.seek(0)
        return uploaded.read(MAX_LEG_JOIN_PLAN_BYTES + 1)
    return st.session_state.get(prefix + "paste", "").encode("utf-8")


def _form_values(prefix: str) -> dict:
    return {field: st.session_state.get(prefix + field) for field, _ in _FIELDS}


def _plan_values(plan: dict) -> dict:
    return {**{f"{side}_{field}": plan[side][field] for side in ("left", "right")
               for field in ("row", "stitches", "marker")}, "chain": plan["chain_stitches"]}


def _preview_restore(slot: str) -> None:
    prefix = f"leg_join_{slot}_"
    st.session_state.pop(prefix + "pending", None)
    try:
        raw = _source_bytes(prefix)
        plan = decode_leg_join_plan(raw)
    except ValueError as exc:
        st.session_state[prefix + "notice"] = (False, str(exc))
        return
    st.session_state[prefix + "pending"] = {
        "plan": plan, "source_mode": st.session_state[prefix + "source"],
        "source_hash": hashlib.sha256(raw).hexdigest(), "before": _form_values(prefix),
    }


def _cancel_restore(slot: str) -> None:
    st.session_state.pop(f"leg_join_{slot}_pending", None)


def _apply_restore(slot: str) -> None:
    prefix = f"leg_join_{slot}_"
    pending = st.session_state.pop(prefix + "pending", None)
    try:
        if (pending is None or st.session_state.get(prefix + "source") != pending["source_mode"]
                or _form_values(prefix) != pending["before"]
                or hashlib.sha256(_source_bytes(prefix)).hexdigest() != pending["source_hash"]):
            raise ValueError("方案文件或当前输入已变化，请重新预览；当前输入已保留。")
    except ValueError as exc:
        st.session_state[prefix + "notice"] = (False, str(exc))
        return
    plan = pending["plan"]
    for side in ("left", "right"):
        for field in ("row", "stitches", "marker"):
            st.session_state[prefix + side + "_" + field] = plan[side][field]
    st.session_state[prefix + "chain"] = plan["chain_stitches"]
    st.session_state[prefix + "notice"] = (True, "方案已恢复；请核对实际开口与连接方向。")


def render_leg_join(slot: str, result: dict | None = None) -> None:
    with st.expander("🧮 锁针并腿方案（手动核对）", expanded=False):
        st.caption("用于两条已留有开口的腿：分别钩完两个开口的每一针，"
                   "连接锁针的两侧各钩一短针。本工具只计算这一种做法。")
        st.warning("填写实际开口圈和记号位置；须人工确认起点、方向、锁针两侧及开口未封闭。"
                   "本方案不会修改当前图解、进度或导出，不检查实物是否适合连接。")
        prefix = f"leg_join_{slot}_"
        with st.container(border=True):
            st.markdown("**恢复已下载的并腿方案**")
            mode = st.radio("恢复方式", ("上传 JSON 文件", "粘贴 JSON"), horizontal=True,
                            key=prefix + "source")
            if mode == "上传 JSON 文件":
                st.file_uploader("选择并腿方案 JSON", type=["json"], key=prefix + "upload")
            else:
                st.text_area("粘贴并腿方案 JSON", key=prefix + "paste", height=120,
                             max_chars=MAX_LEG_JOIN_PLAN_BYTES)
            st.caption("限 16 KiB。先预览输入变化，应用后替换下方输入；图解和进度不变。")
            st.button("预览恢复并腿方案", key=prefix + "restore", on_click=_preview_restore, args=(slot,))
            notice = st.session_state.pop(prefix + "notice", None)
            if notice:
                (st.success if notice[0] else st.error)(notice[1])
            pending = st.session_state.get(prefix + "pending")
            preview = st.empty()
            if pending is not None:
                with preview.container():
                    proposed = _plan_values(pending["plan"])
                    st.markdown("**恢复预览 · 尚未应用**")
                    st.table([{"项目": label, "当前输入": pending["before"][field]
                               if pending["before"][field] is not None else "未填",
                               "恢复后": proposed[field]} for field, label in _FIELDS])
                    st.caption(f"恢复后的连接圈为 {pending['plan']['result_stitches']} 针。"
                               "预览后如修改文件或当前输入，请重新预览。")
                    apply, cancel = st.columns(2)
                    apply.button("应用恢复方案", key=prefix + "restore_apply",
                                 on_click=_apply_restore, args=(slot,))
                    cancel.button("取消恢复预览", key=prefix + "restore_cancel",
                                  on_click=_cancel_restore, args=(slot,))
        left, right = st.columns(2)
        values = {}
        for col, side, label in ((left, "left", "左腿"), (right, "right", "右腿")):
            for field, desc in (("row", "开口圈号"), ("stitches", "开口针数"),
                                ("marker", "记号针序号")):
                values[f"{side}_{field}"] = col.number_input(
                    f"{label}{desc}", min_value=1, max_value=MAX_ROUND_STITCHES,
                    value=None, step=1, key=f"leg_join_{slot}_{side}_{field}")
        values["chain"] = st.number_input(
            "连接锁针数", min_value=1, max_value=MAX_ROUND_STITCHES, value=None, step=1,
            key=f"leg_join_{slot}_chain")
        # Replace the whole output when an inline edit reruns with empty inputs.
        # Otherwise old comparison widgets can survive inside the expander.
        output = st.empty()
        if any(value is None for value in values.values()):
            output.caption("填完全部项目后显示方案；记号针按各自开口圈的针序编号。")
            return
        try:
            plan = leg_join_plan(**cast(dict[str, int], values))
        except ValueError as exc:
            output.error(str(exc))
            return
        with output.container():
            _render_plan(plan, prefix, result)


def _render_plan(plan: dict, prefix: str, result: dict | None) -> None:
    st.info(f"身体连接圈：{plan['left']['stitches']} + {plan['right']['stitches']} + "
            f"2 × {plan['chain_stitches']} = {plan['result_stitches']} 针。"
            "锁针的两侧各计一次，不把锁针本身另外算作成品针。")
    st.caption("请另行确定记号与钩织方向，核对左右腿朝向和首尾连接；"
               "若有加减针、跳针或其他接法，此计算不适用。")
    svg = leg_join_svg(plan)
    st.markdown(svg, unsafe_allow_html=True)
    st.download_button("下载并腿数量示意图 SVG", svg, file_name="leg-join-counts.svg",
                       mime="image/svg+xml", key=prefix + "diagram")
    if result is not None and st.checkbox("与当前图解核对圈号和针数", key=prefix + "compare"):
        parts = result.get("params", {}).get("parts", [])
        indices = {p["name"]: index for index, p in enumerate(parts)}
        options = list(indices)
        signature = hashlib.sha256(json.dumps(
            [(p["name"], p.get("quantity", 1)) for p in parts], ensure_ascii=False
        ).encode("utf-8")).hexdigest()[:16]
        labels = {p["name"]: f"{p['name']}（{p.get('quantity', 1)} 份）" for p in parts}
        st.caption("分别选择左右腿对应的图解部件；同一部件用于两腿时须有至少两份实体。")
        left_col, right_col = st.columns(2)

        def part_label(part_name):
            return labels[part_name]

        def select_part(column, side, label):
            remembered = st.session_state.get(prefix + side + "_selection")
            if remembered is not None and remembered not in indices:
                st.warning(f"{label}之前选择的部件已不存在，请重新选择。")
                remembered = None
            selected = column.selectbox(
                f"{label}对应部件", options,
                index=options.index(remembered) if remembered is not None else None,
                format_func=part_label,
                key=prefix + side + "_part_" + signature,
            )
            st.session_state[prefix + side + "_selection"] = selected
            return selected

        left_name = select_part(left_col, "left", "左腿")
        right_name = select_part(right_col, "right", "右腿")
        if left_name is not None and right_name is not None:
            left_index, right_index = indices[left_name], indices[right_name]
            rows, issues = compare_leg_join(plan, parts, left_index, right_index)
            st.table(rows)
            if issues:
                st.warning("；".join(issues))
            else:
                st.info("所选部件的圈号、针数和实体数量均符合所填方案；接合条件仍需核对。")
            for advisory in leg_join_advisories(plan, parts, left_index, right_index):
                st.warning(advisory)
            st.caption("仅核对图解记录，不确认开口是否留空、记号位置、实际方向或实物是否适合接合。"
                       "修改或更换图解后请重新核对；选择不会写入方案文件。")
    st.download_button("下载并腿方案 JSON", json.dumps(plan, ensure_ascii=False, indent=2),
                       file_name="leg-join-plan.json", mime="application/json", key=prefix + "download")
    st.caption("方案可在上方恢复，不能作为图解或工程文件导入。")
