"""Tab 3: 2D pixel-grid pattern (tapestry crochet / C2C / cross-stitch)."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from app.models.gauge import gauge_from_ui
from app.models.grid_pattern import (
    GRID_PROJECT_MAX_BYTES,
    crop_image_fraction,
    export_grid_markdown,
    export_grid_project,
    generate_grid_pattern,
    grid_pattern_from_payload,
    grid_pattern_to_payload,
    import_grid_project,
    recolor_grid_cell,
    recolor_grid_region,
    render_c2c_chart,
    render_legend_html,
    render_legend_markdown,
    render_svg,
    render_text_chart,
)
from app.utils.images import load_uploaded_image_cached

_GRID_HISTORY_LIMIT = 5


def _bounded_history_append(history: list, payload: dict) -> None:
    """Keep only lightweight grid payloads, never rendered SVG/chart strings."""
    history.append(payload)
    if len(history) > _GRID_HISTORY_LIMIT:
        del history[:-_GRID_HISTORY_LIMIT]


def _rendered_grid_view(pattern) -> dict:
    """Build the cached render bundle plus a lightweight editable grid."""
    legend = render_legend_markdown(pattern)
    chart = render_text_chart(pattern)
    c2c = render_c2c_chart(pattern)
    return {
        "width": pattern.width,
        "height": pattern.height,
        "clamped_from": pattern.clamped_from,
        "n_colors": len(pattern.palette),
        "pattern_payload": grid_pattern_to_payload(pattern),
        "project_json": export_grid_project(pattern),
        "svg": render_svg(pattern, cell_px=14),
        "legend": legend,
        "legend_html": render_legend_html(pattern),
        "chart": chart,
        "c2c": c2c,
        "markdown": export_grid_markdown(
            pattern, legend=legend, chart=chart, c2c=c2c),
    }


def _reset_grid_editor_state() -> None:
    """Clear dimension-dependent widgets when installing a different grid."""
    prefixes = (
        "grid_edit_row", "grid_edit_col", "grid_edit_color_",
        "grid_edit_mode", "grid_region_",
    )
    for key in list(st.session_state):
        if key.startswith(prefixes):
            del st.session_state[key]
    st.session_state.grid_undo_stack = []
    st.session_state.grid_redo_stack = []


def render_tab_grid() -> None:
    st.subheader("🎨 制作平面像素图案")
    st.markdown(
        "<p class='crochet-section-note'>将照片整理成彩色针目网格，适合平面嵌花钩织、"
        "C2C 或十字绣。每格代表 1 针，符号对应一种毛线颜色。</p>",
        unsafe_allow_html=True,
    )

    with st.expander("📂 恢复可编辑网格工程", expanded=False):
        project_file = st.file_uploader(
            "上传此前下载的网格工程 JSON",
            type=["json"],
            key="grid_project_uploader",
            help="只接受本应用导出的、版本兼容且不超过 1MB 的网格工程。",
        )
        if project_file is not None and st.button(
            "恢复网格工程", key="grid_restore_project", width="stretch"
        ):
            try:
                if project_file.size > GRID_PROJECT_MAX_BYTES:
                    raise ValueError("grid project exceeds the size limit")
                restored_pattern = import_grid_project(project_file.getvalue())
                _reset_grid_editor_state()
                st.session_state.grid_view = _rendered_grid_view(restored_pattern)
                st.session_state.grid_project_notice = (
                    f"已恢复 {restored_pattern.width} × {restored_pattern.height} "
                    "可编辑网格")
                st.rerun()
            except ValueError as exc:
                st.error(f"网格工程恢复失败：{exc}")
    restore_notice = st.session_state.pop("grid_project_notice", None)
    if restore_notice:
        st.success(f"✅ {restore_notice}，撤销/重做历史已重新开始。")

    col_g1, col_g2 = st.columns([1, 1])
    with col_g1:
        grid_file = st.file_uploader(
            "上传图片", type=["jpg", "jpeg", "png"],
            key="grid_uploader",
            help="建议上传轮廓清晰、颜色对比度高的图片",
        )
    with col_g2:
        grid_width = st.slider("网格宽度（针数/行）", 10, 80, 40, 5, key="grid_w")
        n_colors = st.slider("颜色数量", 2, 10, 6, 1, key="grid_nc")
        _g = gauge_from_ui(st.session_state.get("gauge_preset", "classic"),
                           st.session_state.get("gauge_st_input"),
                           st.session_state.get("gauge_rw_input"))
        _gauge_wh = round(_g.aspect_wh, 2)
        # 按小样推导的比例可能与固定选项等值（如 16针×12行 → 0.75），
        # 去重保持顺序，避免滑块出现双刻度
        _options = []
        for _o in (0.5, 0.6, 0.75, _gauge_wh, 1.0):
            if _o not in _options:
                _options.append(_o)
        _fmt = {0.5: "长针 dc (~0.5)", 0.6: "中长 hdc (~0.6)",
                0.75: "短针 sc (~0.75)", 1.0: "正方"}
        aspect = st.select_slider(
            "针法比例",
            options=_options,
            value=0.75,
            format_func=lambda x: _fmt.get(x, f"按小样 ({_gauge_wh})"),
            key="grid_aspect",
        )
        resample = st.select_slider(
            "缩放算法",
            options=["lanczos", "nearest"],
            value="lanczos",
            format_func={"lanczos": "平滑（照片）", "nearest": "锐利（像素画）"}.get,
            key="grid_resample",
        )

    if grid_file:
        grid_image = load_uploaded_image_cached(grid_file)
        if grid_image is not None:
            with st.expander("✂️ 生成前裁剪与定位", expanded=False):
                crop_x = st.slider(
                    "横向保留范围（左 → 右，%）", 0, 100, (0, 100), 1,
                    key="grid_crop_x")
                crop_y = st.slider(
                    "纵向保留范围（上 → 下，%）", 0, 100, (0, 100), 1,
                    key="grid_crop_y")
                if crop_x[0] == crop_x[1] or crop_y[0] == crop_y[1]:
                    st.error("裁剪范围必须保留非零宽度和高度。")
                    cropped_image = None
                else:
                    cropped_image = crop_image_fraction(
                        grid_image,
                        crop_x[0] / 100.0,
                        crop_y[0] / 100.0,
                        crop_x[1] / 100.0,
                        crop_y[1] / 100.0,
                    )
                    st.image(
                        cropped_image,
                        caption=(f"裁剪预览：{cropped_image.width} × "
                                 f"{cropped_image.height}px"),
                        width="stretch",
                    )
                st.caption("裁剪会改变构图和网格高宽比；调整后请重新生成。")

            if cropped_image is not None and st.button(
                "🎨 生成网格图案", type="primary", width="stretch", key="btn_grid"
            ):
                with st.spinner("生成中…"):
                    pattern = generate_grid_pattern(
                        cropped_image, grid_width=grid_width,
                        n_colors=n_colors, aspect_ratio=aspect, resample=resample,
                    )
                    # 预渲染字符串保证普通 rerun 轻量；额外保存纯整数色板索引，
                    # 仅在用户明确修色时恢复 GridPattern 并重新渲染。
                    _reset_grid_editor_state()
                    st.session_state.grid_view = _rendered_grid_view(pattern)

    if "grid_view" in st.session_state:
        view = st.session_state.grid_view
        _clamp_note = (f"（原始比例需 {view['clamped_from']:,} 行，已达单元上限，"
                       f"已钳至 {view['height']:,} 行——建议先裁剪图片）"
                       if view.get("clamped_from") else "")
        st.success(f"✅ 网格大小：{view['width']} 列 × {view['height']} 行，"
                   f"{view['n_colors']} 种颜色 {_clamp_note}")

        if view.get("pattern_payload"):
            undo_stack = st.session_state.setdefault("grid_undo_stack", [])
            redo_stack = st.session_state.setdefault("grid_redo_stack", [])
            history_c1, history_c2 = st.columns(2)
            with history_c1:
                if st.button(
                    "↶ 撤销修色", key="grid_undo", width="stretch",
                    disabled=not undo_stack,
                ):
                    previous_payload = undo_stack.pop()
                    _bounded_history_append(
                        redo_stack, view["pattern_payload"])
                    st.session_state.grid_view = _rendered_grid_view(
                        grid_pattern_from_payload(previous_payload))
                    st.session_state.grid_edit_notice = "已撤销最近一次修色"
                    st.rerun()
            with history_c2:
                if st.button(
                    "↷ 重做修色", key="grid_redo", width="stretch",
                    disabled=not redo_stack,
                ):
                    next_payload = redo_stack.pop()
                    _bounded_history_append(
                        undo_stack, view["pattern_payload"])
                    st.session_state.grid_view = _rendered_grid_view(
                        grid_pattern_from_payload(next_payload))
                    st.session_state.grid_edit_notice = "已重做最近一次修色"
                    st.rerun()

            with st.expander("✏️ 单格 / 矩形修色（不重新量化图片）", expanded=False):
                edit_mode = st.radio(
                    "编辑范围", ["单格", "矩形"], horizontal=True,
                    key="grid_edit_mode")
                # 普通 rerun 只读两个整数/短色板；GridPattern（最多 8 万个
                # GridCell）仅在点击“应用”时恢复，保持预渲染缓存的性能收益。
                payload = view["pattern_payload"]
                palette_entries = payload["palette"]
                palette_names = [entry["name"] for entry in palette_entries]
                if edit_mode == "单格":
                    edit_c1, edit_c2 = st.columns(2)
                    with edit_c1:
                        crochet_row = int(st.number_input(
                            "行号（从成品底部向上）", min_value=1,
                            max_value=int(view["height"]), value=1, step=1,
                            key="grid_edit_row"))
                    with edit_c2:
                        crochet_col = int(st.number_input(
                            "列号（从左向右）", min_value=1,
                            max_value=int(view["width"]), value=1, step=1,
                            key="grid_edit_col"))
                    image_row_start = int(view["height"]) - crochet_row
                    image_row_end = image_row_start
                    image_col_start = crochet_col - 1
                    image_col_end = image_col_start
                    current_index = int(
                        payload["cells"][image_row_start][image_col_start])
                    current_name = palette_names[current_index]
                    color_label = f"替换颜色（当前：{current_name}）"
                    color_key = f"grid_edit_color_{crochet_row}_{crochet_col}"
                    apply_label = "应用到该格"
                    edit_description = f"R{crochet_row} / C{crochet_col}"
                else:
                    row_c1, row_c2 = st.columns(2)
                    with row_c1:
                        crochet_row_start = int(st.number_input(
                            "起始行（从底部向上）", min_value=1,
                            max_value=int(view["height"]), value=1, step=1,
                            key="grid_region_row_start"))
                    with row_c2:
                        crochet_row_end = int(st.number_input(
                            "结束行（含，端点顺序不限）", min_value=1,
                            max_value=int(view["height"]), value=1, step=1,
                            key="grid_region_row_end"))
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        crochet_col_start = int(st.number_input(
                            "起始列（从左向右）", min_value=1,
                            max_value=int(view["width"]), value=1, step=1,
                            key="grid_region_col_start"))
                    with col_c2:
                        crochet_col_end = int(st.number_input(
                            "结束列（含，端点顺序不限）", min_value=1,
                            max_value=int(view["width"]), value=1, step=1,
                            key="grid_region_col_end"))
                    crochet_row_start, crochet_row_end = sorted(
                        (crochet_row_start, crochet_row_end))
                    crochet_col_start, crochet_col_end = sorted(
                        (crochet_col_start, crochet_col_end))
                    image_row_start = int(view["height"]) - crochet_row_end
                    image_row_end = int(view["height"]) - crochet_row_start
                    image_col_start = crochet_col_start - 1
                    image_col_end = crochet_col_end - 1
                    current_index = int(
                        payload["cells"][image_row_start][image_col_start])
                    color_label = "矩形替换颜色"
                    color_key = (
                        f"grid_region_color_{crochet_row_start}_"
                        f"{crochet_row_end}_{crochet_col_start}_{crochet_col_end}")
                    apply_label = "应用到矩形区域"
                    edit_description = (
                        f"R{crochet_row_start}–R{crochet_row_end} / "
                        f"C{crochet_col_start}–C{crochet_col_end}")

                selected_name = st.selectbox(
                    color_label,
                    palette_names,
                    index=current_index,
                    key=color_key,
                )
                if st.button(apply_label, key="grid_apply_cell"):
                    editable_pattern = grid_pattern_from_payload(payload)
                    selected_index = palette_names.index(selected_name)
                    if edit_mode == "单格":
                        changed = recolor_grid_cell(
                            editable_pattern,
                            image_row_start,
                            image_col_start,
                            selected_index,
                        )
                    else:
                        changed = recolor_grid_region(
                            editable_pattern,
                            image_row_start,
                            image_row_end,
                            image_col_start,
                            image_col_end,
                            selected_index,
                        )
                    if changed:
                        _bounded_history_append(undo_stack, payload)
                        redo_stack.clear()
                        st.session_state.grid_view = _rendered_grid_view(
                            editable_pattern)
                        st.session_state.grid_edit_notice = (
                            f"{edit_description} 中 {changed} 格已改为{selected_name}")
                        st.rerun()
                    else:
                        st.info("所选区域已经全部是该颜色，没有产生修改。")
                edit_notice = st.session_state.pop("grid_edit_notice", None)
                if edit_notice is not None:
                    st.success(
                        f"✅ 网格修色：{edit_notice}；"
                        "已同步到预览、图例和下载文件。")
                st.caption(
                    f"仅可换成当前毛线色板中的颜色；行号与文字符号图一致。"
                    f"撤销/重做各保留最近 {_GRID_HISTORY_LIMIT} 步。")
        else:
            st.caption("当前为旧版缓存网格；重新生成后可使用裁剪和网格修色。")

        col_v1, col_v2 = st.columns([3, 1])
        with col_v1:
            st.subheader("🖼️ 彩色网格预览")
            # components.html 比 st.markdown(unsafe_allow_html=True) 对 <svg>
            # 的渲染更稳定（markdown 管线对内联 SVG 的 sanitize 行为随版本波动），
            # 且 iframe 自带滚动，大网格无需外层 div。
            components.html(view["svg"], height=600, scrolling=True)
        with col_v2:
            st.subheader("📋 颜色图例")
            # 屏幕版图例带真实色块（色名→色表 RGB）；下载版仍用纯 Markdown
            st.markdown(view["legend_html"], unsafe_allow_html=True)

        st.subheader("📝 文字符号图表")
        with st.expander("展开查看 / 复制到聊天", expanded=False):
            st.code(view["chart"], language="")
        with st.expander("🧶 C2C 逐行指令（对角行）", expanded=False):
            st.code(view["c2c"], language="")

        # Downloads（复用已渲染的字符串，不再二次渲染）
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.download_button(
                "📥 下载 SVG 网格图",
                view["svg"],
                file_name="tapestry_grid.svg",
                mime="image/svg+xml",
            )
        with col_d2:
            st.download_button(
                ("📄 下载完整 Markdown 图解"
                 if view.get("markdown") else "📄 下载 Markdown 图例"),
                view.get("markdown") or view["legend"],
                file_name=("tapestry_pattern.md"
                           if view.get("markdown") else "tapestry_legend.md"),
                mime="text/markdown",
            )
        with col_d3:
            if view.get("project_json"):
                st.download_button(
                    "💾 下载可编辑工程",
                    view["project_json"],
                    file_name="tapestry_grid_project.json",
                    mime="application/json",
                )
            else:
                st.caption("旧缓存需重新生成后才能保存工程")
