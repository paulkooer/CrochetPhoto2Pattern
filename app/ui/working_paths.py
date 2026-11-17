"""Load, check and read explicit manual recipes without claiming photo inference."""
from __future__ import annotations

import hashlib
import importlib.util
import json

import streamlit as st

from app.models.working_path import (
    FastenOff,
    NewYarn,
    ParkYarn,
    ResumeYarn,
    Route,
    StitchEvent,
    WeaveEnds,
    WorkingPath,
    compile_working_path,
)
from app.ui.result_renderer import md_safe
from app.utils.working_path_export import export_working_path_markdown, step_text
from app.utils.working_recipe_export import export_working_recipe_pdf, route_formula
from app.working_paths import MAX_PLAN_BYTES, read_path


def render_yarn_steps(plan: WorkingPath) -> None:
    actions = [step for step in plan.steps
               if isinstance(step, (NewYarn, FastenOff, ParkYarn, ResumeYarn, WeaveEnds))]
    if not actions:
        return
    with st.expander("查看接线、暂停与收尾"):
        for step in actions:
            st.markdown(f"**{md_safe(step.label)}**")
            st.write(step_text(step))


def render_working_path_reader() -> None:
    with st.expander("人工工序图解（校验与阅读）"):
        st.caption("载入人工录入或按参数生成的起针、袖窿、挑针和接合工序；这不是照片自动生成入口。")
        file = st.file_uploader("工序图解 JSON", type=["json"], key="working_path_upload")
        data = None
        source_hash = None
        if file is not None:
            if file.size > MAX_PLAN_BYTES:
                st.error("工序文件超过2 MiB上限。")
            else:
                data = file.getvalue()
                source_hash = hashlib.sha256(data).hexdigest()
        if st.button("校验并载入工序", key="working_path_load", disabled=data is None):
            try:
                assert data is not None
                plan = read_path(data)
                compile_working_path(plan)
                st.session_state["working_path_plan"] = plan.model_dump()
                st.session_state["working_path_source"] = source_hash
                st.session_state.pop("working_path_pdf", None)
            except ValueError as exc:
                st.error(f"工序需要核对：{md_safe(exc)}")
        stored = st.session_state.get("working_path_plan")
        if stored is None:
            return
        try:
            plan = WorkingPath.model_validate(stored)
            result = compile_working_path(plan)
        except ValueError:
            st.error("已存工序不符合当前检查规则，请重新校验后载入。")
            return
        stale = source_hash is None or source_hash != st.session_state.get("working_path_source")
        if stale:
            st.info("上传内容已改变；下方仍是上一份工序，重新校验后才能下载。")
        st.markdown("**工序设计核对稿 · 未实钩、未试穿**")
        st.write(plan.title)
        for note in plan.review_notes:
            st.info(note)
        render_yarn_steps(plan)
        st.caption("通过的是已声明针位与控制步骤的检查；成品边及孔边保留也按声明计账，"
                   "不代表这些位置实际钩过。原文疑点、织物方向和实际合身仍须核对。")
        records = []
        events_by_route: dict[str, list[StitchEvent]] = {}
        for event in result.events:
            events_by_route.setdefault(event.route, []).append(event)
        for step in plan.steps:
            if isinstance(step, Route):
                formula, binding = route_formula(step, events=events_by_route.get(step.id, []))
                records.append({"工序": step.label, "操作": formula, "工作针位": step.expected_sites,
                                "接合": binding, "依据": step.source_ref})
        with st.expander("查看逐行操作"):
            st.dataframe(records, hide_index=True, width="stretch")
        st.download_button("下载工序 JSON", plan.model_dump_json(indent=2), "working-path.json",
                           "application/json", key="working_path_download_plan", disabled=stale)
        st.download_button("下载逐步说明", export_working_path_markdown(plan), "working-path.md",
                           "text/markdown", key="working_path_download_md", disabled=stale)
        if importlib.util.find_spec("reportlab") is not None:
            plan_hash = hashlib.sha256(plan.model_dump_json().encode()).hexdigest()
            if st.button("准备工序 PDF", key="working_path_prepare_pdf", disabled=stale):
                try:
                    st.session_state["working_path_pdf"] = {
                        "source": plan_hash, "data": export_working_recipe_pdf(plan),
                    }
                except (ValueError, ImportError):
                    st.error("PDF未能生成，已载入工序仍保留；可先下载逐步说明。")
            pdf = st.session_state.get("working_path_pdf")
            if pdf and pdf["source"] == plan_hash:
                st.download_button("下载工序 PDF", pdf["data"], "working-recipe.pdf", "application/pdf",
                                   key="working_path_download_pdf", disabled=stale)
        with st.expander("查看针位来源记录"):
            st.caption("接合及行端引用记录，不是织物形变或成品外观模拟。")
            sources = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            st.download_button("下载针位来源 JSON", sources,
                               "working-path-sources.json", "application/json",
                               key="working_path_download_sources", disabled=stale)
