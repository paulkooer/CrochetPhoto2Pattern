"""结构 v2 → 静态等距 3D 示意（服务端 SVG，零脚本/零外部依赖）。

对照 crogen/CrochetPARADE 的"逐行 → 即时 3D"思路：instances 的归一化
位置/旋转 + 部件尺寸 → 三角面片 + 画家算法 + Lambert 着色。这是示意性
结构预览，不是物理仿真；y 按全高、x/z 同尺度缩放为简化假设。

历史：v1 是 canvas 软渲染（拖拽旋转/缩放），但 st.html 的 DOMPurify
净化器剥离 <script>（1.60 实测，unsafe_allow_javascript 也不保留），
组件 iframe 方案又已过官方弃用线——改为服务端投影出静态等距 SVG，
与环形图/符号条同走 st.markdown unsafe_allow_html 通道。尺寸按整体
高度归一化适配画幅（旧 canvas 版固定焦距下 18cm 玩偶仅占 ~44px，
属未目检的存量缺陷，此处一并修复）。
"""
from __future__ import annotations

import math
from typing import Any

from app import theme
from app.models.gauge import gauge_from_result

# 单色部件的占位色（skin/body 不是毛线色名）→ 中性示意色
_PLACEHOLDER_HEX = {"skin": "#e8bfa8", "body": "#9aa7b8"}


def _hex_by_name(result: dict) -> dict[str, str]:
    """params 部件名 → 毛线色 hex（结构层的 color 字段可能还是占位符）。"""
    from app.models.colors import YARN_COLORS

    hex_by_name: dict[str, str] = {}
    for pp in (result.get("params") or {}).get("parts", []):
        pd = pp if isinstance(pp, dict) else (
            pp.model_dump() if hasattr(pp, "model_dump") else {})
        color = str(pd.get("color", ""))
        for (r, g, b), name in YARN_COLORS:
            if name == color:
                hex_by_name[str(pd.get("name"))] = f"#{r:02x}{g:02x}{b:02x}"
                break
        else:
            if color in _PLACEHOLDER_HEX:
                hex_by_name[str(pd.get("name"))] = _PLACEHOLDER_HEX[color]
    return hex_by_name


def build_payload(result: dict) -> dict[str, Any] | None:
    """result dict → 3D 预览数据；无可渲染实体时返回 None。"""
    structure = result.get("structure") or {}
    sparts = structure.get("parts") or []
    if not sparts:
        return None
    analysis = result.get("analysis") or {}
    height = float(analysis.get("height_cm") or 18.0)
    gauge = gauge_from_result(result)
    stitch_w = gauge.stitch_w_cm
    row_h = gauge.row_h_cm

    hex_by_name = _hex_by_name(result)
    rounds_by_name: dict[str, list] = {}
    for pp in (result.get("params") or {}).get("parts", []):
        pd = pp if isinstance(pp, dict) else (
            pp.model_dump() if hasattr(pp, "model_dump") else {})
        rounds_by_name[str(pd.get("name"))] = pd.get("rounds") or []

    items: list[dict[str, Any]] = []
    for part in sparts:
        name = str(part.get("name", "?"))
        shape = part.get("shape")
        entry: dict[str, Any] = {
            "name": name,
            "color": hex_by_name.get(name, "#c9a68a"),
            "shape": shape,
            "instances": [],
        }
        if shape == "profile":
            rounds = rounds_by_name.get(name) or []
            if not rounds:
                continue
            entry["lathe"] = {
                # 逐圈针数 → 半径（r = N·针宽 / 2π），与环形圈数图同口径
                "radii": [max(0.15, int(r.get("stitches", 0)) * stitch_w
                              / (2 * 3.14159265)) for r in rounds],
                "row_h": row_h,
            }
        else:
            diameter = float(part.get("diameter_cm") or 0)
            if diameter <= 0:
                # 圆柱/杯形部件的直径未存于结构层（由针数推导）：
                # r = N_max·针宽 / 2π，与环形圈数图同口径
                rounds = rounds_by_name.get(name) or []
                max_st = max((int(r.get("stitches", 0)) for r in rounds),
                             default=0)
                diameter = max_st * stitch_w / 3.14159265
            part_height = float(part.get("height_cm")
                                or part.get("length_cm") or 0)
            if shape == "sphere":
                part_height = diameter  # 球体高即直径
            if diameter <= 0 or part_height <= 0:
                continue
            entry["dims"] = {"r": diameter / 2.0, "h": part_height}
        for inst in part.get("instances", []):
            pos = inst.get("position") or {}
            rot = inst.get("rotation_deg") or {}
            entry["instances"].append({
                "p": [float(pos.get("x", 0)) * height,
                      float(pos.get("y", 0)) * height,
                      float(pos.get("z", 0)) * height],
                "r": [float(rot.get("x", 0)), float(rot.get("y", 0)),
                      float(rot.get("z", 0))],
            })
        if entry["instances"]:
            items.append(entry)
    if not items:
        return None
    return {"height": height, "items": items}


