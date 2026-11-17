"""Readable recipe tables derived from checked routes, not a second stitch script."""
from __future__ import annotations

import html
import io
import math
import re
from dataclasses import dataclass
from itertools import groupby

from app.models.working_path import (
    ChainBridge,
    ConstructionGauge,
    Route,
    RowEdges,
    Step,
    StitchEvent,
    Work,
    WorkingPath,
    compile_working_path,
)
from app.utils.working_path_export import scope_note, step_text
from app.utils.working_path_format import route_controls, route_formula


@dataclass(frozen=True)
class RecipeRow:
    first: int
    last: int
    formula: str
    working_sites: int
    hook: str
    controls: str


def recipe_rows(routes: list[Route], gauges: dict[str, ConstructionGauge], *,
                events_by_route: dict[str, list[StitchEvent]] | None = None) -> list[RecipeRow]:
    rows: list[RecipeRow] = []
    previous_id = ""
    for index, route in enumerate(routes, 1):
        formula, binding = route_formula(route, events=None if events_by_route is None else
                                         events_by_route.get(route.id, []))
        gauge = gauges.get(route.gauge or "")
        origins = [f"{op.source.edge}第{op.source.first}–{op.source.last}位"
                   for op in route.operations if isinstance(op, Work) and op.disposition == "working"
                   and op.source.edge != previous_id]
        source_note = "来源：" + "、".join(origins) if origins else ""
        controls = "；".join(filter(None, (binding, source_note, route_controls(route))))
        row = RecipeRow(route.row_number or index, route.row_number or index, formula, route.expected_sites,
                        f"{gauge.hook_mm:g}" if gauge is not None else "未填", controls)
        if rows and rows[-1].last + 1 == row.first and (
            rows[-1].formula, rows[-1].working_sites, rows[-1].hook, rows[-1].controls
        ) == (row.formula, row.working_sites, row.hook, row.controls):
            previous = rows.pop()
            row = RecipeRow(previous.first, row.last, row.formula, row.working_sites, row.hook, row.controls)
        rows.append(row)
        previous_id = route.id
    return rows


