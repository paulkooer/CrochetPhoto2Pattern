"""Result renderer: analysis / structure / pattern / progress / edit-regenerate.

被照片 Tab 与手动 Tab 复用。widget key 全部以 result_id 为命名空间，
保证两份结果同屏渲染不冲突、重新生成后进度不串档。
"""
from __future__ import annotations

import html
import json
import uuid

import streamlit as st

from app.models.crochet_params import refresh_derived
from app.schemas import PART_NAMES, CrochetPart, CrochetStitch
from app.utils.exporters import export_markdown

# 以 result_id 为命名空间的 widget key 前缀（chk_/all_/clear_ 后跟 `rid_…`，
# 其余后跟 `rid` 本体）。旧结果被替换时用 purge_result_state 清理。
_WIDGET_KEY_PREFIXES = (
    "chk_", "all_", "clear_", "json_edit_", "regen_", "dl_json_", "dl_md_",
    "dl_backup_", "import_", "importbtn_",
)


def _rebuild_params(corrected: dict) -> dict:
    """把用户 JSON 中的 parts 重建为 CrochetPart 并重算派生量（regen/导入共用）。"""
    rebuilt_parts = []
    for p in corrected.get("parts", []):
        p = dict(p)  # 不原地改动用户输入
        raw_rounds = p.pop("rounds", [])
        # rows 由 len(rounds) 派生（schema 已无该字段），丢弃过期值防失同步。
        p.pop("rows", None)
        rounds = [CrochetStitch(**r) for r in raw_rounds]
        rebuilt_parts.append(CrochetPart(rounds=rounds, **p))
    corrected["parts"] = rebuilt_parts
    # 时长/总针数/材料克数是 parts 的派生量，必须随编辑重算。
    refresh_derived(corrected)
    return corrected


def purge_result_state(result: dict) -> None:
    """Drop widget state namespaced to a result that is about to be replaced.

    result_id 每次生成都不同，若不清理，逐圈 checkbox 等几十个 key 会在
    session_state 中随使用次数无限累积。
    """
    rid = result.get("result_id")
    if not rid:
        return
    for key in list(st.session_state.keys()):
        if key.startswith(tuple(p + rid for p in _WIDGET_KEY_PREFIXES)):
            del st.session_state[key]


