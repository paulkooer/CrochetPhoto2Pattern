"""Reviewable exports for the construction prototype, with no legacy gate claim."""
from __future__ import annotations

import html
import io
import json
from dataclasses import dataclass

from app.models.dressed_doll.models import Component, DollPlan, WorkStep
from app.utils.exporters import _md_cell, _md_text


def checked_plan(plan: DollPlan) -> DollPlan:
    return DollPlan.model_validate(plan.model_dump())


@dataclass(frozen=True)
class StepGroup:
    first: int
    last: int
    step: WorkStep

    @property
    def label(self) -> str:
        return str(self.first) if self.first == self.last else f"{self.first}–{self.last}"


def step_groups(component: Component) -> list[StepGroup]:
    result: list[StepGroup] = []
    for step in component.steps:
        data = step.model_dump(exclude={"number"})
        if result and data == result[-1].step.model_dump(exclude={"number"}):
            previous = result.pop()
            result.append(StepGroup(previous.first, step.number, previous.step))
        else:
            result.append(StepGroup(step.number, step.number, step))
    return result


def foundation_text(component: Component) -> str:
    f = component.foundation
    if f.kind == "magic_ring":
        return "魔法环起针；首圈直接按操作式钩短针，随后螺旋圈钩，不引拔、不翻转。"
    if f.kind == "chain_ring":
        return (f"锁 {f.chains} 针，不扭转地引拔连接成环；"
                "引拔不计入圈针数。第 1 圈每锁针钩 1 短针，之后螺旋圈钩。")
    if f.kind == "flat_chain":
        return (f"锁 {f.chains} 针；从钩上倒数第 2 针开始，沿锁针回钩第 1 行。"
                "后续每行先锁 1 针再翻转；翻转锁针不计入本行针数、不在其中钩针。")
    return (f"锁 {f.chains} 针；从倒数第 2 针开始，在近端锁针钩 3 短针，"
            f"沿直边 {f.chains - 3} 针各钩 1 短针，远端锁针钩 3 短针，"
            f"转到锁针另一侧，沿直边 {f.chains - 3} 针各钩 1 短针。"
            "首圈结束后转为螺旋圈钩；在鞋头弧段第一针放记号扣，另标鞋跟弧段。")


def _operation_text(step: WorkStep) -> str:
    turn = "先 CH 1，翻转；" if step.turning_chain else ""
    loops = {"both": "", "front": "只挑前半针；", "back": "只挑后半针；"}[step.loops]
    return turn + loops + step.expression


def export_doll_markdown(plan: DollPlan) -> str:
    plan = checked_plan(plan)
    d = plan.design
    lines = ["# 穿衣人偶结构原型", "",
             "> **未实钩验证。人工选型与尺寸驱动；不是照片自动识别或原作精确图解。**", "",
             f"> 目标总高 {d.height_cm:g}cm（不含帽子）；目标头径 {d.head_diameter_cm:g}cm。",
             f"> 输入密度：每 10cm {d.stitches_per_10cm:g} 针、{d.rows_per_10cm:g} 行/圈；"
             "须分别量片钩与圈钩小样。",
             f"> {len(plan.components)} 份逻辑图解，{sum(c.quantity for c in plan.components)} 个实体部件；"
             f"短针产出与锁针计数合计 {plan.total_operations}。不据此推算克重或工时。", "",
             "记号：X=短针；V=同一针目钩 2 短针；A=2 短针并一针；"
             "W=同一针目钩 3 短针；CH=锁针。括号内为重复单元。", "",
             "连续相同行/圈合并显示，如 2–6 表示第 2、3、4、5、6 行分别执行同一操作式。", "",
             "## 先检查这些部位", ""]
    lines.extend(f"- {_md_text(note)}" for note in plan.trial_checkpoints)
    lines.extend(["", "## 部件与连接", "", "| 部件 | 数量 | 方法 | 连接位置 |",
                  "|---|---:|---|---|"])
    targets = {j.source: j for j in plan.joins}
    names = {p.id: p.name for p in plan.components}
    for p in plan.components:
        join = targets.get(p.id)
        target = names[join.target] if join else "根部件"
        lines.append(f"| {_md_cell(p.name)} | {p.quantity} | "
                     f"{'片钩' if p.work == 'rows' else '圈钩'} | {_md_cell(target)} |")
    for p in plan.components:
        unit = "行" if p.work == "rows" else "圈"
        lines.extend(["", f"## {_md_text(p.name)} × {p.quantity}", "",
                      f"用途：{_md_text(p.role)}；颜色：{_md_text(p.color)}。", "",
                      _md_text(foundation_text(p)), "",
                      f"| {unit} | 段落 | 本{unit}操作式 | 本{unit}针数 | 提示 |",
                      "|---|---|---|---:|---|"])
        for group in step_groups(p):
            s = group.step
            lines.append(f"| {group.label} | {_md_cell(s.section)} | {_md_cell(_operation_text(s))} "
                         f"| {s.stitches} | {_md_cell(s.note)} |")
        lines.extend(["", f"收尾：{_md_text(p.finish)}", ""])
        lines.extend(f"- 试合：{_md_text(note)}" for note in p.fitting)
        join = targets.get(p.id)
        if join:
            lines.extend(["", f"连接到 {_md_text(names[join.target])}：{_md_text(join.placement)}"])
    lines.extend(["", "## 装配顺序", ""])
    lines.extend(f"{i}. {_md_text(note)}" for i, note in enumerate(plan.assembly, 1))
    lines.extend(["", "## 尚未验证与未覆盖", ""])
    lines.extend(f"- {_md_text(note)}" for note in plan.limitations)
    return "\n".join(lines) + "\n"


