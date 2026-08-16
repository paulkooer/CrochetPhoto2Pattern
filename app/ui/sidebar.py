"""Sidebar: API key configuration."""
from __future__ import annotations

import streamlit as st


def render_sidebar() -> None:
    with st.sidebar:
        st.header("⚙️ 设置")
        # 无条件写回（含空串）：否则用户清空输入框后旧 key 仍残留在
        # session_state 且会在下次 rerun 时回填输入框，造成"删不掉"的假象。
        openai_key = st.text_input(
            "OpenAI API Key", type="password",
            value=st.session_state.get("openai_key", ""),
            key="openai_key_input",
        ).strip()
        anthropic_key = st.text_input(
            "Anthropic API Key (推荐)", type="password",
            value=st.session_state.get("anthropic_key", ""),
            key="anthropic_key_input",
        ).strip()
        st.session_state.openai_key = openai_key
        st.session_state.anthropic_key = anthropic_key

        if openai_key or anthropic_key:
            st.success("✅ API Key 已设置")
            st.caption("输入框内容优先于 .env；清空输入框即回退到 .env（未配置则 Mock）")
        else:
            st.warning("未在输入框设置 API Key")
            st.caption(
                "若 .env 中配置了 Key 仍会使用（并真实计费）；无 Key 时照片 Tab 默认走本地视觉估算"
                "（免费、基于照片），也可切换 Mock 演示。"
                "⚠️ 请勿在多人共享的部署上输入 API Key。"
            )
