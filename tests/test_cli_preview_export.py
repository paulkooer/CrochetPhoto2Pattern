"""CLI ``--preview`` 成品预览图（SVG 矢量 / PNG 位图）单测。

预览与结果页共用同一渲染器（``app.ui.preview3d.assembly_preview_html``：每个
部件的真实圈数做成旋转体，再用 ``--assemble`` 的同一套解剖布局摆成成品），
所以这里盯三件事：与界面同源、PNG 真的把多边形画进去、新输出同样走 CLI 的
输出安全预检（冲突与格式都在生成前判掉）。
"""
import io
import re

import pytest
from PIL import Image, ImageDraw

from app import cli
from app.ui.preview3d import assembly_preview_html
from app.utils.preview_export import (
    PREVIEW_SUFFIXES,
    _cjk_font,
    export_preview,
    preview_svg,
    rasterise_preview_svg,
)

_VIEWBOX = re.compile(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"')
_RGB_FILL = re.compile(r"rgb\((\d+),(\d+),(\d+)\)")


def _rounds(counts):
    rounds, prev = [], counts[0]
    for i, n in enumerate(counts):
        rd = {"row": i + 1, "stitches": n}
        if i:
            diff = n - prev
            if diff > 0:
                rd["increase"] = diff
            elif diff < 0:
                rd["decrease"] = -diff
        rounds.append(rd)
        prev = n
    return rounds


def _sphere(peak: int, rows: int):
    up = list(range(6, peak + 1, 6))
    down = list(reversed(up))[1:]
    return _rounds(up + [peak] * max(1, rows - len(up) - len(down)) + down)


def _result() -> dict:
    return {
        "params": {
            "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
            "parts": [
                {"name": "头部", "quantity": 1, "color": "米色", "rounds": _sphere(30, 14)},
                {"name": "身体", "quantity": 1, "color": "桃肤色", "rounds": _sphere(36, 15)},
                {"name": "耳朵", "quantity": 2, "color": "灰色",
                 "rounds": _rounds([6, 6] + [10] * 12)},
            ],
        },
        "analysis": {"height_cm": 14.0},
    }


def _colours(svg: str) -> set[tuple[int, int, int]]:
    return {(int(r), int(g), int(b)) for r, g, b in _RGB_FILL.findall(svg)}


def _pixels(png: bytes) -> set[tuple[int, int, int]]:
    with Image.open(io.BytesIO(png)) as image:
        colours = image.convert("RGB").getcolors(maxcolors=1 << 24) or []
    pixels: set[tuple[int, int, int]] = set()
    for _count, colour in colours:
        if isinstance(colour, tuple) and len(colour) == 3:
            pixels.add((int(colour[0]), int(colour[1]), int(colour[2])))
    return pixels


def test_preview_is_the_result_page_renderer():
    """同一份 result → CLI 落盘的 SVG 与结果页渲染的是同一张图。"""
    result = _result()
    assert preview_svg(result) == assembly_preview_html(result)


def test_preview_png_renders_the_svg_faces():
    svg = preview_svg(_result())
    png = rasterise_preview_svg(svg)
    fills = _colours(svg)
    seen = _pixels(png)

    min_x, min_y, width, height = (float(v) for v in _VIEWBOX.search(svg).groups())
    assert min_x == 0 and min_y == 0            # 画幅无边距时坐标可直接比
    with Image.open(io.BytesIO(png)) as image:
        assert image.size == (round(width), round(height))
    assert len(fills & seen) >= 4               # 多个部件的着色面都画出来了
    assert len(seen) > len(fills)               # 抗锯齿过渡色（不是纯色块）
    # 背景矩形（theme.SHEET，由渲染器写在 SVG 里）铺满画布
    background = re.search(r'<rect[^>]*fill="([^"]+)"', svg).group(1)
    assert tuple(int(background[i:i + 2], 16) for i in (1, 3, 5)) in seen


def test_preview_png_is_deterministic():
    svg = preview_svg(_result())
    assert rasterise_preview_svg(svg) == rasterise_preview_svg(svg)


def test_preview_svg_bytes_are_the_utf8_svg():
    svg = preview_svg(_result())
    assert export_preview(_result(), "preview.svg") == svg.encode("utf-8")


def test_preview_rejects_other_suffixes(tmp_path):
    with pytest.raises(ValueError, match="预览格式不支持"):
        export_preview(_result(), tmp_path / "preview.webp")
    assert PREVIEW_SUFFIXES == (".svg", ".png")


def test_preview_without_renderable_parts_is_an_error():
    with pytest.raises(ValueError, match="没有可渲染的部件"):
        export_preview({}, "preview.png")


def test_rasteriser_follows_the_preview_dialect():
    """方言：背景矩形 + 画家顺序多边形（+ 一行标注）。"""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
           '<rect width="20" height="20" fill="#010203"/>'
           '<polygon points="0,0 20,0 10,20" fill="rgb(200,100,50)"/>'
           "</svg>")
    png = rasterise_preview_svg(svg)
    with Image.open(io.BytesIO(png)) as image:
        assert image.size == (20, 20)
        assert image.getpixel((10, 7)) == (200, 100, 50)   # 三角形内部
        assert image.getpixel((19, 19)) == (1, 2, 3)       # 背景


