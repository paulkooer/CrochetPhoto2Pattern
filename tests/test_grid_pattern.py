"""Tests for grid_pattern module — 2D tapestry crochet grid generator."""
import json
import random
import re

import pytest
from PIL import Image

from app.models.grid_pattern import (
    GRID_PROJECT_MAX_BYTES,
    GridCell,
    GridPattern,
    crop_image_fraction,
    export_grid_markdown,
    export_grid_project,
    generate_grid_pattern,
    grid_pattern_from_payload,
    grid_pattern_to_payload,
    import_grid_project,
    recolor_grid_cell,
    recolor_grid_region,
    render_c2c_chart,
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


def _editable_pattern():
    palette = [("红色", (255, 0, 0)), ("蓝色", (0, 120, 215))]
    return GridPattern(
        width=2,
        height=2,
        cells=[
            [GridCell(0, *palette[0]), GridCell(0, *palette[0])],
            [GridCell(0, *palette[0]), GridCell(1, *palette[1])],
        ],
        palette=palette,
        symbol_map={0: "■", 1: "▲"},
    )


# ── crop / edit payload ─────────────────────────────────────────────────────

def test_fractional_crop_uses_top_left_image_coordinates():
    image = Image.new("RGB", (100, 80), (255, 255, 255))
    cropped = crop_image_fraction(image, 0.25, 0.25, 0.75, 0.75)
    assert cropped.size == (50, 40)


def test_fractional_crop_rejects_empty_or_non_finite_selection():
    image = Image.new("RGB", (20, 20))
    with pytest.raises(ValueError):
        crop_image_fraction(image, 0.5, 0.0, 0.5, 1.0)
    with pytest.raises(ValueError):
        crop_image_fraction(image, 0.0, float("nan"), 1.0, 1.0)


def test_grid_payload_round_trip_preserves_palette_and_cells():
    original = _editable_pattern()
    restored = grid_pattern_from_payload(grid_pattern_to_payload(original))
    assert restored.width == 2 and restored.height == 2
    assert restored.palette == original.palette
    assert [[cell.col_index for cell in row] for row in restored.cells] == [
        [0, 0], [0, 1]]
    assert set(restored.symbol_map) == {0, 1}


def test_grid_payload_rejects_invalid_cell_index():
    payload = grid_pattern_to_payload(_editable_pattern())
    payload["cells"][0][0] = 99
    with pytest.raises(ValueError, match="cell index"):
        grid_pattern_from_payload(payload)


def test_editable_grid_project_round_trip_is_versioned_and_compact():
    original = _editable_pattern()
    encoded = export_grid_project(original)
    document = json.loads(encoded)
    assert document["format"] == "crochet-photo2pattern-grid"
    assert document["schema_version"] == "1.0"
    assert len(encoded) < 1_000
    restored = import_grid_project(encoded)
    assert restored.palette == original.palette
    assert [[cell.col_index for cell in row] for row in restored.cells] == [
        [0, 0], [0, 1]]


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda doc: doc.update(schema_version="99"), "schema version"),
        (lambda doc: doc.update(format="another-app"), "format"),
        (lambda doc: doc["pattern"].update(width=2.5), "width"),
        (lambda doc: doc["pattern"]["cells"][0].__setitem__(0, True),
         "cell index"),
    ],
)
def test_grid_project_rejects_unsupported_or_coerced_values(mutation, message):
    document = json.loads(export_grid_project(_editable_pattern()))
    mutation(document)
    with pytest.raises(ValueError, match=message):
        import_grid_project(json.dumps(document))


def test_grid_project_rejects_duplicate_keys_invalid_utf8_and_oversize():
    duplicate = (
        b'{"format":"crochet-photo2pattern-grid","format":"duplicate",'
        b'"schema_version":"1.0","pattern":{}}')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        import_grid_project(duplicate)
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        import_grid_project(b"\xff\xfe")
    with pytest.raises(ValueError, match="size limit"):
        import_grid_project(b" " * (GRID_PROJECT_MAX_BYTES + 1))


def test_grid_project_rejects_forged_yarn_name_or_rgb():
    document = json.loads(export_grid_project(_editable_pattern()))
    document["pattern"]["palette"][0]["name"] = "<script>伪造色</script>"
    with pytest.raises(ValueError, match="not in the yarn palette"):
        import_grid_project(json.dumps(document, ensure_ascii=False))

    document = json.loads(export_grid_project(_editable_pattern()))
    document["pattern"]["palette"][1]["rgb"] = [0, 0, 255]
    with pytest.raises(ValueError, match="does not match"):
        import_grid_project(json.dumps(document, ensure_ascii=False))

    document = json.loads(export_grid_project(_editable_pattern()))
    document["pattern"]["palette"][1] = dict(
        document["pattern"]["palette"][0])
    with pytest.raises(ValueError, match="duplicate colors"):
        import_grid_project(json.dumps(document, ensure_ascii=False))


