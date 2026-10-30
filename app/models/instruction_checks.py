"""Conservative checks for explicit current-round claims, not a prose parser."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .stitch_notation import (
    NotationError,
    StitchExpression,
    UnsupportedLoopError,
    mentions_invisible_decrease,
    mentions_loop_technique,
    parse_stitch_expression,
)

_TOTAL = re.compile(r"(?:本圈)?(?:共|总计)\s*([0-9]+)\s*针[。.!！]?")
_PLAIN = re.compile(r"([0-9]+)\s*(?:(?:个)?短针|X)(?:（不加不减）)?[。.!！]?")
_UNCHANGED = re.compile(r"不加不减(?:[，,]\s*(?:本圈)?(?:共|总计)\s*([0-9]+)\s*针)?[。.!！]?")
_START = re.compile(r"魔法环起\s*([0-9]+)\s*针(?:（X×([0-9]+)）)?[。.!！]?")
_GENERATED_CHANGE = re.compile(
    r"(.+)，(?:隔[0-9]+针[加减]1针|均匀[加减][0-9]+针)[。.!！]?"
)
_GENERATED_ALL = re.compile(r"([加减])针×([0-9]+)（([VA]×[0-9]+)，(每针都加|每2针并1针)）")
_GENERATED_CLOSURE = re.compile(
    r"断线留[0-9]+(?:\.[0-9]+)?cm，穿末圈每针前半针后拉紧(?:（无痕收口）)?藏线头"
    r"(?:（(?:无痕收口，社区/PlanetJune fastening off 通行技法|勿再减针收成6针，底部会过尖)）)?[。.!！]?"
)
_LOOP_DIRECTIVES = {
    "flo": "FLO", "blo": "BLO",
    "front loop only": "FLO", "front loops only": "FLO",
    "back loop only": "BLO", "back loops only": "BLO",
    "只挑前半针": "FLO", "本圈只挑前半针": "FLO",
    "只挑后半针": "BLO", "本圈只挑后半针": "BLO",
}


def _loop_directive(clause: str) -> str | None:
    return _LOOP_DIRECTIVES.get(clause.strip().rstrip("。.!！").lower())


_INTERVAL = re.compile(r"隔([0-9]+)针([加减])1针")
_EVEN = re.compile(r"均匀([加减])([0-9]+)针")


def _decimal(digits: str) -> str:
    return digits.lstrip("0") or "0"


def _count_label(digits: str) -> str:
    number = _decimal(digits)
    return number if len(number) <= 18 else f"{number[:18]}…（{len(number)}位）"


@dataclass(frozen=True)
class _Spacing:
    leading: int
    trailing: int
    changes: int


def _matches_interval(expression: StitchExpression, digits: str, direction: str) -> bool:
    """Check cyclic plain-stitch gaps in O(tree nodes), without expanding repeats.

    A span remembers only its plain prefix/suffix and shaping count. Joining
    spans checks their boundary; repeating a span checks that boundary once.
    The final boundary joins the round's tail to its start, allowing a split
    gap such as ``(X,V,X)×6`` for an interval of two plain stitches.
    """
    gap = _decimal(digits)
    changes = {"V"} if direction == "加" else {"A", "inv-sc2tog"}

    def summarize(node: StitchExpression) -> _Spacing | None:
        if node.stitch is not None:
            symbol = node.stitch.removesuffix("-FLO").removesuffix("-BLO")
            if symbol == "X":
                return _Spacing(node.repeats, node.repeats, 0)
            if symbol not in changes:
                return None  # Mixed shaping or W/M is not a single +1/-1 step.
            span = _Spacing(0, 0, 1)
        else:
            span = _Spacing(0, 0, 0)
            for child in node.children:
                following = summarize(child)
                if following is None:
                    return None
                if (span.changes and following.changes
                        and str(span.trailing + following.leading) != gap):
                    return None
                span = _Spacing(
                    span.leading if span.changes else span.leading + following.leading,
                    following.trailing if following.changes else span.trailing + following.trailing,
                    span.changes + following.changes,
                )
        if not span.changes:
            return _Spacing(span.leading * node.repeats, span.trailing * node.repeats, 0)
        if node.repeats > 1 and str(span.trailing + span.leading) != gap:
            return None
        return _Spacing(span.leading, span.trailing, span.changes * node.repeats)

    result = summarize(expression)
    return (result is not None and result.changes > 0
            and str(result.trailing + result.leading) == gap)


def _interval_issues(clause: str, expression: StitchExpression) -> list[str]:
    """F-14：核对“隔N针加/减1针”「均匀加/减N针」文字里的数字与操作式一致。

    生成器口径（见 crochet_params._inc_note_by_before/_dec_note）：
    ``(aX,V)×6`` ↔ 隔 a 针加 1 针，``(aX,A)×6`` ↔ 隔 a 针减 1 针。
    间隔按实际短针序列核对，包含圈首尾衔接，不能仅用平均针数推断。
    「均匀加/减 N 针」只核对 N = 加/减针数，不证明物理分布均匀。"""
    out: list[str] = []
    counts = expression.counts
    interval = _INTERVAL.search(clause)
    if interval is not None:
        digits, direction = interval.groups()
        actual = counts.increase if direction == "加" else counts.decrease
        label = f"隔{_count_label(digits)}针{direction}1针"
        if actual == 0:
            out.append(f"文字“{label}”与操作式不符（操作式没有{direction}针）")
        elif not _matches_interval(expression, digits, direction):
            out.append(f"文字“{label}”与操作式的逐针顺序不符"
                       f"（含圈首尾衔接，每次{direction}1针之间须有指定数量的短针）")
    even = _EVEN.search(clause)
    if even is not None:
        direction, digits = even.groups()
        actual = counts.increase if direction == "加" else counts.decrease
        if _decimal(digits) != str(actual):
            out.append(f"文字“均匀{direction}{_count_label(digits)}针”与操作式的{direction} {actual} 针不符")
    every = _GENERATED_ALL.fullmatch(clause)
    if every is not None:
        direction, digits, formula, rule = every.groups()
        actual = counts.increase if direction == "加" else counts.decrease
        operation = "加" if formula.startswith("V") else "减"
        if direction != operation or _decimal(digits) != str(actual):
            operation_count = counts.increase if operation == "加" else counts.decrease
            out.append(f"文字“{direction}针×{_count_label(digits)}”"
                       f"与操作式的{operation} {operation_count} 针不符")
        expected_rule = "每针都加" if operation == "加" else "每2针并1针"
        if rule != expected_rule:
            out.append(f"文字“{rule}”与操作式的{operation}针不符（应为“{expected_rule}”）")
    return out


def _clause_expression(clause: str) -> StitchExpression | None:
    generated = _GENERATED_CHANGE.fullmatch(clause)
    every = _GENERATED_ALL.fullmatch(clause)
    plain = _PLAIN.fullmatch(clause)
    if generated:
        text = generated[1]
    elif every:
        text = every[3]
    elif plain:
        text = f"{plain[1]}X"
    else:
        text = clause
    return parse_stitch_expression(text)


def round_expression(text: object) -> StitchExpression | None:
    """Return the single explicit whole-round formula in semicolon clauses.

    Multiple formulas cannot select a unique stitch order even if counts agree.
    Keep that ambiguity visible to exports instead of picking the first one.
    """
    if not isinstance(text, str):
        return None
    expressions: list[StitchExpression] = []
    loops: set[str] = set()
    unsupported = False
    for clause in re.split(r"[；;\n]", text):
        clause = clause.strip()
        if _GENERATED_CLOSURE.fullmatch(clause):
            continue  # Threading the cut tail is finishing, not a crochet-loop modifier.
        loop = _loop_directive(clause)
        if loop:
            loops.add(loop)
            continue
        expression = _clause_expression(clause)
        if expression is not None:
            expressions.append(expression)
        elif mentions_loop_technique(clause):
            unsupported = True
    if len(loops) > 1:
        raise NotationError("针法说明同时指定整圈 FLO 和 BLO，请明确挑针范围")
    if len(expressions) > 1:
        raise NotationError("针法说明含多个独立操作式，请合并为一个完整的本圈操作式")
    expression = expressions[0] if expressions else None
    if (expression is not None and mentions_invisible_decrease(text)
            and (loops or expression.has_loop_technique)):
        raise UnsupportedLoopError("隐形减针与 FLO/BLO 的组合需人工核对，请明确具体针法")
    if expression is not None and loops:
        expression = expression.with_loop(next(iter(loops)))
    if unsupported or (loops and expression is None):
        raise UnsupportedLoopError("挑针说明缺少明确的操作式或范围，请使用 BLO(12X)、sc-FLO 等写法")
    return expression


def instruction_issues(
    text: object, stitches: int, increase: int, decrease: int,
    *, previous_stitches: int | None = None,
) -> list[str]:
    """Only full standalone clauses carry checked claims.

    Ignore conditional instructions, references to other rounds and free prose.
    Compare decimal strings to avoid allocating huge ints from imported notes.
    """
    if not isinstance(text, str):
        return []
    issues: list[str] = []
    for clause in re.split(r"[；;\n]", text):
        clause = clause.strip()
        if _loop_directive(clause):
            continue
        total = _TOTAL.fullmatch(clause)
        plain = _PLAIN.fullmatch(clause)
        unchanged = _UNCHANGED.fullmatch(clause)
        start = _START.fullmatch(clause)
        match = total or plain or unchanged or start
        if match is not None:
            if any(_decimal(digits) != str(stitches)
                   for digits in match.groups() if digits is not None):
                issues.append(f"文字说明的总针数与数值 {stitches} 不一致")
            if (plain or unchanged) and (increase or decrease):
                issues.append("说明为不加不减，但数值含加减针")
        else:
            try:
                expression = _clause_expression(clause)
            except UnsupportedLoopError:
                continue
            except NotationError as exc:
                issues.append(str(exc))
                continue
            if expression is None:
                continue
            counts = expression.counts
            if previous_stitches is not None and counts.consumed != previous_stitches:
                issues.append(f"针法说明消耗 {counts.consumed} 个针目，与上圈 {previous_stitches} 针不一致")
            if counts.produced != stitches:
                issues.append(f"针法说明产出 {counts.produced} 针，与本圈数值 {stitches} 不一致")
            if counts.increase != increase or counts.decrease != decrease:
                issues.append(
                    f"针法说明加 {counts.increase} 针、减 {counts.decrease} 针，"
                    f"与数值加 {increase} 针、减 {decrease} 针不一致"
                )
            issues.extend(_interval_issues(clause, expression))
    if mentions_loop_technique(text):
        try:
            round_expression(text)
        except UnsupportedLoopError:
            pass  # Free prose remains usable manually, but cannot be exported as ordinary sc.
        except NotationError as exc:
            issues.append(str(exc))
    return list(dict.fromkeys(issues))
