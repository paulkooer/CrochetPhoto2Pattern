"""生成前针数预览：确认生成之前展示各部件最宽一圈和可钩性提示。"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import streamlit as st

from app.models.crochetability import (
    CrochetabilityAdvice,
    at_or_above,
    crochetability_findings,
    widest_rounds,
)
from app.models.gauge import PRESET_LABELS
from app.ui.result_renderer import md_safe


def preset_option(advice: CrochetabilityAdvice) -> list[str]:
    if not advice.presets:
        return []
    return [f"在侧栏把密度预设改为「{PRESET_LABELS[advice.presets[0]]}」（更细的线）"]


def render_stitch_preview(params: Mapping[str, Any], suggest: Callable[[str], list[str]]) -> bool:
    """Show counts and findings; return True when generation must stay disabled.

    ``suggest(level)`` returns the single-change options that clear findings at
    that level. It runs only when something needs attention, because it builds
    several candidate patterns.
    """
    if peaks := widest_rounds(params):
        st.caption("生成前预览 · 各部件最宽一圈："
                   + " · ".join(f"{md_safe(name)} {count} 针" for name, count in peaks))
    findings = crochetability_findings(params)
    blocking = at_or_above(findings, "block")
    warnings = [f for f in findings if f.level == "warn"]
    notes = [f for f in findings if f.level == "note"]
    options = suggest("block" if blocking else "warn") if blocking or warnings else []
    if blocking:
        st.error("⛔ 暂不能生成：" + "；".join(md_safe(f.message) for f in blocking) + "。")
        if options:
            st.info("调整任意一项即可：" + "；".join(options) + "。")
        else:
            st.info("在可调范围内找不到能通过的设置；请改用更细的线，或在「手动输入」页直接指定尺寸。")
    elif warnings:
        st.warning("⚠️ " + "；".join(md_safe(f.message) for f in warnings) + "。")
        if options:
            st.caption("如需达到常见尺寸，可调整任意一项：" + "；".join(options) + "。")
    if notes:
        st.caption("ℹ️ " + "；".join(md_safe(f.message) for f in notes) + "。")
    return bool(blocking)
