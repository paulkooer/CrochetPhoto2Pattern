"""大网格的资源边界回归测试：不即时渲染/存储逐格 SVG，改用位图预览，
SVG 下载按需生成且与 render_svg 一致；常规网格行为不变。对应审核 F-07。"""
from __future__ import annotations

import json

from streamlit.testing.v1 import AppTest

from app.models.colors import YARN_COLORS
from app.models.grid_pattern import import_grid_project, render_svg
from app.ui import tab_grid

_UI = '''
from app.ui.tab_grid import render_tab_grid
render_tab_grid()
'''
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _grid(width: int, height: int):
    palette = [{"name": name, "rgb": list(rgb)} for rgb, name in YARN_COLORS[:6]]
    cells = [[(x + y) % 6 for x in range(width)] for y in range(height)]
    blob = json.dumps({"format": "crochet-photo2pattern-grid", "schema_version": "1.0",
                       "pattern": {"width": width, "height": height, "clamped_from": None,
                                   "palette": palette, "cells": cells}},
                      separators=(",", ":")).encode()
    return import_grid_project(blob)


def test_large_grid_skips_inline_svg_and_uses_png_preview():
    pattern = _grid(120, 100)  # 12,000 格 > 阈值
    assert pattern.width * pattern.height > tab_grid._SVG_PREVIEW_MAX_CELLS
    view = tab_grid._rendered_grid_view(pattern)
    assert view["svg"] is None
    assert view["preview_png"].startswith(_PNG_SIGNATURE)
    # 位图预览远小于逐格 SVG
    assert len(view["preview_png"]) * 10 < len(render_svg(pattern, cell_px=14))


def test_large_grid_svg_download_is_lazy_and_identical():
    pattern = _grid(120, 100)
    view = tab_grid._rendered_grid_view(pattern)
    data = tab_grid._svg_download_data(view)
    assert callable(data)
    assert data() == render_svg(pattern, cell_px=14)


def test_small_grid_keeps_inline_svg_and_direct_download():
    pattern = _grid(20, 20)
    view = tab_grid._rendered_grid_view(pattern)
    assert view["preview_png"] is None
    assert view["svg"] == render_svg(pattern, cell_px=14)
    assert tab_grid._svg_download_data(view) == view["svg"]


def test_large_grid_renders_without_exception_and_shows_raster_preview():
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["grid_view"] = tab_grid._rendered_grid_view(_grid(120, 100))
    at.run()
    assert not at.exception
    markdown = "".join(str(m.value) for m in at.markdown)
    assert "data:image/png;base64," in markdown
    assert "<svg" not in markdown  # 不再把逐格 SVG 推给浏览器
    assert any("位图预览" in str(c.value) for c in at.caption)
