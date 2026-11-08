"""Count a small, explicit round-notation grammar without expanding repeats.

This is not a natural-language or chart parser. Unknown stitches/prose return
None, so partial expressions never masquerade as an entire round. Fully
recognized notation with bad syntax or excessive counts raises NotationError.

T, F, E, B, SL, NX and S-SC count as one stitch in and one stitch out.
FV is a taller increase (1→2) and FA a taller together (2→1). K is a skip:
it consumes one stitch, produces none, and its decrease count stays 0.
These symbols stay themselves. Equal arithmetic does not make them short
crochet. Chains, chain spaces, worded skips, worded bobbles and other prose
stay unrecognized.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, replace

from app.schemas import MAX_ROUND_STITCHES

_TOKEN = re.compile(
    # Longer tokens before single letters, so BLO/FV/FA/NX are not split.
    r"[0-9]+|(?:inv-sc2tog|sc-inc|sc2tog|inc|dec|sc|sl)(?:-(?:FLO|BLO))?"
    r"|FLO|BLO|(?:S-SC|FV|FA|NX)(?:-(?:FLO|BLO))?"
    r"|(?:[XTFEVAWMBK])(?:-(?:FLO|BLO))?|[(),+×*]",
    re.I,
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


def mentions_invisible_decrease(text: object) -> bool:
    return isinstance(text, str) and bool(re.search(
        r"(?<![A-Za-z])(?:inv-sc2tog|invdec|invisible[ -]+decreases?)(?![A-Za-z])|隐形减针",
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
    "T": StitchCounts(1, 1), "F": StitchCounts(1, 1), "E": StitchCounts(1, 1),
    "B": StitchCounts(1, 1), "SL": StitchCounts(1, 1),
    "NX": StitchCounts(1, 1), "S-SC": StitchCounts(1, 1),
    "FV": StitchCounts(1, 2, 1), "FA": StitchCounts(2, 1, 0, 1),
    # A skip drops a stitch without being a together. Decrease stays 0.
    "K": StitchCounts(1, 0),
}
# Explicit on purpose. Shared arithmetic must not collapse a symbol onto X, V or A.
_CANONICAL = {
    "X": "X", "SC": "X",
    "V": "V", "INC": "V", "SC-INC": "V",
    "A": "A", "DEC": "A", "SC2TOG": "A",
    "INV-SC2TOG": "inv-sc2tog",
    "W": "W", "M": "M",
    "T": "T", "F": "F", "E": "E", "B": "B", "SL": "SL",
    "NX": "NX", "S-SC": "S-SC", "FV": "FV", "FA": "FA", "K": "K",
}
_SHORT_STITCHES = frozenset({"X", "V", "A", "W", "M", "inv-sc2tog"})


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
        return (self.stitch is not None and self.stitch.endswith(("-FLO", "-BLO"))
                or any(child.has_loop_technique for child in self.children))

    @property
    def has_invisible_decrease(self) -> bool:
        return (self.stitch == "inv-sc2tog"
                or any(child.has_invisible_decrease for child in self.children))

    def with_loop(self, loop: str) -> StitchExpression:
        """Apply a scoped loop qualifier without expanding repeats or losing counts."""
        if self.stitch is not None:
            if self.has_invisible_decrease:
                raise UnsupportedLoopError("隐形减针与 FLO/BLO 的组合需人工核对，请明确具体针法")
            # Only a trailing loop suffix counts. S-SC contains a hyphen of its own.
            existing = ""
            symbol = self.stitch
            for name in ("FLO", "BLO"):
                if symbol.endswith("-" + name):
                    existing = name
                    symbol = symbol[: -(len(name) + 1)]
                    break
            if existing and existing != loop:
                raise NotationError("针法说明在同一针位同时指定 FLO 和 BLO，请明确挑针范围")
            return replace(self, stitch=f"{symbol}-{loop}")
        return replace(self, children=tuple(child.with_loop(loop) for child in self.children))


def non_sc_symbols(expression: StitchExpression) -> tuple[str, ...]:
    """Stitches that must not be stored or drawn as short crochet.

    Walks the compact tree. Repeats are not expanded. Includes 1→1 letters,
    taller increases and togethers, and skips.
    """
    found: list[str] = []

    def walk(node: StitchExpression) -> None:
        if node.stitch is not None:
            symbol = node.stitch.removesuffix("-FLO").removesuffix("-BLO")
            if symbol not in _SHORT_STITCHES and symbol not in found:
                found.append(symbol)
            return
        for child in node.children:
            walk(child)

    walk(expression)
    return tuple(found)


def format_stitch_expression(expression: StitchExpression) -> str:
    """Retain order, scoped loops, invisible decreases and compact repeats."""
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

    def _prefixed_repeat(self) -> bool:
        """N*stitch or N×stitch. A letter x after a number is still the stitch X."""
        nxt = self.index + 1
        return (nxt < len(self.tokens) and self.tokens[self.index].isdigit()
                and self.tokens[nxt] in ("×", "*"))

    def term(self, depth: int) -> StitchExpression:
        if depth > _MAX_DEPTH:
            raise NotationError("针法说明的重复组嵌套过深")
        if self._prefixed_repeat():
            count = self.number()
            self.index += 1
            return self.term(depth + 1).repeat(count)
        prefixed = self.peek().isdigit()
        count = self.number() if prefixed else 1
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
        elif not prefixed and self.peek().isdigit() and value.stitch == "K":
            # K2 is two skips. Other stitches keep a prefix count (12FV, 8SL).
            # M1 stays unfinished: a leading M plus a number is a section label.
            value = value.repeat(self.number())
        return value


def parse_stitch_expression(text: str) -> StitchExpression | None:
    """Parse X/V/A/W/M, taller letters, US aliases, loops and repeats.

    Examples: ``(2X,V)×6``, ``BLO((X,V,X)×5)``, ``2sc-FLO``, ``12F``, ``8SL``,
    ``12FV``, ``K2``, ``4*FV``. FV, FA, K, NX and S-SC stay themselves.
    Chains, chain spaces, worded skips and prose return None, including a
    recognized prefix followed by an unknown suffix.
    No eval(), expanded stitch list, or unbounded ints.
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
    if mentions_loop_technique(text) and mentions_invisible_decrease(text):
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
