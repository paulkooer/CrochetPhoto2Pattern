"""r02: expand every written instruction of plan.md independently (no app imports) and
cross-check plan.md <-> plan.json <-> assembly.dot for both packaged starters.

Usage: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -I <this> [plan_dir ...]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdreader import ancestors_at, expand, read_plan  # noqa: E402

PACKAGED = Path("<repo>/eval_outputs/"
                "fable52-system-audit-20261117/examples/generated")
dirs = [Path(a) for a in sys.argv[1:]] or [PACKAGED / "doll-wide-brim", PACKAGED / "doll-folded-cap"]

total_problems = 0
for root in dirs:
    print("=" * 100)
    print(root)
    md = (root / "plan.md").read_text(encoding="utf-8")
    plan = read_plan(md)
    data = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    dot = (root / "assembly.dot").read_text(encoding="utf-8")

    # ---- 1. stitch-by-stitch expansion of the written text
    print("\n[1] independent expansion of the written steps")
    for part in plan.parts:
        steps = sum(len(r.numbers) for r in part.rows)
        status = "OK" if not part.problems else "PROBLEM"
        c = part.counts
        shown = (",".join(map(str, c)) if len(c) <= 40
                 else ",".join(map(str, c[:20])) + ",…," + ",".join(map(str, c[-6:])))
        print(f"  {status:7s} {part.name} ×{part.quantity}: {part.kind} chains={part.chains} "
              f"{steps} {part.unit}; counts={shown}")
        for p in part.problems:
            total_problems += 1
            print(f"      !! {p}")

    # ---- 2. plan.md vs plan.json, step by step
    print("\n[2] plan.md vs plan.json")
    mismatches = []
    comps = data["components"]
    if [p.name for p in plan.parts] != [c["name"] for c in comps]:
        mismatches.append("component order/names differ")
    for part, comp in zip(plan.parts, comps):
        if part.quantity != comp["quantity"]:
            mismatches.append(f"{part.name}: quantity {part.quantity} != {comp['quantity']}")
        if part.kind != comp["foundation"]["kind"] or part.chains != comp["foundation"]["chains"]:
            mismatches.append(f"{part.name}: foundation text {part.kind}/{part.chains} != json {comp['foundation']}")
        if (part.unit == "行") != (comp["work"] == "rows"):
            mismatches.append(f"{part.name}: unit {part.unit} vs work {comp['work']}")
        flat = [(n, r) for r in part.rows for n in r.numbers]
        if len(flat) != len(comp["steps"]):
            mismatches.append(f"{part.name}: {len(flat)} steps in md, {len(comp['steps'])} in json")
            continue
        for (n, row), step in zip(flat, comp["steps"]):
            if (n, row.section, row.expression, row.stated, row.turn, row.loops, row.note) != (
                    step["number"], step["section"], step["expression"], step["stitches"],
                    bool(step["turning_chain"]), step["loops"], step["note"]):
                mismatches.append(f"{part.name} step {n}: md={row.raw_operation!r}/{row.stated}/{row.note!r} "
                                  f"json={step}")
        if part.finish != comp["finish"]:
            mismatches.append(f"{part.name}: finish text differs")
        if part.fitting != comp["fitting"]:
            mismatches.append(f"{part.name}: fitting notes differ")
        if part.role != comp["role"] or part.color != comp["color"]:
            mismatches.append(f"{part.name}: role/colour differ")
    names = {c["id"]: c["name"] for c in comps}
    md_joins = {(p.name, p.join_target, p.join_text) for p in plan.parts if p.join_target}
    js_joins = {(names[j["source"]], names[j["target"]], j["placement"]) for j in data["joins"]}
    if md_joins != js_joins:
        mismatches.append(f"joins differ: md-only={md_joins - js_joins} json-only={js_joins - md_joins}")
    if plan.assembly != data["assembly"]:
        mismatches.append("assembly list differs")
    if plan.limitations != data["limitations"]:
        mismatches.append("limitations differ")
    if plan.checkpoints != data["trial_checkpoints"]:
        mismatches.append("checkpoints differ")
    summary_names = [s[0] for s in plan.summary]
    if summary_names != [c["name"] for c in comps]:
        mismatches.append("summary table rows differ from components")
    for (name, qty, method, target), comp in zip(plan.summary, comps):
        j = next((j for j in data["joins"] if j["source"] == comp["id"]), None)
        want = names[j["target"]] if j else "根部件"
        if (qty, method, target) != (comp["quantity"], "片钩" if comp["work"] == "rows" else "圈钩", want):
            mismatches.append(f"summary row {name}: {(qty, method, target)}")
    print("  mismatches:", len(mismatches))
    for m in mismatches:
        total_problems += 1
        print("   !!", m)

    # ---- 3. assembly.dot vs plan.json joins
    print("\n[3] assembly.dot vs joins")
    dot_nodes = dict(re.findall(r'^(\w+) \[label="(.+)"\];$', dot, re.M))
    dot_edges = re.findall(r"^(\w+) -> (\w+);$", dot, re.M)
    js_edges = [(j["source"], j["target"]) for j in data["joins"]]
    print(f"  dot nodes={len(dot_nodes)} edges={len(dot_edges)}; json components={len(comps)} joins={len(js_edges)}")
    print("  edges identical and in same order:", dot_edges == js_edges)
    print("  node labels identical:", dot_nodes == {c["id"]: f'{c["name"]} × {c["quantity"]}' for c in comps})
    print("  dot mentions prototype/unverified/manual status:",
          any(k in dot for k in ("未实钩", "unverified", "原型", "人工选型", "manual")))
    roots = [c["id"] for c in comps if c["id"] not in {s for s, _ in js_edges}]
    print("  roots:", roots)

    # ---- 4. header totals recomputed from the text
    print("\n[4] header totals recomputed from the expanded text")
    logical = len(plan.parts)
    physical = sum(p.quantity for p in plan.parts)
    ops = 0
    for p in plan.parts:
        per_copy = p.chains + sum(p.counts) + sum(len(r.numbers) for r in p.rows if r.turn)
        ops += p.quantity * per_copy
    m = re.search(r"> (\d+) 份逻辑图解，(\d+) 个实体部件；短针产出与锁针计数合计 (\d+)", md)
    print(f"  header says {m[1]} logical / {m[2]} physical / {m[3]} operations; "
          f"recomputed {logical} / {physical} / {ops}")
    if (int(m[1]), int(m[2]), int(m[3])) != (logical, physical, ops):
        total_problems += 1
        print("   !! header totals differ")

    # ---- 5. where do the shaping stitches go? (structural, from the text only)
    print("\n[5] placement of increases (descendants of each base stitch at the last round)")
    for part in plan.parts:
        if part.problems or len(part.counts) < 3:
            continue
        if part.kind == "chain_ring" and part.counts[-1] != part.counts[0]:
            desc = Counter()
            for anc in ancestors_at(part, len(part.counts), 1):
                for a in anc:
                    desc[a] += 1 / len(anc)
            spread = sorted(desc.items())
            big = [(i + 1, round(v, 2)) for i, v in spread if v > 1.01]
            print(f"  {part.name}: {part.counts[0]} foundation stitches -> {part.counts[-1]} hem stitches; "
                  f"foundation stitches with more than one descendant: {big}")
    for part in plan.parts:
        if "帽檐" in {r.section for r in part.rows} and not part.problems:
            first_brim = next(n for r in part.rows for n in r.numbers if r.section == "帽檐")
            base = first_brim - 1
            desc = Counter()
            for anc in ancestors_at(part, len(part.counts), base):
                for a in anc:
                    desc[a] += 1 / len(anc)
            big = [(i + 1, round(v, 2)) for i, v in sorted(desc.items()) if v > 1.01]
            print(f"  {part.name} brim: {part.counts[base - 1]} crown-edge stitches -> {part.counts[-1]}; "
                  f"edge stitches carrying increases: {big}")

    # ---- 6. shoe: which end does each decrease belong to?
    print("\n[6] shoe arcs traced from the foundation chain")
    for part in plan.parts:
        if part.kind != "oval_chain" or part.problems:
            continue
        k = part.chains - 3
        # round-1 stitches: 0..2 near-end chain, 3..2+k side A, 3+k..5+k far-end chain, rest side B
        zone = {}
        for i in range(part.counts[0]):
            zone[i] = ("toe(near end)" if i < 3 else "sideA" if i < 3 + k else
                       "heel(far end)" if i < 6 + k else "sideB")
        for row in part.rows:
            for n in row.numbers:
                anc = ancestors_at(part, n, 1)
                tally = Counter()
                for a in anc:
                    zs = {zone[x] for x in a}
                    tally["+".join(sorted(zs))] += 1
                ops = expand(row.expression)
                dec = ops.count("A")
                print(f"  圈 {n:2d} [{row.section}] {row.raw_operation:38s} -> {part.counts[n - 1]:3d} | "
                      f"decreases={dec} | stitches by origin: {dict(tally)}")

print("\nTOTAL PROBLEMS:", total_problems)
