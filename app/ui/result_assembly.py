"""Chapters 4 and 5: assembly text, local edits, downloads and Parade export."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import streamlit as st

from app.schemas import PatternResult, ResultData, strip_photo_derived
from app.services import result_logic
from app.services.color_identity import require_aligned_copy_colors
from app.services.result_logic import rebuild_params
from app.services.workspace import workspace
from app.ui.design_system import section_heading
from app.ui.result_analysis import md_safe
from app.utils.color_labels import display_color_name
from app.utils.exporters import export_markdown


def render_assembly(result: ResultData, validation: dict[str, Any]) -> None:
    """装配说明。自检未通过时保留图解里已有的装配文本。"""
    params = result["params"]
    _v = validation
    # Section 4: Assembly
    section_heading(4, "装配说明")
    # 装配文本内嵌部件名（模型/结构 JSON 可写）——纯文本渲染，
    # 不经 Markdown（链接/图片语法不生效）
    from app.models.assembly import assembly_for_pattern

    asm = assembly_for_pattern(params) if _v["ok"] else params.get("assembly_instructions") or ""
    st.text(asm if isinstance(asm, str) else str(asm))


def render_edits(result: ResultData, slot: str, validation: dict[str, Any]) -> None:
    """局部修正、按需挂载的 JSON 编辑器、下载和 CrochetPARADE 导出。"""
    analysis = result["analysis"]
    structure = result["structure"]
    params = result["params"]
    geometry = result.get("geometry") or {}
    result_key = result.get("result_id") or slot
    _v = validation
    # Section 5: Edit & Re-generate
    section_heading(5, "局部修正")
    # A5: st.success 后立即 st.rerun() 的话消息会被 rerun 丢弃（用户看不见），
    # 改为记在新结果的工作区，下一次 rerun 渲染时弹出。
    ws = workspace(result, slot, st.session_state)
    if success := ws["success"]:
        ws["success"] = None
        st.success(success)
    from app.ui.edit_history import preview_edit
    from app.ui.pattern_editor import apply_edit_with_notice, render_pattern_editor

    # Undo/redo first, then the common editors in order of use (size → parts and
    # rounds → materials). Raw JSON editing is the advanced layer below them.
    render_pattern_editor(result, slot)

    serializable_params = json.loads(
        json.dumps(params, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
                   ensure_ascii=False, indent=2)
    )
    applied_params_json = json.dumps(serializable_params, ensure_ascii=False, indent=2)

    # ── 高级编辑：两段 JSON 编辑器共用默认折叠的面板，首次启用后才挂载 ──────
    # 两段编辑器必须一起存在：Streamlit 会丢弃未渲染控件的状态，用切换会让
    # 尚未应用的草稿消失。启用前不渲染 text_area——两份 JSON 都很大，挂着就
    # 会在每次 rerun 被重新序列化并下发给浏览器。启用一次后保持挂载（闩按
    # 标签页记录，重新生成后仍可用，未应用的草稿不丢）。
    def _render_json_editors() -> bool:
        st.caption("直接编辑生成结果或部件结构的 JSON；建议先预览影响再应用。"
                   "尺寸、部件、逐圈与材料的常用修正请使用上方面板。")
        correction_json = st.text_area(
            "编辑 JSON 输出",
            applied_params_json,
            height=300,
            key=f"json_edit_{result_key}",
        )
        draft_pending = correction_json != applied_params_json
        if draft_pending:
            st.caption("JSON 草稿尚未应用。请点击「重新生成」应用修改；"
                       "下载、分享和存入历史使用当前已应用的图解。")
        with st.container(horizontal=True):
            preview_json = st.button("预览 JSON 修改影响", key=f"edit_{result_key}_json_preview")
            apply_json = st.button("重新生成", key=f"regen_{result_key}")
        if apply_json or preview_json:
            try:
                corrected = json.loads(correction_json)
                candidate = deepcopy(result)
                candidate["params"] = rebuild_params(
                    corrected, previous=result["params"], structure=result["structure"])
                candidate["gauge"] = candidate["params"].get("gauge")
                from app.services.color_identity import copy_color_alignment_rows

                alignment = copy_color_alignment_rows(corrected, candidate["params"])
                for row in alignment:
                    row["对齐后颜色"] = display_color_name(row["对齐后颜色"])
                if preview_json:
                    preview_edit(slot, result, candidate,
                                 detail={"copy_color_alignment": alignment} if alignment else None)
                else:
                    message = ("✅ 已更新图解并按实体 ID 对齐逐份颜色，请核对各份配色。" if alignment
                               else "✅ 已根据修正更新图解，向上查看结果！")
                    apply_edit_with_notice(slot, result, candidate, message)
            except Exception as e:
                st.error(f"解析/应用失败: {md_safe(e)}")

        # ── StructureGeometry 修正：严格校验后本地重生成，不重新调用 AI ──────
        st.caption(
            "部件结构 JSON：可修改部件尺寸、形状、数量、位置和连接节点。结构 v2 会严格检查 "
            "part_id、实例数量、镜像引用与 attachment 目标；修改数量时也要同步 "
            "instances。位置/旋转用于结构表达，连接节点影响装配说明；"
            "针数主要由形状和尺寸决定。")
        structure_json = st.text_area(
            "编辑结构 JSON",
            json.dumps(structure, ensure_ascii=False, indent=2),
            height=360,
            key=f"struct_edit_{result_key}",
        )
        with st.container(horizontal=True):
            preview_structure = st.button("预览结构 JSON 修改影响",
                                          key=f"edit_{result_key}_structure_preview")
            apply_structure = st.button("校验结构并重新生成", key=f"struct_go_{result_key}")
        if apply_structure or preview_structure:
            try:
                # 校验 + 重生成在 result_logic（纯函数，可离线单测）
                _updated = result_logic.regenerate_with_structure(
                    result, json.loads(structure_json))
                if preview_structure:
                    preview_edit(slot, result, _updated)
                else:
                    apply_edit_with_notice(slot, result, _updated,
                                           "✅ 已按修正后的部件结构重新生成图解与装配说明！")
            except Exception as e:
                st.error(f"结构校验或重生成失败: {md_safe(e)}")
        return draft_pending

    draft_pending = False
    with st.expander("高级编辑（JSON）", expanded=False):
        editor_mounted_key = f"json_editor_open_{slot}"
        if not st.session_state.get(editor_mounted_key):
            st.caption("启用后才加载两段 JSON 编辑器；未启用时不会在每次刷新时序列化整份图解。")
            if st.button("启用 JSON 编辑器", key=f"json_open_{result_key}"):
                st.session_state[editor_mounted_key] = True
                st.rerun()
        if st.session_state.get(editor_mounted_key):
            draft_pending = _render_json_editors()

    from app.models.runtime import timed_export
    from app.ui.export_cache import EXPORT_CACHE_VERSION, cached_export, export_fingerprint, parade_payload
    export_record = ws["export_trace"]
    export_cache = ws["export_cache"]
    # Bind portable text to all inputs its exporter consumes, including source
    # labels. Widget edits and unrelated diagnostics do not invalidate it.
    from app import software_version
    markdown_source = {
        "params": serializable_params, "analysis": analysis,
        "vision_meta": result.get("vision_meta"), "sizing": result.get("sizing"),
        # Provenance text depends on the presence of these records, not their
        # potentially large, photo-derived contents.
        "geometry_provenance": {"body_region": bool(geometry.get("body_region")),
                                "mask_review": bool(geometry.get("mask_review"))},
        "generator_version": result.get("generator_version"), "export_version": software_version(),
    }
    md_content = ""
    md_ready = False
    pdf_fingerprint = None
    if _v["ok"]:
        try:
            pdf_fingerprint = export_fingerprint(markdown_source)
            md_content = cached_export(
                export_cache, "markdown", markdown_source,
                lambda: timed_export(
                    export_record, "markdown", lambda: export_markdown(params, analysis, result=result)))
            md_ready = True
        except Exception as exc:
            st.error(f"Markdown 生成失败：{md_safe(exc)}")

    # ── 下载与保存：常用出口始终可见，不进折叠面板 ─────────────────────────
    st.markdown("**下载与保存**")
    if draft_pending:
        st.caption("「高级编辑」中有尚未应用的 JSON 草稿；以下下载、分享和存入历史使用当前已应用的图解。")

    # ── 完整结果备份/导入（刷新会丢 session，备份 JSON 可跨会话恢复）───────
    # F24：备份与分享使用同一结果契约——旧版只写三键，导入后
    # 快速调尺寸会把一体件拆回分件、egg 退化 ladder（style/spans 全丢）
    # 下载的备份也可能被转发分享，因此剔除 preview 缩略图和 mask_review
    # 画笔掩码；照片分析与轮廓摘要仍可能保留。单用户历史不走此导出路径。
    backup_data = strip_photo_derived(PatternResult.from_result({
        **result, "params": serializable_params,
    }).to_backup())
    backup_json = json.dumps(backup_data, ensure_ascii=False)
    col_bk1, col_bk2, col_bk3 = st.columns(3)
    with col_bk1:
        st.download_button(
            "备份完整结果",
            backup_json,
            file_name="amigurumi_backup.json",
            mime="application/json",
            key=f"dl_backup_{result_key}",
            help="含解析、结构与参数，可稍后导入恢复图解；不含照片缩略图和人工修正掩码",
        )
        if (result.get("geometry") or {}).get("mask_review"):
            st.caption("备份、分享、工程文件及新建试钩包不保存画笔修正掩码；生成的图解与轮廓摘要仍会保存，"
                       "但恢复后无法识别画笔修正来源。要重新修正选区须重新上传照片。")
        st.download_button(
            "下载 JSON",
            applied_params_json,
            file_name="amigurumi_pattern.json",
            mime="application/json",
            key=f"dl_json_{result_key}",
        )
        st.download_button(
            "下载 Markdown 图解",
            md_content,
            file_name="amigurumi_pattern.md",
            mime="text/markdown",
            key=f"dl_md_{result_key}",
            disabled=not md_ready,
        )
    with col_bk2:
        # A PDF is a snapshot: discard it whenever its inputs or format change,
        # even if the result identifier itself stayed the same.
        if (ws["pdf"] is not None
                and (pdf_fingerprint is None
                     or ws["pdf"].get("format") != EXPORT_CACHE_VERSION
                     or ws["pdf"].get("fingerprint") != pdf_fingerprint)):
            ws["pdf"] = None
        # PDF（S4）：点"生成"才构建（避免每次 rerun 都渲染 PDF），
        # 字节缓存进工作区后出现下载按钮
        if st.button("生成 PDF 图解", key=f"pdf_gen_{result_key}",
                     disabled=not _v["ok"] or pdf_fingerprint is None):
            try:
                from app.utils.pdf_export import export_pdf
                ws["pdf"] = {"format": EXPORT_CACHE_VERSION, "fingerprint": pdf_fingerprint,
                             "bytes": timed_export(
                    export_record, "pdf", lambda: export_pdf(params, analysis, result=result))}
            except ImportError:
                st.caption("PDF 导出需安装 reportlab："
                           "pip install crochet-photo2pattern[pdf]")
            except Exception as e:
                st.error(f"PDF 生成失败: {md_safe(e)}")
        _pdf_bytes = ws["pdf"]["bytes"] if ws["pdf"] is not None else None
        if _pdf_bytes and _v["ok"]:
            st.download_button("下载 PDF", _pdf_bytes,
                               file_name="amigurumi_pattern.pdf",
                               mime="application/pdf",
                               key=f"dl_pdf_{result_key}")
    with col_bk3:
        from app.ui.workspace import live_workspace, seed_widget, title_key

        seed_widget(title_key(result_key), live_workspace(result, slot)["title"])
        st.text_input("历史命名（可选）",
                      key=title_key(result_key),
                      placeholder="给这份图解起个名字", label_visibility="collapsed")
        # F23：分享入口。token 计算含全量 JSON + zlib，按需生成并缓存进
        # 工作区——不再每次 rerun 都压缩；共享数据变化后须重新生成。
        from app.utils.share import encode_result
        try:
            share_fingerprint = export_fingerprint(backup_data)
        except (TypeError, ValueError):
            share_fingerprint = None
        if (ws["share"] is not None
                and (share_fingerprint is None or ws["share"].get("fingerprint") != share_fingerprint)):
            ws["share"] = None
        if st.button("生成分享链接", key=f"share_{result_key}", disabled=share_fingerprint is None):
            try:
                token = encode_result(backup_data)
            except ValueError as exc:
                ws["share"] = None
                st.error(f"分享链接生成失败：{md_safe(exc)}")
            else:
                ws["share"] = {"fingerprint": share_fingerprint, "token": token}
        _share_token = ws["share"]["token"] if ws["share"] is not None else None
        if share_fingerprint is None:
            st.info("图解包含无法分享的数据，请先检查并修正。")
        elif ws["share"] is not None and _share_token is None:
            st.info("图解超过分享链接大小上限，请使用「备份完整结果」文件分享。")
        elif _share_token is None:
            st.caption("🔗 点「生成分享链接」得到可分享的 URL 参数；链接包含图解和分析摘要，"
                       "不含照片缩略图与画笔掩码。图解过大时请使用「备份完整结果」文件。")
        else:
            st.caption(f"🔗 分享链接（{len(_share_token)}/6000 字符，"
                       f"复制下面整行拼到本应用域名后打开即载入；"
                       f"修改图解后请重新生成）：")
            with st.expander("展开分享链接", expanded=False):
                st.code(f"?p={_share_token}", language=None)
        # 历史持久化（S4）：SQLite 单文件，跨会话在侧栏"我的图解"恢复
        from app.utils import history

        if st.button("存入历史", key=f"hist_save_{result_key}",
                     disabled=not history.history_enabled() or not _v["ok"],
                     help="保存到部署主机的图解历史，可在侧栏随时载回"):
            try:
                saved = result.copy()
                require_aligned_copy_colors(result)
                saved["params"] = rebuild_params(serializable_params, structure=result["structure"])
                saved["gauge"] = saved["params"].get("gauge")
                _title = (live_workspace(result, slot)["title"] or "").strip() or None
                saved_id = history.save_result(saved, title=_title)
                if saved_id:
                    result["history_id"] = saved_id
                    result["title"] = _title
                st.success("✅ 已存入历史（左侧栏「我的图解」可载回）")
            except Exception as e:
                st.error(f"存入历史失败: {md_safe(e)}")
        from app.ui.backup_import import render_backup_import

        render_backup_import(slot, result_key=result_key)

    # ── CrochetPARADE 导出（3D 验证）：独立 DSL 出口的差异化功能 ──────────
    with st.expander("导出 CrochetPARADE（3D 验证）", expanded=False):
        st.caption(
            "把图解翻译为 [CrochetPARADE](https://crochetparade.org) 的文本语法："
            "粘贴到其网页应用（本地计算、照片不外发）可得可旋转 3D 模型、"
            "\"过松/过紧针目\"物理分析与逐针动画——本应用代数自检之外的"
            "独立检查工具。语法映射基于其官方手册的已核对子集。")
        st.caption("本应用只检查导出完整性与文本语法，尚未运行外部仿真；仿真结果也不能替代实体试钩。")
        st.caption("可识别操作式保留针法顺序及明确的 FLO/BLO；挑针范围不清时停止该部件导出。"
                   "仅文字描述的错位和收口动作需对照原图解核对。")
        try:
            if not _v["ok"]:
                raise ValueError("请先修复图解自检错误")
            _parade = cached_export(
                export_cache, "parade", {"params": serializable_params, "export_version": software_version()},
                lambda: parade_payload(result))
            _parade_text = _parade["text"]
            if _parade["inferred_rounds"]:
                st.caption(f"{_parade['inferred_rounds']} 个实体圈次仅按数值均匀安排针位；"
                           "其余可识别操作式保留针法顺序，特殊工艺及文字错位提示仍需核对。")
            if not _parade["complete"]:
                st.warning("仅导出部分图解；不可视为完整验证："
                           f"{_parade['exported_rounds']}/{_parade['requested_rounds']} 圈次，"
                           f"{_parade['exported_parts']}/{_parade['requested_parts']} 个完整实体部件。")
            _parade_issues = _parade["issues"]
            if _parade_issues:
                st.warning("导出自检提示：\n" + "\n".join(md_safe(i)
                                                       for i in _parade_issues))
            st.code(_parade_text, language=None)
            st.download_button(
                "下载 CrochetPARADE DSL",
                _parade_text,
                file_name="amigurumi_parade.txt",
                mime="text/plain",
                key=f"dl_parade_{result_key}")
        except Exception as e:
            st.caption(f"CrochetPARADE 导出不可用: {md_safe(e)}")

    with st.expander("最近一次导出耗时"):
        st.json(export_record.get("diagnostics", {}))

    # Inline Markdown preview
    with st.expander("预览 Markdown 图解", expanded=False):
        st.markdown(md_content)
