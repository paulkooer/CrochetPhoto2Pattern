"""Tests for grid_pattern module — 2D tapestry crochet grid generator."""
import random

import pytest
from PIL import Image

from app.models.grid_pattern import (
    GridPattern,
    generate_grid_pattern,
    render_legend_markdown,
    render_svg,
    render_text_chart,
)


def _make_solid(color=(200, 100, 50), size=(100, 150)):
    return Image.new("RGB", size, color)


def _make_random(seed=42, size=(100, 100)):
    rng = random.Random(seed)
    img = Image.new("RGB", size)
    pix = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            pix[x, y] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    return img


# ── generate_grid_pattern ────────────────────────────────────────────────────

def test_grid_dimensions():
    img = _make_solid(size=(200, 300))
    g = generate_grid_pattern(img, grid_width=20, n_colors=4)
    assert g.width == 20
    assert g.height > 0
    assert len(g.cells) == g.height
    assert all(len(row) == g.width for row in g.cells)


def test_palette_within_n_colors():
    img = _make_random()
    g = generate_grid_pattern(img, grid_width=30, n_colors=6)
    assert 1 <= len(g.palette) <= 6


def test_symbol_map_covers_palette():
    img = _make_random()
    g = generate_grid_pattern(img, grid_width=20, n_colors=5)
    for i in range(len(g.palette)):
        assert i in g.symbol_map


def test_cells_reference_valid_palette_index():
    img = _make_random()
    g = generate_grid_pattern(img, grid_width=15, n_colors=4)
    n_pal = len(g.palette)
    for row in g.cells:
        for cell in row:
            assert 0 <= cell.col_index < n_pal


def test_rgba_image_handled():
    img = Image.new("RGBA", (80, 80), (70, 130, 180, 200))
    g = generate_grid_pattern(img, grid_width=10, n_colors=3)
    assert g.width == 10


def test_n_colors_clamped_to_minimum():
    img = _make_solid()
    g = generate_grid_pattern(img, grid_width=10, n_colors=0)
    assert len(g.palette) >= 1


# ── render_svg ───────────────────────────────────────────────────────────────

def test_svg_contains_required_tags():
    g = generate_grid_pattern(_make_solid(), grid_width=10, n_colors=3)
    svg = render_svg(g, cell_px=12)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_svg_contains_rect_elements():
    g = generate_grid_pattern(_make_solid(), grid_width=5, n_colors=2)
    svg = render_svg(g, cell_px=14)
    assert "<rect" in svg


# ── render_legend_markdown ───────────────────────────────────────────────────

def test_legend_has_header_row():
    g = generate_grid_pattern(_make_solid(), grid_width=10, n_colors=3)
    md = render_legend_markdown(g)
    assert "符号" in md
    assert "颜色名称" in md
    assert "用量估算" in md


def test_legend_has_one_row_per_color():
    g = generate_grid_pattern(_make_random(), grid_width=20, n_colors=5)
    md = render_legend_markdown(g)
    # Header + divider + one row per palette color
    data_rows = [l for l in md.split("\n") if l.startswith("|") and "符号" not in l and ":----:" not in l]
    assert len(data_rows) == len(g.palette)


# ── render_text_chart ────────────────────────────────────────────────────────

def test_text_chart_row_count():
    g = generate_grid_pattern(_make_solid(size=(100, 150)), grid_width=20, n_colors=3)
    txt = render_text_chart(g)
    rows = txt.strip().split("\n")
    assert len(rows) == g.height


def test_text_chart_first_row_is_top():
    g = generate_grid_pattern(_make_solid(size=(100, 150)), grid_width=10, n_colors=2)
    txt = render_text_chart(g)
    first_row = txt.split("\n")[0]
    assert first_row.startswith(f"R{g.height:02d}:")