def test_rasteriser_skips_broken_geometry():
    """看不懂的多边形跳过，不炸整张图。"""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
           '<rect width="10" height="10" fill="#ffffff"/>'
           '<polygon points="a,b c,d" fill="rgb(1,2,3)"/>'
           '<polygon points="0,0 10,0 10,10" fill="rgb(9,9,9)"/>'
           "</svg>")
    assert (9, 9, 9) in _pixels(rasterise_preview_svg(svg))


def test_rasteriser_draws_the_caption_when_a_cjk_font_exists():
    """中文标注需要系统中文字体；没有字体时只画图形（矢量 SVG 始终带标注）。"""
    if _cjk_font(12) is None:
        pytest.skip("本机没有可用的中文字体")
    head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60">'
            '<rect width="200" height="60" fill="#ffffff"/>')
    tail = "</svg>"
    plain = rasterise_preview_svg(head + tail)
    captioned = rasterise_preview_svg(
        head + '<text x="4" y="30" font-size="24" fill="#ff0000">示意预览</text>' + tail)
    assert plain != captioned


# ── CLI 接线：产物、批量、输出安全 ──────────────────────────────────────────

@pytest.mark.parametrize("suffix", [".svg", ".png"])
def test_cli_exports_preview(tmp_path, suffix):
    preview = tmp_path / f"pattern.preview{suffix}"
    rc = cli.main(["--mock", "--out", str(tmp_path / "pattern.json"),
                   "--preview", str(preview), "--quiet"])
    assert rc == 0
    if suffix == ".svg":
        assert preview.read_text(encoding="utf-8").startswith("<svg")
    else:
        with Image.open(preview) as image:
            assert image.format == "PNG"
            assert len(_pixels(preview.read_bytes())) > 1


def test_cli_rejects_unknown_preview_suffix_before_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "run", lambda _: pytest.fail("must preflight before pipeline"))
    assert cli.main(["--mock", "--preview", str(tmp_path / "pattern.webp"),
                     "--quiet"]) == 1
    assert not (tmp_path / "pattern.webp").exists()


def test_preview_alias_of_the_input_photo_is_rejected(tmp_path, monkeypatch):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (30, 60), (240, 240, 240)).save(photo)
    before = photo.read_bytes()
    monkeypatch.setattr(cli, "run", lambda _: pytest.fail("must preflight before pipeline"))
    assert cli.main(["--image", str(photo), "--preview", str(photo), "--quiet"]) == 1
    assert photo.read_bytes() == before


def test_preview_conflicts_with_another_output(tmp_path, monkeypatch):
    target = tmp_path / "pattern.json"
    monkeypatch.setattr(cli, "run", lambda _: pytest.fail("must preflight before pipeline"))
    assert cli.main(["--mock", "--out", str(target),
                     "--preview", str(target), "--quiet"]) == 1
    assert not target.exists()


def test_cli_batch_exports_preview_per_image(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    for i in range(2):
        img = Image.new("RGB", (100, 160), (245, 245, 245))
        draw = ImageDraw.Draw(img)
        draw.ellipse([30, 12, 70, 52], fill=(230, 180, 150))
        draw.rounded_rectangle([35, 55, 65, 150], radius=8, fill=(0, 120, 215))
        img.save(in_dir / f"doll{i}.png")
    out_dir = tmp_path / "out"
    assert cli.main(["--batch-dir", str(in_dir), "--out-dir", str(out_dir),
                     "--preview", str(out_dir / "unused.png"), "--quiet"]) == 0
    for stem in ("doll0", "doll1"):
        assert (out_dir / f"{stem}.preview.png").exists()
