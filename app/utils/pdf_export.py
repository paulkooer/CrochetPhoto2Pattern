"""PDF 图解导出（S4，roadmap 第 2 项）——reportlab 生成可打印图解。

reportlab 是可选依赖（pip install crochet-photo2pattern[pdf]）；
中文用 Adobe CID 字体 STSong-Light（无需携带字体文件）。
布局：封面元信息 → 材料 → 逐部件圈数表 → 装配说明。
"""
from __future__ import annotations

import html
import io
import re
from typing import Any, Dict, Optional


def export_pdf(params: Dict[str, Any], analysis: Optional[Dict[str, Any]] = None) -> bytes:
    """生成图解 PDF，返回字节流。reportlab 缺失时抛 ImportError。"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    _invisible_re = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069]")

    def esc(value: Any) -> str:
        """用户/模型提供的文本必须转义后再进 Paragraph——reportlab 会把
        <b>/<script> 等当作行内标记解析（U1 注塑面）；零宽/BiDi 控制符
        一并剥离（E1 显示欺骗面）。"""
        return html.escape(_invisible_re.sub("", str(value)))

    body = ParagraphStyle("body", fontName="STSong-Light", fontSize=10.5,
                          leading=16)
    title = ParagraphStyle("title", parent=body, fontSize=18, leading=24,
                           spaceAfter=4)
    head = ParagraphStyle("head", parent=body, fontSize=13.5, leading=18,
                          spaceBefore=10, spaceAfter=4)
    small = ParagraphStyle("small", parent=body, fontSize=9, leading=13,
                           textColor=colors.HexColor("#666666"))
    cell = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=13)
    cell_head = ParagraphStyle("cell_head", parent=cell, textColor=colors.white)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Amigurumi 钩织图解",
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    story = []

    story.append(Paragraph("🧶 Amigurumi 钩织图解", title))
    if analysis:
        story.append(Paragraph(
            f"体型 {esc(analysis.get('body_type', '—'))} · "
            f"目标头径 {esc(analysis.get('head_diameter_cm', '—'))}cm · "
            f"目标高 {esc(analysis.get('height_cm', '—'))}cm · "
            f"难度 {esc(analysis.get('difficulty', '—'))}", small))
    # U24（升级）：密度随图解导出 + 兜底声明
    g = params.get("gauge") or {}
    st_g, rw_g = g.get("stitches_per_10cm"), g.get("rows_per_10cm")
    if st_g and rw_g:
        story.append(Paragraph(
            f"密度（小样）：10cm × {st_g:g} 针 × {rw_g:g} 行——请先试钩核对。"
            f"若你的小样密度不同，请改密度后重新生成", small))
    else:
        story.append(Paragraph(
            "密度（小样）：未记录（按经典图解默认 13 针 × 16 行 / 10cm）",
            small))
    from app.models.validator import shaping_policy_for_pattern
    shaping = shaping_policy_for_pattern(params)
    story.append(Paragraph(
        f"塑形：当前密度的连续几何变化率约 "
        f"{shaping['continuous_delta']:.2f} 针/圈，按六等分针法向上量化为每圈 "
        f"±{shaping['max_stitch_change']} 针；较平缓轮廓仍可使用 6 针步长",
        small))
    physical_parts = sum(
        max(1, int((part.model_dump() if hasattr(part, "model_dump") else part).get(
            "quantity", 1)))
        for part in params.get("parts", []))
    minutes = max(0, int(params.get("estimated_time_minutes") or 0))
    story.append(Paragraph(
        f"工作量：{physical_parts} 个实体部件 · "
        f"{int(params.get('total_stitches') or 0):,} 针 · "
        f"基础操作估时 {minutes} 分钟（约 {minutes / 60:.1f} 小时）",
        small))
    story.append(Paragraph(
        "工时是未校准的低置信度经验值，只按针数与实体圈次计算；"
        "不含缝合、填充、换色、刺绣、返工和休息。",
        small))
    story.append(Paragraph(
        "记号：X=短针，V=加针，A=减针；(2X,V)×6 = “2 短针 + 1 加针”重复 6 次。"
        "螺旋钩（不引拔不翻转），每圈第一针挂记号扣；减针建议隐形减针。",
        small))
    story.append(Paragraph(
        "Stitch Key: X = sc (single crochet) · V = 2 sc in same st (increase) · "
        "A = sc2tog (invisible decrease) · SL = sl st · CH = ch。"
        "X/V/A 为日式 Amigurumi 惯例，与西方 CYC 图解体系对照如上。",
        small))
    story.append(Spacer(1, 6))

    # 材料
    story.append(Paragraph("🧵 所需材料", head))
    story.append(Paragraph("克重/米数为估算值（请以实际线标为准）", small))
    mat_rows = [[Paragraph("材料", cell_head), Paragraph("用量", cell_head)]]
    for mat in params.get("materials", []):
        if isinstance(mat, dict):
            mat_rows.append([Paragraph(esc(mat.get("item", "?")), cell),
                             Paragraph(esc(mat.get("quantity", "?")), cell)])
        else:
            mat_rows.append([Paragraph(esc(mat), cell), Paragraph("", cell)])
    mat_table = Table(mat_rows, colWidths=[70 * mm, 90 * mm])
    mat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a85442")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#faf6f2")]),
    ]))
    story.append(mat_table)

    # 逐部件
    for part in params.get("parts", []):
        pd = part.model_dump() if hasattr(part, "model_dump") else part
        rounds = pd.get("rounds", [])
        quantity = max(1, int(pd.get("quantity", 1)))
        qty_label = f" × {quantity} 个" if quantity > 1 else ""
        story.append(Paragraph(
            f"🧶 {esc(pd.get('name', '?'))}{qty_label}"
            f"（{len(rounds)} 圈/个 · {esc(pd.get('type', '—'))}）",
            head))
        dims = []
        if pd.get("diameter_cm"):
            dims.append(f"直径 {esc(pd['diameter_cm'])}cm")
        if pd.get("height_cm"):
            dims.append(f"高 {esc(pd['height_cm'])}cm")
        if dims:
            story.append(Paragraph(" · ".join(dims), small))
        if pd.get("notes"):
            story.append(Paragraph(esc(pd["notes"]), small))
        if rounds:
            head_cells = [Paragraph(h, cell_head) for h in
                          ("圈", "针数", "加/减", "配色", "说明")]
            rows = [head_cells]
            for r in rounds:
                rd = r if isinstance(r, dict) else (
                    r.model_dump() if hasattr(r, "model_dump") else {})
                inc = f"+{rd['increase']}" if rd.get("increase") else (
                    f"-{rd['decrease']}" if rd.get("decrease") else "—")
                rows.append([
                    Paragraph(esc(rd.get("row", "")), cell),
                    Paragraph(esc(rd.get("stitches", "")), cell),
                    Paragraph(esc(inc), cell),
                    Paragraph(esc(rd.get("color") or "—"), cell),
                    Paragraph(esc(rd.get("notes") or ""), cell),
                ])
            rt = Table(rows, colWidths=[10 * mm, 14 * mm, 14 * mm, 22 * mm,
                                        116 * mm], repeatRows=1)
            rt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#a85442")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#faf6f2")]),
            ]))
            story.append(rt)

    # 装配
    assembly = params.get("assembly_instructions") or ""
    if assembly:
        story.append(Paragraph("🔧 装配说明", head))
        for step in str(assembly).split("\n"):
            if step.strip():
                story.append(Paragraph(esc(step), body))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "由 Photo2Amigurumi 生成 — 比例可能需要试钩调整", small))
    doc.build(story)
    return buf.getvalue()
