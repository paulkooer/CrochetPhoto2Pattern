"""Sidebar: API key configuration."""
from __future__ import annotations

import streamlit as st


def render_sidebar() -> None:
    with st.sidebar:
        st.header("🧺 创作设置")
        st.caption("先选择密度与塑形偏好，再开始生成你的专属钩织图解。")
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

        # 中转站（自定义 API 地址）：UI URL 必须和 UI Key 成对，不能
        # 回退搭配服务器环境 Key；否则共享部署会把服务器密钥发给用户 URL。
        with st.expander("🔗 中转站地址（可选）", expanded=False):
            openai_base = st.text_input(
                "OpenAI Base URL",
                value=st.session_state.get("openai_base_url", ""),
                key="openai_base_url_input",
                placeholder="https://api.openai.com/v1",
                help="第三方 API 代理/中转站地址。填写时必须同时在上方输入"
                     "你自己的 OpenAI Key；留空 = 官方默认",
            ).strip()
            anthropic_base = st.text_input(
                "Anthropic Base URL",
                value=st.session_state.get("anthropic_base_url", ""),
                key="anthropic_base_url_input",
                placeholder="https://api.anthropic.com",
                help="填写时必须同时在上方输入你自己的 Anthropic Key；"
                     "留空 = 官方默认",
            ).strip()
        if openai_base and not openai_key:
            st.warning("OpenAI 自定义地址必须同时提供你自己的 OpenAI Key。")
        if anthropic_base and not anthropic_key:
            st.warning("Anthropic 自定义地址必须同时提供你自己的 Anthropic Key。")
        st.session_state.openai_base_url = openai_base or None
        st.session_state.anthropic_base_url = anthropic_base or None

        st.divider()
        st.subheader("🧵 编织密度（小样）")
        preset = st.select_slider(
            "密度预设",
            options=["classic", "dk", "fine", "custom"],
            value="classic",
            format_func={"classic": "经典图解(粗线)", "dk": "DK 中粗",
                         "fine": "紧密玩偶(2.5mm)", "custom": "自定义"}.get,
            key="gauge_preset",
            help="钩 10×10cm 小样数一下针数×行数再选/填——所有尺寸、网格比例、"
                 "材料标签都由它推导（消除两层隐含几何互相矛盾的问题）",
        )
        # widget 值经 key 由消费方直接读取（对带 key 的 widget 赋
        # session_state 是 Streamlit 禁止操作）
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.number_input(
                "10cm 针数", 6.0, 40.0, 13.0, 0.5, key="gauge_st_input",
                disabled=preset != "custom")
        with col_g2:
            st.number_input(
                "10cm 行数", 8.0, 50.0, 16.0, 0.5, key="gauge_rw_input",
                disabled=preset != "custom")

        st.divider()
        with st.expander("🎛 塑形选项（进阶）", expanded=False):
            st.select_slider(
                "头部球体", options=["ladder", "ideal", "egg"], value="ladder",
                format_func={"ladder": "经典阶梯球（图解通行）",
                             "ideal": "理想球（sinθ，更圆）",
                             "egg": "蛋形（下半收窄）"}.get,
                key="style_sphere",
                help="阶梯球=发布图解通用做法；理想球逐圈针数按 sin 极角分布"
                     "（mspremiseconclusion 2010），布料量更接近真球；蛋形为"
                     "玩偶头主流形状",
            )
            st.checkbox("头身一体钩（免缝合）", value=False, key="style_onepiece",
                        help="头收针到颈围后不断线直接钩身体")
            st.select_slider(
                "裙子做法", options=["ring", "attached"], value="ring",
                format_func={"ring": "独立裙筒（腰部环起）",
                             "attached": "挑后半针（钩在身体上）"}.get,
                key="style_skirt",
            )
            st.checkbox("波浪裙摆（末圈每针放2针）", value=False, key="style_ruffle")

        if openai_key or anthropic_key:
            st.success("✅ API Key 已设置")
            st.caption("输入框内容优先于 .env；清空输入框即回退到 .env（未配置则进入免费模式）")
        else:
            st.warning("未在输入框设置 API Key")
            st.caption(
                "若 .env 中配置了 Key 仍会使用（并真实计费）；照片 Tab 可在"
                "「AI 视觉解析 / 本地视觉估算」间选择。输入框与 .env 都无 Key 时"
                "默认走本地视觉估算（免费、基于照片），也可切换 Mock 演示。"
                "⚠️ 请勿在多人共享的部署上输入 API Key。"
            )

        # ── 图解历史（S4）：SQLite 本机持久化，跨会话载回 ─────────────────
        st.divider()
        with st.expander("🗂 我的图解（历史）", expanded=False):
            from app.ui.result_renderer import purge_result_state
            from app.utils import history

            _search = st.text_input("搜索历史", "", key="hist_search",
                                    placeholder="关键词（体型/部件…）")
            try:
                items = history.list_results(query=_search.strip() or None)
            except Exception as e:  # DB 损坏不阻塞主功能
                st.caption(f"历史读取失败: {e}")
                items = []
            if not items:
                st.caption("暂无匹配的历史——生成图解后点「存入历史」即可跨会话保留")
            for it in items:
                c_h1, c_h2, c_h3 = st.columns([5, 1, 1])
                # U8/K2：缩略图随行返回（无 N+1 全量读取）；
                # U25 方案(b)：分享/导入路径无 preview → 占位标记
                if it.get("preview"):
                    c_h1.image(it["preview"], width=64)
                else:
                    c_h1.markdown("<div style='width:64px;height:44px;"
                                  "display:flex;align-items:center;"
                                  "justify-content:center;border:1px dashed #ccc;"
                                  "border-radius:6px;'>🧶</div>",
                                  unsafe_allow_html=True)
                _display = it.get("title") or it["summary"]
                c_h1.caption(f"{history.format_time(it['created_at'])}\n\n{_display}")
                if c_h2.button("载入", key=f"hist_load_{it['rid']}"):
                    data = history.load_result(it["rid"])
                    if data is None:
                        st.error("该记录已不存在")
                    else:
                        # V5：与备份导入同等待遇——历史记录可能是当初
                        # 存入的坏结果（JSON 修正改坏后存档），直接入库
                        # 会崩在渲染层；在此校验并给出 st.error + 删除出路
                        try:
                            from app.ui.result_renderer import _validated_backup
                            analysis, structure = _validated_backup(data)
                            from app.ui.result_renderer import _rebuild_params
                            data["params"] = _rebuild_params(dict(data["params"]))
                            data["analysis"] = analysis
                            data["structure"] = structure
                        except Exception as e:
                            st.error(f"该记录已损坏，无法载入（可点「删」清除）: {e}")
                            st.stop()
                        if "result" in st.session_state:
                            purge_result_state(st.session_state["result"])
                        data.setdefault("result_id", it["rid"])
                        st.session_state["result"] = data
                        st.rerun()
                if c_h3.button("删", key=f"hist_del_{it['rid']}"):
                    history.delete_result(it["rid"])
                    st.rerun()
