"""Round 3 (2026-11-19): acceptance of the working-tree fix against commit 6c88b7d.

Inputs: two JSON-lines dumps from r3_dump_plans.py (old = a worktree of 6c88b7d,
new = this checkout) over the same 160 inputs (body rows 2-41 x sleeve rows
17/18 x both cuff modes).
1. Stage and site inventory per input, old vs new: zero contradictions must not come from
   dropping inputs or stitches.
2. New plans: independent side-rule findings (r2_side_rule_sweep.side_rule_findings).
3. Old plans compiled by the fixed checker: every complete one must be rejected.

Usage: python r3_fixed_tree_acceptance.py <old.jsonl> <new.jsonl>
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import app  # noqa: E402
import r2_side_rule_sweep as probe  # noqa: E402
from app.models.working_path import WorkingPath, compile_working_path  # noqa: E402

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__

with open(sys.argv[1]) as handle:
    old = [json.loads(line) for line in handle]
with open(sys.argv[2]) as handle:
    new = [json.loads(line) for line in handle]


def key(row):
    return row["body"], row["sleeve"], row["cuff"]


assert [key(r) for r in old] == [key(r) for r in new]
print(f"inputs: {len(new)}; stage differs old vs new: "
      f"{sum(a['stage'] != b['stage'] for a, b in zip(old, new, strict=True))}")

same_inventory = sum(a["inventory"] == b["inventory"] for a, b in zip(old, new, strict=True))
print(f"site inventory (sites created, consumed, size of every final edge, step count, stitch counts "
      f"by kind), each plan compiled by its own tree's checker: identical for {same_inventory} of {len(new)}")
for a, b in zip(old, new, strict=True):
    if a["inventory"] != b["inventory"]:
        print("   differs:", key(a), a["inventory"], b["inventory"])
        break

table: collections.Counter = collections.Counter()
for row in new:
    parity = "body odd " if row["body"] % 2 else "body even"
    if not row["stage"].startswith("integrated"):
        table[(parity, "not generated: " + row["stage"])] += 1
        continue
    found = probe.side_rule_findings(WorkingPath.model_validate(row["plan"]))
    table[(parity, "; ".join(found) or "no contradiction")] += 1
print("== fixed generator, independent side rule")
for (parity, what), count in sorted(table.items()):
    print(f"   {parity}: {count:3d} -> {what}")

table = collections.Counter()
for row in old:
    if not row["stage"].startswith("integrated"):
        continue
    parity = "body odd " if row["body"] % 2 else "body even"
    try:
        compile_working_path(WorkingPath.model_validate(row["plan"]))
        table[(parity, "ACCEPTED by the fixed checker")] += 1
    except ValueError as error:
        table[(parity, "rejected: " + re.sub(r"design_\w+", "<step>", str(error))[:80])] += 1
print("== complete plans from the 6c88b7d generator, compiled by the fixed checker")
for (parity, what), count in sorted(table.items()):
    print(f"   {parity}: {count:3d} -> {what}")
