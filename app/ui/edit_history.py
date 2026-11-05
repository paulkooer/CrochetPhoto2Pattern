"""Bounded, per-tab undo/redo of patterns and their physical-round progress."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

import streamlit as st

from app.schemas import ResultData
from app.services.progress_state import (
    ambiguous_legacy_progress,
    capture_progress,
    color_only_change,
    install_progress,
    progress_impact,
    reconcile_restored_progress,
    retained_progress,
)
from app.services.workspace import carried_workspace, workspace, workspace_key

MAX_SNAPSHOTS = 12
MAX_HISTORY_BYTES = 8 << 20


def metrics(result: ResultData) -> dict:
    from app.models.gauge import gauge_from_result, part_gauge_text
    from app.models.materials import YarnSpec
    from app.models.stitch_attachments import WAIST_POSITION_KEY

    params = result["params"]
    gauge = gauge_from_result(result)
    yarn = params.get("material_summary") or {}
    raw_spec = params.get("yarn_spec")
    spec = YarnSpec.model_validate(raw_spec).model_dump() if raw_spec is not None else {}
    swatch = "未使用称重试片"
    if spec.get("swatch_weight_g") is not None:
        origin = spec.get("swatch_gauge")
        density = (f"10cm × {origin['stitches_per_10cm']:g} 针 × {origin['rows_per_10cm']:g} 行"
                   if origin else "密度待确认")
        swatch = (f"{spec['swatch_weight_g']:g}g / {spec['swatch_stitches']} 针 × "
                  f"{spec['swatch_rows']} 行；{density}")
    dimensions = []
    for part in result["structure"].get("parts", []):
        values: Mapping[str, Any] = part
        sizes = "、".join(
            f"{label} {values[key]:g}"
            for key, label in (("diameter_cm", "直径"), ("height_cm", "高度"), ("length_cm", "长度"))
            if values.get(key) is not None
        )
        dimensions.append(f"{part['name']} × {part.get('count', 1)}：{sizes}")
    return {
        "总针数": params.get("total_stitches", 0),
        "估算毛线（g）": yarn.get("grams"),
        "估算毛线（m）": yarn.get("meters"),
        "购线团数": yarn.get("balls") if yarn.get("balls") is not None else "未提供线标",
        "预留比例（%）": yarn.get("waste_percent"),
        "线标（每团）": (f"{spec['ball_weight_g']:g}g / {spec['ball_length_m']:g}m"
                         if spec else "未提供线标"),
        "称重试片": swatch,
        "目标高度（cm）": result["analysis"].get("height_cm"),
        "10 cm 针数": gauge.stitches_per_10cm,
        "10 cm 行数": gauge.rows_per_10cm,
        "部件独立密度": "；".join(f"{p['name']}：{part_gauge_text(p, gauge)}" for p in params["parts"]
                                   if p.get("gauge") is not None) or "沿用默认",
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


def get_history(slot: str, result: ResultData, *, create: bool = True) -> dict:
    key = f"edit_history_{slot}"
    identity = result.get("result_id") or slot
    history = st.session_state.get(key)
    if history is None or history["current_id"] != identity:
        history = {"current_id": identity, "undo": [], "redo": [], "comparison": None}
        if create:
            st.session_state[key] = history
    return history


def _install(slot: str, current: ResultData, updated: ResultData, history: dict,
             progress: dict) -> ResultData:
    from app.ui.result_renderer import purge_result_state
    from app.ui.workspace import live_workspace

    updated = deepcopy(updated)
    # Persistence belongs to the live workspace, not an undo/preview snapshot.
    updated.pop("history_id", None)
    if current.get("history_id"):
        updated["history_id"] = current["history_id"]
    updated.pop("title", None)
    if current.get("title") is not None:
        updated["title"] = current["title"]
    updated["result_id"] = uuid.uuid4().hex[:12]
    history["current_id"] = updated["result_id"]
    history["comparison"] = {"修改前": metrics(current), "修改后": metrics(updated)}
    trim_history(history)
    prepared: dict = {}
    install_progress(updated, slot, progress, prepared)
    prepared[workspace_key(slot)] = carried_workspace(
        live_workspace(current, slot, create=False), updated, slot)
    # All copying, metrics and serialization must succeed before session mutation.
    purge_result_state(current)
    st.session_state.update(prepared)
    st.session_state[slot] = updated
    st.session_state[f"edit_history_{slot}"] = history
    return updated


def commit_edit(slot: str, current: ResultData, updated: ResultData) -> ResultData:
    from app.services.color_identity import require_aligned_copy_colors
    from app.utils.project import pattern_revision

    require_aligned_copy_colors(updated)
    if pattern_revision(current) == pattern_revision(updated):
        ws = workspace(current, slot, st.session_state)
        ws["pending_preview"] = None
        ws["notice"] = "设置与当前图解相同，已保留撤销、重做及完成进度。"
        return current
    history = deepcopy(get_history(slot, current, create=False))
    progress = capture_progress(current, slot, st.session_state)
    history["undo"].append({"result": deepcopy(current), "progress": progress,
                            "progress_identity_version": "2"})
    history["redo"].clear()
    history["legacy_ambiguous_count"] = 0
    history["unmapped_progress"] = 0
    history["color_only_notice"] = color_only_change(current, updated)
    retained = retained_progress(current, updated, slot, progress)
    history["cleared_progress"] = len(progress) - len(retained)
    return _install(slot, current, updated, history, retained)


def restore_edit(slot: str, current: ResultData, direction: str) -> ResultData:
    if direction not in ("undo", "redo"):
        raise ValueError("invalid history direction")
    history = deepcopy(get_history(slot, current, create=False))
    if not history[direction]:
        return current
    snapshot = history[direction].pop()
    history["cleared_progress"] = 0
    # In-process sessions may still contain snapshots made before this update.
    updated = snapshot.get("result", snapshot)
    history["color_only_notice"] = color_only_change(current, updated)
    progress = snapshot.get("progress", {})
    ambiguous = (ambiguous_legacy_progress(updated, progress)
                 if snapshot.get("progress_identity_version") != "2" else set())
    history["legacy_ambiguous_count"] = len(ambiguous)
    history["unmapped_progress"] = 0
    progress = {key: value for key, value in progress.items() if key not in ambiguous}
    live_progress = capture_progress(current, slot, st.session_state)
    if snapshot.get("progress_identity_version") == "2":
        progress, history["unmapped_progress"] = reconcile_restored_progress(
            current, updated, live_progress, progress)
    history["redo" if direction == "undo" else "undo"].append({
        "result": deepcopy(current), "progress": live_progress,
        "progress_identity_version": "2",
    })
    return _install(slot, current, updated, history, progress)


def preview_edit(slot: str, current: ResultData, candidate: ResultData,
                 detail: dict | None = None) -> None:
    """An optional review path; apply exactly this candidate against its source.

    ``detail`` lets an editor supply its own impact tables (affected rounds, kept
    stripes, per-colour material use); the preview renders them verbatim so the
    review shows what the editor actually proposes to change.
    """
    from app.services.color_identity import require_aligned_copy_colors
    from app.utils.project import pattern_revision

    require_aligned_copy_colors(candidate)
    live = st.session_state.get(slot)
    if (live is None or live.get("result_id") != current.get("result_id")
            or pattern_revision(live) != pattern_revision(current)):
        st.warning("当前图解已变化，请关闭预览后重新生成修改方案。")
        return
    workspace(current, slot, st.session_state)["pending_preview"] = {
        "source": deepcopy(current), "candidate": deepcopy(candidate),
        "detail": deepcopy(detail) if detail else None}
    st.rerun()


def _render_preview_detail(detail: dict | None) -> None:
    """Editor-supplied impact tables for a pending edit, when one was given."""
    if not detail:
        return
    for caption in detail.get("captions", []):
        st.caption(caption)
    if detail.get("affected"):
        st.caption("受影响的圈次（旧色 → 新色）")
        st.table(detail["affected"])
    if detail.get("kept"):
        st.caption("按「保留已有条纹」保留的圈（已有圈色或逐份配色，不会被覆盖）")
        st.table(detail["kept"])
    if alignment := detail.get("copy_color_alignment"):
        st.caption("按实体 ID 对齐后的逐份颜色")
        st.table(alignment)
    if materials := detail.get("materials"):
        st.caption("逐色材料用量（估算，含预留线尾）")
        st.table(materials)
    for warning in detail.get("warnings", []):
        st.warning(warning)


def render_edit_preview(slot: str, current: ResultData) -> None:
    from app.utils.project import pattern_revision

    ws = workspace(current, slot, st.session_state)
    with st.container(border=ws["pending_preview"] is not None):
        pending = ws["pending_preview"]
        if pending is None:
            return
        st.markdown("**修改影响预览 · 尚未应用**")
        if pattern_revision(current) != pattern_revision(pending["source"]):
            st.warning("当前图解已变化，请重新预览修改。")
            ws["pending_preview"] = None
            return
        candidate = pending["candidate"]
        progress = capture_progress(current, slot, st.session_state)
        st.table(progress_impact(current, candidate, slot, progress))
        pure_color = current != candidate and color_only_change(current, candidate)
        if pure_color:
            # 纯颜色修改保留全部已完成圈次，但实物不会跟着变：这条提示与具体编辑器
            # 无关，选色面板与 JSON 编辑两条路径都必须看到。
            st.warning("本次只改动颜色：进度影响见上表。已钩出的旧颜色不会因为图解"
                       "改色而改变，请按实物决定是否重钩。")
        _render_preview_detail(pending.get("detail"))
        before, after = metrics(current), metrics(candidate)
        changes = [{"项目": name, "修改前": str(before[name]), "修改后": str(after[name])}
                   for name in before if before[name] != after[name]]
        if changes:
            st.table(changes)
        from app.models.crochetability import crochetability_findings
        from app.ui.result_renderer import md_safe

        if concerns := [f for f in crochetability_findings(candidate["params"]) if f.level != "note"]:
            st.warning("应用后的可钩性提示：" + "；".join(md_safe(f.message) for f in concerns) + "。")
        st.caption("此预览记录点击时的修改方案；继续改动输入或勾选后请重新预览。应用时使用最新进度。"
                   "进度按上表处理；各部件有效密度、整体信息或依赖接合变化时需重新核对。"
                   "勾选记录不代表实物无需返工。")
        # Commit before the full render, so old progress fragments cannot leave
        # stale widgets behind when the new pattern changes their layout.
        with st.container(horizontal=True):
            st.button("应用这次修改", key=f"edit_{current.get('result_id') or slot}_preview_apply",
                      on_click=_apply_preview, args=(slot,))
            st.button("取消预览", key=f"edit_{current.get('result_id') or slot}_preview_cancel",
                      on_click=_cancel_preview, args=(slot,))


def _cancel_preview(slot: str) -> None:
    if (live := st.session_state.get(slot)) is not None:
        workspace(live, slot, st.session_state)["pending_preview"] = None


def _apply_preview(slot: str) -> None:
    from app.utils.project import pattern_revision

    live = st.session_state.get(slot)
    if live is None:
        return
    # The workspace belongs to the live result, so a preview made for another result is gone.
    pending = workspace(live, slot, st.session_state)["pending_preview"]
    if (pending is not None
            and live.get("result_id") == pending["source"].get("result_id")
            and pattern_revision(live) == pattern_revision(pending["source"])):
        commit_edit(slot, live, pending["candidate"])


def _restore_before_render(slot: str, direction: str) -> None:
    restore_edit(slot, st.session_state[slot], direction)


def render_history(slot: str, result: ResultData) -> None:
    history = get_history(slot, result)
    render_edit_preview(slot, result)
    rid = result.get("result_id") or slot
    ws = workspace(result, slot, st.session_state)
    if notice := ws["notice"]:
        ws["notice"] = None
        st.info(notice)
    with st.container(horizontal=True):
        st.button("↶ 撤销修改", key=f"edit_{rid}_undo", disabled=not history["undo"],
                  on_click=_restore_before_render, args=(slot, "undo"))
        st.button("↷ 重做修改", key=f"edit_{rid}_redo", disabled=not history["redo"],
                  on_click=_restore_before_render, args=(slot, "redo"))
    st.caption("保留本会话最近的修改（最多 12 份、合计 8 MB）；重新导入或生成会开启新的记录。")
    st.caption("材料估算修改保留进度；逐圈修改保留首次变化前的圈次，有效密度或整体变化的部件重新核对。"
               "依赖接合件同时重新核对。撤销或重做时，未受影响的圈保留最新勾选，"
               "受影响的圈恢复对应快照。")
    progress_notice = st.empty()
    if history.get("cleared_progress"):
        progress_notice.warning(f"本次修改清除了 {history['cleared_progress']} 个受影响的已完成圈次；"
                                "其他部件进度及个人备注已保留，可撤销恢复。")
    if count := history.get("legacy_ambiguous_count"):
        st.warning(f"旧撤销记录中有 {count} 个完成圈次无法区分属于哪份实体，已暂不标记；"
                   "请按实物核对后重新勾选。")
    if count := history.get("unmapped_progress"):
        st.warning(f"有 {count} 个当前完成圈次涉及施工变化，已恢复目标图解的进度快照；"
                   "请按实物核对。")
    if history.get("color_only_notice"):
        st.warning("已钩出的旧颜色不会因为图解改色而改变，请按实物决定是否重钩。")
    with st.expander("最近一次修改前后对比"):
        if history["comparison"]:
            before, after = history["comparison"]["修改前"], history["comparison"]["修改后"]
            st.table([{"项目": key, "修改前": str(before[key]), "修改后": str(after[key])} for key in before])
