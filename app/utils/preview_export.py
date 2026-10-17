"""成品预览图导出（CLI ``--preview``）。

预览走的是结果页同一个渲染器（:func:`app.ui.preview3d.assembly_preview_html`：
每个部件的**真实圈数**做成旋转体，再用 ``--assemble`` 的同一套解剖布局摆成
成品），所以 CLI 落盘的图和界面上看到的是同一张。

格式由后缀决定：

* ``.svg``——无损矢量，带"示意预览（静态等距视图，非物理仿真）"标注；
* ``.png``——把上面那张 SVG 栅格化。只认本项目预览的方言（背景矩形 + 画家
  算法排序的多边形 + 一行标注），不引入 cairosvg——它在 Windows 上还要额外
  的 cairo DLL。标注是中文，PNG 需要系统中文字体；找不到字体时只画图形，
  矢量 SVG 始终带着标注，是无损的那一份。
"""
from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PREVIEW_SUFFIXES = (".svg", ".png")

# PNG 标注用的中文字体：先试这些（含 Pillow 会去系统字体目录找的裸文件名），
# 都找不到就退回 Pillow 自带——但自带字体没有 CJK 字形，中文会画成方框，
# 所以宁可不画这一行。
_FONT_FILES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "msyh.ttc",
    "simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)

_SUPERSAMPLE = 2
_RE_VIEWBOX = re.compile(r'viewBox="([-\d.eE\s]+)"')
_RE_ELEMENT = re.compile(r"<(rect|polygon|text)\b([^>]*)>([^<]*)")
_RE_ATTR = re.compile(r'([a-zA-Z-]+)="([^"]*)"')
_RE_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")
_RE_RGB = re.compile(r"rgba?\(([^)]*)\)\Z")


def preview_svg(result: dict[str, Any]) -> str:
    """result → 预览 SVG（与结果页同源：装配预览优先，退回结构预览）。"""
    from app.ui.preview3d import assembly_preview_html, structure_preview_html

    svg = assembly_preview_html(result) or structure_preview_html(result)
    if not svg:
        raise ValueError("没有可渲染的部件（缺少圈数或针宽），无法生成预览图")
    return svg


def export_preview(result: dict[str, Any], path: str | Path) -> bytes:
    """按后缀导出预览图（``.svg`` 矢量 / ``.png`` 位图）。"""
    suffix = Path(path).suffix.lower()
    if suffix not in PREVIEW_SUFFIXES:
        raise ValueError(f"预览格式不支持: {Path(path).name}（用 .svg 或 .png）")
    svg = preview_svg(result)
    if suffix == ".svg":
        return svg.encode("utf-8")
    return rasterise_preview_svg(svg)


def rasterise_preview_svg(svg: str, *, supersample: int = _SUPERSAMPLE) -> bytes:
    """把预览 SVG 渲成 PNG（只认 :func:`app.ui.preview3d._render_static_svg` 的方言）。

    多边形按文档顺序绘制——渲染器已经用画家算法排好序，所以照抄即可。
    2 倍超采样后缩放，避免斜边锯齿。
    """
    from PIL import Image, ImageDraw

    match = _RE_VIEWBOX.search(svg)
    numbers = [float(v) for v in match.group(1).split()] if match else []
    if len(numbers) != 4:
        raise ValueError("预览 SVG 缺少或非法 viewBox")
    min_x, min_y, width, height = numbers
    if width <= 0 or height <= 0:
        raise ValueError("预览 SVG 的画幅非法")

    scale = max(1, int(supersample))
    canvas = Image.new("RGB", (round(width) * scale, round(height) * scale), "white")
    draw = ImageDraw.Draw(canvas)
    for tag, blob, body in _RE_ELEMENT.findall(svg):
        attrs = dict(_RE_ATTR.findall(blob))
        if tag == "rect":
            rect_x = _number(attrs.get("x"), 0.0) - min_x
            rect_y = _number(attrs.get("y"), 0.0) - min_y
            rect_w = _number(attrs.get("width"), width)
            rect_h = _number(attrs.get("height"), height)
            draw.rectangle([rect_x * scale, rect_y * scale,
                            (rect_x + rect_w) * scale, (rect_y + rect_h) * scale],
                           fill=_rgb(attrs.get("fill")) or (255, 255, 255))
            continue
        if tag == "polygon":
            points = _points(attrs.get("points", ""))
            colour = _rgb(attrs.get("fill"))
            if colour and len(points) >= 3:
                draw.polygon([((px - min_x) * scale, (py - min_y) * scale)
                              for px, py in points], fill=colour)
            continue
        # text：SVG 的 y 是基线，锚点也用基线；没有中文字体就只画图形。
        size = _number(attrs.get("font-size"), 12.0)
        font = _cjk_font(max(1, round(size * scale)))
        if font is not None and body.strip():
            draw.text(((_number(attrs.get("x"), 0.0) - min_x) * scale,
                       (_number(attrs.get("y"), 0.0) - min_y) * scale),
                      body, font=font, fill=_rgb(attrs.get("fill")) or (0, 0, 0),
                      anchor="ls")
    if scale > 1:
        canvas = canvas.resize((round(width), round(height)), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


@lru_cache(maxsize=8)
def _cjk_font(size: int):
    """系统中文字体；没有可用字体时返回 None（标注则跳过）。"""
    from PIL import ImageFont

    for name in _FONT_FILES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return None


def _number(value: str | None, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _points(value: str) -> list[tuple[float, float]]:
    """``"x,y x,y ..."`` → 坐标列表；出现非法数字时返回空（跳过该多边形）。"""
    try:
        flat = [float(v) for v in value.replace(",", " ").split()]
    except ValueError:
        return []
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def _rgb(value: str | None) -> tuple[int, int, int] | None:
    text = str(value or "").strip()
    if _RE_HEX.match(text):
        digits = text[1:]
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
    match = _RE_RGB.match(text)
    if match:
        parts = [p for p in re.split(r"[,\s]+", match.group(1).strip()) if p]
        try:
            channels = [round(float(p)) for p in parts[:3]]
        except ValueError:
            return None
        if len(channels) == 3:
            return (max(0, min(255, channels[0])), max(0, min(255, channels[1])),
                    max(0, min(255, channels[2])))
    return None
