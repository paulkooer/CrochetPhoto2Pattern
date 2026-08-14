from __future__ import annotations

import json
import logging
import uuid

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from app.models.orchestrator import PipelineOrchestrator
from app.models.grid_pattern import (
    generate_grid_pattern, render_svg, render_legend_markdown, render_text_chart
)
from app.schemas import CrochetPart, CrochetStitch, ImageAnalysis

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Photo2Amigurumi", page_icon="\U0001f9f6", layout="wide")
st.title("\U0001f9f6 Photo2Amigurumi")
st.markdown("**\u4ece\u4e00\u5f20\u7167\u7247 \u2192 \u7acb\u4f53\u4eba\u7269\u9489\u7ec7\u5b8c\u6574\u56fe\u89e3** (Amigurumi \u98ce\u683c)")

# \u2500\u2500 Sidebar: API Keys \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
with st.sidebar:
    st.header("\u2699\ufe0f \u8bbe\u7f6e")
    openai_key = st.text_input("OpenAI API Key", type="password",
                                value=st.session_state.get("openai_key", ""))
    anthropic_key = st.text_input("Anthropic API Key (\u63a8\u8350)", type="password",
                                   value=st.session_state.get("anthropic_key", ""))
    if openai_key:
        st.session_state.openai_key = openai_key
    if anthropic_key:
        st.session_state.anthropic_key = anthropic_key

    has_key = bool(openai_key or anthropic_key)
    if has_key:
        st.success("\u2705 API Key \u5df2\u8bbe\u7f6e")
    else:
        st.warning("\u672a\u8bbe\u7f6e API Key\uff0c\u5c06\u4f7f\u7528 Mock \u6570\u636e\u6f14\u793a")


# \u2500\u2500 Utility: Markdown Exporter \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _export_markdown(params: dict, analysis: dict | None = None) -> str:
    """Convert crochet params dict to a printable Markdown pattern."""
    lines: list[str] = []
    lines.append("# \U0001f9f6 Amigurumi \u9489\u7ec7\u56fe\u89e3")
    lines.append("")
    if analysis:
        lines.append(f"> \u4f53\u578b\uff1a{analysis.get('body_type', '—')}  \u00b7  "
                     f"\u5934\u5f84\uff1a{analysis.get('head_diameter_cm', '—')} cm  \u00b7  "
                     f"\u9ad8\u5ea6\uff1a{analysis.get('height_cm', '—')} cm  \u00b7  "
                     f"\u96be\u5ea6\uff1a{analysis.get('difficulty', '—')}")
        lines.append("")
    lines.append("---")

    # Materials
    lines.append("## \U0001f9f5 \u6240\u9700\u6750\u6599")
    lines.append("")
    for mat in params.get("materials", []):
        lines.append(f"- **{mat['item']}**\uff1a{mat['quantity']}")
    lines.append("")
    lines.append("---")

    # Each part
    for part in params.get("parts", []):
        pd = part.model_dump() if hasattr(part, "model_dump") else part
        lines.append(f"## \U0001f9f6 {pd['name']} ({pd.get('rows', '?')} \u5708)")
        lines.append("")
        lines.append(f"- **\u5f62\u72b6**\uff1a{pd.get('type', '—')}")
        lines.append(f"- **\u989c\u8272**\uff1a{pd.get('color', '—')}")
        if pd.get("diameter_cm"):
            lines.append(f"- **\u76f4\u5f84**\uff1a{pd['diameter_cm']} cm")
        if pd.get("height_cm"):
            lines.append(f"- **\u9ad8\u5ea6/\u957f\u5ea6**\uff1a{pd['height_cm']} cm")
        if pd.get("magic_ring"):
            lines.append("- \u2728 \u9b54\u6cd5\u73af\u8d77\u9488")
        if pd.get("notes"):
            lines.append(f"\n> {pd['notes']}")
        lines.append("")

        # Rounds table
        rounds = pd.get("rounds", [])
        if rounds:
            lines.append("| \u5708\u6570 | \u9488\u6570 | \u52a0\u9488 | \u51cf\u9488 | \u8bf4\u660e |")
            lines.append("|:----:|:----:|:----:|:----:|------|")
            for r in rounds:
                rd = r if isinstance(r, dict) else (r.model_dump() if hasattr(r, "model_dump") else {})
                inc = f"+{rd['increase']}" if rd.get("increase") else "—"
                dec = f"-{rd['decrease']}" if rd.get("decrease") else "—"
                lines.append(f"| {rd.get('row','')} | {rd.get('stitches','')} | "
                              f"{inc} | {dec} | {rd.get('notes', '')} |")
        lines.append("")
        lines.append("---")

    # Assembly
    assembly = params.get("assembly_instructions", "")
    if assembly:
        lines.append("## \U0001f527 \u88c5\u914d\u8bf4\u660e")
        lines.append("")
        for step in assembly.split("\n"):
            lines.append(step)
        lines.append("")

    lines.append("---")
    lines.append("*\u7531 Photo2Amigurumi AI \u81ea\u52a8\u751f\u6210 \u2014 \u90e8\u5206\u6bd4\u4f8b\u53ef\u80fd\u9700\u8981\u8bd5\u94a9\u8c03\u6574*")
    return "\n".join(lines)


