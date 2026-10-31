"""Record a physical trial against its saved source, independently of live edits."""
from __future__ import annotations

import re
import uuid
from datetime import date

import streamlit as st

from app.utils.project import pattern_revision
from app.utils.trial_bundle import (
    MAX_TRIAL_BUNDLE_BYTES,
    TrialBundle,
    create_trial_bundle,
    decode_trial_bundle,
    encode_trial_bundle,
    update_trial_bundle,
)
from app.utils.trial_history import restore_trial_version, save_trial_version


def _replace_fields(slot: str, workspace: dict) -> None:
    prefix = f"trial_fields_{slot}_"
    for key in list(st.session_state):
        if str(key).startswith(prefix):
            del st.session_state[key]
    st.session_state[f"trial_workspace_{slot}"] = {
        **workspace, "token": uuid.uuid4().hex[:12],
    }


def _install(slot: str, bundle: TrialBundle) -> None:
    # Validate/serialize first, so a failed import leaves the active trial intact.
    archive = encode_trial_bundle(bundle)
    _replace_fields(slot, {"bundle": bundle, "archive": archive, "undo": [], "redo": []})
    st.session_state.pop(f"trial_notice_{slot}", None)


def _restore(slot: str, data: bytes) -> None:
    _install(slot, decode_trial_bundle(data))


def render_trial_open() -> None:
    """Open a saved trial and its original pattern without generating a seed result."""
    from app.ui.result_logic import import_backup
    from app.ui.result_renderer import md_safe, purge_result_state
    from app.utils.backup import decode_backup_json

    with st.expander("🧪 打开试钩包", expanded=False):
        st.caption("恢复原图解与实测记录，在「照片分析（本地）」页继续。"
                   "会替换该页当前图解与试钩记录，需要保留时请先分别保存。")
        uploaded = st.file_uploader("选择试钩包 ZIP", type=["zip"], key="trial_open_file")
        if st.button("打开试钩及原图解", key="trial_open_apply", disabled=uploaded is None):
            try:
                assert uploaded is not None
                uploaded.seek(0)
                bundle = decode_trial_bundle(uploaded.read(MAX_TRIAL_BUNDLE_BYTES + 1))
                original = import_backup(decode_backup_json(bundle.source), uuid.uuid4().hex[:12])
                _install("result", bundle)
            except Exception as exc:
                st.error(f"打开失败，当前工作保持不变：{md_safe(exc)}")
            else:
                if "result" in st.session_state:
                    purge_result_state(st.session_state["result"])
                st.session_state["result"] = original
                st.rerun()


def _measurements(bundle: TrialBundle, prefix: str, *, can_undo: bool, can_redo: bool
                  ) -> tuple[dict, dict, bool, str | None]:
    record = bundle.record
    st.caption("测量可分次填写，未完成时先保存草稿；缺少的数据留空。"
               "全部测量完成后勾选「标记为完成」再保存，系统会检查必填项。")
    with st.form(prefix + "form"):
        complete = st.checkbox("标记为完成（需填写必填测量）", value=record.status == "completed",
                               key=prefix + "complete")
        st.caption("小样初始密度来自图解；请换成实际测量值后确认。")
        swatch: dict = {"measured": st.checkbox("已实际测量小样", value=record.swatch.measured,
                                                key=prefix + "measured")}
        left, right = st.columns(2)
        for column, field, label, low, high in (
            (left, "stitches_per_10cm", "实测 10 cm 针数", 6.0, 40.0),
            (right, "rows_per_10cm", "实测 10 cm 行数", 8.0, 50.0),
        ):
            swatch[field] = column.number_input(label, low, high, value=getattr(record.swatch, field),
                                                step=0.1, key=prefix + field)
        swatch["hook_mm"] = st.number_input("钩针直径（mm，可不填）", 0.0, 20.0,
                                            value=record.swatch.model_dump()["hook_mm"], step=0.25,
                                            key=prefix + "hook")
        for field, label, limit in (("yarn_brand", "线材品牌", 100), ("yarn_line", "线材系列", 100),
                                    ("yarn_lot", "线材批次", 100), ("fiber", "纤维成分", 200)):
            swatch[field] = st.text_input(label + "（可不填）", value=getattr(record.swatch, field) or "",
                                          max_chars=limit, key=prefix + field).strip() or None
        previous = record.observation or bundle.draft
        old = previous.model_dump() if previous is not None else {}
        observation: dict = {"completed_on": st.date_input(
            "完成日期（完成时必填）", value=old.get("completed_on"),
            max_value=date.today(), key=prefix + "date")}
        for field, label, high in (("overall_height_cm", "成品实测总高（cm）", 300.0),
                                   ("yarn_used_grams", "实际用线（g，不含填充物与配件）", 5000.0),
                                   ("yarn_used_meters", "实际用线（m，可不填）", 100_000.0)):
            observation[field] = st.number_input(label, 0.0, high, value=old.get(field), step=0.1,
                                                   key=prefix + field)
        observation["active_minutes"] = st.number_input("实际操作时间（分钟，不含暂停）", 1, 100_000,
                                                          value=old.get("active_minutes"), step=1,
                                                          key=prefix + "minutes")
        scopes = ("full_project", "round_crochet_baseline")
        observation["time_scope"] = st.selectbox(
            "工时包含哪些操作", scopes, index=scopes.index(old.get("time_scope", "full_project")),
            format_func=lambda v: "完整项目（含装配、填充、换色等收尾）" if v == "full_project"
            else "仅逐圈钩织与换圈", key=prefix + "scope")
        observation["pattern_modified"] = st.checkbox("实际钩织时改过这份原图解",
                                                        value=old.get("pattern_modified", False),
                                                        key=prefix + "modified")
        modifications = st.text_area("修改内容（每行一项；未改图解时留空）",
                                      value="\n".join(old.get("modifications", [])),
                                      max_chars=20_000, key=prefix + "modifications")
        observation["modifications"] = [line.strip() for line in modifications.splitlines() if line.strip()]
        observation["notes"] = st.text_area("试钩备注（可不填）", value=old.get("notes") or "",
                                             max_chars=2000, key=prefix + "notes").strip() or None
        save, undo, redo = st.columns([2, 1, 1])
        submitted = save.form_submit_button("保存记录并更新下载")
        undone = undo.form_submit_button("↶ 撤销保存", disabled=not can_undo)
        redone = redo.form_submit_button("↷ 重做保存", disabled=not can_redo)
        st.caption("撤销/重做针对已保存版本。表单有未保存修改时会保留输入，请先保存再操作。"
                   "历史只留在当前会话，最多 8 份；重新打开或结束记录后清空。")
    action = "save" if submitted else "undo" if undone else "redo" if redone else None
    return swatch, observation, complete, action


