"""Count a small, explicit round-notation grammar without expanding repeats.

This is not a natural-language or chart parser. Unknown stitches/prose return
None, so partial expressions never masquerade as an entire round. Fully
recognized notation with bad syntax or excessive counts raises NotationError.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, replace

from app.schemas import MAX_ROUND_STITCHES

_TOKEN = re.compile(
    r"[0-9]+|(?:inv-sc2tog|sc-inc|sc2tog|inc|dec|sc|[XVAWM])(?:-(?:FLO|BLO))?"
    r"|FLO|BLO|[(),+×*]", re.I,
)
_PUNCTUATION = str.maketrans({"（": "(", "）": ")", "[": "(", "]": ")",
                             "，": ",", "、": ",", "＊": "*"})
_ENGLISH_REPEAT = re.compile(
    r"\*(.+)\*\s*(?:crochet|repeat)\s+(?:([0-9]+)\s+times|(twice))", re.I,
)
_MAX_TOKENS = 1024
_MAX_DEPTH = 12


class NotationError(ValueError):
    """Recognized stitch notation cannot be counted safely or unambiguously."""


class UnsupportedLoopError(NotationError):
    """Loop prose lacks an executable scope; it may still be a valid manual note."""


def mentions_loop_technique(text: object) -> bool:
    return isinstance(text, str) and bool(re.search(
        r"(?<![A-Za-z])(?:FLO|BLO)(?![A-Za-z])|\b(?:front|back)\s+loops?\b|[前后]半针",
        text, re.I,
    ))


@dataclass(frozen=True)
class StitchCounts:
    consumed: int = 0
    produced: int = 0
    increase: int = 0
    decrease: int = 0

    def add(self, other: StitchCounts) -> StitchCounts:
        return _bounded(self.consumed + other.consumed, self.produced + other.produced,
                        self.increase + other.increase, self.decrease + other.decrease)

    def repeat(self, count: int) -> StitchCounts:
        return _bounded(self.consumed * count, self.produced * count,
                        self.increase * count, self.decrease * count)


def _bounded(consumed: int, produced: int, increase: int, decrease: int) -> StitchCounts:
    if max(consumed, produced, increase, decrease) > MAX_ROUND_STITCHES:
        raise NotationError(f"针法说明的针数或重复次数超过上限 {MAX_ROUND_STITCHES}")
    return StitchCounts(consumed, produced, increase, decrease)


_COUNTS = {
    "X": StitchCounts(1, 1), "SC": StitchCounts(1, 1),
    "V": StitchCounts(1, 2, 1), "INC": StitchCounts(1, 2, 1), "SC-INC": StitchCounts(1, 2, 1),
    "A": StitchCounts(2, 1, 0, 1), "DEC": StitchCounts(2, 1, 0, 1),
    "SC2TOG": StitchCounts(2, 1, 0, 1), "INV-SC2TOG": StitchCounts(2, 1, 0, 1),
    "W": StitchCounts(1, 3, 2), "M": StitchCounts(3, 1, 0, 2),
}
_CANONICAL = {alias: symbol for alias, counts in _COUNTS.items()
              for symbol in "XVAWM" if counts == _COUNTS[symbol]}


@dataclass(frozen=True)
class StitchExpression:
    """A bounded, ordered stitch tree; repeats remain compact until iterated."""

    counts: StitchCounts
    stitch: str | None = None
    children: tuple[StitchExpression, ...] = ()
    repeats: int = 1

    def repeat(self, count: int) -> StitchExpression:
        return replace(self, counts=self.counts.repeat(count), repeats=self.repeats * count)

    def iter_stitches(self) -> Iterator[str]:
        for _ in range(self.repeats):
            if self.stitch is not None:
                yield self.stitch
            else:
                for child in self.children:
                    yield from child.iter_stitches()

    @property
    def has_loop_technique(self) -> bool:
        return (self.stitch is not None and "-" in self.stitch
                or any(child.has_loop_technique for child in self.children))

    def with_loop(self, loop: str) -> StitchExpression:
        """Apply a scoped loop qualifier without expanding repeats or losing counts."""
        if self.stitch is not None:
            symbol, _, existing = self.stitch.partition("-")
            if existing and existing != loop:
                raise NotationError("针法说明在同一针位同时指定 FLO 和 BLO，请明确挑针范围")
            return replace(self, stitch=f"{symbol}-{loop}")
        return replace(self, children=tuple(child.with_loop(loop) for child in self.children))


def format_stitch_expression(expression: StitchExpression) -> str:
    """Canonical X/V/A/W/M notation, retaining order, loop qualifiers and repeats."""
    if expression.stitch is not None:
        if expression.repeats == 1:
            return expression.stitch
        if expression.stitch.split("-")[0] == "X":
            return f"{expression.repeats}{expression.stitch}"
        return f"({expression.stitch})×{expression.repeats}"
    body = ",".join(format_stitch_expression(child) for child in expression.children)
    return f"({body})×{expression.repeats}" if expression.repeats != 1 else body


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> str:
        return self.tokens[self.index] if self.index < len(self.tokens) else ""

    def number(self) -> int:
        raw = self.peek()
        if not raw.isascii() or not raw.isdigit():
            raise NotationError("针法说明的重复次数必须为正整数")
        self.index += 1
        digits = raw.lstrip("0") or "0"
        if len(digits) > len(str(MAX_ROUND_STITCHES)):
            raise NotationError(f"针法说明的重复次数超过上限 {MAX_ROUND_STITCHES}")
        count = int(digits)
        if not 1 <= count <= MAX_ROUND_STITCHES:
            raise NotationError(f"针法说明的重复次数必须为 1–{MAX_ROUND_STITCHES}")
        return count

    def sequence(self, depth: int = 0) -> StitchExpression:
        if depth > _MAX_DEPTH:
            raise NotationError("针法说明的重复组嵌套过深")
        children = [self.term(depth)]
        total = children[0].counts
        while self.peek() in (",", "+"):
            self.index += 1
            child = self.term(depth)
            total = total.add(child.counts)
            children.append(child)
        return children[0] if len(children) == 1 else StitchExpression(total, children=tuple(children))

    def term(self, depth: int) -> StitchExpression:
        count = self.number() if self.peek().isdigit() else 1
        token = self.peek()
        self.index += 1
        loop = token.upper() if token.upper() in ("FLO", "BLO") else ""
        if loop:
            if self.peek() != "(":
                raise NotationError("针法说明的 FLO/BLO 后须用括号明确作用范围")
            self.index += 1
        if token == "(" or loop:
            value = self.sequence(depth + 1)
            if self.peek() != ")":
                raise NotationError("针法说明的重复组缺少右括号")
            self.index += 1
            if loop:
                value = value.with_loop(loop)
        else:
            qualified = token.upper().endswith(("-FLO", "-BLO"))
            base = token[:-4].upper() if qualified else token.upper()
            if base not in _COUNTS:
                raise NotationError("针法说明缺少针法或重复组")
            value = StitchExpression(_COUNTS[base], stitch=_CANONICAL[base])
            if qualified:
                value = value.with_loop(token[-3:].upper())
        value = value.repeat(count)
        if self.peek() in ("×", "*", "x"):
            self.index += 1
            value = value.repeat(self.number())
        return value


def parse_stitch_expression(text: str) -> StitchExpression | None:
    """Parse X/V/A/W/M, US sc/inc/dec aliases, scoped loops and repeat groups.

    Examples: ``(2X,V)×6``, ``BLO((X,V,X)×5)``, ``2sc-FLO,2X``.
    Unknown prose/techniques return None, including a recognized prefix followed
    by an unknown suffix. No eval(), expanded stitch list, or unbounded ints.
    """
    text = text.strip().rstrip("。.!！").translate(_PUNCTUATION)
    scoped = re.fullmatch(r"(FLO|BLO)\s*[:：]\s*(.+)", text, re.I)
    if scoped:
        text = f"{scoped[1]}({scoped[2]})"
    english = _ENGLISH_REPEAT.fullmatch(text)
    if english:
        text = f"({english[1]})×{english[2] or '2'}"
    # Scan all input before interpreting it: unsupported suffixes must not make
    # a partial (potentially contradictory) expression look like a whole round.
    tokens: list[str] = []
    pos = 0
    too_many = False
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        match = _TOKEN.match(text, pos)
        if match is None:
            return None
        if len(tokens) < _MAX_TOKENS:
            tokens.append(match[0])
        else:
            too_many = True
        pos = match.end()
    if not tokens:
        return None
    if too_many:
        raise NotationError("针法说明过长，请简化重复组")
    if mentions_loop_technique(text) and re.search(r"inv-sc2tog", text, re.I):
        raise UnsupportedLoopError("隐形减针与 FLO/BLO 的组合需人工核对，请明确具体针法")
    parser = _Parser(tokens)
    result = parser.sequence()
    if parser.index != len(tokens):
        raise NotationError("针法说明的括号、分隔符或重复次数不完整")
    return result


def parse_stitch_notation(text: str) -> StitchCounts | None:
    """Compatibility counting API, sharing the ordered parser used by exports."""
    expression = parse_stitch_expression(text)
    return expression.counts if expression is not None else None
