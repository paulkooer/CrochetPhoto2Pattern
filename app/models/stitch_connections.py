"""Windowed stitch-parent associations from an explicit adjacent-round formula.

This is a combinatorial view of the supported short-stitch grammar, not a yarn
simulation. No positions are inferred from aggregate counts or assembly prose.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass

from app.models.instruction_checks import instruction_issues, round_expression
from app.models.stitch_notation import (
    StitchExpression,
    format_stitch_expression,
    mentions_invisible_decrease,
)
from app.schemas import MAX_PART_ROUNDS, MAX_ROUND_STITCHES
from app.utils.counts import integer_count

CONNECTION_PAGE_SIZE = 24
MAX_CONNECTION_WINDOW = 40


@dataclass(frozen=True)
class StitchConnection:
    index: int
    symbol: str
    loop: str
    sources: tuple[int, ...]
    targets: tuple[int, ...]


@dataclass(frozen=True)
class RoundConnections:
    part_name: str
    source_row: int
    target_row: int
    source_stitches: int
    target_stitches: int
    formula: str
    operation_count: int
    start: int
    operations: tuple[StitchConnection, ...]

    def to_dict(self) -> dict:
        return {"schema_version": "1", "kind": "round_stitch_connection_window",
                "basis": "explicit_expression", "index_base": 1,
                "complete": self.start == 0 and len(self.operations) == self.operation_count,
                **asdict(self)}


def _operation_counts(expression: StitchExpression, counts: dict[int, int]) -> int:
    unit = (1 if expression.stitch is not None else
            sum(_operation_counts(child, counts) for child in expression.children))
    counts[id(expression)] = unit * expression.repeats
    return counts[id(expression)]


def _window(expression: StitchExpression, start: int, stop: int, counts: dict[int, int],
            *, index: int = 0, source: int = 0, target: int = 0) -> Iterator[StitchConnection]:
    """Skip entire repeat blocks using their counts, including before a late page."""
    unit_ops = counts[id(expression)] // expression.repeats
    unit_in = expression.counts.consumed // expression.repeats
    unit_out = expression.counts.produced // expression.repeats
    for repeat in range(start // unit_ops, (stop - 1) // unit_ops + 1):
        offset = repeat * unit_ops
        local_start, local_stop = max(0, start - offset), min(unit_ops, stop - offset)
        op_index = index + offset
        source_offset, target_offset = source + repeat * unit_in, target + repeat * unit_out
        if expression.stitch is not None:
            symbol, _, loop = expression.stitch.partition("-")
            yield StitchConnection(
                op_index + 1, symbol, loop or "both",
                tuple(range(source_offset + 1, source_offset + unit_in + 1)),
                tuple(range(target_offset + 1, target_offset + unit_out + 1)),
            )
        else:
            child_start = 0
            for child in expression.children:
                child_stop = child_start + counts[id(child)]
                if child_start < local_stop and child_stop > local_start:
                    yield from _window(
                        child, max(0, local_start - child_start),
                        min(counts[id(child)], local_stop - child_start), counts,
                        index=op_index, source=source_offset, target=target_offset,
                    )
                child_start = child_stop
                op_index += counts[id(child)]
                source_offset += child.counts.consumed
                target_offset += child.counts.produced


def round_connections(part: dict, row_index: int, *, start: int = 0,
                      limit: int = CONNECTION_PAGE_SIZE) -> RoundConnections:
    """Map a bounded window of operations; row_index is an index, not a row label."""
    if type(start) is not int or start < 0:
        raise ValueError("连接窗口起点须为非负整数")
    if type(limit) is not int or not 1 <= limit <= MAX_CONNECTION_WINDOW:
        raise ValueError(f"每次仅可查看 1–{MAX_CONNECTION_WINDOW} 个操作")
    rounds = part.get("rounds")
    if (not isinstance(rounds, list) or len(rounds) > MAX_PART_ROUNDS
            or type(row_index) is not int or not 0 <= row_index < len(rounds)):
        raise ValueError("请选择当前部件的有效圈次")
    if row_index == 0:
        raise ValueError("首圈没有本部件的上一圈；魔法环、锁针起针及跨部件接合请另行核对")
    previous, current = rounds[row_index - 1], rounds[row_index]
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise ValueError("相邻圈记录须为对象")
    try:
        source_row = integer_count(previous.get("row", row_index))
        target_row = integer_count(current.get("row", row_index + 1))
        before = integer_count(previous.get("stitches"))
        after = integer_count(current.get("stitches"))
        inc = integer_count(0 if current.get("increase") is None else current["increase"])
        dec = integer_count(0 if current.get("decrease") is None else current["decrease"])
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("圈号、针数及加减针须为有效整数") from exc
    if (source_row < 1 or target_row < 1 or source_row == target_row
            or not 1 <= before <= MAX_ROUND_STITCHES or not 1 <= after <= MAX_ROUND_STITCHES
            or not 0 <= inc <= MAX_ROUND_STITCHES or not 0 <= dec <= MAX_ROUND_STITCHES
            or after != before + inc - dec):
        raise ValueError("相邻圈的圈号、针数或加减针不一致或超出范围")
    notes = current.get("notes")
    if mentions_invisible_decrease(notes):
        raise ValueError("隐形减针的具体挑针过程未纳入此连接图，请人工核对")
    issues = instruction_issues(notes, after, inc, dec, previous_stitches=before)
    if issues:
        raise ValueError("；".join(issues))
    expression = round_expression(notes)
    if expression is None:
        raise ValueError("缺少明确的完整操作式；连接图不按聚合针数推测针位")
    c = expression.counts
    if (c.consumed, c.produced, c.increase, c.decrease) != (before, after, inc, dec):
        raise ValueError("操作式的消耗、产出或加减针与相邻圈不一致")
    counts: dict[int, int] = {}
    total = _operation_counts(expression, counts)
    if start >= total:
        raise ValueError("连接窗口起点超出本圈操作数")
    operations = tuple(_window(expression, start, min(total, start + limit), counts))
    return RoundConnections(str(part.get("name", "未命名")), source_row, target_row,
                            before, after, format_stitch_expression(expression), total, start, operations)
