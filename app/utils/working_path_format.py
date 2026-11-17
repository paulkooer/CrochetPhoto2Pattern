"""Instruction text from explicit operations and their resolved physical-site kinds."""
from __future__ import annotations

from itertools import groupby

from app.models.working_path import ChainBridge, Route, StitchEvent, Work


def _qualifier(face: str, loop: str) -> str:
    if loop != "both":
        return "-FLO" if loop == "front" else "-BLO"
    return {"top": "", "front_loop": "-FLO", "back_loop": "-BLO", "underside": "（里山）",
            "corner_start": "（转角）", "corner_end": "（转角）",
            "row_left": "（行端）", "row_right": "（行端）", "binding": "（接合位）"}[face]


def _event_qualifier(event: StitchEvent) -> str:
    tags = tuple(_qualifier(site.face, loop)
                 for site, loop in zip(event.sources, event.source_loops, strict=True))
    if len(set(tags)) == 1:
        return tags[0]
    return "（依次：" + "、".join(tag or "针目顶部" for tag in tags) + "）"


def _chain_text(route: Route, index: int, op: ChainBridge) -> str:
    text = f"{op.count}CH"
    if op.skipped is not None:
        return text + f"，跳过{op.skipped.last - op.skipped.first + 1}针"
    before, after = route.operations[index - 1], route.operations[index + 1]
    if isinstance(before, Work) and isinstance(after, Work):
        a, b = before.source, after.source
        if a.edge == b.edge and a.direction == b.direction:
            gap = (a.first - b.last - 1) if a.direction == "reverse" else (b.first - a.last - 1)
            if gap > 0:
                text += f"，保留{gap}针作开口"
    return text


def route_formula(route: Route, *, events: tuple[StitchEvent, ...] | list[StitchEvent] | None = None
                  ) -> tuple[str, str]:
    """Resolved events prevent an alias edge from hiding chains, corners or row ends.

    Without events this formats explicit syntax only. User-facing readers always
    pass the compiler's events, since a named edge can contain several site kinds.
    """
    selected = None if events is None else [event for event in events if event.route == route.id
                                           and event.role in ("working", "binding")]
    cursor = 0
    working, binding = [], []
    for index, op in enumerate(route.operations):
        if isinstance(op, ChainBridge):
            if selected is not None:
                batch = selected[cursor:cursor + 1]
                cursor += 1
                if (len(batch) != 1 or batch[0].stitch != "chain"
                        or len(batch[0].outputs) != 2*op.count or batch[0].outputs[0].edge != op.id):
                    raise ValueError("锁针文字与已解析的工序事件不一致")
            working.append(_chain_text(route, index, op))
            continue
        count = op.source.last - op.source.first + 1
        operations = count // 2 if op.stitch == "dec" else count
        if selected is None:
            groups = [(operations, _qualifier(op.source.face, op.loop))]
        else:
            batch = selected[cursor:cursor + operations]
            cursor += operations
            if len(batch) != operations or any(event.stitch != op.stitch or event.role != op.disposition
                                                for event in batch):
                raise ValueError("针法文字与已解析的工序事件不一致")
            groups = [(len(list(group)), qualifier)
                      for qualifier, group in groupby(batch, key=_event_qualifier)]
        if op.disposition == "binding":
            tags = list(dict.fromkeys(qualifier for _, qualifier in groups if qualifier))
            qualifier = "、".join(tags)
            binding.append(f"接合{count}引拔{qualifier}→{op.source.edge}第{op.source.first}–{op.source.last}位")
            continue
        symbol = {"sc": "X", "standing_sc": "起立X", "inc": "V", "dec": "A", "slst": "SL"}[op.stitch]
        working.extend(f"{n}{symbol}{qualifier}" for n, qualifier in groups)
    if selected is not None and cursor != len(selected):
        raise ValueError("已解析事件未完整进入图解文字")
    return "，".join(working), "；".join(binding)


def route_controls(route: Route) -> str:
    turn = "逆时针翻面" if route.turn == "counterclockwise" else "顺时针翻面"
    chain = f"CH{route.turning_chains}" if route.turning_chains else "不加翻转链"
    if route.closure == "before_turn":
        return f"隐形引拔→{turn}→{chain}"
    if route.closure == "after_turn":
        return f"{turn}→隐形引拔→{chain}"
    if route.turn == "none":
        return "本行不翻面；接下一道工序或收尾"
    return f"{chain}，{turn}" if route.turning_chains else f"{turn}，不加翻转链"
