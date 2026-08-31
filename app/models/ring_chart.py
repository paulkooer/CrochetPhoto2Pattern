"""RingChart（T8）——部件顶视图的环形圈数图。

借鉴 CrochetPARADE 的符号图思路，把"逐圈配色 + 针数"画成同心圆：
每圈半径 = 该圈物理周长的一半（r = N·针宽 / 2π），颜色 = 该圈毛线色。
球形成部件的顶视图即真实形状；加针段圆环外扩、减针段内收，一眼可读。

SVG 结构：配色圆 + 右侧引线标注（圈号 · 针数 · 颜色名），交替节距防重叠。
"""
from __future__ import annotations

import html
from typing import Any, Dict, List

_SVG_W, _SVG_H = 320, 320


def render_ring_svg(part: Any, stitch_w_cm: float = 0.77) -> str:
    """部件 → 环形圈数图 SVG 字符串。

    part 可为 CrochetPart 或 dict（JSON 修正路径）；无配色圈退化为灰环。
    """
    rounds_raw = (part.get("rounds", []) if isinstance(part, dict)
                  else getattr(part, "rounds", []))
    rounds: List[Dict[str, Any]] = []
    for r in rounds_raw:
        rounds.append(r if isinstance(r, dict) else (
            r.model_dump() if hasattr(r, "model_dump") else {}))
    if not rounds:
        return ""

    name = (part.get("name") if isinstance(part, dict)
            else getattr(part, "name", "?"))
    hex_of = _rgb_hex_lookup()

    # 物理半径：r = N·针宽 / 2π；最外圈占满可用区
    radii = [max(0.5, r.get("stitches", 1) * stitch_w_cm / (2 * 3.14159265))
             for r in rounds]
    r_max = max(radii)
    cx, cy = _SVG_W / 2, _SVG_H / 2 + 8
    usable = min(_SVG_W, _SVG_H) / 2 - 26
    scale = usable / r_max if r_max else 1.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_W}" '
        f'height="{_SVG_H}" viewBox="0 0 {_SVG_W} {_SVG_H}">',
        f'<rect width="{_SVG_W}" height="{_SVG_H}" fill="#fffdf8" '
        f'stroke="#ead8ca" rx="12"/>',
        f'<text x="12" y="18" font-size="12" fill="#543f35">'
        f'{html.escape(str(name))} · 顶视图（内=起针）</text>',
    ]

    # F19：只标注"变化圈"——首圈、末圈、以及配色或加/减针相位相对
    # 上一圈发生变化的位置。逐圈标注在 >14 圈时标签必然重叠（旧实现
    # (i%14)*18 造成 R1/R15 同坐标）；完整信息在旁边的逐圈表格里。
    def _phase(rd: Dict[str, Any]) -> Any:
        return (int(rd.get("increase") or 0) > 0,
                int(rd.get("decrease") or 0) > 0)

    labeled: List[int] = []
    for i, rd in enumerate(rounds):
        if i == 0 or i == len(rounds) - 1:
            labeled.append(i)
            continue
        prev = rounds[i - 1]
        if rd.get("color") != prev.get("color") or _phase(rd) != _phase(prev):
            labeled.append(i)

    # 全部圈都绘制几何圆环（顶视图形状完整），仅标注走变化圈过滤
    for i, rd in enumerate(rounds):
        r_px = radii[i] * scale
        c = rd.get("color")
        fill = hex_of.get(c, "#e8e0d8") if c else "#e8e0d8"
        stroke = "#b9a795" if not c else "#8f7d6d"
        if r_px >= 1:
            lines.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r_px:.1f}" '
                f'fill="{fill}" fill-opacity="0.55" stroke="{stroke}" '
                f'stroke-width="1"/>')

    label_ys: List[float] = []
    for i in labeled:
        rd = rounds[i]
        c = rd.get("color")
        # 标注双列交替 + 节距按标签数动态分配，保证坐标唯一不重叠
        idx = len(label_ys)
        row, col = idx % 14, idx // 14
        ly = 34 + row * 18
        side = 186 if col % 2 == 0 else 244
        label_ys.append(ly)
        lines.append(
            f'<text x="{side}" y="{ly + 8}" font-size="9.5" fill="#543f35">'
            f'R{i + 1} · {rd.get("stitches", "?")}X'
            f'{(" · " + html.escape(str(c))) if c else ""}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


_HEX_CACHE: Dict[str, str] = {}


def _rgb_hex_lookup() -> Dict[str, str]:
    """毛线色名 → hex（模块级缓存）。"""
    if not _HEX_CACHE:
        from .colors import YARN_COLORS
        for rgb, name in YARN_COLORS:
            _HEX_CACHE[name] = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    return _HEX_CACHE


def _spread_operations(total: int, special: int, symbol: str) -> List[str]:
    """Distribute increases/decreases evenly across crochet operations."""
    total = max(0, int(total))
    special = max(0, min(int(special), total))
    if total == 0:
        return []
    # Integer accumulator: 30 operations / 6 increases becomes
    # (X X X X V) × 6, with no floating-point drift.
    return [
        symbol if ((i + 1) * special) // total > (i * special) // total else "X"
        for i in range(total)
    ]


def _round_operation_sequence(rounds: List[Dict[str, Any]], index: int) -> List[str]:
    """Compile aggregate round counts into operations on the previous round.

    V consumes one stitch and produces two; A consumes two and produces one.
    Therefore an increase round has ``previous_stitches`` operations, while a
    decrease round has ``result_stitches`` operations.  This distinction was
    lost when the old chart used the result stitch count for every row.
    """
    rd = rounds[index]
    stitches = max(0, int(rd.get("stitches", 0) or 0))
    increase = max(0, int(rd.get("increase") or 0))
    decrease = max(0, int(rd.get("decrease") or 0))
    if index == 0:
        return ["X"] * stitches
    if increase and not decrease:
        previous = max(0, int(rounds[index - 1].get("stitches", 0) or 0))
        return _spread_operations(previous, increase, "V")
    if decrease and not increase:
        return _spread_operations(stitches, decrease, "A")
    return ["X"] * stitches


def render_symbol_strip(part: Any, max_marks: int = 18,
                        max_rounds: int = 24) -> str:
    """逐圈符号条（U7）——把每圈可执行的针法序列画成记号横条。

    记号与本仓记号体系一致（图例随图自带）：
      ×  = 短针 X        两条交叉短线
      V  = 加针（1 针目出 2 针，两腿并立向上）
      A  = 减针（2 针并 1，两腿并立向下）
    每行最多画 max_marks 个记号，超出以 "+N" 截断；行数超过 max_rounds
    时只显示末 max_rounds 行（起针圈在最上，向下递增）。
    """
    rounds_raw = (part.get("rounds", []) if isinstance(part, dict)
                  else getattr(part, "rounds", []))
    rounds: List[Dict[str, Any]] = []
    for r in rounds_raw:
        rounds.append(r if isinstance(r, dict) else (
            r.model_dump() if hasattr(r, "model_dump") else {}))
    if not rounds:
        return ""
    name = (part.get("name") if isinstance(part, dict)
            else getattr(part, "name", "?"))
    all_rounds = rounds
    start_row = max(0, len(all_rounds) - max_rounds)
    rounds = all_rounds[start_row:]

    mark_w, row_h, left = 14, 16, 46
    width = left + max_marks * mark_w + 60
    height = len(rounds) * row_h + 30
    hex_of = _rgb_hex_lookup()

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#fffdf8" '
        f'stroke="#ead8ca" rx="10"/>',
        f'<text x="8" y="16" font-size="11" fill="#543f35">'
        f'{html.escape(str(name))} · 逐圈符号条'
        f'（{"自起针圈后 " + str(start_row + 1) + " 圈起" if start_row else "自起针圈"}）</text>',
        # 图例
        f'<text x="{width - 118}" y="16" font-size="9.5" fill="#806d63">'
        f'图例：×=X · V=加针 · A=减针</text>',
    ]

    def _glyph_x(x: float, y: float) -> str:
        return (f'<line x1="{x-3:.1f}" y1="{y-3:.1f}" x2="{x+3:.1f}" y2="{y+3:.1f}" '
                f'stroke="{stroke}" stroke-width="1.4"/>'
                f'<line x1="{x-3:.1f}" y1="{y+3:.1f}" x2="{x+3:.1f}" y2="{y-3:.1f}" '
                f'stroke="{stroke}" stroke-width="1.4"/>')

    def _glyph_v(x: float, y: float) -> str:  # 加针：两腿向上并立（V）
        return (f'<path d="M {x-4:.1f} {y-4:.1f} L {x:.1f} {y+4:.1f} '
                f'L {x+4:.1f} {y-4:.1f}" fill="none" stroke="{stroke}" '
                f'stroke-width="1.4"/>')

    def _glyph_a(x: float, y: float) -> str:  # 减针：两腿向下并立（倒 V）
        return (f'<path d="M {x-4:.1f} {y+4:.1f} L {x:.1f} {y-4:.1f} '
                f'L {x+4:.1f} {y+4:.1f}" fill="none" stroke="{stroke}" '
                f'stroke-width="1.4"/>')

    for ri, rd in enumerate(rounds):
        y = 30 + ri * row_h
        c = rd.get("color")
        stroke = hex_of.get(c, "#543f35") if c else "#543f35"
        n = int(rd.get("stitches", 0) or 0)
        seq = _round_operation_sequence(all_rounds, start_row + ri)
        shown = min(len(seq), max_marks)
        marks = []
        for mi, kind in enumerate(seq[:shown]):
            gx = left + mi * mark_w + mark_w / 2
            gy = y + 4
            glyph = {"X": _glyph_x, "V": _glyph_v, "A": _glyph_a}[kind](gx, gy)
            marks.append(f'<g data-kind="{kind}">{glyph}</g>')
        row_svg = "".join(marks)
        overflow = len(seq) - shown
        suffix = (f'<text x="{left + max_marks * mark_w + 4:.1f}" y="{y + 8}" '
                  f'font-size="9" fill="#806d63">+{overflow}</text>'
                  if overflow > 0 else "")
        label = f'R{start_row + ri + 1} · 成圈 {n}X'
        lines.append(
            f'<text x="8" y="{y + 8:.1f}" font-size="9.5" fill="#543f35">'
            f'{html.escape(label)}</text>')
        lines.append(row_svg + suffix)
    lines.append("</svg>")
    return "\n".join(lines)
