"""Bounded, per-tab undo/redo of patterns and their physical-round progress."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy

import streamlit as st

from app.ui.progress_state import capture_progress, install_progress, progress_impact, retained_progress

MAX_SNAPSHOTS = 12
MAX_HISTORY_BYTES = 8 << 20


def metrics(result: dict) -> dict:
    from app.models.gauge import gauge_from_result
    from app.models.stitch_attachments import WAIST_POSITION_KEY

    params = result["params"]
    gauge = gauge_from_result(result)
    yarn = params.get("material_summary") or {}
    dimensions = []
    for part in result["structure"].get("parts", []):
        sizes = "、".join(
            f"{label} {part[key]:g}"
            for key, label in (("diameter_cm", "直径"), ("height_cm", "高度"), ("length_cm", "长度"))
            if part.get(key) is not None
        )
        dimensions.append(f"{part['name']} × {part.get('count', 1)}：{sizes}")
    return {
        "总针数": params.get("total_stitches", 0),
        "估算毛线（g）": yarn.get("grams"),
        "目标高度（cm）": result["analysis"].get("height_cm"),
        "10 cm 针数": gauge.stitches_per_10cm,
        "10 cm 行数": gauge.rows_per_10cm,
        "部件尺寸（cm）": "；".join(dimensions),
        "接裙腰位策略": (f"固定候选圈序位置 {params[WAIST_POSITION_KEY]:.1%}"
                         if WAIST_POSITION_KEY in params else "自动定位"),
    }


def trim_history(history: dict) -> None:
    """Evict oldest snapshots, accounting for both directions together."""
    while len(history["undo"]) + len(history["redo"]) > MAX_SNAPSHOTS:
        (history["undo"] or history["redo"]).pop(0)
    while (history["undo"] or history["redo"]) and len(
        json.dumps([history["undo"], history["redo"]], ensure_ascii=False).encode()
    ) > MAX_HISTORY_BYTES:
        (history["undo"] or history["redo"]).pop(0)


def get_history(slot: str, result: dict, *, create: bool = True) -> dict:
    key = f"edit_history_{slot}"
    identity = result.get("result_id") or slot
    history = st.session_state.get(key)
    if history is None or history["current_id"] != identity:
        history = {"current_id": identity, "undo": [], "redo": [], "comparison": None}
        if create:
            st.session_state[key] = history
    return history


def _install(slot: str, current: dict, updated: dict, history: dict, progress: dict) -> dict:
    from app.ui.result_renderer import purge_result_state

    updated = deepcopy(updated)
    # Persistence belongs to the live workspace, not an undo/preview snapshot.
    updated.pop("history_id", None)
    if current.get("history_id"):
        updated["history_id"] = current["history_id"]
    updated["result_id"] = uuid.uuid4().hex[:12]
    history["current_id"] = updated["result_id"]
    history["comparison"] = {"修改前": metrics(current), "修改后": metrics(updated)}
    trim_history(history)
    prepared_progress: dict = {}
    install_progress(updated, slot, progress, prepared_progress)
    old_rid = current.get("result_id") or slot
    prepared_progress[f"project_notes_{updated['result_id']}"] = st.session_state.get(
        f"project_notes_{old_rid}", "")
    # All copying, metrics and serialization must succeed before session mutation.
    purge_result_state(current)
    st.session_state.update(prepared_progress)
    st.session_state[slot] = updated
    st.session_state[f"edit_history_{slot}"] = history
    return updated


def commit_edit(slot: str, current: dict, updated: dict) -> dict:
    history = deepcopy(get_history(slot, current, create=False))
    progress = capture_progress(current, slot, st.session_state)
    history["undo"].append({"result": deepcopy(current), "progress": progress})
    history["redo"].clear()
    retained = retained_progress(current, updated, slot, progress)
    history["cleared_progress"] = len(progress) - len(retained)
    return _install(slot, current, updated, history, retained)


def restore_edit(slot: str, current: dict, direction: str) -> dict:
    if direction not in ("undo", "redo"):
        raise ValueError("invalid history direction")
    history = deepcopy(get_history(slot, current, create=False))
    if not history[direction]:
        return current
    snapshot = history[direction].pop()
    history["cleared_progress"] = 0
    # In-process sessions may still contain snapshots made before this update.
    updated = snapshot.get("result", snapshot)
    history["redo" if direction == "undo" else "undo"].append({
        "result": deepcopy(current), "progress": capture_progress(current, slot, st.session_state),
    })
    return _install(slot, current, updated, history, snapshot.get("progress", {}))


def preview_edit(slot: str, current: dict, candidate: dict) -> None:
    """An optional review path; apply exactly this candidate against its source."""
    from app.utils.project import pattern_revision

    live = st.session_state.get(slot)
    if (live is None or live.get("result_id") != current.get("result_id")
            or pattern_revision(live) != pattern_revision(current)):
        st.warning("当前图解已变化，请关闭预览后重新生成修改方案。")
        return
    key = f"edit_{current.get('result_id') or slot}_pending_preview"
    st.session_state[key] = {"source": deepcopy(current), "candidate": deepcopy(candidate)}
    st.rerun()


def render_edit_preview(slot: str, current: dict) -> None:
    from app.utils.project import pattern_revision

    key = f"edit_{current.get('result_id') or slot}_pending_preview"
    with st.container(border=key in st.session_state):
        pending = st.session_state.get(key)
        if pending is None:
            return
        st.markdown("**修改影响预览 · 尚未应用**")
        if pattern_revision(current) != pattern_revision(pending["source"]):
            st.warning("当前图解已变化，请重新预览修改。")
            st.session_state.pop(key, None)
            return
        candidate = pending["candidate"]
        progress = capture_progress(current, slot, st.session_state)
        st.table(progress_impact(current, candidate, slot, progress))
        before, after = metrics(current), metrics(candidate)
        changes = [{"项目": name, "修改前": str(before[name]), "修改后": str(after[name])}
                   for name in before if before[name] != after[name]]
        if changes:
            st.table(changes)
        st.caption("此预览记录点击时的修改方案；继续改动输入或勾选后请重新预览。应用时使用最新进度。"
                   "只保留首次变化之前的圈次；密度、部件整体信息或依赖接合变化时重新核对。"
                   "勾选记录不代表实物无需返工。")
        # Commit before the full render, so old progress fragments cannot leave
        # stale widgets behind when the new pattern changes their layout.
        apply, cancel = st.columns(2)
        apply.button("应用这次修改", key=f"edit_{current.get('result_id') or slot}_preview_apply",
                     on_click=_apply_preview, args=(slot, key))
        cancel.button("取消预览", key=f"edit_{current.get('result_id') or slot}_preview_cancel",
                      on_click=_cancel_preview, args=(key,))


def _cancel_preview(key: str) -> None:
    st.session_state.pop(key, None)


def _apply_preview(slot: str, key: str) -> None:
    from app.utils.project import pattern_revision

    pending = st.session_state.get(key)
    live = st.session_state.get(slot)
    if (pending is not None and live is not None
            and live.get("result_id") == pending["source"].get("result_id")
            and pattern_revision(live) == pattern_revision(pending["source"])):
        commit_edit(slot, live, pending["candidate"])


def _restore_before_render(slot: str, direction: str) -> None:
    restore_edit(slot, st.session_state[slot], direction)


def render_history(slot: str, result: dict) -> None:
    history = get_history(slot, result)
    render_edit_preview(slot, result)
    rid = result.get("result_id") or slot
    left, right = st.columns(2)
    left.button("↶ 撤销修改", key=f"edit_{rid}_undo", disabled=not history["undo"],
                on_click=_restore_before_render, args=(slot, "undo"))
    right.button("↷ 重做修改", key=f"edit_{rid}_redo", disabled=not history["redo"],
                 on_click=_restore_before_render, args=(slot, "redo"))
    st.caption("保留本会话最近的修改（最多 12 份、合计 8 MB）；重新导入或生成会开启新的记录。")
    st.caption("材料估算修改保留进度；逐圈修改保留首次变化前的圈次，密度或部件整体变化重新核对整件。"
               "依赖接合件同时重新核对；撤销可恢复。")
    progress_notice = st.empty()
    if history.get("cleared_progress"):
        progress_notice.warning(f"本次修改清除了 {history['cleared_progress']} 个受影响的已完成圈次；"
                                "其他部件进度及个人备注已保留，可撤销恢复。")
    with st.expander("最近一次修改前后对比"):
        if history["comparison"]:
            before, after = history["comparison"]["修改前"], history["comparison"]["修改后"]
            st.table([{"项目": key, "修改前": str(before[key]), "修改后": str(after[key])} for key in before])
