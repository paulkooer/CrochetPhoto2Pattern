"""Photo2Amigurumi — Streamlit entry point.

入口只做四件事：全局配置、侧栏、三个 Tab 的分发、页脚。
各 Tab 的具体 UI 在 app/ui/ 对应模块中，导出工具在 app/utils/。
"""
from __future__ import annotations

import logging

import streamlit as st
from dotenv import load_dotenv

from app.ui.design_system import apply_design_system, render_hero
from app.ui.sidebar import render_sidebar
from app.ui.tab_grid import render_tab_grid
from app.ui.tab_manual import render_tab_manual
from app.ui.tab_photo import render_tab_photo

load_dotenv()
# 仅在根 logger 尚无 handler 时配置（以库形式 import app.main 时不劫持宿主配置）
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

st.set_page_config(page_title="Photo2Amigurumi", page_icon="🧶", layout="wide")
apply_design_system()
render_hero()

# U8：分享链接载入（?p=<token>）。V3：result_id 必须唯一——固定
# "shared" 会让两次"存入历史"互相覆盖（rid 是历史表主键）
_qp = st.query_params
if "p" in _qp and "result" not in st.session_state:
    import uuid as _uuid

    from app.utils.share import decode_result
    _shared = decode_result(_qp["p"])
    if _shared:
        # V5：与备份导入同级的校验（坏 token 不进 session）
        from app.ui.result_renderer import _rebuild_params, _validated_backup
        try:
            analysis, structure = _validated_backup(_shared)
            _shared["params"] = _rebuild_params(dict(_shared["params"]))
            _shared["analysis"] = analysis
            _shared["structure"] = structure
        except Exception:
            st.error("分享链接内容无效或已损坏，无法载入")
            _shared = None
    if _shared:
        _shared["result_id"] = _uuid.uuid4().hex[:12]
        st.session_state["result"] = _shared
        st.info("🔗 已通过分享链接载入图解——可点结果页「🗂 存入历史」"
                "永久保留到本机")

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
st.caption("Photo2Amigurumi — AI 驱动的立体钩织图解生成器")
