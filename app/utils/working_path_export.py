"""Explain explicit working-site routes without depicting an unproved garment."""
from __future__ import annotations

import html
import io
import re

from app.models.working_path import (
    ChainBridge,
    EdgePath,
    FastenOff,
    FinishEdge,
    FoundationChain,
    FreeLoops,
    Hold,
    NewYarn,
    ParkYarn,
    ResumeYarn,
    RowEdges,
    Seam,
    Span,
    Step,
    StitchEvent,
    WeaveEnds,
    WorkingPath,
    compile_working_path,
)
from app.utils.exporters import _md_text
from app.utils.working_path_format import route_formula

BOUNDARY = ("这是工序校验演示，起始织片由人工声明；没有起针、线材、尺寸或完整衣物步骤。"
            "只检查工作位置的来源、保留和使用，不能当作可穿着衣物或目标照片的试钩图解。")


_BLOCK_START = re.compile(r"^(#|>|&gt;|[-+*=]|\d+[.)]|```|~~~)")


def _md_line(value) -> str:
    """File-supplied text as one inert Markdown line.

    Titles, labels and notes come from the loaded plan. Line breaks are folded
    so the text cannot start a paragraph, heading or quote of its own, and a
    leading block marker is escaped so a list item cannot become a heading.
    """
    text = _md_text(" ".join(str(value).split()))
    return "\\" + text if _BLOCK_START.match(text) else text


def _span_text(span: Span) -> str:
    face = {"top": "顺序工作位", "underside": "锁针反面工作位", "front_loop": "前半针工作位",
            "back_loop": "后半针工作位", "corner_start": "锁针桥起端转角位", "corner_end": "锁针桥末端转角位",
            "row_left": "左行端", "row_right": "右行端", "binding": "接合引拔位"}[span.face]
    order = "反向" if span.direction == "reverse" else "正向"
    return f"{span.edge} 的{face}第 {span.first}–{span.last} 位（{order}）"


def scope_note(plan: WorkingPath) -> str:
    if plan.input_origin == "manual_existing_edges":
        return BOUNDARY
    if plan.input_origin == "parametric_design":
        return ("这是按人工指定的尺寸和做法生成的工序设计草稿，尚未实钩、试穿或独立专家复核。"
                "不是原教程复原或照片自动生成。声明的工作边与尺寸估算不证明成衣合身。")
    return ("这是人工录入工序的桌面核对稿，尚未实钩、试穿或独立专家复核。"
            "记录起针、保留、挑针、接合与控制步骤，不证明原教程完全无误或成品必然合身。"
            "成品边及孔边保留按声明计账，不代表在这些位置实际钩织。")


