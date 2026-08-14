"""Tab 3: 2D pixel-grid pattern (tapestry crochet / C2C / cross-stitch)."""
from __future__ import annotations

import streamlit as st
from PIL import Image

from app.models.grid_pattern import (
    generate_grid_pattern, render_svg, render_legend_markdown, render_text_chart
)


def render_tab_grid() -> None:
    st.subheader("📹 2D 像素网格图案（Tapestry Crochet）")
    st.info(
        "将照片转化为彩色网格图案，适合平面采花钉织、C2C 角路派或十字绣。"
        "每格 = 1 针，符号代表毛线颜色。"
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
        aspect = st.select_slider(
            "针法比例",
            options=[0.5, 0.6, 0.75, 1.0],
            value=0.75,
            format_func=lambda x: {0.5: "长针 dc (~0.5)", 0.6: "中长 hdc (~0.6)",
                                    0.75: "短针 sc (~0.75)", 1.0: "正方"}[x],
            key="grid_aspect",
        )

    if grid_file:
        grid_image = Image.open(grid_file)
        if st.button("🎨 生成网格图案", type="primary",
                     use_container_width=True, key="btn_grid"):
            with st.spinner("生成中…"):
                pattern = generate_grid_pattern(
                    grid_image, grid_width=grid_width,
                    n_colors=n_colors, aspect_ratio=aspect,
                )
            st.session_state.grid_pattern = pattern

    if "grid_pattern" in st.session_state:
        pat = st.session_state.grid_pattern
        st.success(f"✅ 网格大小：{pat.width} 列 × {pat.height} 行，{len(pat.palette)} 种颜色")

        col_v1, col_v2 = st.columns([3, 1])
        with col_v1:
            st.subheader("🖼️ 彩色网格预览")
            svg_str = render_svg(pat, cell_px=14)
            # Wrap in scrollable div for large grids
            st.markdown(
                f'<div style="overflow:auto;max-height:600px;border:1px solid #ccc;border-radius:6px;padding:4px;">'
                + svg_str + "</div>",
                unsafe_allow_html=True,
            )
        with col_v2:
            st.subheader("📋 颜色图例")
            st.markdown(render_legend_markdown(pat))

        st.subheader("📝 文字符号图表")
        with st.expander("展开查看 / 复制到聊天", expanded=False):
            st.code(render_text_chart(pat), language="")

        # Downloads
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                "📥 下载 SVG 网格图",
                render_svg(pat, cell_px=14),
                file_name="tapestry_grid.svg",
                mime="image/svg+xml",
            )
        with col_d2:
            st.download_button(
                "📄 下载 Markdown 图例",
                render_legend_markdown(pat),
                file_name="tapestry_legend.md",
                mime="text/markdown",
            )
