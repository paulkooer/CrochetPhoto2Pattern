"""grid_pattern.py - 2D Pixel / Tapestry Crochet Pattern Generator.

Converts any PIL image into a color-coded grid pattern suitable for
tapestry crochet, C2C (corner-to-corner), or cross-stitch projects.
No external dependencies beyond Pillow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
from PIL import Image


@dataclass
class GridCell:
    """A single cell in the crochet grid."""
    col_index: int
    color_name: str
    rgb: Tuple[int, int, int]


@dataclass
class GridPattern:
    """Complete 2D grid pattern ready for rendering."""
    width: int
    height: int
    clamped_from: Optional[int] = None   # F28：行数被钳制前的原始行数
    cells: List[List[GridCell]] = None
    palette: List[Tuple[str, Tuple[int, int, int]]] = None
    symbol_map: Dict[int, str] = None


_SYMBOLS = "■▲●◆★✦◉▼⊕①②③④⑤⑥⑦⑧⑨⑩"

# UI slider 与文档约定的调色上限（符号表 20 个只是防御性硬顶）
_MAX_PALETTE = 10
# F28：网格单元总数上界——1×10000 的细长图按宽高比推导可放大到 30 万行
# （实测 4.5GB RSS + 2.2GB SVG 字符串塞进 session_state）。8 万格
# （≈80 列 × 1000 行）已远超实用图案尺寸；被钳制时 GridPattern.clamped_from
# 记录原始行数，UI 诚实告知。
_MAX_CELLS = 80_000
_MAX_GRID_WIDTH = 200
_GRID_PROJECT_FORMAT = "crochet-photo2pattern-grid"
_GRID_PROJECT_VERSION = "1.0"
GRID_PROJECT_MAX_BYTES = 1_000_000
_MAX_COLOR_NAME_CHARS = 64


def _strict_int(value: Any, message: str) -> int:
    """Accept a JSON integer, not bool/float/numeric text coercions."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(message)
    return value