def test_recolor_updates_every_derived_grid_output():
    pattern = _editable_pattern()
    recolor_grid_cell(pattern, row_index=0, column_index=0, palette_index=1)
    assert pattern.cells[0][0].color_name == "蓝色"
    assert "50% (2 格)" in render_legend_markdown(pattern)
    assert render_text_chart(pattern).splitlines()[0].endswith("▲■")
    assert "蓝色" in render_c2c_chart(pattern)
    assert "#0078d7" in render_svg(pattern)


def test_recolor_rejects_coordinates_or_palette_outside_grid():
    pattern = _editable_pattern()
    with pytest.raises(IndexError):
        recolor_grid_cell(pattern, 2, 0, 0)
    with pytest.raises(ValueError):
        recolor_grid_cell(pattern, 0, 0, 2)


def test_region_recolor_is_inclusive_and_reports_real_changes():
    pattern = _editable_pattern()
    changed = recolor_grid_region(
        pattern, row_start=0, row_end=1,
        column_start=0, column_end=0, palette_index=1)
    assert changed == 2
    assert [row[0].col_index for row in pattern.cells] == [1, 1]
    # 重复应用不制造虚假的历史步骤。
    assert recolor_grid_region(pattern, 0, 1, 0, 0, 1) == 0


def test_region_recolor_rejects_reversed_or_out_of_bounds_rectangle():
    pattern = _editable_pattern()
    with pytest.raises(ValueError, match="start"):
        recolor_grid_region(pattern, 1, 0, 0, 1, 1)
    with pytest.raises(IndexError, match="column"):
        recolor_grid_region(pattern, 0, 1, 0, 2, 1)


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


def test_n_colors_clamped_to_documented_max():
    """n_colors 文档约定 2-10：传 99 也不应超过 10（符号表 20 只是防御顶）。"""
    img = _make_random()
    g = generate_grid_pattern(img, grid_width=40, n_colors=99)
    assert len(g.palette) <= 10


# ── aspect_ratio 比例补偿 ────────────────────────────────────────────────────

def test_square_image_with_sc_yields_compensated_grid():
    """方图 + 短针(0.75)：行数 = 列数×0.75，成品因针偏高仍为正方形。

    回归锁定：grid_height = grid_width · aspect_ratio · (orig_h/orig_w)。
    曾被怀疑方向弄反——推导见 grid_pattern.generate_grid_pattern 注释。
    """
    img = _make_solid(size=(100, 100))
    g = generate_grid_pattern(img, grid_width=40, aspect_ratio=0.75)
    assert g.height == 30  # 40 × 0.75


def test_aspect_ratio_preserves_physical_proportions():
    """不同针法比例下，成品的物理宽高比都应等于原图宽高比。"""
    img = _make_solid(size=(200, 100))  # 2:1 横图
    for ratio in (0.5, 0.6, 0.75, 1.0):
        g = generate_grid_pattern(img, grid_width=40, aspect_ratio=ratio)
        # 成品宽 = 40·w，成品高 = g.height·h，w/h = ratio
        fabric_aspect = 40 * ratio / g.height
        assert abs(fabric_aspect - 2.0) < 0.15, (
            f"ratio={ratio}: fabric {fabric_aspect:.2f} vs orig 2.00"
        )


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


def test_svg_renders_symbols_and_bold_grid_lines():
    g = generate_grid_pattern(_make_random(), grid_width=12, n_colors=4)
    svg = render_svg(g, cell_px=14)
    for sym in g.symbol_map.values():
        assert sym in svg, f"symbol {sym!r} missing from SVG overlay"
    assert "<line" in svg  # every-10 bold grid lines


def test_legend_percentages_roughly_total_100():
    g = generate_grid_pattern(_make_random(), grid_width=20, n_colors=5)
    md = render_legend_markdown(g)
    pcts = [int(m) for m in re.findall(r"\| (\d+)% \(", md)]
    assert pcts, "legend should contain percentage cells"
    assert 90 <= sum(pcts) <= 110  # 各行四舍五入后允许误差


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
    data_rows = [
        ln for ln in md.split("\n")
        if ln.startswith("|") and "符号" not in ln and ":----:" not in ln
    ]
    assert len(data_rows) == len(g.palette)


def test_full_markdown_export_contains_chart_legend_and_c2c():
    pattern = _editable_pattern()
    markdown = export_grid_markdown(pattern)
    assert "# 🧶 平面网格钩织图解" in markdown
    assert "2 列 × 2 行" in markdown
    assert "| ■ | 红色 |" in markdown
    assert "R02: ■■" in markdown
    assert "C2C 逐行指令" in markdown
    assert "对角行 3" in markdown


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


def test_resample_nearest_option():
    """像素画模式可用且纯色图结果一致。"""
    g = generate_grid_pattern(_make_solid(), grid_width=8, n_colors=2,
                              resample="nearest")
    assert g.width == 8 and len(g.palette) >= 1


def test_resample_invalid_value_defaults_lanczos():
    g = generate_grid_pattern(_make_solid(), grid_width=8, n_colors=2,
                              resample="bogus")
    assert g.width == 8  # 未识别值回退默认，不崩