# \u2500\u2500 Utility: run pipeline steps \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _run_pipeline_from_analysis(analysis: ImageAnalysis, openai_key=None, anthropic_key=None) -> dict:
    """Run structure + param stages given an already-parsed ImageAnalysis."""
    orchestrator = PipelineOrchestrator(openai_key=openai_key, anthropic_key=anthropic_key)
    structure = orchestrator.structure_designer.design_3d_structure(analysis)
    params = orchestrator.params_generator.generate_params(analysis, structure)
    return {
        "analysis": analysis.model_dump(),
        "structure": structure,
        "params": params,
        "result_id": uuid.uuid4().hex[:12],
    }


def _render_results(result: dict, slot: str) -> None:
    """Render the result UI. `slot` is the st.session_state key holding `result`,
    so edits/regeneration write back to the tab that owns this result."""
    analysis = result["analysis"]
    structure = result["structure"]
    params = result["params"]
    # Widget-key namespace: unique per generated result, stable across reruns.
    result_key = result.get("result_id") or str(id(result))

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

    # Color palette swatches (from extract_color_palette)
    colors = analysis.get("recommended_colors") or []
    if colors:
        st.write("**🎨 推荐毛线颜色**（按主色占比排序）:")
        swatch_html = (
            "<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;'>"
            + "".join(
                f"<span style='background:#f4f4f4;padding:4px 14px;border-radius:20px;"
                f"font-size:0.85rem;border:1px solid #ccc;'>🧶 {c}</span>"
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
    st.subheader("3️⃣ 钉织参数")
    st.write("**所需材料**:")
    for mat in params.get("materials", []):
        st.write(f"  - {mat['item']}: {mat['quantity']}")

    for part in params.get("parts", []):
        part_data = part.model_dump() if hasattr(part, "model_dump") else part
        part_key = f"{result_key}_{part_data['name']}"
        rounds_list = part_data.get("rounds", [])
        n_rounds = len(rounds_list)
        # Checkbox widget state is the single source of truth for progress.
        # It is updated by Streamlit before the rerun, so the counts below
        # already include the click that triggered this run (no one-step lag).
        chk_keys = [f"chk_{part_key}_{i}" for i in range(n_rounds)]
        n_done = sum(bool(st.session_state.get(k)) for k in chk_keys)
        pct = int(n_done / n_rounds * 100) if n_rounds else 0
        label_exp = (
            f"🧶 {part_data['name']} ({part_data['rows']} 圈)"
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
                lbl = f"第 {rd.get('row', i + 1)} 圈：{rd.get('stitches', '?')}针{change}{notes_str}"
                st.checkbox(lbl, key=chk_keys[i])

    # Section 4: Assembly
    st.subheader("4️⃣ 装配说明")
    st.markdown(params.get("assembly_instructions", ""))


    # Section 5: Edit & Re-generate
    st.subheader("5\ufe0f\u20e3 \u5c40\u90e8\u4fee\u6b63")
    st.info("\u53ef\u76f4\u63a5\u7f16\u8f91\u4e0b\u65b9 JSON\uff0c\u4fee\u6539\u9488\u6570\u6216\u6bd4\u4f8b\u540e\u70b9\u51fb \u2018\u91cd\u65b0\u751f\u6210\u2019")

    serializable_params = json.loads(
        json.dumps(params, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
                   ensure_ascii=False, indent=2)
    )
    correction_json = st.text_area(
        "\u7f16\u8f91 JSON \u8f93\u51fa",
        json.dumps(serializable_params, ensure_ascii=False, indent=2),
        height=300,
        key=f"json_edit_{result_key}",
    )

    md_content = _export_markdown(params, analysis)

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("\U0001f504 \u91cd\u65b0\u751f\u6210", key=f"regen_{result_key}"):
            try:
                corrected = json.loads(correction_json)
                rebuilt_parts = []
                for p in corrected.get("parts", []):
                    rounds = [CrochetStitch(**r) for r in p.pop("rounds", [])]
                    rebuilt_parts.append(CrochetPart(**p, rounds=rounds))
                corrected["parts"] = rebuilt_parts
                st.session_state[slot]["params"] = corrected
                st.success("\u2705 \u5df2\u6839\u636e\u4fee\u6b63\u66f4\u65b0\u56fe\u89e3\uff0c\u5411\u4e0a\u67e5\u770b\u7ed3\u679c\uff01")
                st.rerun()
            except Exception as e:
                st.error(f"\u89e3\u6790/\u5e94\u7528\u5931\u8d25: {e}")
    with col_btn2:
        st.download_button(
            "\U0001f4e5 \u4e0b\u8f7d JSON",
            correction_json,
            file_name="amigurumi_pattern.json",
            mime="application/json",
            key=f"dl_json_{result_key}",
        )
    with col_btn3:
        st.download_button(
            "\U0001f4c4 \u4e0b\u8f7d Markdown \u56fe\u89e3",
            md_content,
            file_name="amigurumi_pattern.md",
            mime="text/markdown",
            key=f"dl_md_{result_key}",
        )

    # Inline Markdown preview
    with st.expander("\U0001f4cb \u9884\u89c8 Markdown \u56fe\u89e3", expanded=False):
        st.markdown(md_content)


# \u2500\u2500 Two main tabs \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

tab_photo, tab_manual, tab_grid = st.tabs(
    ["\U0001f4f8 \u7167\u7247\u8bc6\u522b\uff08AI\uff09", "\u270f\ufe0f \u624b\u52a8\u8f93\u5165", "\U0001f4f9 2D \u50cf\u7d20\u7f51\u683c"]
)

# ─── Tab 1: Photo Upload ──────────────────────────────────────────────────────
with tab_photo:
    st.subheader("\U0001f4f7 \u7167\u7247\u4e0a\u4f20")
    col_upload, col_preview = st.columns([1, 1])

    with col_upload:
        uploaded_file = st.file_uploader(
            "\u4e0a\u4f20\u7167\u7247\uff08\u6b63\u9762\u4e3a\u4e3b\uff09", type=["jpg", "jpeg", "png"],
            help="\u5efa\u8bae\u4e0a\u4f20\u6b63\u9762\u6e05\u6670\u7167\u7247",
            key="photo_uploader",
        )
        with st.expander("\u2795 \u8f85\u52a9\u89d2\u5ea6\u7167\u7247\uff08\u5373\u5c06\u652f\u6301\uff09", expanded=False):
            st.info("\U0001f6a7 Coming Soon \u2014 \u4e0a\u4f20\u4fa7\u9762/\u80cc\u9762\u7167\u7247\u4ee5\u63d0\u5347 3D \u7ed3\u6784\u63a8\u7406\u51c6\u786e\u5ea6")

    if uploaded_file:
        image = Image.open(uploaded_file)
        with col_preview:
            st.image(image, caption="\u4e0a\u4f20\u7684\u7167\u7247", use_container_width=True)

        if st.button("\U0001f680 \u751f\u6210\u9489\u7ec7\u56fe\u89e3", type="primary",
                     use_container_width=True, key="btn_photo"):
            orchestrator = PipelineOrchestrator(
                openai_key=st.session_state.get("openai_key"),
                anthropic_key=st.session_state.get("anthropic_key"),
            )
            progress = st.progress(0, text="\u51c6\u5907\u4e2d...")
            try:
                progress.progress(10, text="Step 1/3: AI \u89c6\u89c9\u89e3\u6790\u4e2d...")
                analysis = orchestrator.parser.parse_image(image)

                progress.progress(40, text="Step 2/3: 3D \u7ed3\u6784\u8bbe\u8ba1\u4e2d...")
                structure = orchestrator.structure_designer.design_3d_structure(analysis)

                progress.progress(70, text="Step 3/3: \u751f\u6210\u9489\u7ec7\u53c2\u6570...")
                params = orchestrator.params_generator.generate_params(analysis, structure)

                progress.progress(100, text="\u2705 \u751f\u6210\u5b8c\u6210\uff01")
                st.session_state.result = {
                    "analysis": analysis.model_dump(),
                    "structure": structure,
                    "params": params,
                    "result_id": uuid.uuid4().hex[:12],
                }
            except Exception as e:
                st.error(f"\u751f\u6210\u5931\u8d25: {e}")
                logger.exception("Pipeline failed")

    # Render outside the `if uploaded_file` block so the last result stays
    # visible even after the uploader is cleared.
    if "result" in st.session_state:
        _render_results(st.session_state.result, "result")


# ─── Tab 2: Manual Input ──────────────────────────────────────────────────────
with tab_manual:
    st.subheader("\u270f\ufe0f \u624b\u52a8\u8f93\u5165\u53c2\u6570")
    st.info("\u65e0\u9700\u4e0a\u4f20\u7167\u7247\uff0c\u624b\u52a8\u586b\u5199\u4eba\u7269\u53c2\u6570\u76f4\u63a5\u751f\u6210\u56fe\u89e3\u3002")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        m_body_type = st.selectbox("\u4f53\u578b", ["\u6807\u51c6", "\u7626", "\u80d6"], key="m_body_type")
        m_head_d = st.slider("\u5934\u90e8\u76f4\u5f84 (cm)", 4.0, 20.0, 9.0, 0.5, key="m_head_d")
        m_height = st.slider("\u6574\u4f53\u9ad8\u5ea6 (cm)", 10.0, 60.0, 18.0, 0.5, key="m_height")
        m_difficulty = st.select_slider(
            "\u96be\u5ea6", options=["easy", "medium", "hard"], value="easy", key="m_difficulty"
        )

    with col_m2:
        m_pose = st.selectbox("\u59ff\u6001", ["\u7ad9\u7acb", "\u5750\u59ff", "\u5176\u4ed6"], key="m_pose")
        m_parts = st.multiselect(
            "\u5305\u542b\u90e8\u4ef6",
            ["\u5934\u90e8", "\u8eab\u4f53", "\u624b\u81c2", "\u817f\u90e8", "\u5c3e\u5df4", "\u8033\u6735", "\u5e3d\u5b50"],
            default=["\u5934\u90e8", "\u8eab\u4f53"],
            key="m_parts",
        )
        m_features = st.text_input(
            "\u4e3b\u8981\u7279\u5f81\uff08\u9017\u53f7\u5206\u9694\uff09",
            "\u5927\u773c\u775b, \u5706\u8138, \u5361\u901a\u98ce\u683c",
            key="m_features",
        )

    if st.button("\U0001f680 \u751f\u6210\u9489\u7ec7\u56fe\u89e3", type="primary",
                 use_container_width=True, key="btn_manual"):
        if not m_parts:
            st.warning("\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u90e8\u4ef6\u3002")
        else:
            try:
                features = [f.strip() for f in m_features.split(",") if f.strip()]
                analysis = ImageAnalysis(
                    body_type=m_body_type,
                    head_diameter_cm=m_head_d,
                    height_cm=m_height,
                    main_features=features or ["\u5361\u901a\u98ce\u683c"],
                    pose=m_pose,
                    difficulty=m_difficulty,
                    parts=m_parts,
                )
                with st.spinner("\u751f\u6210\u56fe\u89e3\u4e2d\u2026"):
                    result = _run_pipeline_from_analysis(
                        analysis,
                        openai_key=st.session_state.get("openai_key"),
                        anthropic_key=st.session_state.get("anthropic_key"),
                    )
                st.session_state.manual_result = result
                st.success("\u2705 \u56fe\u89e3\u5df2\u751f\u6210\uff01")
            except Exception as e:
                st.error(f"\u751f\u6210\u5931\u8d25: {e}")
                logger.exception("Manual pipeline failed")

    if "manual_result" in st.session_state:
        _render_results(st.session_state.manual_result, "manual_result")



# ─── Tab 3: 2D Pixel Grid ────────────────────────────────────────────────
with tab_grid:
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

st.divider()
st.caption("Photo2Amigurumi \u2014 AI \u9a71\u52a8\u7684\u7acb\u4f53\u9489\u7ec7\u56fe\u89e3\u751f\u6210\u5668")
