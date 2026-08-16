"""Tab 3: 2D pixel-grid pattern (tapestry crochet / C2C / cross-stitch)."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from app.models.gauge import gauge_from_ui
from app.models.grid_pattern import (
    generate_grid_pattern,
    render_legend_markdown,
    render_svg,
    render_text_chart,
)
from app.utils.images import load_uploaded_image_cached


def render_tab_grid() -> None:
    st.subheader("📹 2D 像素网格图案（Tapestry Crochet）")
    st.info(
        "将照片转化为彩色网格图案，适合平面嵌花钩织（Tapestry）、"
        "C2C（角对角）或十字绣。每格 = 1 针，符号代表毛线颜色。"
    )

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
        _options = [0.5, 0.6, 0.75, _gauge_wh, 1.0]
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
        if grid_image is not None and st.button(
            "🎨 生成网格图案", type="primary", use_container_width=True, key="btn_grid"
        ):
            with st.spinner("生成中…"):
                pattern = generate_grid_pattern(
                    grid_image, grid_width=grid_width,
                    n_colors=n_colors, aspect_ratio=aspect, resample=resample,
                )
                # 只在此处渲染一次，存轻量字符串视图：GridPattern 含上万
                # GridCell 对象，且每次 rerun 重渲染 SVG 是纯浪费。
                st.session_state.grid_view = {
                    "width": pattern.width,
                    "height": pattern.height,
                    "n_colors": len(pattern.palette),
                    "svg": render_svg(pattern, cell_px=14),
                    "legend": render_legend_markdown(pattern),
                    "chart": render_text_chart(pattern),
                }

    if "grid_view" in st.session_state:
        view = st.session_state.grid_view
        st.success(f"✅ 网格大小：{view['width']} 列 × {view['height']} 行，{view['n_colors']} 种颜色")

        col_v1, col_v2 = st.columns([3, 1])
        with col_v1:
            st.subheader("🖼️ 彩色网格预览")
            # components.html 比 st.markdown(unsafe_allow_html=True) 对 <svg>
            # 的渲染更稳定（markdown 管线对内联 SVG 的 sanitize 行为随版本波动），
            # 且 iframe 自带滚动，大网格无需外层 div。
            components.html(view["svg"], height=600, scrolling=True)
        with col_v2:
            st.subheader("📋 颜色图例")
            st.markdown(view["legend"])

        st.subheader("📝 文字符号图表")
        with st.expander("展开查看 / 复制到聊天", expanded=False):
            st.code(view["chart"], language="")

        # Downloads（复用已渲染的字符串，不再二次渲染）
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                "📥 下载 SVG 网格图",
                view["svg"],
                file_name="tapestry_grid.svg",
                mime="image/svg+xml",
            )
        with col_d2:
            st.download_button(
                "📄 下载 Markdown 图例",
                view["legend"],
                file_name="tapestry_legend.md",
                mime="text/markdown",
            )
