"""Profile-driven shaping —— 照片轮廓剖面 → 旋转体逐圈针数。

范式依据（已联网核实）：
- AmiGo: Computational Design of Amigurumi Crochet Patterns
  (Zur & Edelstein 等, Technion, SIGGRAPH Asia 2022 / arXiv:2211.01178)
  —— 3D 模型按表面横向切圈，每圈针数 = 该圈周长 ÷ 针宽。
- 单张正面照没有 3D 网格，但"轮廓剖面 + 圆形截面假设 = 旋转体"，
  信息刚好够用（fable5 方案的本地化）。
- 每圈针数变化 ≤ ±6 的惯例有几何依据：短针平盘的极限加针率
  Δ = 2π·(行高/针宽) ≈ 6 针/圈，超过会起浪/起褶。

生成约束：针数恒为 6 的倍数、相邻圈 |ΔN| ≤ 6、剖面三点平滑。
模板形状（球/柱/杯）仍作为"无照片"时的降级路径保留。
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple


def _smooth3(values: Sequence[float]) -> List[float]:
    out = []
    n = len(values)
    for i, v in enumerate(values):
        lo = values[max(0, i - 1)]
        hi = values[min(n - 1, i + 1)]
        out.append((lo + 2.0 * v + hi) / 4.0)
    return out


def profile_to_rounds(
    profile: Sequence[float],
    span: Tuple[float, float],
    height_cm: float,
    gauge,
    ref_stitches: int,
    direction: str = "bottom_up",
    min_rounds: int = 3,
) -> List[int]:
    """照片宽度剖面 → 部件筒壁逐圈针数（返回每圈针数列表，按钩织顺序）。

    Args:
        profile:      主体归一化宽度剖面（index 0 = 照片顶部，1.0 = 主体最宽）。
        span:         该部件在主体上的纵向占比 (start, end)，0 顶 → 1 底。
        height_cm:    该部件筒壁目标高度。
        gauge:        Gauge（针宽/行高来源）。
        ref_stitches: 部件区间内"最宽处"的锚点针数（如身体 = 头径比例锚点）。
        direction:    "bottom_up"（R1=照片低处，身体/四肢）或 "top_down"。

    Returns:
        每圈针数（6 的倍数、相邻差 ≤6、≥6），自 R1 起的钩织顺序。
    """
    span_s, span_e = span
    span_len = max(1e-6, span_e - span_s)
    n = len(profile)
    wall_n = max(min_rounds, gauge.rounds_for_height(height_cm))

    # 采样部件区间的剖面（自照片顶部到底部），并按区间峰值归一
    raw = []
    for j in range(wall_n):
        f = (j + 0.5) / wall_n            # 0=区间顶（照片上方）
        frac = span_s + span_len * f
        idx = min(n - 1, max(0, int(frac * n)))
        raw.append(max(0.0, float(profile[idx])))
    peak = max(raw) or 1.0
    norm = _smooth3([v / peak for v in raw])

    # 目标针数 → 6 的倍数量化（锚点 ref 对应区间最宽处）
    targets = [max(6, int(round(v * ref_stitches / 6.0)) * 6) for v in norm]

    # 钩织顺序映射 + 相邻圈 |Δ| ≤ 6 钳制（物理极限：不起浪不起褶）
    order = list(reversed(targets)) if direction == "bottom_up" else list(targets)
    clamped = [order[0]]
    for t in order[1:]:
        prev = clamped[-1]
        if t > prev + 6:
            t = prev + 6
        elif t < prev - 6:
            t = prev - 6
        clamped.append(max(6, t))
    return clamped


def rounds_to_notes(stitches: Sequence[int]) -> List[str]:
    """逐圈针数 → 标准符号说明（复用通行 (aX,V)/(aX,A) 口径）。"""
    from .crochet_params import _dec_note, _inc_note_by_before

    notes = []
    for i, n in enumerate(stitches):
        if i == 0:
            notes.append(f"{n}X（起针圈）")
            continue
        before = stitches[i - 1]
        if n == before:
            notes.append(f"{n}X（不加不减）")
        elif n > before:
            notes.append(_inc_note_by_before(before))
        else:
            notes.append(_dec_note(before))
    return notes


def render_silhouette_svg(
    stitches: Sequence[int],
    gauge,
    photo_profile: Optional[Sequence[float]] = None,
    span: Optional[Tuple[float, float]] = None,
    width_px: int = 220,
    height_px: int = 300,
) -> str:
    """把生成的逐圈针数反渲染为旋转体侧影，可叠加照片剖面（M1.5 可视化）。

    生成侧影：第 j 圈直径 = N×针宽，纵向每圈一个行高——与照片剖面同框
    叠加，"图解↔照片"的对应关系一眼可见（也作为回归的可视指标）。
    """
    n_rounds = len(stitches)
    row_h = gauge.row_h_cm
    stitch_w = gauge.stitch_w_cm
    body_h_cm = n_rounds * row_h
    max_d_cm = max(s * stitch_w / math.pi for s in stitches) if stitches else 1.0

    pad = 14.0
    usable_w = width_px - 2 * pad
    usable_h = height_px - 2 * pad
    scale_x = usable_w / (2.0 * max(max_d_cm, 1e-6)) / 2.0  # 半宽比例
    scale_y = usable_h / max(body_h_cm, 1e-6)
    cx = width_px / 2.0

    def y_of(j: int) -> float:      # j=0（R1，底部）在图下方
        return pad + usable_h - (j + 0.5) * row_h * scale_y

    # 生成侧影（左右镜像闭合）
    pts_right = [(cx + s * stitch_w / math.pi * scale_x, y_of(j))
                 for j, s in enumerate(stitches)]
    pts_left = [(2 * cx - x, y) for (x, y) in reversed(pts_right)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_right + pts_left)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" '
        f'height="{height_px}" viewBox="0 0 {width_px} {height_px}">',
        f'<rect width="{width_px}" height="{height_px}" fill="#fafafa" '
        f'stroke="#ddd"/>',
        '<text x="6" y="12" font-size="10" fill="#666">生成侧影（照片驱动）</text>',
        f'<polygon points="{poly}" fill="#9ecae1" fill-opacity="0.55" '
        f'stroke="#2171b5" stroke-width="1.2"/>',
    ]

    # 照片剖面对照（同一部件区间，按峰值对齐到锚点半宽）
    if photo_profile and span:
        span_s, span_e = span
        m = len(photo_profile)
        ref_d_cm = max(s * stitch_w / math.pi for s in stitches)
        pts = []
        for j in range(n_rounds):
            f = (j + 0.5) / n_rounds
            frac = span_e - (span_e - span_s) * f   # 自底向上（R1=照片低处）
            idx = min(m - 1, max(0, int(frac * m)))
            half = float(photo_profile[idx]) * (ref_d_cm / 2.0) * scale_x
            pts.append((cx + half, y_of(j)))
        pts += [(2 * cx - x, y) for (x, y) in reversed(pts)]
        poly2 = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        lines.append(
            f'<polygon points="{poly2}" fill="none" stroke="#e6550d" '
            f'stroke-width="1.2" stroke-dasharray="4 2"/>')
        lines.append(
            f'<text x="6" y="{height_px - 6}" font-size="10" fill="#e6550d">'
            f'虚线=照片轮廓</text>')
    lines.append("</svg>")
    return "\n".join(lines)