def step_text(step: Step, *, events: list[StitchEvent] | tuple[StitchEvent, ...] | None = None) -> str:
    if isinstance(step, NewYarn):
        side = "正面RS" if step.side == "RS" else "反面WS"
        if step.anchor is None:
            return f"取新线段 {step.yarn}，准备独立起链；织片首行以{side}为工作面。"
        return (f"取新线段 {step.yarn}，在{_span_text(step.anchor)}另接线；朝向{side}，"
                "下一步在该位置作一个无结起立短针，随后按表钩织。")
    if isinstance(step, FastenOff):
        return (f"在{_span_text(step.source)}对应的当前工作环结束线段 {step.yarn}。"
                f"剪断线，留约{step.tail_cm:g}cm尾线，将线端从工作环抽出并拉紧；藏线另列。"
                "这一步不增加或消耗织物针目。")
    if isinstance(step, ParkYarn):
        return (f"将线段 {step.yarn} 在{_span_text(step.source)}对应的工作环放大，用记号扣固定；"
                "暂不剪线，保留给后续接合。此时仍连接原线团，随后另接线须有另一可用线头。")
    if isinstance(step, ResumeYarn):
        return f"将线段 {step.yarn} 先前暂停的工作环重新套回钩针，收回适当大小后继续。"
    if isinstance(step, WeaveEnds):
        ends = {"starting": "起线端", "finishing": "结束端", "both": "起线端与结束端"}[step.ends]
        return (f"用缝针将线段 {step.yarn} 的{ends}在织物反面沿已有针脚分向穿藏；"
                "轻整织物，检查线端固定后修剪余线。这是制作步骤，不表示已经完成实物验证。")
    if isinstance(step, EdgePath):
        return ("将已有针位依此顺序命名为新的工作边："
                + "；".join(_span_text(span) for span in step.spans)
                + "。后续须用新名称引用；此步只重排工作位置，不作钩织或缝合。")
    if isinstance(step, Hold):
        return "依序保留：" + "；".join(_span_text(span) for span in step.spans) + "。这些位置暂不钩织。"
    if isinstance(step, FoundationChain):
        if step.anchor is None:
            anchor = "独立起链"
        elif step.anchor_mode == "continues_loop":
            anchor = f"从 {_span_text(step.anchor)} 的当前工作环继续起链"
        else:
            anchor = f"在 {_span_text(step.anchor)} 接入起链根部"
        faces = {"top": "起链另一侧针目", "underside": "里山", "front_loop": "前半针", "back_loop": "后半针"}
        turn = {"none": "", "clockwise": "起链后顺时针翻面。",
                "counterclockwise": "起链后逆时针翻面。"}[step.turn_after_chain]
        return (f"{anchor}，锁 {step.chains} 针；跳过钩旁 {step.skip_from_hook} 针。"
                f"{turn}后续工作用{faces[step.work_face]}，{faces[step.other_face]}另有记录。{step.note}")
    if isinstance(step, RowEdges):
        return "依序挑行端：" + "；".join(f"{ref.row} 的 {ref.side} 行端" for ref in step.rows)
    if isinstance(step, FreeLoops):
        return f"引用 {_span_text(step.source)} 先前明确保留的 {step.loop} 半针；不凭空新增针目。"
    if isinstance(step, Seam):
        selected = [] if events is None else [event for event in events if event.route == step.id
                                              and event.role == "binding"]

        def selection(index, loop):
            if loop != "both":
                return "只挑前半针 FLO" if loop == "front" else "只挑后半针 BLO"
            faces = {event.sources[index].face for event in selected}
            if faces == {"front_loop"}:
                return "已预留的前半针 FLO"
            if faces == {"back_loop"}:
                return "已预留的后半针 BLO"
            return "该工作边所提供的针位"

        facing = ("" if step.side is None else
                  f"以{'正面RS' if step.side == 'RS' else '反面WS'}朝向自己，前后半针按此时所见区分；")
        return (f"{facing}将 {_span_text(step.left)}（{selection(0, step.left_loop)}）"
                f"与 {_span_text(step.right)}（{selection(1, step.right_loop)}）依序配对，"
                f"同时穿过两侧作引拔接合；接合针不作为下一行工作边。{step.note}")
    if isinstance(step, FinishEdge):
        return f"{_span_text(step.source)} 作为成品边保留，不再继续工作；记录原因 {step.reason}。"
    descriptions = []
    for op in step.operations:
        if isinstance(op, ChainBridge):
            used, held = ("正面", "反面") if op.route_face == "top" else ("反面", "正面")
            descriptions.append(f"锁 {op.count} 针，命名 {op.id}；{used}进入本段工作边，{held}留作开口边")
            if op.corner_sites:
                descriptions.append("两端各有一个转角入针位，来源为基底与桥端的连接处")
            if op.placement == "buttonhole":
                assert op.skipped is not None
                descriptions.append(f"{_span_text(op.skipped)} 不钩，作为扣眼孔边保留")
        else:
            stitch = {"sc": "每位置 1 短针", "standing_sc": "无结起立短针", "inc": "每位置 2 短针",
                      "dec": "每两位置并成 1 短针", "slst": "每位置 1 引拔针"}[op.stitch]
            loop = {"both": "", "front": "只挑前半针，", "back": "只挑后半针，"}[op.loop]
            binding = "；这些是接合引拔，不进入下一行工作边" if op.disposition == "binding" else ""
            descriptions.append(f"在 {_span_text(op.source)} {loop}钩{stitch}{binding}")
    chain_note = "（含锁针桥所选工作面）" if any(isinstance(op, ChainBridge)
                                               for op in step.operations) else ""
    controls = []
    if step.mode != "segment":
        controls.append(f"{step.mode}，{step.side}，行方向 {step.row_direction}")
    if step.closure != "none":
        controls.append("先隐形引拔后翻面" if step.closure == "before_turn" else "先翻面后隐形引拔")
    elif step.turn != "none":
        controls.append("逆时针翻面" if step.turn == "counterclockwise" else "顺时针翻面")
    if step.turning_chains:
        controls.append(f"翻转锁针 {step.turning_chains} 针，不计入工作边")
    if step.gauge:
        controls.append(f"密度记录 {step.gauge}")
    if step.source_ref:
        controls.append(f"依据 {step.source_ref}")
    if step.note:
        controls.append(step.note)
    if events is not None:
        formula, binding = route_formula(step, events=events)
        controls.append("按实际来源分段：" + formula + ("；" + binding if binding else ""))
    suffix = "；".join(controls)
    return ("；".join(descriptions) + f"。本段形成 {step.expected_sites} 个工作位置{chain_note}。"
            + (suffix + "。" if suffix else ""))


