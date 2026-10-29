"""Conservative checks for explicit current-round claims, not a prose parser."""
from __future__ import annotations

import re

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
_GENERATED_ALL = re.compile(r"[加减]针×[0-9]+（([VA]×[0-9]+)，(?:每针都加|每2针并1针)）")
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


def _interval_issues(clause: str, counts) -> list[str]:
    """F-14：核对“隔N针加/减1针”「均匀加/减N针」文字里的数字与操作式一致。

    生成器口径（见 crochet_params._inc_note_by_before/_dec_note）：
    ``(aX,V)×6`` ↔ 隔 a 针加 1 针，a = consumed/increase − 1；
    ``(aX,A)×6`` ↔ 隔 a 针减 1 针，a = consumed/decrease − 2；
    「均匀加/减 N 针」的 N = 加/减针数。此前只核对逗号前的操作式，文字里的
    这些数字不参与校验（``(2X,V)×6，隔5针加1针`` 这种自相矛盾可通过）。"""
    out: list[str] = []
    interval = _INTERVAL.search(clause)
    if interval is not None:
        n = int(interval.group(1))
        if interval.group(2) == "加" and counts.increase and counts.consumed % counts.increase == 0:
            expected = counts.consumed // counts.increase - 1
            if expected != n:
                out.append(f"文字“隔{n}针加1针”与操作式不符（应为隔{expected}针）")
        elif interval.group(2) == "减" and counts.decrease and counts.consumed % counts.decrease == 0:
            expected = counts.consumed // counts.decrease - 2
            if expected != n:
                out.append(f"文字“隔{n}针减1针”与操作式不符（应为隔{expected}针）")
    even = _EVEN.search(clause)
    if even is not None:
        n = int(even.group(2))
        actual = counts.increase if even.group(1) == "加" else counts.decrease
        if actual and actual != n:
            out.append(f"文字“均匀{even.group(1)}{n}针”与操作式的{even.group(1)} {actual} 针不符")
    return out


def _clause_expression(clause: str) -> StitchExpression | None:
    generated = _GENERATED_CHANGE.fullmatch(clause) or _GENERATED_ALL.fullmatch(clause)
    plain = _PLAIN.fullmatch(clause)
    text = generated[1] if generated else f"{plain[1]}X" if plain else clause
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
            if any((digits.lstrip("0") or "0") != str(stitches)
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
            issues.extend(_interval_issues(clause, counts))
    if mentions_loop_technique(text):
        try:
            round_expression(text)
        except UnsupportedLoopError:
            pass  # Free prose remains usable manually, but cannot be exported as ordinary sc.
        except NotationError as exc:
            issues.append(str(exc))
    return list(dict.fromkeys(issues))
