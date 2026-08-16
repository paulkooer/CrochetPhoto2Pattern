"""grid_pattern.py - 2D Pixel / Tapestry Crochet Pattern Generator.

Converts any PIL image into a color-coded grid pattern suitable for
tapestry crochet, C2C (corner-to-corner), or cross-stitch projects.
No external dependencies beyond Pillow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from PIL import Image

# Yarn table + perceptual matching live in app.models.colors (shared source)
from .colors import nearest_yarn


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
    cells: List[List[GridCell]]
    palette: List[Tuple[str, Tuple[int, int, int]]]
    symbol_map: Dict[int, str]


_SYMBOLS = "■▲●◆★✦◉▼⊕①②③④⑤⑥⑦⑧⑨⑩"

# UI slider 与文档约定的调色上限（符号表 20 个只是防御性硬顶）
_MAX_PALETTE = 10


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
    img = image.convert("RGB")
    orig_w, orig_h = img.size
    # 比例补偿推导（aspect_ratio = 针的宽/高，sc≈0.75 即针略"高"）：
    #   成品宽/高 = grid_width·w / (grid_height·h) 应等于 orig_w/orig_h
    #   ⇒ grid_height = grid_width · (w/h) · orig_h/orig_w = grid_width · aspect_ratio · orig_h/orig_w
    # 例：正方形图片 + 0.75 → 行数 = 列数×0.75，成品因针本身偏高仍为正方形。
    # int(x+0.5) 半步向上取整（Python round 是银行家舍入，.5 偏向偶数）。
    grid_height = max(2, int(grid_width * orig_h / orig_w * aspect_ratio + 0.5))
    resampler = (Image.Resampling.NEAREST if resample == "nearest"
                 else Image.Resampling.LANCZOS)
    img_small = img.resize((grid_width, grid_height), resampler)
    quantized = img_small.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    raw_palette = quantized.getpalette()

    # PIL getpalette() returns exactly actual_colors*3 entries on Python 3.9+
    actual_colors = len(raw_palette) // 3
    q_to_yarn: Dict[int, Tuple[str, Tuple[int, int, int]]] = {}
    for idx in range(actual_colors):
        rv, gv, bv = raw_palette[idx * 3], raw_palette[idx * 3 + 1], raw_palette[idx * 3 + 2]
        name, yarn_rgb = nearest_yarn(rv, gv, bv)
        q_to_yarn[idx] = (name, yarn_rgb)

    name_to_pal_idx: Dict[str, int] = {}
    palette: List[Tuple[str, Tuple[int, int, int]]] = []
    for idx in range(actual_colors):
        name, yarn_rgb = q_to_yarn[idx]
        if name not in name_to_pal_idx:
            name_to_pal_idx[name] = len(palette)
            palette.append((name, yarn_rgb))

    symbol_map = {i: _SYMBOLS[i % len(_SYMBOLS)] for i in range(len(palette))}

    pixels = list(quantized.getdata())
    cells: List[List[GridCell]] = []
    for row in range(grid_height):
        row_cells: List[GridCell] = []
        for col in range(grid_width):
            q_idx = pixels[row * grid_width + col]
            name, yarn_rgb = q_to_yarn.get(q_idx, ("白色", (255, 255, 255)))
            pal_idx = name_to_pal_idx.get(name, 0)
            row_cells.append(GridCell(col_index=pal_idx, color_name=name, rgb=yarn_rgb))
        cells.append(row_cells)

    return GridPattern(
        width=grid_width, height=grid_height,
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
        lines.append(f"| {sym} | {name} | {pct}% ({cnt} 格) |")
    return "\n".join(lines)


def render_text_chart(pattern: GridPattern) -> str:
    """Return a plain-text symbol chart (rows from bottom-up, crochet style)."""
    rows = []
    for row_idx, row in enumerate(pattern.cells):
        row_num = pattern.height - row_idx
        sym_row = "".join(pattern.symbol_map.get(c.col_index, "?") for c in row)
        rows.append(f"R{row_num:02d}: {sym_row}")
    return "\n".join(rows)
