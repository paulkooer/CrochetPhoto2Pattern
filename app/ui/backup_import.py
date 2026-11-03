"""Open a saved result before generation, or replace a result in its own tab."""
from __future__ import annotations

import hashlib
import uuid

import streamlit as st

from app.services.result_logic import import_backup
from app.utils.backup import MAX_BACKUP_BYTES, MAX_PASTED_BACKUP_BYTES, decode_backup_json


def _payload_fingerprint(payload: str | bytes) -> str | None:
    try:
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    except UnicodeError:
        return None
    return hashlib.sha256(raw).hexdigest()


def render_backup_import(slot: str = "result", *, result_key: str | None = None) -> None:
    # Keep the existing per-result paste/button keys for session compatibility.
    home = result_key is None
    source_key = "open_backup_source" if home else f"import_source_{result_key}"
    file_key = "open_backup_file" if home else f"import_file_{result_key}"
    text_key = "open_backup_text" if home else f"import_{result_key}"
    button_key = "open_backup_apply" if home else f"importbtn_{result_key}"
    pending_key = "open_backup_ambiguous" if home else f"import_{result_key}_ambiguous"
    recovery_key = "open_backup_recover_ambiguous" if home else f"import_{result_key}_recover_ambiguous"
    label = "打开备份图解" if home else "导入结果备份"
    with st.expander(label, expanded=False):
        if home:
            st.caption("无需先生成图解或开启历史。导入后在「照片分析（本地）」页查看。")
        st.caption("支持完整图解备份和钩织工程；工程会同时恢复已完成圈次与个人备注。")
        method = st.radio("导入方式", ("上传 JSON 文件", "粘贴 JSON"),
                          index=0 if home else 1, horizontal=True, key=source_key)
        payload: str | bytes = ""
        limit = MAX_PASTED_BACKUP_BYTES
        if method == "上传 JSON 文件":
            uploaded = st.file_uploader("选择完整备份 JSON", type=["json"], key=file_key,
                                        help="选择「备份完整结果」下载的文件，最多 20 MiB。")
            limit = MAX_BACKUP_BYTES
            if uploaded is not None:
                # Bound reads even if the host's uploader limit is configured higher.
                uploaded.seek(0)
                payload = uploaded.read(limit + 1)
        else:
            payload = st.text_area("粘贴备份 JSON 内容", height=120, key=text_key)
            st.caption("粘贴限 2 MiB；较大备份请上传文件（最多 20 MiB）。")
        if slot in st.session_state:
            destination = "「照片分析（本地）」页" if home else "本页"
            st.caption(f"成功导入会替换{destination}当前图解，请先保存需要保留的完整备份。")
        button = "导入并打开图解" if home else "导入并替换当前结果"
        requested = st.button(button, key=button_key, disabled=not payload)
        pending = st.session_state.get(pending_key)
        if pending and (not payload or _payload_fingerprint(payload) != pending["fingerprint"]):
            st.session_state.pop(pending_key, None)
            pending = None
        recover = False
        if pending:
            st.warning(f"旧工程中有 {pending['count']} 个完成圈次无法区分属于哪份实体。"
                       "可保留原文件，并选择只恢复其他进度；这些圈次需要按实物重新勾选。")
            recover = st.button("仅恢复无歧义进度并打开", key=recovery_key)
        if requested or recover:
            from app.ui.result_renderer import md_safe, purge_result_state
            from app.utils.project import AmbiguousProjectProgressError

            try:
                from app.services.progress_state import install_progress
                from app.services.workspace import new_workspace, workspace_key
                from app.utils.project import read_project_state

                data = decode_backup_json(payload, max_bytes=limit)
                imported = import_backup(data, uuid.uuid4().hex[:12])
                progress, notes = read_project_state(data, imported, clear_legacy_ambiguity=recover)
                prepared: dict = {}
                install_progress(imported, slot, progress, prepared)
                recovery_notice = None
                if recover and pending:
                    recovery_notice = (
                        f"从旧工程恢复时，{pending['count']} 个完成圈次无法区分属于哪份实体，"
                        "已暂不标记；请按实物核对后重新勾选，再保存工程。")
                prepared[workspace_key(slot)] = new_workspace(
                    imported, slot, notes=notes, recovery_notice=recovery_notice)
            except AmbiguousProjectProgressError as exc:
                st.session_state[pending_key] = {"fingerprint": _payload_fingerprint(payload),
                                                 "count": exc.count}
                st.rerun()
            except Exception as exc:
                st.error(f"导入失败：{md_safe(exc)}")
            else:
                st.session_state.pop(pending_key, None)
                if slot in st.session_state:
                    purge_result_state(st.session_state[slot])
                st.session_state.update(prepared)
                st.session_state[slot] = imported
                if home:
                    st.session_state["opened_backup_result_id"] = imported["result_id"]
                st.rerun()
        if (home and (current := st.session_state.get(slot))
                and st.session_state.get("opened_backup_result_id") == current.get("result_id")):
            st.success("备份已打开，请在「照片分析（本地）」页查看。")
