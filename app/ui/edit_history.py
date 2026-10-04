"""Bounded, per-tab undo/redo. Snapshots contain pattern data only."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy

import streamlit as st

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


def get_history(slot: str, result: dict) -> dict:
    key = f"edit_history_{slot}"
    identity = result.get("result_id") or slot
    history = st.session_state.get(key)
    if history is None or history["current_id"] != identity:
        history = {"current_id": identity, "undo": [], "redo": [], "comparison": None}
        st.session_state[key] = history
    return history


def _install(slot: str, current: dict, updated: dict, history: dict) -> dict:
    from app.ui.result_renderer import purge_result_state

    updated = deepcopy(updated)
    updated["result_id"] = uuid.uuid4().hex[:12]
    purge_result_state(current)
    st.session_state[slot] = updated
    history["current_id"] = updated["result_id"]
    history["comparison"] = {"修改前": metrics(current), "修改后": metrics(updated)}
    trim_history(history)
    return updated


def commit_edit(slot: str, current: dict, updated: dict) -> dict:
    history = get_history(slot, current)
    history["undo"].append(deepcopy(current))
    history["redo"].clear()
    return _install(slot, current, updated, history)


def restore_edit(slot: str, current: dict, direction: str) -> dict:
    if direction not in ("undo", "redo"):
        raise ValueError("invalid history direction")
    history = get_history(slot, current)
    if not history[direction]:
        return current
    updated = history[direction].pop()
    history["redo" if direction == "undo" else "undo"].append(deepcopy(current))
    return _install(slot, current, updated, history)


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
    with st.expander("最近一次修改前后对比"):
        if history["comparison"]:
            before, after = history["comparison"]["修改前"], history["comparison"]["修改后"]
            st.table([{"项目": key, "修改前": str(before[key]), "修改后": str(after[key])} for key in before])
