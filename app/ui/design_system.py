"""Shared warm handmade-style visual system for the Streamlit UI."""
from __future__ import annotations

import streamlit as st


def apply_design_system() -> None:
    """Apply the shared visual theme without changing application behavior."""
    st.markdown(
        """
        <style>
        :root {
            --cream: #fffaf2;
            --paper: #fffdf8;
            --peach: #d9785f;
            --peach-dark: #b95f4b;
            --peach-deep: #a85442;
            --rose-soft: #f7ddd4;
            --sage: #71866f;
            --sage-soft: #e6eee2;
            --brown: #543f35;
            --muted: #806d63;
            --line: #ead8ca;
            --shadow: 0 8px 24px rgba(91, 62, 47, 0.08);
        }

        .stApp {
            background:
                radial-gradient(circle at 8% 4%, rgba(247, 221, 212, 0.48), transparent 24rem),
                radial-gradient(circle at 95% 10%, rgba(230, 238, 226, 0.55), transparent 26rem),
                var(--cream);
            color: var(--brown);
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 {
            color: var(--brown);
            letter-spacing: -0.02em;
        }

        h1 {
            font-weight: 800;
        }

        [data-testid="stSidebar"] {
            background: #f8eee5;
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.25rem;
        }

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 0.55rem;
            background: rgba(255, 253, 248, 0.72);
            border: 1px solid var(--line);
            border-radius: 1rem;
            padding: 0.45rem;
            box-shadow: var(--shadow);
        }

        [data-testid="stTabs"] button[role="tab"] {
            border-radius: 0.75rem;
            color: var(--muted);
            font-weight: 650;
            padding: 0.55rem 1rem;
        }

        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background: var(--rose-soft);
            color: var(--peach-dark);
        }

        [data-testid="stMetric"],
        [data-testid="stExpander"],
        [data-testid="stFileUploader"] section {
            background: rgba(255, 253, 248, 0.92);
            border: 1px solid var(--line);
            border-radius: 1rem;
            box-shadow: var(--shadow);
        }

        [data-testid="stMetric"] {
            padding: 1rem;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 999px;
            border-color: var(--peach);
            font-weight: 700;
            transition: transform 120ms ease, box-shadow 120ms ease;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: var(--peach-deep);
            color: var(--peach-deep);
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(185, 95, 75, 0.16);
        }

        .stButton > button[kind="primary"] {
            /* #a85442 与白字对比 5.23:1（WCAG AA 正文 ≥4.5:1）——
               原 --peach 仅 3.09:1 不达标 */
            background: var(--peach-deep);
            border-color: var(--peach-deep);
            color: white;
        }

        [data-testid="stAlert"] {
            border-radius: 0.9rem;
        }

        [data-testid="stProgress"] > div > div > div > div {
            background-color: var(--peach);
        }

        hr {
            border-color: var(--line);
        }

        .crochet-hero {
            padding: 1.5rem 1.65rem;
            margin-bottom: 1.25rem;
            border: 1px solid var(--line);
            border-radius: 1.4rem;
            background: linear-gradient(135deg, rgba(255,253,248,.96), rgba(247,221,212,.72));
            box-shadow: var(--shadow);
        }

        .crochet-hero__eyebrow {
            color: var(--peach-dark);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .crochet-hero__title {
            margin: 0.25rem 0;
            color: var(--brown);
            font-size: clamp(1.8rem, 4vw, 3rem);
            font-weight: 850;
        }

        .crochet-hero__copy {
            max-width: 48rem;
            margin: 0;
            color: var(--muted);
            font-size: 1.02rem;
            line-height: 1.7;
        }

        .crochet-section-note {
            margin: -0.35rem 0 1rem;
            color: var(--muted);
        }

        .crochet-footer {
            padding: 1rem;
            color: var(--muted);
            text-align: center;
        }

        .crochet-empty {
            padding: 2.2rem 1rem;
            border: 1.5px dashed var(--line);
            border-radius: 1.2rem;
            text-align: center;
            color: var(--muted);
            font-size: 1.02rem;
            line-height: 1.9;
            background: rgba(255, 253, 248, 0.6);
        }

        /* ── 打印样式：钩织时打纸质图解是真实场景 ─────────────────────
           隐藏界面 chrome（侧栏/横幅/Tab 栏/按钮/输入控件），正文以
           白底黑字输出，图解部分可读性优先。 */
        @media print {
            [data-testid="stSidebar"],
            [data-testid="stHeader"],
            [data-testid="stTabs"] [data-baseweb="tab-list"],
            [data-testid="stToolbar"],
            [data-testid="stStatusWidget"],
            .crochet-hero,
            .crochet-empty,
            .stButton,
            .stDownloadButton,
            .stSlider,
            .stTextArea,
            [data-testid="stFileUploader"] {
                display: none !important;
            }
            .stApp {
                background: #ffffff !important;
                color: #000000 !important;
            }
            .block-container {
                max-width: 100%;
                padding: 0;
                margin: 0;
            }
            [data-testid="stMetric"],
            [data-testid="stExpander"],
            [data-testid="stAlert"] {
                box-shadow: none !important;
                border: 1px solid #ddd !important;
                background: #ffffff !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    """Render the application introduction using the shared visual language."""
    st.markdown(
        """
        <section class="crochet-hero">
          <div class="crochet-hero__eyebrow">Photo to handmade pattern</div>
          <div class="crochet-hero__title">🧶 Photo2Amigurumi</div>
          <p class="crochet-hero__copy">
            从一张照片出发，整理人物比例、立体结构与逐圈针法，生成一份可以边钩边勾选的玩偶图解。
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