def export_working_recipe_pdf(plan: WorkingPath) -> bytes:
    result = compile_working_path(plan)
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        Flowable,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.platypus.doctemplate import LayoutError

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    normal = ParagraphStyle("RecipeBody", fontName="STSong-Light", fontSize=9, leading=13,
                            wordWrap="CJK", spaceAfter=6)
    heading = ParagraphStyle("RecipeHeading", parent=normal, fontSize=13, leading=18,
                             spaceBefore=9, spaceAfter=7, keepWithNext=True)
    title = ParagraphStyle("RecipeTitle", parent=heading, fontSize=16, leading=22)
    cell = ParagraphStyle("RecipeCell", parent=normal, fontSize=8, leading=11, spaceAfter=0)

    def p(text, style=normal):
        pieces, previous = [], 0
        for token in re.finditer(r"[A-Za-z0-9_./=<>-]+", text):
            pieces.append(html.escape(text[previous:token.start()]))
            pieces.append('<font face="Helvetica">' + html.escape(token.group()) + '</font>')
            previous = token.end()
        pieces.append(html.escape(text[previous:]))
        return Paragraph("".join(pieces), style)

    story = [p(result.plan.title, title), p(scope_note(result.plan))]
    if result.plan.review_notes:
        story.append(p("审查说明与候选修改", heading))
        story.extend(p(note) for note in result.plan.review_notes)
    story += [p("记号与计数", heading),
              p("X=短针；V=同针目2短针；A=2针并1针；SL=引拔；CH=锁针；"
                "BLO/FLO=只挑后/前半针；起立X=无结起立短针。"),
              p("工作针位包含锁针桥。接合引拔、翻转链和隐形闭合单列，不加入下一行针数。"
                "合并行号中的每一行均执行同一操作；这些行仍须逐行完成。")]
    events_by_route: dict[str, list[StitchEvent]] = {}
    for event in result.events:
        events_by_route.setdefault(event.route, []).append(event)
    gauges = {g.id: g for g in result.plan.gauges}
    if gauges:
        story.append(p("针号与密度", heading))
        for gauge in gauges.values():
            values = (f"每10cm {gauge.stitches_per_10cm:g}针 × {gauge.rows_per_10cm:g}行"
                      if gauge.stitches_per_10cm is not None and gauge.rows_per_10cm is not None
                      else "密度未测，不套用其他针法的数值")
            basis = {"reference_declared": "参考教程声明，非本次实测", "unmeasured": "待测小样",
                     "hypothetical": "假设值，仅用于设计",
                     "user_entered_swatch": "用户输入的小样数据，未独立核验"}[gauge.basis]
            story.append(p(f"{gauge.method}：{gauge.hook_mm:g}mm；{values}；{basis}。"))

    bridge_ids = {op.id for step in result.plan.steps if isinstance(step, Route)
                  for op in step.operations if isinstance(op, ChainBridge)}
    openings = [(name, sites) for name, sites in result.held_edges.items()
                if sum(site.face.startswith("corner_") for site in sites) == 2 and len(sites) <= 40]
    if openings:
        story += [p("袖窿来源顺序示意", heading),
                  p("编号只表示工序中的落针顺序；圆形排布不是实物形状或线股路径。"
                    "蓝色=锁针桥，灰色=预留针位，红色=转角。")]

        class OpeningFigure(Flowable):
            def __init__(self, name, sites):
                super().__init__()
                self.width, self.height = 82*mm, 62*mm
                self.name, self.sites = name, sites

            def draw(self):
                canvas = self.canv
                cx, cy, radius = self.width/2, 31*mm, 20*mm
                canvas.setFillColor(colors.black)
                canvas.setFont("Helvetica", 8)
                canvas.drawCentredString(cx, self.height-9, f"{self.name}: {len(self.sites)}")
                for index, site in enumerate(self.sites):
                    angle = math.pi/2-2*math.pi*index/len(self.sites)
                    x, y = cx+radius*math.cos(angle), cy+radius*math.sin(angle)
                    role = ("corner" if site.face.startswith("corner_") else
                            "bridge" if site.edge in bridge_ids else "held")
                    color = {"corner": "#c54545", "bridge": "#347aa5", "held": "#858f99"}[role]
                    canvas.setFillColor(colors.HexColor(color))
                    canvas.setStrokeColor(colors.black)
                    canvas.setLineWidth(1.2 if index == 0 else .3)
                    canvas.circle(x, y, 3.8, stroke=1, fill=1)
                    canvas.setFillColor(colors.black)
                    canvas.setFont("Helvetica", 7)
                    canvas.drawCentredString(cx+(radius+11)*math.cos(angle),
                                             cy+(radius+11)*math.sin(angle)-2.5, str(index+1))
                counts = [sum(site.edge in bridge_ids and not site.face.startswith("corner_")
                              for site in self.sites),
                          sum(site.edge not in bridge_ids for site in self.sites),
                          sum(site.face.startswith("corner_") for site in self.sites)]
                canvas.setFont("STSong-Light", 8)
                canvas.drawCentredString(cx, 5, f"桥 {counts[0]} + 预留 {counts[1]} + 转角 {counts[2]}")

        for index in range(0, len(openings), 2):
            figures = [OpeningFigure(name, sites) for name, sites in openings[index:index+2]]
            story.append(Table([figures], colWidths=[87*mm]*len(figures)))

    blocks: list[tuple[str, list[Step]]] = []
    for key, items in groupby(result.plan.steps,
                              key=lambda step: step.section if isinstance(step, Route) else ""):
        blocks.append((key, list(items)))
    for section, block in blocks:
        if section:
            routes = [step for step in block if isinstance(step, Route)]
            label = re.sub(r"\s*第\s*\d+\s*行.*$", "", routes[0].label)
            story.append(p(label, heading))
            if routes[0].side is not None:
                side = "正面 RS" if routes[0].side == "RS" else "反面 WS"
                story.append(p(f"下表首行朝向：{side}；之后依表翻面。工作来源见起针、保留边与接合准备。"))
            rows = [[p(text, cell) for text in ("行", "工作操作", "针位", "mm", "接合及翻面")]]
            for row in recipe_rows(routes, gauges, events_by_route=events_by_route):
                label = str(row.first) if row.first == row.last else f"{row.first}–{row.last}"
                rows.append([p(text, cell) for text in (label, row.formula, str(row.working_sites),
                                                       row.hook, row.controls)])
            table = Table(rows, colWidths=[13*mm, 78*mm, 12*mm, 10*mm, 61*mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7edf2")),
                ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#b9c3cb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story += [table, Spacer(1, 2*mm)]
            for route in routes:
                if route.note:
                    story.append(p(f"第{route.row_number}行提示：{route.note}"))
        else:
            for step in block:
                if isinstance(step, Route):
                    text = step_text(step, events=events_by_route.get(step.id))
                elif isinstance(step, RowEdges):
                    first, last = step.rows[0], step.rows[-1]
                    text = (f"按顺序取 {first.row} 的{first.side}行端至 {last.row} 的{last.side}行端，"
                            f"共{len(step.rows)}个位置；完整逐位来源保存在配套JSON。")
                else:
                    text = step_text(step, events=events_by_route.get(step.id))
                story.append(KeepTogether([p(step.label, heading), p(text)]))
    story += [p("本稿检查范围", heading),
              p("已检查声明针位的建立、保留、使用与去向，以及记录的行号、接合和翻面控制。"
                "未实钩、未试穿，也未作织物形变或最终外观模拟。候选修改不等于原作者意图已确认。")]
    buffer = io.BytesIO()

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, *A4, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.setFont("STSong-Light", 8)
        canvas.drawString(18*mm, 10*mm, "人工工序核对稿 · 未实钩 / 未试穿")
        canvas.drawRightString(A4[0]-18*mm, 10*mm, str(doc.page))
        canvas.restoreState()

    try:
        SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                          topMargin=16*mm, bottomMargin=18*mm,
                          title=result.plan.title, author="CrochetPhoto2Pattern").build(
                              story, onFirstPage=page, onLaterPages=page)
    except LayoutError as exc:
        raise ValueError("单行工序超出PDF页面，请使用逐步Markdown或拆分该工序") from exc
    return buffer.getvalue()
