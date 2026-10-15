"""Bounded, per-tab undo/redo of patterns and their physical-round progress."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy

import streamlit as st

from app.ui.progress_state import capture_progress, install_progress, retained_progress

MAX_SNAPSHOTS = 12
MAX_HISTORY_BYTES = 8 << 20


def metrics(result: dict) -> dict:
    params = result["params"]
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
        "部件尺寸（cm）": "；".join(dimensions),
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
    updated["result_id"] = uuid.uuid4().hex[:12]
    history["current_id"] = updated["result_id"]
    history["comparison"] = {"修改前": metrics(current), "修改后": metrics(updated)}
    trim_history(history)
    prepared_progress: dict = {}
    install_progress(updated, slot, progress, prepared_progress)
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
    return _install(slot, current, updated, history, retained_progress(current, updated, slot, progress))


def restore_edit(slot: str, current: dict, direction: str) -> dict:
    if direction not in ("undo", "redo"):
        raise ValueError("invalid history direction")
    history = deepcopy(get_history(slot, current, create=False))
    if not history[direction]:
        return current
    snapshot = history[direction].pop()
    # In-process sessions may still contain snapshots made before this update.
    updated = snapshot.get("result", snapshot)
    history["redo" if direction == "undo" else "undo"].append({
        "result": deepcopy(current), "progress": capture_progress(current, slot, st.session_state),
    })
    return _install(slot, current, updated, history, snapshot.get("progress", {}))


def render_history(slot: str, result: dict) -> None:
    history = get_history(slot, result)
    rid = result.get("result_id") or slot
    left, right = st.columns(2)
    if left.button("↶ 撤销修改", key=f"edit_{rid}_undo", disabled=not history["undo"]):
        restore_edit(slot, result, "undo")
        st.rerun()
    if right.button("↷ 重做修改", key=f"edit_{rid}_redo", disabled=not history["redo"]):
        restore_edit(slot, result, "redo")
        st.rerun()
    st.caption("保留本会话最近的修改（最多 12 份、合计 8 MB）；重新导入或生成会开启新的记录。")
    st.caption("材料修改保留进度；图解变化只清除受影响部件的进度，密度变化清除全部进度。撤销可恢复。")
    with st.expander("最近一次修改前后对比"):
        if history["comparison"]:
            before, after = history["comparison"]["修改前"], history["comparison"]["修改后"]
            st.table([{"项目": key, "修改前": str(before[key]), "修改后": str(after[key])} for key in before])