def render_results(result: dict, slot: str) -> None:
    """Render the result UI. `slot` is the st.session_state key holding `result`,
    so edits/regeneration write back to the tab that owns this result."""
    analysis = result["analysis"]
    structure = result["structure"]
    params = result["params"]
    # Widget-key namespace: unique per generated result, stable across reruns.
    # Fallback to the stable slot name — id(result) may be reused across reruns.
    result_key = result.get("result_id") or slot

    st.divider()

    # Section 1: Analysis
    st.subheader("1️⃣ 人物语义解析")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("体型", analysis["body_type"])
        st.metric("难度", analysis["difficulty"])
    with col_b:
        st.metric("头部直径", f"{analysis['head_diameter_cm']} cm")
        st.metric("整体高度", f"{analysis['height_cm']} cm")
    st.write("**主要特征**:", ", ".join(analysis["main_features"]))
    st.write("**识别部件**:", ", ".join(analysis["parts"]))

    # 规范名之外的部件会被降级为小球处理——只在日志里提示用户看不见，
    # 这里补一条 UI 内提示
    unknown = [p for p in analysis.get("parts", []) if p not in PART_NAMES]
    if unknown:
        st.caption(f"⚠️ 未识别的部件 {('、'.join(unknown))} 将按小配件（球）处理")

    # Vision 调用的 token 用量（仅照片 Tab 的真实解析路径会有值）
    usage = result.get("usage") or {}
    if usage.get("input_tokens") is not None:
        st.caption(
            f"📊 Vision 用量（{usage.get('provider', '?')}）："
            f"输入 {usage['input_tokens']} tok · 输出 {usage.get('output_tokens', '?')} tok"
        )

    # 解析来源透明展示：AI（LLM）/ 本地估算 / Mock 三类（vision_meta）
    vmeta = result.get("vision_meta") or {}
    if vmeta.get("source") == "mock":
        st.caption("🎬 Mock 演示数据（与照片内容无关，仅供体验流程）")
    elif vmeta.get("source"):
        source = vmeta["source"]
        label = {
            "anthropic": "🤖 Anthropic Vision（AI 语义解析）",
            "openai": "🤖 OpenAI Vision（AI 语义解析）",
            "opencv-face": "🧮 本地视觉估算（人脸检测）",
            "default": "🧮 本地默认估算",
        }.get(source, f"解析来源：{source}")
        ratio = vmeta.get("body_ratio")
        ratio_str = f"，身高/头径 ≈ {ratio}" if ratio else ""
        st.caption(f"{label}{ratio_str} — {vmeta.get('note', '')}")

    # Color palette swatches (from extract_color_palette)
    colors = analysis.get("recommended_colors") or []
    if not isinstance(colors, list):
        colors = []
    if colors:
        st.write("**🎨 推荐毛线颜色**（按主色占比排序）:")
        # html.escape：颜色名来自模型可写字段，图片内文字可能借 prompt
        # injection 让模型输出 HTML 片段，转义后才能进 unsafe_allow_html。
        swatch_html = (
            "<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;'>"
            + "".join(
                f"<span style='background:#f4f4f4;padding:4px 14px;border-radius:20px;"
                f"font-size:0.85rem;border:1px solid #ccc;'>🧶 {html.escape(c)}</span>"
                for c in colors
            )
            + "</div>"
        )
        st.markdown(swatch_html, unsafe_allow_html=True)
        st.caption("颜色仅供参考，请根据实际毛线颜色调整")

    # Section 2: Structure
    st.subheader("2️⃣ 立体结构设计")
    for part in structure.get("parts", []):
        with st.expander(f"📦 {part['name']} — {part['shape']}"):
            st.json(part)

    # Section 3: Crochet Pattern  (with round progress tracking)
    st.subheader("3️⃣ 钩织参数")
    st.caption(
        "记号：X=短针，V=加针（1针目钩2短针），A=减针（2针并1针）；"
        "(4X,V)×6 = “4短针+1加针”重复 6 次。"
        "螺旋钩法（不引拔不翻转），每圈第一针挂记号扣；减针建议隐形减针（只挑前半针）"
    )
    st.write("**所需材料**:")
    for mat in params.get("materials", []):
        # JSON 编辑器可能把材料改坏（如纯字符串）——渲染层降级显示而非崩溃
        if isinstance(mat, dict):
            st.write(f"  - {mat.get('item', '?')}: {mat.get('quantity', '?')}")
        else:
            st.write(f"  - {mat}")

    # 同名部件（历史坏结果/JSON 编辑复制部件）会生成冲突 widget key → 整页
    # 崩溃；重名时追加序号后缀。正常结果首个部件不带后缀，key 保持稳定。
    seen_names: dict = {}
    for part in params.get("parts", []):
        part_data = part.model_dump() if hasattr(part, "model_dump") else part
        name = part_data.get("name", "?")
        seen_names[name] = seen_names.get(name, 0) + 1
        suffix = "" if seen_names[name] == 1 else f"_{seen_names[name]}"
        part_key = f"{result_key}_{name}{suffix}"
        rounds_list = part_data.get("rounds", [])
        n_rounds = len(rounds_list)
        # 用户在 JSON 编辑器删减圈数后，超过新圈数的旧勾选状态残留在
        # session_state（rid 未变不会被 purge），圈数加回时会"复活"——渲染时清理。
        prefix = f"chk_{part_key}_"
        stale = [
            k for k in st.session_state
            if k.startswith(prefix)
            and k[len(prefix):].isdigit()
            and int(k[len(prefix):]) >= n_rounds
        ]
        for k in stale:
            del st.session_state[k]
        # Checkbox widget state is the single source of truth for progress.
        # It is updated by Streamlit before the rerun, so the counts below
        # already include the click that triggered this run (no one-step lag).
        chk_keys = [f"chk_{part_key}_{i}" for i in range(n_rounds)]
        n_done = sum(bool(st.session_state.get(k)) for k in chk_keys)
        pct = int(n_done / n_rounds * 100) if n_rounds else 0
        label_exp = (
            f"🧶 {part_data['name']} ({n_rounds} 圈)"
            f"  —  ✅ {n_done}/{n_rounds} 圈"
        )
        with st.expander(label_exp):
            st.write(f"**形状**: {part_data['type']} | **颜色**: {part_data['color']}")
            if part_data.get("notes"):
                st.info(part_data["notes"])
            st.progress(pct, text=f"钩织进度 {pct}%  ({n_done}/{n_rounds} 圈)")
            st.markdown("**逐圈进度** — 勾选已完成的圈：")
            col_clear, col_all = st.columns(2)
            with col_clear:
                if st.button("↩️ 重置进度", key=f"clear_{part_key}"):
                    for k in chk_keys:
                        st.session_state[k] = False
                    st.rerun()
            with col_all:
                if st.button("✅ 全部完成", key=f"all_{part_key}"):
                    for k in chk_keys:
                        st.session_state[k] = True
                    st.rerun()
            for i, r in enumerate(rounds_list):
                rd = r if isinstance(r, dict) else r.model_dump() if hasattr(r, "model_dump") else {}
                inc_str = f"+{rd['increase']}" if rd.get("increase") else ""
                dec_str = f"-{rd['decrease']}" if rd.get("decrease") else ""
                change = f" ({inc_str}{dec_str})" if (inc_str or dec_str) else ""
                notes_str = f" — {rd['notes']}" if rd.get("notes") else ""
                color_str = f" · {rd['color']}" if rd.get("color") else ""
                lbl = (f"第 {rd.get('row', i + 1)} 圈：{rd.get('stitches', '?')}针"
                       f"{change}{notes_str}{color_str}")
                st.checkbox(lbl, key=chk_keys[i])

    # Section 4: Assembly
    st.subheader("4️⃣ 装配说明")
    asm = params.get("assembly_instructions") or ""
    st.markdown(asm if isinstance(asm, str) else str(asm))

    # Section 5: Edit & Re-generate
    st.subheader("5️⃣ 局部修正")
    # A5: st.success 后立即 st.rerun() 的话消息会被 rerun 丢弃（用户看不见），
    # 改为 session 标志，下一次 rerun 渲染时弹出。
    _ok_flag = f"regen_{result_key}_ok"
    if st.session_state.pop(_ok_flag, False):
        st.success("✅ 已根据修正更新图解，向上查看结果！")
    st.info("可直接编辑下方 JSON，修改针数或比例后点击 '重新生成'")

    serializable_params = json.loads(
        json.dumps(params, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
                   ensure_ascii=False, indent=2)
    )
    correction_json = st.text_area(
        "编辑 JSON 输出",
        json.dumps(serializable_params, ensure_ascii=False, indent=2),
        height=300,
        key=f"json_edit_{result_key}",
    )

    md_content = export_markdown(params, analysis)

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("🔄 重新生成", key=f"regen_{result_key}"):
            try:
                corrected = json.loads(correction_json)
                st.session_state[slot]["params"] = _rebuild_params(corrected)
                st.session_state[_ok_flag] = True
                st.rerun()
            except Exception as e:
                st.error(f"解析/应用失败: {e}")
    with col_btn2:
        st.download_button(
            "📥 下载 JSON",
            correction_json,
            file_name="amigurumi_pattern.json",
            mime="application/json",
            key=f"dl_json_{result_key}",
        )
    with col_btn3:
        st.download_button(
            "📄 下载 Markdown 图解",
            md_content,
            file_name="amigurumi_pattern.md",
            mime="text/markdown",
            key=f"dl_md_{result_key}",
        )

    # ── 完整结果备份/导入（刷新会丢 session，备份 JSON 可跨会话恢复）───────
    backup_json = json.dumps(
        {"analysis": analysis, "structure": structure, "params": serializable_params},
        ensure_ascii=False,
    )
    col_bk1, col_bk2 = st.columns(2)
    with col_bk1:
        st.download_button(
            "💾 备份完整结果",
            backup_json,
            file_name="amigurumi_backup.json",
            mime="application/json",
            key=f"dl_backup_{result_key}",
            help="含解析/结构/参数的完整结果，可稍后在任意会话导入恢复",
        )
    with col_bk2:
        with st.expander("📂 导入结果备份"):
            pasted = st.text_area(
                "粘贴备份 JSON 内容", height=120, key=f"import_{result_key}"
            )
            if st.button("导入并替换当前结果", key=f"importbtn_{result_key}"):
                try:
                    data = json.loads(pasted)
                    restored_params = _rebuild_params(dict(data["params"]))
                    # 只替换当前槽位；另一个 Tab 的结果不受影响
                    if slot in st.session_state:
                        purge_result_state(st.session_state[slot])
                    st.session_state[slot] = {
                        "analysis": data["analysis"],
                        "structure": data["structure"],
                        "params": restored_params,
                        "result_id": uuid.uuid4().hex[:12],
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"导入失败: {e}")

    # Inline Markdown preview
    with st.expander("📋 预览 Markdown 图解", expanded=False):
        st.markdown(md_content)