# ── 静态等距投影（服务端 SVG；视角 = 旧交互版默认 yaw 0.6 / pitch 0.35）──
_YAW, _PITCH = 0.6, 0.35
_SEG = 12          # 圆周分段（示意精度）
_LIGHT = (0.4, 0.7, -0.6)


def _hx(h: str) -> tuple[int, int, int]:
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


def _mesh_sphere(r: float) -> tuple[list, list]:
    vs, fs = [], []
    ring = 8
    for i in range(ring + 1):
        phi = math.pi * i / ring
        for j in range(_SEG + 1):
            th = 2 * math.pi * j / _SEG
            vs.append((r * math.sin(phi) * math.cos(th),
                       r * math.cos(phi), r * math.sin(phi) * math.sin(th)))
    for i in range(ring):
        for j in range(_SEG):
            a = i * (_SEG + 1) + j
            b = a + _SEG + 1
            fs.append((a, b, a + 1))
            fs.append((b, b + 1, a + 1))
    return vs, fs


def _mesh_cyl(r: float, h: float, open_top: bool) -> tuple[list, list]:
    vs, fs = [], []
    for i in range(2):
        y = -h / 2 if i else h / 2
        for j in range(_SEG + 1):
            th = 2 * math.pi * j / _SEG
            vs.append((r * math.cos(th), y, r * math.sin(th)))
    for j in range(_SEG):
        a, b = j, _SEG + 1 + j
        fs.append((a, b, a + 1))
        fs.append((b, b + 1, a + 1))
    top = len(vs)
    vs.append((0, h / 2, 0))
    bot = len(vs)
    vs.append((0, -h / 2, 0))
    for j in range(_SEG):
        if not open_top:
            fs.append((top, j + 1, j))
        fs.append((bot, j + _SEG + 2, j + _SEG + 1))
    return vs, fs


def _mesh_lathe(radii: list, row_h: float) -> tuple[list, list]:
    vs, fs = [], []
    n = len(radii)
    h = n * row_h
    for i, rad in enumerate(radii):
        y = h / 2 - i * row_h
        for j in range(_SEG + 1):
            th = 2 * math.pi * j / _SEG
            vs.append((rad * math.cos(th), y, rad * math.sin(th)))
    for i in range(n - 1):
        for j in range(_SEG):
            a = i * (_SEG + 1) + j
            b = a + _SEG + 1
            fs.append((a, b, a + 1))
            fs.append((b, b + 1, a + 1))
    c0 = list(range(_SEG + 1))
    cs = [(n - 1) * (_SEG + 1) + j for j in range(_SEG + 1)]
    top = len(vs)
    vs.append((0, h / 2, 0))
    bot = len(vs)
    vs.append((0, h / 2 - h, 0))
    for j in range(_SEG):
        fs.append((top, c0[j + 1], c0[j]))
        fs.append((bot, cs[j], cs[j + 1]))
    return vs, fs


def _view(x: float, y: float, z: float) -> tuple[float, float, float]:
    """世界系 → 视图系（yaw 绕 y，pitch 绕 x）。"""
    cy, sy = math.cos(_YAW), math.sin(_YAW)
    x1, z1 = x * cy + z * sy, -x * sy + z * cy
    cp, sp = math.cos(_PITCH), math.sin(_PITCH)
    y2, z2 = y * cp - z1 * sp, y * sp + z1 * cp
    return x1, y2, z2


def _rot_instance(v, rz_deg: float, rx_deg: float, ry_deg: float = 0.0):
    """Apply template Euler rotations in Z → X → Y order."""
    cz, sz = math.cos(math.radians(rz_deg)), math.sin(math.radians(rz_deg))
    cx, sx = math.cos(math.radians(rx_deg)), math.sin(math.radians(rx_deg))
    x1, y1 = v[0] * cz - v[1] * sz, v[0] * sz + v[1] * cz
    y2, z2 = y1 * cx - v[2] * sx, y1 * sx + v[2] * cx
    cy, sy = math.cos(math.radians(ry_deg)), math.sin(math.radians(ry_deg))
    return (x1 * cy + z2 * sy, y2, -x1 * sy + z2 * cy)


