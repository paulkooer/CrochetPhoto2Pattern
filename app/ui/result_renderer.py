"""Result renderer: analysis / structure / pattern / progress / edit-regenerate.

被照片 Tab 与手动 Tab 复用。widget key 全部以 result_id 为命名空间，
保证两份结果同屏渲染不冲突、重新生成后进度不串档。

章节正文在 result_analysis、result_structure、result_progress、result_assembly。
这里只编排，并继续导出既有入口。
"""
from __future__ import annotations

import streamlit as st

from app.schemas import ResultData
from app.services.workspace import workspace
from app.ui.result_analysis import (
    _confidence_text,
    _ratio_text,
    _silhouette_verifications,
    md_safe,
    render_analysis,
)
from app.ui.result_assembly import render_assembly, render_edits
from app.ui.result_progress import _render_paged_progress, render_pattern
from app.ui.result_structure import render_structure

__all__ = [
    "_confidence_text",
    "_ratio_text",
    "_render_paged_progress",
    "_silhouette_verifications",
    "md_safe",
    "purge_result_state",
    "render_results",
]


def purge_result_state(result: ResultData) -> None:
    """Drop widget state namespaced to a result that is about to be replaced.

    result_id 每次生成都不同，若不清理，逐圈 checkbox 等几十个 key 会在
    session_state 中随使用次数无限累积。控件键把 result_id 作为以 ``_`` 分隔的
    一整段（``chk_<rid>_…``、``sz_head_<rid>``），而 result_id 是随机令牌，所以
    含这一段的键都属于该结果，新控件无需登记前缀。不是控件值的状态在标签页
    工作区里，随结果一起替换。
    """
    rid = result.get("result_id")
    if not rid:
        return
    for key in list(st.session_state.keys()):
        # A whole segment: another result whose ID begins with rid keeps its state.
        if rid in str(key).split("_"):
            del st.session_state[key]



def render_results(result: ResultData, slot: str) -> None:
    """Render the result UI. `slot` is the st.session_state key holding `result`,
    so edits/regeneration write back to the tab that owns this result."""
    # Widget-key namespace: unique per generated result, stable across reruns.
    # Fallback to the stable slot name — id(result) may be reused across reruns.
    from app.ui.edit_history import get_history
    get_history(slot, result)

    st.divider()
    st.markdown(
        "<p class='sheet-note'>下面是这份图解：先核对比例与结构，"
        "再按部件逐圈勾选进度；需要时局部修正，并下载备份。</p>",
        unsafe_allow_html=True,
    )
    if notice := workspace(result, slot, st.session_state)["recovery_notice"]:
        st.warning(notice)
    from app.services.color_identity import require_aligned_copy_colors

    try:
        require_aligned_copy_colors(result)
    except ValueError as exc:
        st.warning(f"逐份配色待修正：{md_safe(exc)}。修正前请保留原备份。")

    render_analysis(result)
    render_structure(result)
    validation = render_pattern(result, slot)
    render_assembly(result, validation)
    render_edits(result, slot, validation)
