"""Dressed-doll prototype: independent arithmetic on the generated plans.

1. Body length: how much of the allocated body+neck height the generated rounds
   can supply. Linear-gauge estimate only (no fabric simulation, no physical
   measurement): a round whose stitch count is unchanged adds one row height
   along the axis; a shaping round changes the radius by dr and can add at most
   sqrt(row_h^2 - dr^2) along the axis (zero when |dr| >= row_h).
2. Hair-cap depth against the eye-candidate round.
3. Parameter sweep: which exception types escape build_doll_plan (the UI only
   catches ValueError).
"""
from __future__ import annotations

import collections
import itertools
import math
import re
from pathlib import Path

import app
from app.models.dressed_doll import build_doll_plan, starter_design
from app.models.gauge import Gauge

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def axial(counts, stitch_w, row_h):
    total, straight = 0.0, 0
    for before, after in zip(counts, counts[1:], strict=False):
        dr = abs(after - before) * stitch_w / (2 * math.pi)
        if after == before:
            straight += 1
        total += math.sqrt(max(0.0, row_h ** 2 - dr ** 2))
    return total, straight


print("== 1. body length supplied by the generated rounds (linear estimate, not measured)")
print("   starter            height  gauge   allocated(body+neck)  rounds  straight  meridian  axial-estimate  share")
for name, height, gauge in itertools.product(("wide_brim_curls", "folded_cap_layers"), (16, 24, 40, 60),
                                             ((22, 28), (30, 36), (14, 16))):
    design = starter_design(name, height_cm=height, gauge=Gauge(*gauge))
    try:
        plan = build_doll_plan(design)
    except ValueError as error:
        print(f"   {name:18s} {height:5.0f}  {gauge}  -> ValueError: {str(error).splitlines()[-1][:70]}")
        continue
    body = next(p for p in plan.components if p.id == "body")
    counts = [s.stitches for s in body.steps]
    stitch_w, row_h = 10 / gauge[0], 10 / gauge[1]
    height_axial, straight = axial(counts, stitch_w, row_h)
    allocated = design.height_cm - design.head_diameter_cm - design.leg_length_cm
    if name == "wide_brim_curls":
        print(f"   {name:18s} {height:5.0f}  {gauge}   {allocated:6.2f} cm            {len(counts):4d}   {straight:4d}    "
              f"{len(counts) * row_h:6.2f}    {height_axial:6.2f} cm      {height_axial / allocated:5.0%}")

design = starter_design("wide_brim_curls")
plan = build_doll_plan(design)
by_id = {p.id: p for p in plan.components}
stitch_w, row_h = 10 / 22, 10 / 28
body_counts = [s.stitches for s in by_id["body"].steps]
print("\n   default body rounds:", body_counts)
sections = collections.Counter(s.section for s in by_id["body"].steps)
print("   rounds per section:", dict(sections))
leg_axial, _ = axial([s.stitches for s in by_id["legs"].steps], stitch_w, row_h)
body_axial, _ = axial(body_counts, stitch_w, row_h)
print(f"   legs estimate {leg_axial:.2f} cm (target {design.leg_length_cm:g}); body+neck estimate {body_axial:.2f} cm "
      f"(allocated {design.height_cm - design.head_diameter_cm - design.leg_length_cm:g}); head target {design.head_diameter_cm:g}")
print(f"   sum with the head at its full target diameter: {leg_axial + body_axial + design.head_diameter_cm:.1f} cm "
      f"against the stated target height {design.height_cm:g} cm")

print("\n== 2. hair cap depth versus the eye-candidate round (both counted from the crown)")
head = [s.stitches for s in by_id["head"].steps]
cap = [s.stitches for s in by_id["hair_cap"].steps]
eye = int(re.search(r"第 (\d+) 圈为眼位候选", by_id["head"].finish).group(1))
join = next(j for j in plan.joins if j.source == "hair_cap")
print(f"   head rounds {len(head)}: {head}")
print(f"   hair cap rounds {len(cap)}: {cap}")
print(f"   eye candidate round: {eye}; cap is {len(cap)} rounds deep = {len(cap) * row_h:.2f} cm from crown to rim; "
      f"crown to eye round = {eye * row_h:.2f} cm")
print(f"   join text: {join.placement}")
print(f"   -> a crown-aligned cap of {len(cap)} rounds ends {len(cap) - eye:+d} rounds relative to the eye round "
      f"({'BELOW' if len(cap) > eye else 'above'} it)")
for height in (16, 24, 40, 60):
    p = build_doll_plan(starter_design("wide_brim_curls", height_cm=height))
    parts = {c.id: c for c in p.components}
    e = int(re.search(r"第 (\d+) 圈为眼位候选", parts["head"].finish).group(1))
    print(f"   height {height}: cap rounds {len(parts['hair_cap'].steps)}, eye round {e}, "
          f"head rounds {len(parts['head'].steps)} -> cap ends {len(parts['hair_cap'].steps) - e:+d} rounds from the eye round")

print("\n== 3. sweep: exception types escaping build_doll_plan")
outcomes = collections.Counter()
samples = {}
base = starter_design("wide_brim_curls").model_dump()
grid = {
    "height_cm": (16.0, 24.0, 60.0),
    "head_diameter_cm": (2.0, 6.0, 20.0),
    "palm_diameter_cm": (0.4, 1.5, 6.0),
    "wrist_diameter_cm": (0.3, 0.9, 4.0),
    "foot_length_cm": (1.0, 3.0, 10.0),
    "foot_width_cm": (0.5, 1.6, 8.0),
    "bodice_length_cm": (1.0, 5.4, 30.0),
    "stitches_per_10cm": (6.0, 22.0, 40.0),
    "rows_per_10cm": (8.0, 28.0, 50.0),
    "hat": ("wide_brim", "folded_band"),
}
from app.models.dressed_doll import DollDesign  # noqa: E402
from app.utils.dressed_doll_export import export_doll_markdown  # noqa: E402

total = 0
for values in itertools.product(*grid.values()):
    total += 1
    raw = base | dict(zip(grid, values, strict=True))
    try:
        design = DollDesign.model_validate(raw)
        result = build_doll_plan(design)
        export_doll_markdown(result)
        outcomes["plan built"] += 1
    except ValueError as error:
        key = "ValueError: " + re.sub(r"\d+(\.\d+)?", "N", str(error).splitlines()[-1])[:60]
        outcomes[key] += 1
    except Exception as error:  # noqa: BLE001 - looking for non-ValueError types
        key = f"*** {type(error).__name__}: {str(error)[:80]}"
        outcomes[key] += 1
        samples.setdefault(key, raw)
print(f"   {total} combinations")
for key, count in outcomes.most_common(14):
    print(f"   {count:6d}  {key}")
for key, raw in samples.items():
    print("   sample for", key, {k: raw[k] for k in grid})
