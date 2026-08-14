"""Sidebar: API key configuration."""
from __future__ import annotations

import streamlit as st


def render_sidebar() -> None:
    with st.sidebar:
        st.header("⚙️ 设置")
        openai_key = st.text_input("OpenAI API Key", type="password",
                                    value=st.session_state.get("openai_key", ""))
        anthropic_key = st.text_input("Anthropic API Key (推荐)", type="password",
                                       value=st.session_state.get("anthropic_key", ""))
        if openai_key:
            st.session_state.openai_key = openai_key
        if anthropic_key:
            st.session_state.anthropic_key = anthropic_key

        has_key = bool(openai_key or anthropic_key)
        if has_key:
            st.success("✅ API Key 已设置")
        else:
            st.warning("未设置 API Key，将使用 Mock 数据演示")
