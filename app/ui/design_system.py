"""The pattern-sheet visual system for the Streamlit UI (图解纸).

Tokens live in `app/theme.py`; this module turns them into CSS, the hero
mark, and the numbered section headings. Concept in one line: a printed
pattern sheet on cool paper, navy ink, and one stitch-marker yellow that
only ever means "where you are / what you have done". Yarn colours are the
only other colour on the page.

Two type families with a semantic split — serif for *the sheet* (headings,
part names, round rows, the numbers that are the content) and system sans
for *the tool* (body copy, labels, controls). No web fonts (offline stance).
"""
from __future__ import annotations

import html
import math

import streamlit as st

from app import PRODUCT_NAME, theme

# Magic-ring increase series: 6, 12, 18 … 36. r = N·stitch/2π grows linearly
# with N, so the rings of a plain +6 sphere sit at equal spacing — that is
# the mark: a top view of the first six rounds.
_MARK_ROUNDS = 6


def html_box(content: str, height: int, scroll: bool = False) -> str:
    """定高/滚动写入内容 HTML 的包装器（st.html 无 height/scrolling 参数）。

    st.components.v1.html 已于 2026-06-01 到达弃用截止日，其替代 API
    st.html 只支持 width；环形图/符号条/轮廓 SVG 的固定高度与滚动行为
    由这里的外层 div 承接。
    """
    overflow = "auto" if scroll else "hidden"
    return (f'<div style="height:{height}px;overflow:{overflow};'
            f'border:none;">{content}</div>')


def ring_mark_svg(size: int = 88, animate: bool = True) -> str:
    """Top view of rounds 1–6 of a +6 sphere; the magic ring wears the marker.

    Each ring carries its own circumference as an inline dash so the CSS
    keyframe (dashoffset → 0) draws it; inline values survive st.html's
    sanitizer, unlike the pathLength attribute. The CSS staggers the rings and
    the reduced-motion query removes the motion.
    """
    c = 48.0
    r_max = 40.0
    parts = [
        f'<svg class="sheet-hero__mark{"" if animate else " is-static"}" '
        f'viewBox="0 0 96 96" width="{size}" height="{size}" role="img" '
        f'aria-label="前六圈顶视图：6、12、18、24、30、36 针">',
    ]
    for k in range(_MARK_ROUNDS, 0, -1):
        r = r_max * k / _MARK_ROUNDS
        circumference = 2 * math.pi * r + 1  # +1 so the join is fully covered
        parts.append(
            f'<circle class="ring" cx="{c}" cy="{c}" r="{r:.2f}" '
            f'style="stroke-dasharray:{circumference:.1f};'
            f'stroke-dashoffset:{circumference:.1f}"/>')
    parts.append(
        f'<circle class="magic" cx="{c}" cy="{c}" r="{r_max / _MARK_ROUNDS * 0.62:.2f}"/>')
    parts.append("</svg>")
    return "".join(parts)


