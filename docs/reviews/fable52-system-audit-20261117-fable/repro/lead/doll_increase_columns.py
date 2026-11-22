"""Where do the dressed-doll recipes put their increases?

Independent expansion of the written operation strings (X, V, A, W, repeats):
each produced stitch is traced back to the foundation stitch it descends from.
If every increase of a flared piece lands in the same column, the stitch counts
still match the table but the piece widens at one point only.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

import app
from app.models.dressed_doll import build_doll_plan, starter_design

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def expand(expression: str) -> list[str]:
    """Flatten e.g. '(2X,V)×6,3X' into a list of single operations."""
    text = expression.replace(" ", "")
    out: list[str] = []
    position = 0
    while position < len(text):
        if text[position] == ",":
            position += 1
            continue
        if text[position] == "(":
            end = text.index(")", position)
            inner = expand(text[position + 1:end])
            position = end + 1
            match = re.match(r"×(\d+)", text[position:])
            repeats = int(match.group(1)) if match else 1
            position += len(match.group(0)) if match else 0
            out.extend(inner * repeats)
            continue
        match = re.match(r"(\d+)X|([VAW])(?:×(\d+))?", text[position:])
        if not match:
            raise ValueError(f"cannot read {expression!r} at {position}")
        if match.group(1):
            out.extend(["X"] * int(match.group(1)))
        else:
            out.extend([match.group(2)] * int(match.group(3) or 1))
        position += len(match.group(0))
    return out


def trace(component):
    """Return (per-round counts, ancestry of the last round as foundation indices)."""
    steps = component.steps
    first = expand(steps[0].expression)
    current: list[int] = []          # for each live stitch: index of its foundation stitch
    foundation = 0
    for op in first:
        made = {"X": 1, "V": 2, "W": 3}[op]
        current.extend([foundation] * made)
        foundation += 1
    counts = [len(current)]
    for step in steps[1:]:
        ops, following, cursor = expand(step.expression), [], 0
        for op in ops:
            if op == "A":
                following.append(current[cursor])   # keep the first parent's column
                cursor += 2
            else:
                following.extend([current[cursor]] * {"X": 1, "V": 2, "W": 3}[op])
                cursor += 1
        assert cursor == len(current), (component.id, step.number, cursor, len(current))
        assert len(following) == step.stitches, (component.id, step.number)
        current = following
        counts.append(len(current))
    return counts, current, foundation


for name in ("wide_brim_curls", "folded_cap_layers"):
    plan = build_doll_plan(starter_design(name))
    print(f"== {name}")
    for component in plan.components:
        if component.work != "rounds":
            continue
        counts, ancestry, foundation = trace(component)
        if counts[-1] <= counts[0] or component.foundation.kind != "chain_ring":
            continue
        share = collections.Counter(ancestry)
        widest = share.most_common(3)
        widened = sum(1 for value in share.values() if value > 1)
        print(f"  {component.name}: {counts[0]} -> {counts[-1]} stitches over {len(counts)} rounds; "
              f"{counts[-1] - counts[0]} increases")
        print(f"     foundation stitches that received any increase: {widened} of {foundation}")
        print(f"     hem stitches descending from the 3 most-increased foundation stitches: "
              f"{[(index + 1, n) for index, n in widest]}")
        tail = [f"{s.number}:{s.expression}" for s in component.steps[1:6]]
        print(f"     first rounds as written: {tail}")
    sys.stdout.flush()
