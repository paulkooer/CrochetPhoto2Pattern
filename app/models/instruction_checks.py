"""Conservative checks for explicit current-round claims, not a prose parser."""
from __future__ import annotations

import re

_TOTAL = re.compile(r"(?:本圈)?(?:共|总计)\s*([0-9]+)\s*针[。.!！]?")
_PLAIN = re.compile(r"([0-9]+)\s*(?:(?:个)?短针|X)(?:（不加不减）)?[。.!！]?")
_UNCHANGED = re.compile(r"不加不减(?:[，,]\s*(?:本圈)?(?:共|总计)\s*([0-9]+)\s*针)?[。.!！]?")
_START = re.compile(r"魔法环起\s*([0-9]+)\s*针(?:（X×([0-9]+)）)?[。.!！]?")


def instruction_issues(text: object, stitches: int, increase: int, decrease: int) -> list[str]:
    """Only full standalone clauses carry checked claims.

    Ignore conditional instructions, references to other rounds and free prose.
    Compare decimal strings to avoid allocating huge ints from imported notes.
    """
    if not isinstance(text, str):
        return []
    issues: list[str] = []
    for clause in re.split(r"[；;\n]", text):
        clause = clause.strip()
        total = _TOTAL.fullmatch(clause)
        plain = _PLAIN.fullmatch(clause)
        unchanged = _UNCHANGED.fullmatch(clause)
        start = _START.fullmatch(clause)
        match = total or plain or unchanged or start
        if match is None:
            continue
        if any((digits.lstrip("0") or "0") != str(stitches)
               for digits in match.groups() if digits is not None):
            issues.append(f"文字说明的总针数与数值 {stitches} 不一致")
        if (plain or unchanged) and (increase or decrease):
            issues.append("说明为不加不减，但数值含加减针")
    return list(dict.fromkeys(issues))
