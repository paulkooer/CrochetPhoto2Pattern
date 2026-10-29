"""A bounded connection schematic shared by screen and printable exports."""
from html import escape

from app.models.stitch_attachments import LoopAttachment, LoopAttachmentPlan


def diagram_rows(connection: dict) -> list[tuple[str, str, str]]:
    c = LoopAttachment.model_validate(connection)
    return [
        ("基底圈", f"{c.target_part} · 第 {c.target_row} 圈", f"第 1–{c.end_stitch} 针"),
        ("先预留", f"{c.target_part} · 第 {c.reservation_row} 圈", "FLO：挑基底圈前半针，留下后半针"),
        ("再接回", f"{c.source_part} · 第 {c.source_row} 圈", f"BLO：接入预留后半针，共 {c.end_stitch} 针"),
    ]


def attachment_svg(connection: dict) -> str:
    rows = diagram_rows(connection)
    fragments = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 288" role="img"',
                 ' aria-label="基底圈、前半针预留与后半针接回的圈序示意">',
                 '<rect width="760" height="288" rx="16" fill="#f6f7fb"/>']
    for i, (action, part, instruction) in enumerate(rows):
        y = 12 + i * 82
        fragments.append(f'<rect x="18" y="{y}" width="724" height="66" rx="9" '
                         'fill="white" stroke="#b3bacd"/>')
        for x, baseline, text, size in ((32, y + 26, action, 15), (126, y + 25, part, 16),
                                        (126, y + 49, instruction, 14)):
            fragments.append(f'<text x="{x}" y="{baseline}" font-size="{size}" '
                             f'font-family="sans-serif" fill="#24324b">{escape(text)}</text>')
        if i < 2:
            fragments.append(f'<path d="M70 {y + 66} v16 m-4 -5 l4 5 4 -5" '
                             'fill="none" stroke="#637fa5" stroke-width="2"/>')
    fragments.append('<text x="20" y="274" font-size="12" font-family="sans-serif" '
                     'fill="#536078">圈序与挑针关系示意；不表示实物比例或实际腰高。多份部件按序一一对应。</text></svg>')
    return "".join(fragments)


def attachment_tables(params: dict) -> list[list[tuple[str, str, str]]]:
    plan = LoopAttachmentPlan.model_validate(params.get("stitch_attachments", {}))
    return [diagram_rows(c.model_dump()) for c in plan.connections]
