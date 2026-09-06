"""Visual tokens for the whole product surface: the pattern sheet (图解纸).

Single source for `.streamlit/config.toml`, the injected CSS in
`app/ui/design_system.py`, and the SVG/canvas renderers in `app/models`
and `app/ui/preview3d.py`. This is a leaf module (no Streamlit import) so
model-layer renderers can depend on it without a models→ui cycle.
`config.toml` cannot import Python; `tests/test_theme_tokens.py` asserts
that it mirrors these values.

Concept: a printed pattern sheet on cool paper, navy ink, and one bright
stitch-marker yellow. The marker is reserved for "where you are / what you
have done" (active tab, chosen option, completed rounds, progress) and is
never used for text or decoration. Yarn colours stay the only other colour.
"""
from __future__ import annotations

# ── Surfaces ────────────────────────────────────────────────────────────
PAPER = "#f6f7f4"        # page ground: uncoated, slightly cool paper
SHEET = "#ffffff"        # the pattern sheet itself: results, inputs, code
DESK = "#e9ecf2"         # sidebar: the desk the sheet lies on
GRID = "#e6eaf2"         # graph-paper lines (1 cell = 1 stitch) in empty states

# ── Ink ─────────────────────────────────────────────────────────────────
INK = "#1d2440"          # navy ink: all text, primary action (≈14:1 on paper)
INK_SOFT = "#5f6580"     # secondary text (5.3:1 on paper, WCAG AA)
INK_HOVER = "#2b3560"    # primary button hover
RULE = "#cfd6e3"         # hairlines between sections (decorative structure)
EDGE = "#848da2"         # control borders (3.0:1 on paper, WCAG 1.4.11)

# ── Marker ──────────────────────────────────────────────────────────────
MARKER = "#ffe14d"       # stitch-marker / highlighter yellow (ink on it: 12.5:1)
MARKER_SOFT = "#fff4b8"  # pale highlight for completed rounds
TRACK = "#e3e7ef"        # progress track under the marker fill

# ── Status inks (alerts are white sheets with a coloured left rule) ─────
OK_INK = "#1f6f43"
WARN_INK = "#9a4d00"     # deliberately orange-brown so warnings never read as marker
ERR_INK = "#a12a2a"
INFO_INK = INK

# ── Type ────────────────────────────────────────────────────────────────
# No web fonts: the app keeps a zero-external-dependency, offline stance
# (see app/ui/preview3d.py) and Google Fonts is unreliable for the mainland
# audience. Latin/digits resolve to the Western faces listed first; CJK
# glyphs fall through to the system 宋体 / 黑体.
FONT_SERIF = (
    'Charter, "Palatino Linotype", Palatino, Cambria, "Songti SC", STSong, '
    '"Noto Serif CJK SC", "Source Han Serif SC", "Noto Serif SC", SimSun, '
    'Georgia, serif'
)
FONT_SANS = (
    '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", '
    '"Noto Sans CJK SC", "Source Han Sans SC", "Noto Sans SC", system-ui, sans-serif'
)
FONT_MONO = '"SF Mono", Menlo, Consolas, "Noto Sans Mono CJK SC", monospace'

# ── Data colours kept by the silhouette overlay (generated vs. photo) ────
SILHOUETTE_FILL = "#9ecae1"
SILHOUETTE_STROKE = "#2171b5"
PHOTO_PROFILE = "#e6550d"

# Legacy palette that must not reappear anywhere in the app surface.
LEGACY_HEX = ("#fffaf2", "#fffdf8", "#d9785f", "#b95f4b", "#a85442",
              "#f7ddd4", "#71866f", "#e6eee2", "#543f35", "#806d63", "#ead8ca")
