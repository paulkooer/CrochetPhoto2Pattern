"""Photo2Amigurumi — Streamlit entry point.

入口只做四件事：全局配置、侧栏、三个 Tab 的分发、页脚。
各 Tab 的具体 UI 在 app/ui/ 对应模块中，导出工具在 app/utils/。
"""
from __future__ import annotations

import logging

import streamlit as st
from dotenv import load_dotenv

from app.ui.sidebar import render_sidebar
from app.ui.tab_grid import render_tab_grid
from app.ui.tab_manual import render_tab_manual
from app.ui.tab_photo import render_tab_photo

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

st.set_page_config(page_title="Photo2Amigurumi", page_icon="🧶", layout="wide")
st.title("🧶 Photo2Amigurumi")
st.markdown("**从一张照片 → 立体人物钉织完整图解** (Amigurumi 风格)")

render_sidebar()

tab_photo, tab_manual, tab_grid = st.tabs(
    ["📸 照片识别（AI）", "✏️ 手动输入", "📹 2D 像素网格"]
)
with tab_photo:
    render_tab_photo()
with tab_manual:
    render_tab_manual()
with tab_grid:
    render_tab_grid()

st.divider()
st.caption("Photo2Amigurumi — AI 驱动的立体钉织图解生成器")
