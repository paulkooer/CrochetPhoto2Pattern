"""A manual, explicitly experimental entry to parametric construction synthesis."""
from __future__ import annotations

import hashlib
import importlib.util
import json

import streamlit as st

from app.models.cardigan_design import CARDIGAN_ENGINE_VERSION, CardiganRequest, RibGauge, assemble_cardigan
from app.models.raglan_yoke import YokeMethod, YokeTarget
from app.models.working_path import WorkingPath
from app.ui.result_renderer import md_safe
from app.ui.working_paths import render_yarn_steps
from app.utils.working_recipe_export import export_working_recipe_pdf


def render_cardigan_designer() -> None:
    with st.expander("开衫工艺设计（试验）"):
        st.caption("按人工指定的尺寸设计领肩、分袖、衣身、门襟与肋纹；示例尺寸未实测，接缝与合身未验证。")
        neck = st.number_input("领口展开边长 cm", min_value=1.0, max_value=30.0,
                               value=8.1, step=.1, key="cardigan_neck")
        body = st.number_input("衣身展开宽度 cm（不含门襟）", min_value=3.0, max_value=50.0,
                               value=17.7, step=.1, key="cardigan_body")
        sleeve = st.number_input("袖围 cm", min_value=2.0, max_value=25.0,
                                 value=6.9, step=.1, key="cardigan_sleeve")
        depth = st.number_input("领肩深度 cm（含分袖行）", min_value=1.0, max_value=20.0,
                                value=3.2, step=.1, key="cardigan_depth")
        body_length = st.number_input("腋下至下摆前的衣身长度 cm", min_value=.5, max_value=30.0,
                                      value=7.5, step=.1, key="cardigan_body_length")
        sleeve_length = st.number_input("袖长 cm（不含袖口）", min_value=.5, max_value=30.0,
                                        value=6.4, step=.1, key="cardigan_sleeve_length")
        mode = st.radio("密度输入方式", ["肋纹密度未提供", "用假设密度查看工程示例", "填入自己的小样密度"],
                        key="cardigan_gauge_mode")
        own = mode == "填入自己的小样密度"
        with st.expander("调整密度、边宽与扣眼"):
            gs = st.number_input("普通短针 / 10cm", min_value=5.0, max_value=60.0,
                                 value=None if own else 26.0,
                                 key="cardigan_sc_own_gs" if own else "cardigan_sc_gs")
            gr = st.number_input("普通短针行 / 10cm", min_value=5.0, max_value=60.0,
                                 value=None if own else 28.0,
                                 key="cardigan_sc_own_gr" if own else "cardigan_sc_gr")
            hem_width = st.number_input("下摆肋纹宽 cm", min_value=.3, max_value=5.0,
                                         value=1.9, step=.1, key="cardigan_hem_width")
            band_width = st.number_input("门襟宽 cm", min_value=.3, max_value=5.0,
                                          value=1.0, step=.1, key="cardigan_band_width")
            cuff_width = st.number_input("袖口肋纹宽 cm", min_value=.3, max_value=8.0,
                                          value=3.5, step=.1, key="cardigan_cuff_width")
            gauges = []
            for name, label, default_gs, default_gr in (
                ("hem", "下摆短针BLO", 26.0, 26.0),
                ("band", "门襟引拔BLO", 40.0, 40.0),
                ("cuff", "袖口引拔BLO", 40.0, 40.0),
            ):
                sts = st.number_input(f"{label}针 / 10cm", min_value=5.0, max_value=80.0,
                                      value=None if own else default_gs,
                                      key=f"cardigan_{name}_own_gs" if own else f"cardigan_{name}_gs",
                                      disabled=mode == "肋纹密度未提供")
                rows = st.number_input(f"{label}行 / 10cm", min_value=5.0, max_value=80.0,
                                       value=None if own else default_gr,
                                       key=f"cardigan_{name}_own_gr" if own else f"cardigan_{name}_gr",
                                       disabled=mode == "肋纹密度未提供")
                gauges.append(RibGauge() if mode == "肋纹密度未提供" else RibGauge(
                    stitches_per_10cm=sts, rows_per_10cm=rows,
                    basis="user_entered_swatch" if mode == "填入自己的小样密度" else "hypothetical"))
            positions = st.text_input("扣眼距工作路径起点 cm（逗号分隔）", "1,3,5",
                                       key="cardigan_holes")
            seam = st.selectbox("袖口接合设计", ["保持打开供审查", "生成指定BLO/FLO接合候选"],
                                key="cardigan_seam")
            tail = st.number_input("收线预留尾长 cm", min_value=5.0, max_value=50.0,
                                   value=15.0, step=1.0, key="cardigan_tail")
        try:
            target = YokeTarget(
                neck_edge_cm=neck, body_span_cm=body, sleeve_circumference_cm=sleeve, yoke_depth_cm=depth,
                stitches_per_10cm=gs, rows_per_10cm=gr,
                gauge_basis="user_entered_swatch" if mode == "填入自己的小样密度" else "hypothetical")
            request = CardiganRequest(
                dimension_basis="hypothetical" if mode != "填入自己的小样密度" else "user_dimensions",
                yoke=target, method=YokeMethod(prefix="design", hook_mm=3.0),
                body_length_cm=body_length, sleeve_length_cm=sleeve_length,
                hem_width_cm=hem_width, band_width_cm=band_width, cuff_width_cm=cuff_width,
                hem_gauge=gauges[0], band_gauge=gauges[1], cuff_gauge=gauges[2],
                buttonhole_positions_cm=[float(value.strip()) for value in positions.split(",")],
                cuff_seam="open_review" if seam == "保持打开供审查" else "blo_to_reserved_flo",
                finishing_tail_cm=tail,
            )
            engine_input = CARDIGAN_ENGINE_VERSION + request.model_dump_json()
            source = hashlib.sha256(engine_input.encode()).hexdigest()
        except ValueError:
            request, source = None, None
            st.error("请核对扣眼位置与设计输入，位置用递增的数字和英文逗号表示。")
        if st.button("生成开衫工序设计", key="cardigan_generate", disabled=request is None):
            try:
                assert request is not None
                result = assemble_cardigan(request)
                st.session_state["cardigan_design_result"] = {
                    "report": result.to_dict(),
                    "plan": None if result.plan is None else result.plan.model_dump(),
                    "source": source,
                }
                st.session_state.pop("cardigan_design_pdf", None)
            except ValueError as exc:
                st.error(f"当前做法不能生成这组设计：{md_safe(exc)}")
        stored = st.session_state.get("cardigan_design_result")
        if stored is None:
            return
        stale = source is None or source != stored["source"]
        if stale:
            st.info("输入或生成器版本已改变，下方保留上一份设计；重新生成后才能下载。")
        report = stored["report"]
        if report["stage"] == "integrated_open_cuffs":
            st.write("已组合领肩、衣身、下摆、门襟扣眼及双袖；袖口尚未接合。")
        elif report["stage"] == "integrated_cuff_seam_candidate":
            st.write("已生成包含指定袖口半针接合的组合候选；折向、边缘和实际合身仍待验证。")
        else:
            st.write("当前只生成到已有依据的阶段，后续缺口如下。")
        for reason in report["unresolved"]:
            st.warning(reason)
        yarns = report.get("yarn_accounting", {})
        if yarns.get("all_weave_steps_present"):
            st.write("已列出三段用线各自的断线与两端藏线步骤；这不是实际完成记录。")
        elif report["stage"] == "integrated_open_cuffs" and yarns.get("mode") == "explicit":
            st.write("打开的袖口工作环用记号扣暂停，仍连接线团；下一袖另备可用线头，接合后再收线。")
        yoke = report["stages"]["yoke"]
        if yoke["layout"] is not None:
            st.write({"领口针数": yoke["layout"]["neck_stitches"],
                      "含分袖行的领肩行数": yoke["layout"]["rows_to_split"],
                      "估算领肩深度cm": round(yoke["estimated_cm"]["yoke_depth"], 3),
                      "相对目标针数的调整": yoke["adjustment_stitches"]})
        st.download_button("下载开衫设计记录", json.dumps(report, ensure_ascii=False, indent=2),
                           "cardigan-design-report.json", "application/json",
                           key="cardigan_download_report", disabled=stale)
        if stored["plan"] is None:
            return
        plan = WorkingPath.model_validate(stored["plan"])
        render_yarn_steps(plan)
        st.download_button("下载开衫工序 JSON", plan.model_dump_json(indent=2), "cardigan-path.json",
                           "application/json", key="cardigan_download_plan", disabled=stale)
        if importlib.util.find_spec("reportlab") is not None:
            if st.button("准备开衫工序 PDF", key="cardigan_prepare_pdf", disabled=stale):
                try:
                    st.session_state["cardigan_design_pdf"] = {
                        "source": stored["source"], "data": export_working_recipe_pdf(plan)}
                except (ValueError, ImportError):
                    st.error("PDF未能生成，设计仍保留，可下载工序JSON。")
            pdf = st.session_state.get("cardigan_design_pdf")
            if pdf and pdf["source"] == stored["source"]:
                st.download_button("下载开衫工序 PDF", pdf["data"], "cardigan-path.pdf", "application/pdf",
                                   key="cardigan_download_pdf", disabled=stale)