def crop_image_fraction(
    image: Image.Image,
    left: float = 0.0,
    top: float = 0.0,
    right: float = 1.0,
    bottom: float = 1.0,
) -> Image.Image:
    """Crop using normalized image coordinates without resizing the source.

    Coordinates use the image convention (top-left origin) and are clamped to
    ``[0, 1]``.  A zero-area selection is rejected instead of silently
    producing a misleading two-row grid.
    """
    import math

    values = (left, top, right, bottom)
    try:
        left, top, right, bottom = (float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise ValueError("crop coordinates must be finite numbers") from exc
    if not all(math.isfinite(value) for value in (left, top, right, bottom)):
        raise ValueError("crop coordinates must be finite numbers")
    left, top = max(0.0, left), max(0.0, top)
    right, bottom = min(1.0, right), min(1.0, bottom)
    if right <= left or bottom <= top:
        raise ValueError("crop selection must have positive width and height")

    width, height = image.size
    x0 = min(width - 1, int(math.floor(left * width)))
    y0 = min(height - 1, int(math.floor(top * height)))
    x1 = max(x0 + 1, min(width, int(math.ceil(right * width))))
    y1 = max(y0 + 1, min(height, int(math.ceil(bottom * height))))
    return image.crop((x0, y0, x1, y1))


def grid_pattern_to_payload(pattern: GridPattern) -> Dict[str, Any]:
    """Serialize a grid without retaining tens of thousands of cell objects."""
    return {
        "width": pattern.width,
        "height": pattern.height,
        "clamped_from": pattern.clamped_from,
        "palette": [
            {"name": name, "rgb": list(rgb)} for name, rgb in pattern.palette
        ],
        "cells": [
            [cell.col_index for cell in row] for row in pattern.cells
        ],
    }


def grid_pattern_from_payload(payload: Mapping[str, Any]) -> GridPattern:
    """Restore and validate the lightweight session payload.

    The payload is intentionally strict because it may survive Streamlit
    reruns independently from the original image.  Invalid dimensions,
    palette values or cell indices are rejected before any renderer sees them.
    """
    try:
        width = _strict_int(payload["width"], "grid payload width is invalid")
        height = _strict_int(payload["height"], "grid payload height is invalid")
        raw_palette = payload["palette"]
        raw_cells = payload["cells"]
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid grid payload header") from exc
    if (width < 1 or width > _MAX_GRID_WIDTH or height < 1
            or width * height > _MAX_CELLS):
        raise ValueError("grid payload dimensions are out of bounds")
    if not isinstance(raw_palette, list) or not 1 <= len(raw_palette) <= _MAX_PALETTE:
        raise ValueError("grid payload palette is invalid")

    from .colors import YARN_COLORS
    yarn_rgb_by_name = {
        yarn_name: yarn_rgb for yarn_rgb, yarn_name in YARN_COLORS
    }
    palette: List[Tuple[str, Tuple[int, int, int]]] = []
    seen_names = set()
    for entry in raw_palette:
        if not isinstance(entry, Mapping):
            raise ValueError("grid payload palette entry is invalid")
        raw_name = entry.get("name")
        name = raw_name if isinstance(raw_name, str) else ""
        raw_rgb = entry.get("rgb")
        if (not name or len(name) > _MAX_COLOR_NAME_CHARS
                or not isinstance(raw_rgb, (list, tuple)) or len(raw_rgb) != 3):
            raise ValueError("grid payload palette entry is invalid")
        try:
            rgb = tuple(_strict_int(channel, "grid payload RGB is invalid")
                        for channel in raw_rgb)
        except ValueError as exc:
            raise ValueError("grid payload RGB is invalid") from exc
        if any(channel < 0 or channel > 255 for channel in rgb):
            raise ValueError("grid payload RGB is invalid")
        expected_rgb = yarn_rgb_by_name.get(name)
        if expected_rgb is None:
            raise ValueError("grid payload color is not in the yarn palette")
        if rgb != expected_rgb:
            raise ValueError("grid payload color RGB does not match the yarn palette")
        if name in seen_names:
            raise ValueError("grid payload palette contains duplicate colors")
        seen_names.add(name)
        palette.append((name, rgb))

    if not isinstance(raw_cells, list) or len(raw_cells) != height:
        raise ValueError("grid payload row count does not match height")
    cells: List[List[GridCell]] = []
    for raw_row in raw_cells:
        if not isinstance(raw_row, list) or len(raw_row) != width:
            raise ValueError("grid payload column count does not match width")
        row: List[GridCell] = []
        for raw_index in raw_row:
            try:
                index = _strict_int(
                    raw_index, "grid payload cell index is invalid")
            except ValueError as exc:
                raise ValueError("grid payload cell index is invalid") from exc
            if index < 0 or index >= len(palette):
                raise ValueError("grid payload cell index is invalid")
            name, rgb = palette[index]
            row.append(GridCell(index, name, rgb))
        cells.append(row)

    clamped_from = payload.get("clamped_from")
    if clamped_from is not None:
        try:
            clamped_from = _strict_int(
                clamped_from, "grid payload clamp metadata is invalid")
        except ValueError as exc:
            raise ValueError("grid payload clamp metadata is invalid") from exc
        if clamped_from < height:
            raise ValueError("grid payload clamp metadata is invalid")
    return GridPattern(
        width=width,
        height=height,
        clamped_from=clamped_from,
        cells=cells,
        palette=palette,
        symbol_map={index: _SYMBOLS[index] for index in range(len(palette))},
    )


def export_grid_project(pattern: GridPattern) -> bytes:
    """Encode the editable chart as a compact, versioned UTF-8 JSON project."""
    project = {
        "format": _GRID_PROJECT_FORMAT,
        "schema_version": _GRID_PROJECT_VERSION,
        "pattern": grid_pattern_to_payload(pattern),
    }
    data = json.dumps(
        project, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(data) > GRID_PROJECT_MAX_BYTES:
        raise ValueError("grid project exceeds the size limit")
    return data


def _reject_duplicate_json_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def import_grid_project(data: Any) -> GridPattern:
    """Decode an editable project under a pre-parse byte limit.

    The limit is checked before UTF-8 decoding/JSON parsing.  Duplicate keys,
    unsupported versions and all malformed grid topology are rejected.
    """
    if isinstance(data, str):
        raw = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        raise ValueError("grid project must be UTF-8 JSON bytes or text")
    if len(raw) > GRID_PROJECT_MAX_BYTES:
        raise ValueError("grid project exceeds the size limit")
    try:
        project = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("grid project is not valid UTF-8 JSON") from exc
    if not isinstance(project, Mapping):
        raise ValueError("grid project root must be an object")
    if project.get("format") != _GRID_PROJECT_FORMAT:
        raise ValueError("unsupported grid project format")
    if project.get("schema_version") != _GRID_PROJECT_VERSION:
        raise ValueError("unsupported grid project schema version")
    pattern_payload = project.get("pattern")
    if not isinstance(pattern_payload, Mapping):
        raise ValueError("grid project pattern is missing")
    return grid_pattern_from_payload(pattern_payload)


def recolor_grid_cell(
    pattern: GridPattern,
    row_index: int,
    column_index: int,
    palette_index: int,
) -> int:
    """Change one cell to an existing yarn color without requantizing the image."""
    return recolor_grid_region(
        pattern,
        row_start=row_index,
        row_end=row_index,
        column_start=column_index,
        column_end=column_index,
        palette_index=palette_index,
    )


def recolor_grid_region(
    pattern: GridPattern,
    row_start: int,
    row_end: int,
    column_start: int,
    column_end: int,
    palette_index: int,
) -> int:
    """Recolor an inclusive image-coordinate rectangle; return changed cells.

    Rows use the stored image convention (top to bottom).  The UI converts
    crochet row numbers (bottom to top) before calling this model function.
    Reversed or out-of-range rectangles are rejected so accidental coordinate
    swaps cannot silently edit a different part of the chart.
    """
    if row_start > row_end or column_start > column_end:
        raise ValueError("grid region start must not exceed end")
    if row_start < 0 or row_end >= pattern.height:
        raise IndexError("grid row is out of range")
    if column_start < 0 or column_end >= pattern.width:
        raise IndexError("grid column is out of range")
    if not 0 <= palette_index < len(pattern.palette):
        raise ValueError("palette index is out of range")
    name, rgb = pattern.palette[palette_index]
    changed = 0
    for row_index in range(row_start, row_end + 1):
        for column_index in range(column_start, column_end + 1):
            cell = pattern.cells[row_index][column_index]
            if cell.col_index == palette_index:
                continue
            pattern.cells[row_index][column_index] = GridCell(
                col_index=palette_index,
                color_name=name,
                rgb=rgb,
            )
            changed += 1
    return changed


def generate_grid_pattern(
    image: Image.Image,
    grid_width: int = 40,
    n_colors: int = 6,
    aspect_ratio: float = 0.75,
    resample: str = "lanczos",
) -> GridPattern:
    """Convert a PIL image to a 2D tapestry crochet grid pattern.

    Args:
        image:        Source image (any mode).
        grid_width:   Number of stitches (columns) in the output.
        n_colors:     Number of yarn colors in the palette (2-10).
        aspect_ratio: Stitch width/height ratio. Single crochet ~0.75.
        resample:     缩放算法："lanczos"（面积加权，照片平滑，默认）或
                      "nearest"（单点采样，像素画不糊边）。

    Returns:
        GridPattern with cells, palette, and symbol map.
    """
    n_colors = max(2, min(n_colors, _MAX_PALETTE, len(_SYMBOLS)))
    grid_width = min(grid_width, _MAX_GRID_WIDTH)
    img = image.convert("RGB")
    orig_w, orig_h = img.size
    # 比例补偿推导（aspect_ratio = 针的宽/高，sc≈0.75 即针略"高"）：
    #   成品宽/高 = grid_width·w / (grid_height·h) 应等于 orig_w/orig_h
    #   ⇒ grid_height = grid_width · (w/h) · orig_h/orig_w = grid_width · aspect_ratio · orig_h/orig_w
    # 例：正方形图片 + 0.75 → 行数 = 列数×0.75，成品因针本身偏高仍为正方形。
    # int(x+0.5) 半步向上取整（Python round 是银行家舍入，.5 偏向偶数）。
    grid_height = max(2, int(grid_width * orig_h / orig_w * aspect_ratio + 0.5))
    clamped_from: Optional[int] = None
    if grid_height > _MAX_CELLS // grid_width:
        clamped_from = grid_height
        grid_height = max(2, _MAX_CELLS // grid_width)
    resampler = (Image.Resampling.NEAREST if resample == "nearest"
                 else Image.Resampling.LANCZOS)
    img_small = img.resize((grid_width, grid_height), resampler)

    # S3 直量化：调色板直接限定为毛线色表（coverage 直选 + CIEDE2000
    # 最近邻分配），替代"中位切分任意色 → 再映射毛线表"的双重量化——
    # 图案里的每一色都是真实可购买的毛线。
    from .colors import YARN_COLORS, _srgb_to_lab_vec, ciede2000_vec, pick_yarn_palette
    pixels = [tuple(int(v) for v in px) for px in np.asarray(
        img_small, dtype=np.uint8).reshape(-1, 3)]
    palette_rgbs = pick_yarn_palette(pixels, n_colors)
    name_by_rgb = {rgb: name for rgb, name in YARN_COLORS}
    palette: List[Tuple[str, Tuple[int, int, int]]] = [
        (name_by_rgb[rgb], rgb) for rgb in palette_rgbs]

    symbol_map = {i: _SYMBOLS[i % len(_SYMBOLS)] for i in range(len(palette))}

    # 逐像素 → 所选色板最近色（K1 批量版）
    px_arr = np.array(pixels, dtype=np.int32)
    px_labs = _srgb_to_lab_vec(px_arr)
    pal_labs = _srgb_to_lab_vec(np.array(palette_rgbs, dtype=np.int32))
    dmat = ciede2000_vec(px_labs, pal_labs, pairwise=False)  # (像素数, 色板数)
    best_idx = dmat.argmin(axis=1)
    flat: List[GridCell] = []
    if len(best_idx) != len(pixels):
        raise RuntimeError("palette assignment count does not match grid pixels")
    for bi, _px in zip(best_idx, pixels):  # noqa: B905 - length checked above
        name, yarn_rgb = palette[bi]
        flat.append(GridCell(col_index=bi, color_name=name, rgb=yarn_rgb))
    cells = [flat[r * grid_width:(r + 1) * grid_width]
             for r in range(grid_height)]

    return GridPattern(
        width=grid_width, height=grid_height, clamped_from=clamped_from,
        cells=cells, palette=palette, symbol_map=symbol_map,
    )


def render_svg(pattern: GridPattern, cell_px: int = 14) -> str:
    """Render a GridPattern as an SVG string with colored cells and symbol overlays."""
    W = pattern.width * cell_px
    H = pattern.height * cell_px
    font_size = max(6, cell_px - 4)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" style="font-family:monospace;">',
    ]
    for row_idx, row in enumerate(pattern.cells):
        y = row_idx * cell_px
        for col_idx, cell in enumerate(row):
            x = col_idx * cell_px
            rv, gv, bv = cell.rgb
            hex_color = f"#{rv:02x}{gv:02x}{bv:02x}"
            sym = pattern.symbol_map.get(cell.col_index, "?")
            lum = 0.299 * rv + 0.587 * gv + 0.114 * bv
            txt_color = "#ffffff" if lum < 128 else "#000000"
            lines.append(
                f'<rect x="{x}" y="{y}" width="{cell_px}" height="{cell_px}" '
                f'fill="{hex_color}" stroke="#888" stroke-width="0.3"/>')
            if cell_px >= 10:
                lines.append(
                    f'<text x="{x + cell_px // 2}" y="{y + cell_px - 2}" '
                    f'text-anchor="middle" font-size="{font_size}" fill="{txt_color}">'
                    + sym + "</text>")
    # Bold grid lines every 10 cells
    for i in range(0, pattern.width + 1, 10):
        x = i * cell_px
        lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="#444" stroke-width="1"/>')
    for i in range(0, pattern.height + 1, 10):
        y = i * cell_px
        lines.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="#444" stroke-width="1"/>')
    lines.append("</svg>")
    return "\n".join(lines)


def render_legend_markdown(pattern: GridPattern) -> str:
    """Return a Markdown table for the color legend with usage percentages."""
    lines = ["| 符号 | 颜色名称 | 用量估算 |", "|:----:|:--------:|:--------:|"]
    total = pattern.width * pattern.height
    counts: Dict[int, int] = {}
    for row in pattern.cells:
        for cell in row:
            counts[cell.col_index] = counts.get(cell.col_index, 0) + 1
    for idx, (name, _rgb) in enumerate(pattern.palette):
        sym = pattern.symbol_map.get(idx, "?")
        cnt = counts.get(idx, 0)
        pct = round(cnt / total * 100) if total else 0
        safe_name = str(name).replace("\\", "\\\\").replace(
            "|", "\\|").replace("\r", " ").replace("\n", " ")
        lines.append(f"| {sym} | {safe_name} | {pct}% ({cnt} 格) |")
    return "\n".join(lines)


def export_grid_markdown(
    pattern: GridPattern,
    *,
    legend: Optional[str] = None,
    chart: Optional[str] = None,
    c2c: Optional[str] = None,
) -> str:
    """Build a self-contained printable chart, not merely a color legend.

    Optional pre-rendered sections let the Streamlit cache reuse work already
    performed for its preview.  Indented code blocks are used so even unusual
    text cannot terminate a Markdown fence.
    """
    legend = legend if legend is not None else render_legend_markdown(pattern)
    chart = chart if chart is not None else render_text_chart(pattern)
    c2c = c2c if c2c is not None else render_c2c_chart(pattern)

    def indented(text: str) -> str:
        return "\n".join(f"    {line}" for line in str(text).splitlines())

    return "\n".join([
        "# 🧶 平面网格钩织图解",
        "",
        f"> 网格：{pattern.width} 列 × {pattern.height} 行 · "
        f"{len(pattern.palette)} 种毛线色",
        "> 坐标：R1 是成品底行；每行符号从左向右阅读。",
        "",
        "## 颜色图例",
        "",
        legend,
        "",
        "## Tapestry / 十字绣逐行符号图",
        "",
        indented(chart),
        "",
        "## C2C 对角行指令",
        "",
        indented(c2c),
        "",
        "---",
        "*由 CrochetPhoto2Pattern 生成；请先用实际毛线试钩小样。*",
    ])


def render_legend_html(pattern: GridPattern) -> str:
    """带真实色块的屏幕图例（对应 render_legend_markdown 的下载版）。

    每行一个色样方块（palette 的实际 RGB）+ 符号 + 名称 + 占比；
    颜色名经 html.escape 后进 unsafe_allow_html 渲染。
    """
    import html as _html

    total = pattern.width * pattern.height
    counts: Dict[int, int] = {}
    for row in pattern.cells:
        for cell in row:
            counts[cell.col_index] = counts.get(cell.col_index, 0) + 1
    rows = []
    for idx, (name, rgb) in enumerate(pattern.palette):
        hex_bg = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
        sym_color = "#ffffff" if lum < 128 else "#222222"
        sym = pattern.symbol_map.get(idx, "?")
        cnt = counts.get(idx, 0)
        pct = round(cnt / total * 100) if total else 0
        rows.append(
            f"<div style='display:flex;align-items:center;gap:8px;"
            f"margin:4px 0;'>"
            f"<span style='width:26px;height:26px;border-radius:6px;"
            f"background:{hex_bg};border:1px solid rgba(0,0,0,0.2);"
            f"display:inline-flex;align-items:center;justify-content:center;"
            f"color:{sym_color};font-size:13px;'>{sym}</span>"
            f"<span style='font-size:0.85rem;'>{_html.escape(name)}"
            f"</span><span style='color:#888;font-size:0.78rem;'>"
            f"{pct}%</span></div>")
    return ("<div style='display:flex;flex-direction:column;gap:2px;'>"
            + "".join(rows) + "</div>")


def render_text_chart(pattern: GridPattern) -> str:
    """Return a plain-text symbol chart (rows from bottom-up, crochet style)."""
    rows = []
    for row_idx, row in enumerate(pattern.cells):
        row_num = pattern.height - row_idx
        sym_row = "".join(pattern.symbol_map.get(c.col_index, "?") for c in row)
        rows.append(f"R{row_num:02d}: {sym_row}")
    return "\n".join(rows)


def render_c2c_chart(pattern: GridPattern) -> str:
    """C2C（corner-to-corner）逐行指令（T3）——对角行 word chart。

    C2C 以"格子块"（tile，3 长针的方块）沿对角线编织：对角行 k 含
    min(k, W, H, W+H-k) 个 tile（增→平→减）。本图从**左下角**开始，
    每行给出工作顺序的 tile 颜色序列，相邻行按 C2C 惯例反向返回。
    """
    W, H = pattern.width, pattern.height
    total_rows = W + H - 1
    lines = [
        f"C2C 逐行指令（{W}×{H} 格，共 {total_rows} 行对角）",
        "每格 = 1 个格子块（3 长针）。从左下角开始，行方向来回交替；",
        "增行 = 本行比上一行多 1 格，减行 = 少 1 格；减到 1 格后收工。",
        "",
    ]
    for k in range(1, total_rows + 1):
        # 对角行 k（1-based）上的格：x+y = k-1，其中 y 从底部计数。
        # pattern.cells 使用图像坐标（第 0 行在顶部），读取时必须翻转 y；
        # 否则文案虽称从左下角起，实际会从左上角起并垂直镜像成品。
        tiles = []
        for x in range(max(0, k - H), min(k, W)):
            crochet_y = k - 1 - x
            image_y = H - 1 - crochet_y
            cell = pattern.cells[image_y][x]
            tiles.append((cell.color_name, cell.rgb, cell.col_index))
        n_prev = min(k - 1, W, H, W + H - (k - 1)) if k > 1 else 0
        n = len(tiles)
        phase = "增行" if n > n_prev else ("减行" if n < n_prev else "平行")
        # 相邻对角行反向工作，保持 C2C 来回编织的阅读顺序。
        ordered = tiles if k % 2 == 1 else list(reversed(tiles))
        seq = "、".join(name for name, _rgb, _i in ordered)
        lines.append(f"对角行 {k}（{n} 格，{phase}）：{seq}")
    lines.append("")
    lines.append("收工：沿最后一行的上边缘钩一圈逆短针（螃蟹针）收边。")
    return "\n".join(lines)