def export_working_path_markdown(plan: WorkingPath) -> str:
    result = compile_working_path(plan)
    lines = [f"# {_md_line(result.plan.title)}", "", f"> {scope_note(result.plan)}", ""]
    if result.plan.review_notes:
        lines += ["## 必须保留的审查说明", ""]
        lines.extend(f"- {_md_line(note)}" for note in result.plan.review_notes)
    lines += ["", "## 起始条件", ""]
    lines.extend(f"- `{edge.id}`：已有织片上人工声明的 {edge.count} 个顺序工作位置。"
                 for edge in result.plan.existing_edges)
    lines += ["", "## 明确的工作路径", ""]
    events_by_step: dict[str, list[StitchEvent]] = {}
    for event in result.events:
        events_by_step.setdefault(event.route, []).append(event)
    lines.extend(f"{index}. **{_md_line(step.label)}**（`{step.id}`）："
                 f"{_md_line(step_text(step, events=events_by_step.get(step.id)))}"
                 for index, step in enumerate(result.plan.steps, 1))
    lines += ["", "## 留给后续工作的边", ""]
    lines.extend(f"- `{name}`：{len(sites)} 个可继续工作的针位。"
                 for name, sites in result.final_edges.items())
    lines += ["", "## 检查结论与边界", "",
              "- 所有来源都已建立、针位未越界；同一位置不能换个名字重复使用。",
              "- 保留位置通过对应保留边继续工作；未用位置必须有明确去向。",
              "- 一条锁针的正反工作位有各自引用；两个工作位不代表锁了两针。",
              "- 工作边长度包含锁针桥；它不等于该工序短针数。",
              "- 转角与行端来自已建立的连接或片钩行；接合引拔与正式工作边分开记录。",
              "- 闭合接头的翻面顺序会检查，半针复用须有先前实际预留的记录。",
              "- 未证明工作方向的实物正确性、密度、穿着余量或成形。",
              "- 跨圈外钩和织物形变尚未实现；这些工序不自动用于旧照片生成器。", ""]
    if result.plan.input_origin == "manual_existing_edges":
        lines.append("本例为数字练习，不是目标作品的完整图解。")
    return "\n".join(lines)


def export_working_path_pdf(plan: WorkingPath) -> bytes:
    result = compile_working_path(plan)
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    normal = ParagraphStyle("PathBody", fontName="STSong-Light", fontSize=10, leading=14,
                            wordWrap="CJK", spaceAfter=6)
    heading = ParagraphStyle("PathHeading", parent=normal, fontSize=12, leading=17,
                             spaceBefore=6, spaceAfter=6)

    def p(text, style=normal):
        return Paragraph(html.escape(text), style)

    story = [p("工序验证说明", heading), p(result.plan.title), p(scope_note(result.plan)),
             p("本次证明什么", heading),
             p("程序能把已有工作边拆成衣身和暂留袖窿；明确锁针桥的两面，然后沿保留位置继续工作。"
               "它会拒绝重复占用针位、漏掉针位或把已用于衣身的桥面再次当作袖子来源。"),
             p("演示的起始条件", heading)]
    story.extend(p(f"{edge.id}：人工声明已有 {edge.count} 个顺序工作位置。")
                 for edge in result.plan.existing_edges)
    story.append(p("逐步路径", heading))
    for index, step in enumerate(result.plan.steps, 1):
        story.append(KeepTogether([p(f"{index}. {step.label}（{step.id}）", heading), p(step_text(step))]))
    story += [Spacer(1, 2 * mm), p("最后留下的工作边", heading)]
    story.extend(p(f"{name}：{len(sites)} 个工作位置。") for name, sites in result.final_edges.items())
    story.append(KeepTogether([
        p("尚未解决", heading),
        p("来源检查和控制步骤不证明织物方向、不同针法密度、穿着余量或实物成形。"
          "没有实体试钩或独立专家复核；跨圈外钩与织物形变尚未实现。"),
        p("每条锁针有正反两个引用位置，仍只是一条锁针。工作边针位数不能直接用作用线、工时或成品尺寸。"),
    ]))
    buffer = io.BytesIO()

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, *A4, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.setFont("STSong-Light", 8)
        canvas.drawString(17 * mm, 10 * mm, "工作路径实验 · 仅针位记录检查 · 未实钩")
        canvas.drawRightString(A4[0] - 17 * mm, 10 * mm, str(doc.page))
        canvas.restoreState()

    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=17 * mm, rightMargin=17 * mm,
                      topMargin=16 * mm, bottomMargin=18 * mm,
                      title="袖窿工序验证说明", author="CrochetPhoto2Pattern").build(
                          story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