def export_doll_pdf(plan: DollPlan) -> bytes:
    plan = checked_plan(plan)
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.platypus.doctemplate import LayoutError

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    normal = ParagraphStyle("DollBody", fontName="STSong-Light", fontSize=9, leading=13,
                            wordWrap="CJK", spaceAfter=5)
    heading = ParagraphStyle("DollHeading", parent=normal, fontSize=13, leading=18,
                             spaceBefore=10, spaceAfter=7)
    cell = ParagraphStyle("DollCell", parent=normal, fontSize=8, leading=11)

    def paragraph(text: str, style=normal):
        return Paragraph(html.escape(text), style)

    d = plan.design
    story = [paragraph("穿衣人偶结构原型", heading),
             paragraph("未实钩验证。人工选型与尺寸驱动，不是照片自动识别或原作精确图解。"),
             paragraph(f"目标总高 {d.height_cm:g}cm（不含帽子）；目标头径 {d.head_diameter_cm:g}cm。"),
             paragraph(f"输入密度：10cm × {d.stitches_per_10cm:g} 针 × {d.rows_per_10cm:g} 行/圈。"
                       "分别测片钩与圈钩小样；厘米值为目标，不是实测。"),
             paragraph("X=短针；V=同针目2短针；A=2针并1针；W=同针目3短针；CH=锁针。"
                       "连续相同行/圈合并显示，每行/圈都须执行对应操作。"),
             paragraph("先检查这些部位", heading)]
    story.extend(paragraph(note) for note in plan.trial_checkpoints)
    names = {p.id: p.name for p in plan.components}
    targets = {j.source: j for j in plan.joins}
    for p in plan.components:
        unit = "行" if p.work == "rows" else "圈"
        component_story = [paragraph(f"{p.name} × {p.quantity}（{p.role}）", heading),
                           paragraph(foundation_text(p)), paragraph(f"颜色：{p.color}。")]
        rows = [[paragraph(t, cell) for t in (unit, "段落", "操作式", "针数", "提示")]]
        for group in step_groups(p):
            s = group.step
            rows.append([paragraph(text, cell) for text in
                         (group.label, s.section, _operation_text(s), str(s.stitches), s.note)])
        table = Table(rows, colWidths=[17 * mm, 24 * mm, 68 * mm, 12 * mm, 53 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        component_story.extend([table, Spacer(1, 3 * mm), paragraph(f"收尾：{p.finish}")])
        component_story.extend(paragraph(f"试合：{note}") for note in p.fitting)
        join = targets.get(p.id)
        if join:
            component_story.append(paragraph(f"连接到 {names[join.target]}：{join.placement}"))
        story.append(KeepTogether(component_story))
    story.append(paragraph("装配顺序", heading))
    story.extend(paragraph(f"{i}. {note}") for i, note in enumerate(plan.assembly, 1))
    story.append(paragraph("尚未验证与未覆盖", heading))
    story.extend(paragraph(note) for note in plan.limitations)
    buffer = io.BytesIO()

    def page_background(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    try:
        SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                          topMargin=16 * mm, bottomMargin=16 * mm).build(
                              story, onFirstPage=page_background, onLaterPages=page_background)
    except LayoutError as exc:
        raise ValueError("PDF 版式无法容纳当前步骤，请先使用 Markdown 或缩短单条说明") from exc
    return buffer.getvalue()


def export_doll_graph(plan: DollPlan) -> str:
    """The actual assembly graph; deliberately not a simulated finished object."""
    plan = checked_plan(plan)
    lines = ['digraph doll {', 'rankdir="LR";', 'node [shape="box"];']
    for p in plan.components:
        label = json.dumps(f"{p.name} × {p.quantity}", ensure_ascii=False)
        lines.append(f'{p.id} [label={label}];')
    lines.extend(f'{j.source} -> {j.target};' for j in plan.joins)
    lines.append('}')
    return "\n".join(lines)
