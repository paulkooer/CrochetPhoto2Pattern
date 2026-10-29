"""Inspect saved measurements and preview a deliberate density regeneration."""
import streamlit as st

from app.models.gauge import Gauge, gauge_from_result
from app.ui.edit_history import preview_edit
from app.utils.project import pattern_revision
from app.utils.trial_bundle import TrialBundle, trial_comparison_rows, trial_gauge_candidate


def render_trial_review(bundle: TrialBundle, result: dict, slot: str) -> None:
    from app.ui.result_renderer import md_safe

    st.markdown("**已保存的实测与原图解对照**")
    st.table(trial_comparison_rows(bundle))
    st.caption("差异 = 实测 ÷ 原图解值 − 1；用线和基础工时仍为估算。"
               "这里读取上次成功保存的数据，输入修改后请先保存记录。")
    if bundle.record.observation and bundle.record.observation.pattern_modified:
        st.caption("这次实物包含改图，尺寸、用线和工时差异也包含改图影响。")
    swatch = bundle.record.swatch
    same_source = pattern_revision(result) == bundle.source_revision
    same_gauge = gauge_from_result(result) == Gauge(swatch.stitches_per_10cm, swatch.rows_per_10cm)
    st.caption("按实测密度重算会保留目标尺寸、结构和固定腰位，沿用当前线材规格，重新生成针数与圈数；"
               "逐圈手改会被生成结果替换，已完成进度需重新核对。先预览，再应用，可撤销。"
               "预览显示在下方「局部修正」区域，原试钩记录及下载保持不变。")
    if not swatch.measured:
        st.caption("请先保存实测小样并确认「已实际测量小样」。")
    elif not same_source:
        st.caption("重算入口仅用于试钩原图解；请从侧栏打开原试钩包后再操作。")
    elif same_gauge:
        st.caption("已保存的实测密度与当前图解一致，无需重算。")
    if st.button("预览按实测密度重算", key=f"trial_gauge_preview_{slot}",
                 disabled=not swatch.measured or not same_source or same_gauge):
        try:
            candidate = trial_gauge_candidate(bundle, result)
        except Exception as exc:
            st.error(f"无法生成密度调整方案：{md_safe(exc)}")
        else:
            preview_edit(slot, result, candidate)
