"""Capture current fragment/widget progress only when the user requests a save."""
from __future__ import annotations

import json

import streamlit as st

from app.ui.progress_state import capture_progress
from app.utils.backup import MAX_BACKUP_BYTES
from app.utils.project import MAX_PROJECT_NOTES, project_backup


@st.dialog("下载钩织工程")
def _download_project(payload: str, completed: int, revision: str) -> None:
    st.caption(f"已记录 {completed} 个完成圈次及个人备注；图解版本 {revision[:12]}。")
    st.caption("这是点击保存时的快照。继续钩织或修改后，请再次点击「保存工程」。")
    st.download_button("下载工程 JSON", payload, file_name="amigurumi_project.json",
                       mime="application/json", key="download_project_snapshot")


def render_project_save(result: dict, slot: str) -> None:
    rid = result.get("result_id") or slot
    with st.expander("🧺 我的钩织工程", expanded=False):
        notes = st.text_area("个人备注（随工程保存）", key=f"project_notes_{rid}",
                             max_chars=MAX_PROJECT_NOTES, height=100,
                             help="可记录针号、线材、暂停位置或返工情况。分享链接和图解备份不包含这些备注。")
        st.caption("工程文件保留每份部件的进度、备注和图解版本；关闭页面前请保存到自己的设备。"
                   "重新打开时，在侧栏「打开备份图解」上传工程文件。撤销历史仅保留在当前会话。")
        if st.button("💾 保存工程（含进度）", key=f"project_save_{rid}"):
            from app.ui.result_renderer import md_safe

            try:
                data = project_backup(result, capture_progress(result, slot, st.session_state), notes)
                payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
                if len(payload.encode("utf-8")) > MAX_BACKUP_BYTES:
                    raise ValueError("工程超过 20 MiB 导入上限，请减少工程内容后再保存")
            except Exception as exc:
                st.error(f"工程保存失败：{md_safe(exc)}")
            else:
                _download_project(payload, len(data["project_state"]["completed_rounds"]),
                                  data["project_state"]["pattern_revision"])