def build_css() -> str:
    """Full stylesheet as a string (tested against the token module)."""
    t = theme
    ring_delays = "\n".join(
        f".sheet-hero__mark .ring:nth-of-type({i + 1}) "
        f"{{ animation-delay: {(_MARK_ROUNDS - i) * 110}ms; }}"
        for i in range(_MARK_ROUNDS)
    )
    return f"""
<style>
:root {{
    --paper: {t.PAPER};
    --sheet: {t.SHEET};
    --desk: {t.DESK};
    --grid: {t.GRID};
    --ink: {t.INK};
    --ink-soft: {t.INK_SOFT};
    --ink-hover: {t.INK_HOVER};
    --rule: {t.RULE};
    --edge: {t.EDGE};
    --marker: {t.MARKER};
    --marker-soft: {t.MARKER_SOFT};
    --track: {t.TRACK};
    --serif: {t.FONT_SERIF};
    --sans: {t.FONT_SANS};
    --mono: {t.FONT_MONO};
}}

/* ── Ground ─────────────────────────────────────────────────────────── */
.stApp {{
    background: var(--paper);
    color: var(--ink);
}}
[data-testid="stHeader"] {{
    background: transparent;
}}
[data-testid="stMainBlockContainer"],
.block-container {{
    max-width: 1120px;
    padding-top: 1.25rem;
    padding-bottom: 5rem;
}}

/* ── Type ───────────────────────────────────────────────────────────── */
h1, h2, h3, h4 {{
    font-family: var(--serif);
    color: var(--ink);
    letter-spacing: 0;
    font-variant-numeric: lining-nums tabular-nums;
}}
[data-testid="stMarkdownContainer"] > p,
[data-testid="stMarkdownContainer"] li {{
    line-height: 1.75;
}}
[data-testid="stMarkdownContainer"] > p {{
    max-width: 44em;
}}
[data-testid="stCaptionContainer"] {{
    color: var(--ink-soft);
}}
[data-testid="stCaptionContainer"] p {{
    line-height: 1.6;
}}
a, a:visited {{
    color: var(--ink);
    text-decoration-color: var(--edge);
}}
hr {{
    border-color: var(--rule);
    margin: 1.75rem 0;
}}

/* ── Desk (sidebar) ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: var(--desk);
    border-right: 1px solid var(--rule);
}}
[data-testid="stSidebar"] h2 {{
    font-size: 1.15rem;
}}
[data-testid="stSidebar"] h3 {{
    font-size: 1rem;
}}

/* ── Binder tabs: the open one wears the marker ─────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    gap: 0.3rem;
    padding: 0;
    background: transparent;
    border-bottom: 1px solid var(--edge);
    box-shadow: none;
}}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {{
    display: none;
}}
[data-testid="stTabs"] button[role="tab"] {{
    margin-bottom: -1px;
    padding: 0.55rem 0.95rem;
    border: 1px solid transparent;
    border-bottom: 1px solid var(--edge);
    border-radius: 3px 3px 0 0;
    background: transparent;
    color: var(--ink-soft);
    font-family: var(--sans);
    font-weight: 600;
}}
[data-testid="stTabs"] button[role="tab"]:hover {{
    color: var(--ink);
    background: var(--sheet);
}}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
    background: var(--marker);
    color: var(--ink);
    border-color: var(--edge);
    border-bottom-color: var(--marker);
}}
[data-testid="stTabs"] button[role="tab"] p {{
    font-family: var(--sans);
}}

/* ── Controls: sans, ruled, no lift ─────────────────────────────────── */
.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {{
    font-family: var(--sans);
    font-weight: 600;
    border-radius: 3px;
    border: 1px solid var(--edge);
    background: var(--sheet);
    color: var(--ink);
    box-shadow: none;
    transition: border-color 120ms ease, background-color 120ms ease;
}}
.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
    border-color: var(--ink);
    background: var(--paper);
    color: var(--ink);
}}
.stButton > button:disabled,
.stDownloadButton > button:disabled {{
    border-color: var(--rule);
    color: var(--ink-soft);
}}
[data-testid="stBaseButton-primary"],
.stButton > button[kind="primary"] {{
    background: var(--ink);
    border-color: var(--ink);
    color: var(--paper);
}}
[data-testid="stBaseButton-primary"]:hover,
.stButton > button[kind="primary"]:hover {{
    background: var(--ink-hover);
    border-color: var(--ink-hover);
    color: var(--paper);
}}
.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible,
[data-testid="stTabs"] button[role="tab"]:focus-visible {{
    outline: 2px solid var(--ink);
    outline-offset: 2px;
}}

/* Chosen option wears the marker (radio) */
[data-testid="stRadio"] label[data-baseweb="radio"] {{
    padding: 0.2rem 0.6rem 0.2rem 0.35rem;
    border-radius: 3px;
    transition: background-color 120ms ease;
}}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{
    background: var(--marker-soft);
}}

/* Uploader: an empty sheet of graph paper (1 cell = 1 stitch) */
[data-testid="stFileUploaderDropzone"] {{
    background-color: var(--sheet);
    background-image:
        linear-gradient(var(--grid) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid) 1px, transparent 1px);
    background-size: 14px 14px;
    border: 1px dashed var(--edge);
    border-radius: 3px;
}}

/* Progress: done = marker */
[data-testid="stProgress"] [role="progressbar"] > div {{
    background: var(--track);
}}
[data-testid="stProgress"] [role="progressbar"] > div > div {{
    background: var(--marker);
}}

/* Alerts: white sheet, status-coloured left rule */
[data-testid="stAlertContainer"] {{
    background: var(--sheet);
    border: 1px solid var(--rule);
    border-left: 3px solid currentColor;
    border-radius: 3px;
}}

/* Code and DSL blocks */
[data-testid="stCode"] pre {{
    background: var(--sheet);
    border: 1px solid var(--rule);
    border-radius: 3px;
}}

/* Disclosures: ruled sheets, no shadow */
[data-testid="stExpander"] details {{
    border: 1px solid var(--rule);
    border-radius: 3px;
    background: var(--sheet);
    box-shadow: none;
}}
[data-testid="stExpander"] summary {{
    padding: 0.65rem 0.9rem;
}}
[data-testid="stExpander"] summary p {{
    font-family: var(--sans);
    font-weight: 600;
}}

/* Metrics: a spec strip, not cards */
[data-testid="stMetric"] {{
    padding: 0.5rem 0 0.35rem;
    border-top: 2px solid var(--ink);
    border-radius: 0;
    background: transparent;
    box-shadow: none;
}}
[data-testid="stMetricLabel"] p {{
    font-family: var(--sans);
    font-size: 0.85rem;
    color: var(--ink-soft);
}}
[data-testid="stMetricValue"] {{
    font-family: var(--serif);
    font-size: 1.75rem;
    font-variant-numeric: lining-nums tabular-nums;
    color: var(--ink);
}}

/* ── The sheet: one part's round-by-round pattern ───────────────────── */
[class*="st-key-sheet_part_"] details {{
    border-color: var(--edge);
}}
[class*="st-key-sheet_part_"] details > summary p {{
    font-family: var(--serif);
    font-size: 1.1rem;
    font-weight: 700;
    font-variant-numeric: lining-nums tabular-nums;
}}
[class*="st-key-sheet_part_"] details details > summary p {{
    font-family: var(--sans);
    font-size: 1rem;
    font-weight: 600;
}}
[class*="st-key-sheet_part_"] [data-testid="stCheckbox"] label {{
    align-items: baseline;
    gap: 0.6rem;
    margin: 0;
    padding: 0.35rem 0.6rem 0.35rem 0.4rem;
    border-bottom: 1px solid var(--rule);
    border-radius: 0;
    background-image: linear-gradient(var(--marker-soft), var(--marker-soft));
    background-repeat: no-repeat;
    background-size: 0% 100%;
    transition: background-size 220ms ease-out;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
}}
[class*="st-key-sheet_part_"] [data-testid="stCheckbox"] label:has(input:checked) {{
    background-size: 100% 100%;
}}
[class*="st-key-sheet_part_"] [data-testid="stCheckbox"] label p {{
    font-family: var(--serif);
    font-size: 1.05rem;
    line-height: 1.6;
    font-variant-numeric: lining-nums tabular-nums;
    margin: 0;
}}
[class*="st-key-sheet_part_"] [data-testid="stCheckbox"] {{
    margin-bottom: 0;
}}

/* ── Hero: mark + title, one drawn moment ───────────────────────────── */
.sheet-hero {{
    display: grid;
    grid-template-columns: 88px 1fr;
    gap: 1.4rem;
    align-items: center;
    margin: 0 0 1.25rem;
    padding: 0.25rem 0 1.25rem;
    border-bottom: 1px solid var(--ink);
}}
.sheet-hero__mark {{
    display: block;
    width: 88px;
    height: 88px;
}}
.sheet-hero__mark .ring {{
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.6;
    animation: sheet-draw 520ms cubic-bezier(0.2, 0.7, 0.2, 1) forwards;
}}
{ring_delays}
.sheet-hero__mark .magic {{
    fill: var(--marker);
    stroke: var(--ink);
    stroke-width: 1.6;
    opacity: 0;
    animation: sheet-fade 320ms ease-out 900ms forwards;
}}
.sheet-hero__mark.is-static .ring {{
    animation: none;
    stroke-dashoffset: 0 !important;
}}
.sheet-hero__mark.is-static .magic {{
    animation: none;
    opacity: 1;
}}
@keyframes sheet-draw {{
    to {{ stroke-dashoffset: 0; }}
}}
@keyframes sheet-fade {{
    to {{ opacity: 1; }}
}}
.sheet-hero__title {{
    margin: 0;
    font-family: var(--serif);
    font-size: clamp(1.6rem, 3vw, 2.1rem);
    font-weight: 700;
    line-height: 1.15;
    color: var(--ink);
}}
.sheet-hero__lead {{
    margin: 0.4rem 0 0;
    max-width: 38em;
    font-family: var(--sans);
    font-size: 1.02rem;
    line-height: 1.7;
    color: var(--ink);
}}
.sheet-hero__note {{
    margin: 0.2rem 0 0;
    font-family: var(--sans);
    font-size: 0.86rem;
    color: var(--ink-soft);
}}
@media (max-width: 640px) {{
    .sheet-hero {{
        grid-template-columns: 56px 1fr;
        gap: 1rem;
    }}
    .sheet-hero__mark {{
        width: 56px;
        height: 56px;
    }}
}}

/* ── Numbered section headings (the result is a sequence 1→5) ───────── */
.sheet-h {{
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin: 2.5rem 0 0.85rem;
    padding-bottom: 0.45rem;
    border-bottom: 1px solid var(--ink);
    font-family: var(--serif);
    font-size: 1.45rem;
    font-weight: 700;
    line-height: 1.3;
    color: var(--ink);
}}
.sheet-h__n {{
    flex: none;
    min-width: 1.65rem;
    height: 1.65rem;
    border: 1px solid var(--ink);
    border-radius: 2px;
    font-size: 0.95rem;
    font-weight: 600;
    line-height: 1.55rem;
    text-align: center;
    font-variant-numeric: lining-nums tabular-nums;
    transform: translateY(-0.2rem);
}}

/* ── Notes, empty state, yarn chips ─────────────────────────────────── */
.sheet-note {{
    margin: -0.25rem 0 1rem;
    max-width: 44em;
    color: var(--ink-soft);
    line-height: 1.7;
}}
.sheet-empty {{
    padding: 2.4rem 1.25rem;
    border: 1px solid var(--rule);
    border-radius: 3px;
    background: var(--sheet);
    color: var(--ink-soft);
    text-align: center;
    line-height: 1.8;
}}
.yarn-chip {{
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.18rem 0.6rem 0.18rem 0.35rem;
    border: 1px solid var(--edge);
    border-radius: 3px;
    background: var(--sheet);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 0.86rem;
}}
.yarn-chip__swatch {{
    display: inline-block;
    width: 14px;
    height: 14px;
    border-radius: 2px;
    border: 1px solid rgba(29, 36, 64, 0.35);
}}
.yarn-chip--unknown .yarn-chip__swatch {{
    background:
        linear-gradient(135deg, transparent 46%, var(--edge) 46%, var(--edge) 54%, transparent 54%);
}}
.yarn-qty {{
    margin-left: 0.5rem;
    color: var(--ink-soft);
    font-size: 0.9rem;
    font-variant-numeric: lining-nums tabular-nums;
}}

/* ── Motion: only answer the maker ──────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {{
    .sheet-hero__mark .ring {{
        animation: none;
        stroke-dashoffset: 0 !important;
    }}
    .sheet-hero__mark .magic {{
        animation: none;
        opacity: 1;
    }}
    [class*="st-key-sheet_part_"] [data-testid="stCheckbox"] label,
    [data-testid="stRadio"] label[data-baseweb="radio"],
    .stButton > button,
    .stDownloadButton > button {{
        transition: none;
    }}
}}

/* ── Print: the sheet goes on paper ─────────────────────────────────── */
@media print {{
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    [data-testid="stTabs"] [data-baseweb="tab-list"],
    [data-testid="stToolbar"],
    [data-testid="stStatusWidget"],
    .sheet-hero__note,
    .sheet-empty,
    .stButton,
    .stDownloadButton,
    .stSlider,
    .stTextArea,
    [data-testid="stFileUploader"] {{
        display: none !important;
    }}
    .stApp {{
        background: #ffffff !important;
        color: #000000 !important;
    }}
    [data-testid="stMainBlockContainer"],
    .block-container {{
        max-width: 100%;
        padding: 0;
        margin: 0;
    }}
    .sheet-hero {{
        border-bottom-color: #000000;
    }}
    .sheet-hero__mark .ring {{
        animation: none;
        stroke-dashoffset: 0 !important;
    }}
    .sheet-hero__mark .magic {{
        animation: none;
        opacity: 1;
    }}
    [data-testid="stExpander"] details,
    [data-testid="stAlertContainer"],
    [data-testid="stCode"] pre {{
        box-shadow: none !important;
        border-color: #bbbbbb !important;
        background: #ffffff !important;
    }}
}}
</style>
"""


def apply_design_system() -> None:
    """Apply the shared visual theme without changing application behavior."""
    st.markdown(build_css(), unsafe_allow_html=True)


def render_hero() -> None:
    """Mark + title + one honest line about what the sheet is."""
    st.html(
        f"""
        <header class="sheet-hero">
          {ring_mark_svg()}
          <div>
            <h1 class="sheet-hero__title">{html.escape(PRODUCT_NAME)}</h1>
            <p class="sheet-hero__lead">
              把一张照片整理成比例、部件结构和逐圈针数，得到一份能边钩边勾选的玩偶图解。
            </p>
            <p class="sheet-hero__note">
              生成结果是设计草稿：尺寸、用线与可钩性以小样和试钩为准。
            </p>
          </div>
        </header>
        """
    )


def section_heading(number: int, title: str) -> None:
    """Numbered heading for the result sheet (sections 1–5 are a sequence)."""
    st.html(
        f'<h2 class="sheet-h"><span class="sheet-h__n">{int(number)}</span>'
        f'{html.escape(title)}</h2>'
    )