def _check_required(swatch: dict, observation: dict, *, completed: bool) -> None:
    if swatch.get("hook_mm") is not None and swatch["hook_mm"] <= 0:
        raise ValueError("钩针直径须大于 0，也可留空")
    if not completed:
        return
    if not swatch["measured"]:
        raise ValueError("完成记录需要实测小样，请填写密度并勾选「已实际测量小样」")
    if observation.get("completed_on") is None:
        raise ValueError("请填写完成日期；尚未完成时可取消「标记为完成」并保存草稿")
    if any(observation.get(field) is None or observation[field] <= 0
           for field in ("overall_height_cm", "yarn_used_grams", "active_minutes")):
        raise ValueError("请填写大于 0 的成品总高、用线克数和实际操作分钟数")
    if bool(observation["modifications"]) != observation["pattern_modified"]:
        raise ValueError("改过图解时请勾选并填写修改内容；未改图解时请将修改内容留空")


def render_trial_editor(result: dict, slot: str) -> None:
    from app.ui.result_renderer import md_safe

    key = f"trial_workspace_{slot}"
    with st.expander("🧪 实体试钩记录", expanded=False):
        if notice := st.session_state.pop(f"trial_notice_{slot}", None):
            st.success(notice)
        st.caption("记录实测密度、尺寸、用线和工时。试钩包独立保存，不包含在普通图解备份或工程文件中。")
        uploaded = st.file_uploader("恢复试钩记录包（ZIP）", type=["zip"], key=f"trial_upload_{slot}",
                                    help="上传本面板下载的 ZIP；恢复不会替换当前图解。")
        if key in st.session_state:
            st.caption("恢复会替换本面板当前试钩记录；需要保留时，请先下载。")
        if st.button("恢复试钩记录", key=f"trial_restore_{slot}", disabled=uploaded is None):
            try:
                assert uploaded is not None
                uploaded.seek(0)
                _restore(slot, uploaded.read(MAX_TRIAL_BUNDLE_BYTES + 1))
            except Exception as exc:
                st.error(f"恢复失败，原记录保持不变：{md_safe(exc)}")
            else:
                st.rerun()
        workspace = st.session_state.get(key)
        if workspace is None:
            from app.models.gauge import INDEPENDENT_TRIAL_MESSAGE, has_independent_gauge

            try:
                independent = has_independent_gauge(result["params"])
            except ValueError:
                independent = True
            if independent:
                st.caption(INDEPENDENT_TRIAL_MESSAGE)
            with st.form(f"trial_new_{slot}"):
                trial_id = st.text_input("试钩编号", value=st.session_state.get(
                    f"trial_id_{slot}", "trial-" + uuid.uuid4().hex[:8]),
                                          max_chars=64, key=f"trial_id_{slot}")
                maker_id = st.text_input("匿名制作者编号", max_chars=64, key=f"trial_maker_{slot}",
                                          help="用稳定的匿名编号区分制作者，例如 maker-a。")
                cohort = st.selectbox(
                    "记录用途", ("calibration", "validation"), key=f"trial_cohort_{slot}",
                    format_func=lambda v: "校准样本" if v == "calibration" else "独立验证样本")
                st.caption("独立验证须使用未参与校准的图解。编号使用字母、数字、点、下划线或短横线。")
                create = st.form_submit_button("以当前图解新建试钩", disabled=independent)
            if create:
                try:
                    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value.strip())
                           for value in (trial_id, maker_id)):
                        raise ValueError("请填写有效的试钩编号和匿名制作者编号，以字母或数字开头")
                    _install(slot, create_trial_bundle(result, trial_id=trial_id.strip(),
                                                       maker_id=maker_id.strip(),
                                                       cohort="validation" if cohort == "validation"
                                                       else "calibration"))
                except Exception as exc:
                    st.error(f"无法新建试钩：{md_safe(exc)}")
                else:
                    st.rerun()
            return
        bundle = workspace["bundle"]
        record = bundle.record
        st.text(f"试钩 {record.trial_id} · 制作者 {record.maker_id} · "
                f"{'校准样本' if record.cohort == 'calibration' else '独立验证样本'}")
        st.caption(f"原图解目标高度 {record.pattern.target_height_cm:g} cm；"
                   f"{record.pattern.total_stitches} 针，{record.pattern.total_physical_rounds} 个实体圈次。")
        if pattern_revision(result) != bundle.source_revision:
            st.warning("当前图解已与试钩原图解不同；本记录继续绑定原图解。"
                       "若实物也采用了修改，请在完成记录中声明改图内容；新设计请另建试钩。")
        prefix = f"trial_fields_{slot}_{workspace['token']}_"
        swatch, observation, complete, action = _measurements(
            bundle, prefix, can_undo=bool(workspace.get("undo")), can_redo=bool(workspace.get("redo")))
        if action is not None:
            try:
                _check_required(swatch, observation, completed=complete)
                updated = update_trial_bundle(bundle, swatch=swatch, observation=observation,
                                               completed=complete)
                if action == "save":
                    next_workspace = save_trial_version(workspace, updated)
                elif updated.record != bundle.record or updated.draft != bundle.draft:
                    raise ValueError("表单有未保存修改，撤销/重做未执行。请先保存当前内容，输入已保留。")
                else:
                    next_workspace = restore_trial_version(workspace, action)
            except Exception as exc:
                message = "记录未保存" if action == "save" else "保存历史未切换，当前输入已保留"
                st.error(f"{message}：{md_safe(exc)}")
            else:
                if action == "save":
                    unchanged = next_workspace is workspace
                    workspace = next_workspace
                    st.session_state[key] = workspace
                    if unchanged:
                        st.success("内容与已保存版本一致，下载保持不变。")
                    else:
                        st.session_state[f"trial_notice_{slot}"] = (
                            "记录已保存到本次会话，请下载更新后的试钩包。")
                        st.rerun()
                else:
                    _replace_fields(slot, next_workspace)
                    st.session_state[f"trial_notice_{slot}"] = (
                        "已撤销保存，表单与下载已恢复。" if action == "undo"
                        else "已重做保存，表单与下载已恢复。")
                    st.rerun()
        saved = workspace["bundle"].record
        if workspace["bundle"].draft is not None:
            st.caption("已保存未完成测量，下次打开试钩包可继续填写；标记完成前不进入成品偏差与校准统计。")
        st.caption(f"下载内容：{'完成记录' if saved.status == 'completed' else '草稿'}及原图解。"
                   "只包含上次保存的数据；继续填写后须再次保存并下载。")
        st.download_button("下载试钩包 ZIP", workspace["archive"], file_name=f"{saved.trial_id}.zip",
                            mime="application/zip", key=f"trial_download_{slot}")
        if saved.observation:
            ratio = saved.observation.overall_height_cm / saved.pattern.target_height_cm
            st.metric("实测总高相对原目标", f"{(ratio - 1) * 100:+.1f}%")
            st.caption("单次记录供偏差核对，不会自动调整生成器。"
                       "完整项目工时不用于每针工时校准，改过图解的记录不进入常数校准。")
        from app.ui.trial_review import render_trial_review

        render_trial_review(workspace["bundle"], result, slot)
        if st.button("结束本次记录（请先下载）", key=f"trial_close_{slot}"):
            del st.session_state[key]
            for field in list(st.session_state):
                if str(field).startswith(prefix):
                    del st.session_state[field]
            st.rerun()
