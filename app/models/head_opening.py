"""Explicit neck openings for newly generated, separate head constructions."""
from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Final

from app.schemas import MAX_ROUND_STITCHES
from app.utils.counts import integer_count

HEAD_OPENING_KEY: Final = "head_opening_stitches"
_EXPLICIT_CLOSURE = re.compile(r"(?:拉紧收口|无痕收口|完全收口|收口)(?:[，,]\s*藏线头?)?[。.!！]?")


def _has_explicit_closure(notes: object) -> bool:
    """Recognize standalone closing instructions, not incidental prose."""
    from .instruction_checks import _GENERATED_CLOSURE

    clauses = (clause.strip() for clause in re.split(r"[；;。\n]", str(notes or "")))
    return any(_EXPLICIT_CLOSURE.fullmatch(clause) or _GENERATED_CLOSURE.fullmatch(clause)
               for clause in clauses)


def has_declared_head_opening(part: Mapping[str, Any]) -> bool:
    """Recognize a terminal opening in authored legacy work without a mode flag."""
    from .assembly import _CLOSING_RE

    rows = part.get("rounds") or []
    if not rows:
        return False
    if part.get("connection_state") == "open":
        from .parts import same_round

        return same_round(part.get("opening_row"), rows[-1].get("row"))
    if part.get("connection_state") == "closed":
        return False
    note = str(rows[-1].get("notes") or "")
    return (not _CLOSING_RE.search(note)
            and (part.get("opening_row") == rows[-1].get("row")
                 or any(word in note for word in ("不收口", "勿收口", "未收口", "没收口"))))


def head_opening_target(value: Any) -> int:
    target = integer_count(value)
    if not 6 <= target <= MAX_ROUND_STITCHES:
        raise ValueError("头部留口针数必须在 6–100000 之间")
    return target


def _decrease_note(before: int, after: int) -> str:
    decreases = before - after
    plain, extra = divmod(before - 2 * decreases, decreases)
    if plain < 0:
        raise ValueError("留口过渡的减针数超过可用针目")

    def group(stitches: int, repeats: int) -> str:
        prefix = ("X," if stitches == 1 else f"{stitches}X,") if stitches else ""
        operations = prefix + "A"
        return f"({operations})×{repeats}" if repeats > 1 else operations

    groups = []
    if decreases - extra:
        groups.append(group(plain, decreases - extra))
    if extra:
        groups.append(group(plain + 1, extra))
    return ",".join(groups)


def leave_head_open(rounds: list[dict], target: int, max_change: int) -> list[dict]:
    """Keep the crown/plateau; finish the descending side at the exact target.

    Input is a freshly generated head, never an authored stitch table. Optional
    final transitions use X/A counts without rounding the requested neck to six.
    """
    target = head_opening_target(target)
    if max_change < 1:
        raise ValueError("留口过渡的每圈变化上限必须为正数")
    rows = deepcopy(rounds)
    maximum = max(row["stitches"] for row in rows)
    if target > maximum:
        raise ValueError(f"头部留口 {target} 针大于当前头围最大 {maximum} 针，请先调小留口针数")
    # Remove only the known fresh generator's finishing action.
    rows[-1]["notes"] = (rows[-1].get("notes") or "").split("；", 1)[0]
    peak = max(i for i, row in enumerate(rows) if row["stitches"] == maximum)
    cut = next((i for i in range(peak + 1, len(rows)) if rows[i]["stitches"] < target), len(rows))
    rows = rows[:cut]
    while rows[-1]["stitches"] > target:
        before = rows[-1]["stitches"]
        change = min(before - target, max_change, before // 2)
        after = before - change
        rows.append({"row":rows[-1]["row"] + 1, "stitches":after,
                     "decrease":change, "notes":_decrease_note(before, after)})
    rows[-1]["notes"] += f"；保留 {target} 针颈部开口，不收口；断线留15cm用于缝合"
    return rows


def head_opening_issues(params: Mapping[str, Any]) -> list[str]:
    """Reject contradictory saved generation intent at every pattern boundary."""
    raw = params.get(HEAD_OPENING_KEY)
    if raw is None:
        return []
    from .assembly import _CLOSING_RE
    from .parts import same_round

    try:
        target = head_opening_target(raw)
        heads = [p for p in params.get("parts", []) if p.get("name") == "头部"]
        if len(heads) != 1 or any(p.get("type") == "onepiece" for p in params.get("parts", [])):
            raise ValueError("头部留口仅适用于独立头部，不能与头身一体同时使用")
        head = heads[0]
        rows = head["rounds"]
        if (not same_round(head.get("opening_row"), rows[-1].get("row"))
                or integer_count(rows[-1]["stitches"]) != target):
            raise ValueError("头部留口必须引用实际末圈，且末圈针数等于保存的留口目标")
        note = rows[-1].get("notes") or ""
        closed = (_has_explicit_closure(note) if head.get("connection_state") == "open"
                  else bool(_CLOSING_RE.search(note)))
        if closed:
            raise ValueError("头部留口末圈不能同时要求收口")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        return [f"头部留口：{exc}"]
    return []
