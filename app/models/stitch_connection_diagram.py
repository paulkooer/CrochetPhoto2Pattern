"""Render only the bounded parent-association window, without a physical layout."""
from html import escape

from app.models.stitch_connections import RoundConnections

_COLORS = {"both": "#64748b", "FLO": "#2563eb", "BLO": "#c2410c"}


def connection_svg(view: RoundConnections) -> str:
    sources = sorted({n for op in view.operations for n in op.sources})
    targets = sorted({n for op in view.operations for n in op.targets})
    width = max(780, 34 * max(len(sources), len(targets)) + 96)

    def positions(nodes):
        return {n: 48 + (i + 0.5) * (width - 96) / len(nodes) for i, n in enumerate(nodes)}

    source_x, target_x = positions(sources), positions(targets)
    name = escape(view.part_name[:80])
    first, last = view.operations[0].index, view.operations[-1].index
    fragments = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="318" '
        f'viewBox="0 0 {width} 318" role="img" aria-label="逐针来源连接图">',
        f'<title>{name}：第 {view.source_row} 圈到第 {view.target_row} 圈的针目关联</title>',
        '<desc>上排为上一圈针目，下排为本圈新针。连线表示来源关系，不是线股路径或实物形状。</desc>',
        f'<rect width="{width}" height="318" rx="12" fill="#f6f7fb"/>',
        '<g font-family="sans-serif" fill="#24324b">',
        f'<text x="24" y="28" font-size="16">{name} · 操作 {first}–{last} / '
        f'{view.operation_count}</text>',
        f'<text x="24" y="55" font-size="14">来源：第 {view.source_row} 圈 · '
        f'全圈 {view.source_stitches} 针</text>',
    ]
    for op in view.operations:
        color = _COLORS[op.loop]
        for source in op.sources:
            for target in op.targets:
                fragments.append(
                    f'<line x1="{source_x[source]:.2f}" y1="106" '
                    f'x2="{target_x[target]:.2f}" y2="208" stroke="{color}" stroke-width="2" '
                    f'data-parent="{source}" data-child="{target}" '
                    f'data-operation="{op.index}" data-kind="{op.symbol}" data-loop="{op.loop}"'
                    + (' stroke-dasharray="5 3"' if op.loop == "BLO" else '') + '>'
                    f'<title>操作 {op.index}：{op.symbol} · {op.loop} · '
                    f'源针 {source} → 新针 {target}</title></line>'
                )
    for nodes, x_values, y in ((sources, source_x, 94), (targets, target_x, 220)):
        for node in nodes:
            fragments.append(
                f'<circle cx="{x_values[node]:.2f}" cy="{y}" r="12" '
                'fill="white" stroke="#64748b"/>'
                f'<text x="{x_values[node]:.2f}" y="{y + 4}" '
                f'text-anchor="middle" font-size="10">{node}</text>'
            )
    fragments.extend([
        f'<text x="24" y="255" font-size="14">本圈：第 {view.target_row} 圈 · '
        f'全圈 {view.target_stitches} 针</text>',
        '<text x="24" y="280" font-size="12">灰色＝双半针；蓝色＝FLO；橙色虚线＝BLO。'
        '一源多针为加针，多源一针为减针。</text>',
        '<text x="24" y="302" font-size="12">按操作式起点线性展开；实物起点、朝向、'
        '附加文字和跨部件接合须另行核对。</text>',
        '</g></svg>',
    ])
    return "".join(fragments)
