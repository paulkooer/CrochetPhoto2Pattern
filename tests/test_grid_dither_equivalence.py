"""抖动的快速实现（按 RGB 三元组缓存最近邻、标量误差扩散）只改速度：
须与优化前逐像素调用 NumPy 的参考实现逐格一致。"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.models import grid_pattern
from app.models.colors import _srgb_to_lab_vec, ciede2000_vec


def _reference_dither(px_arr, width, height, palette_rgbs, pal_labs):
    # 优化前的实现，原样保留作对照
    buf = px_arr.reshape(height, width, 3).astype(np.float64).copy()
    idx = np.zeros(height * width, dtype=np.int64)
    for y in range(height):
        for x in range(width):
            rgb = np.clip(np.round(buf[y, x]), 0, 255).astype(np.int32).reshape(1, -1)
            d = ciede2000_vec(_srgb_to_lab_vec(rgb), pal_labs, pairwise=False)[0]
            bi = int(d.argmin())
            idx[y * width + x] = bi
            err = buf[y, x] - np.asarray(palette_rgbs[bi], dtype=np.float64)
            if x + 1 < width:
                buf[y, x + 1] += err * 7 / 16
            if y + 1 < height:
                if x > 0:
                    buf[y + 1, x - 1] += err * 3 / 16
                buf[y + 1, x] += err * 5 / 16
                if x + 1 < width:
                    buf[y + 1, x + 1] += err * 1 / 16
    return idx


def _image(name: str) -> Image.Image:
    yy, xx = np.mgrid[0:90, 0:120]
    if name == "gradient":
        arr = np.stack([xx * 255 // 119, yy * 255 // 89, (xx + yy) * 127 // 207], -1)
    elif name == "random":
        arr = np.random.default_rng(7).integers(0, 256, (90, 120, 3))
    else:  # 大色块：缓存命中多、误差在边界处跨色块扩散
        arr = np.zeros((90, 120, 3))
        arr[:, :60] = (200, 40, 40)
        arr[30:, 60:] = (30, 90, 200)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


@pytest.mark.parametrize("name", ["gradient", "random", "blocks"])
@pytest.mark.parametrize("n_colors", [2, 6, 10])
def test_fast_dither_matches_reference(monkeypatch, name, n_colors):
    image = _image(name)
    fast = grid_pattern.generate_grid_pattern(image, grid_width=32, n_colors=n_colors, dither=True)
    monkeypatch.setattr(grid_pattern, "_assign_dithered", _reference_dither)
    reference = grid_pattern.generate_grid_pattern(image, grid_width=32, n_colors=n_colors, dither=True)
    assert grid_pattern.grid_pattern_to_payload(fast) == grid_pattern.grid_pattern_to_payload(reference)