def _render_static_svg(payload: dict) -> str:
    """payload → 静态等距 SVG（画家算法 + 背面剔除 + Lambert 着色）。

    尺寸按整体高度归一化适配画幅（修复旧 canvas 固定焦距下图形过小）。
    """
    W, H = 460, 420
    faces: list[tuple[float, list, tuple, tuple]] = []
    ys: list[float] = []
    for item in payload["items"]:
        rgb = _hx(item["color"])
        if item["shape"] == "sphere":
            vs, fs = _mesh_sphere(max(float(item["dims"]["r"]), 0.4))
        elif item["shape"] == "cup":
            vs, fs = _mesh_cyl(max(float(item["dims"]["r"]), 0.4),
                               float(item["dims"]["h"]), True)
        elif item["shape"] == "cylinder":
            vs, fs = _mesh_cyl(max(float(item["dims"]["r"]), 0.4),
                               float(item["dims"]["h"]), False)
        elif item.get("lathe"):
            vs, fs = _mesh_lathe(item["lathe"]["radii"],
                                 float(item["lathe"]["row_h"]))
        else:
            continue
        for inst in item["instances"]:
            wp = [_rot_instance(v, inst["r"][2], inst["r"][0], inst["r"][1]) for v in vs]
            wp = [(v[0] + inst["p"][0], v[1] + inst["p"][1],
                   v[2] + inst["p"][2]) for v in wp]
            ys.extend(v[1] for v in wp)
            for tri in fs:
                a, b, c = wp[tri[0]], wp[tri[1]], wp[tri[2]]
                nx = ((b[1] - a[1]) * (c[2] - a[2])
                      - (b[2] - a[2]) * (c[1] - a[1]))
                ny = ((b[2] - a[2]) * (c[0] - a[0])
                      - (b[0] - a[0]) * (c[2] - a[2]))
                nz = ((b[0] - a[0]) * (c[1] - a[1])
                      - (b[1] - a[1]) * (c[0] - a[0]))
                nl = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                nx, ny, nz = nx / nl, ny / nl, nz / nl
                va, vb, vc = _view(*a), _view(*b), _view(*c)
                _, _, nvz = _view(nx, ny, nz)
                if nvz <= 0:      # 背面剔除（视图法线背向相机）
                    continue
                vz = (va[2] + vb[2] + vc[2]) / 3.0
                faces.append((vz,
                              [(va[0], va[1]), (vb[0], vb[1]),
                               (vc[0], vc[1])], rgb,
                              (abs(nx), abs(ny), abs(nz))))
    if not faces:
        return ""

    lo, hi = min(ys), max(ys)
    span = max(hi - lo, 1e-6)
    scale = 0.86 * H / span          # 高度归一化：图形占画幅 86%
    cx = W / 2.0
    cy = H / 2.0 + (hi + lo) / 2.0 * scale   # 居中

    faces.sort(key=lambda f: -f[0])  # 画家算法：远 → 近
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f"font-family='{theme.FONT_SANS}'>",
        f'<rect width="{W}" height="{H}" fill="{theme.SHEET}"/>',
    ]
    for _vz, pts, rgb, nabs in faces:
        d = max(0.0, sum(nabs[i] * _LIGHT[i] for i in range(3)))
        k = 0.55 + 0.45 * d
        fill = (f"rgb({round(rgb[0] * k)},{round(rgb[1] * k)},"
                f"{round(rgb[2] * k)})")
        pstr = " ".join(f"{cx + x * scale:.1f},{cy - y * scale:.1f}"
                        for x, y in pts)
        parts.append(
            f'<polygon points="{pstr}" fill="{fill}" '
            f'stroke="{theme.INK}" stroke-opacity="0.06" stroke-width="0.5"/>')
    parts.append(
        f'<text x="10" y="18" font-size="12" fill="{theme.INK_SOFT}">'
        "示意预览（静态等距视图，非物理仿真）</text>")
    parts.append("</svg>")
    return "".join(parts)


def structure_preview_html(result: dict) -> str | None:
    """结构 v2 → 静态等距 SVG；无可渲染实体时返回 None。

    与环形图/符号条同通道：经 st.markdown unsafe_allow_html 渲染
    （st.html 的净化器剥 <svg> 与 <script>，1.60 实测）。
    """
    payload = build_payload(result)
    if payload is None:
        return None
    return _render_static_svg(payload)
