"""Dressed-doll: (1) shoe toe/heel arcs, (2) which validation layer rejects swept inputs."""
from __future__ import annotations

import collections
import itertools
import re
from pathlib import Path

import app
from pydantic import ValidationError

from app.models.dressed_doll import DollDesign, build_doll_plan, starter_design
from app.models.gauge import Gauge

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__

print("== 1. shoe: stitches left on the toe arc and the heel arc at the opening")
print("   (arcs are the two 'W' ends of the oval; the straight sides never change)")
for height, gauge in ((16, (22, 28)), (24, (22, 28)), (24, (30, 36)), (40, (22, 28)), (60, (22, 28))):
    plan = build_doll_plan(starter_design("wide_brim_curls", height_cm=height, gauge=Gauge(*gauge)))
    shoe = next(p for p in plan.components if p.id == "shoes")
    leg = next(p for p in plan.components if p.id == "legs").steps[-1].stitches
    straight = shoe.foundation.chains - 3
    toe_rounds = [s.number for s in shoe.steps if s.section == "鞋头收窄"]
    heel_rounds = [s.number for s in shoe.steps if s.section == "鞋跟与鞋口"]
    widest = max(s.stitches for s in shoe.steps)
    arc = (widest - 2 * straight) // 2
    opening = shoe.steps[-1].stitches
    # Decreases recorded per section, read from the written expressions.
    lost = {name: sum(len(re.findall(r"A", s.expression)) * (int(m.group(1)) if (m := re.search(r"\(A\)×(\d+)", s.expression)) else 1)
                      for s in shoe.steps if s.section == name) for name in ("鞋头收窄", "鞋跟与鞋口")}
    toe_left, heel_left = arc - lost["鞋头收窄"], arc - lost["鞋跟与鞋口"]
    print(f"   height {height:2d} gauge {gauge}: sole edge {widest} (arcs {arc}+{arc}, sides {straight}+{straight}); "
          f"toe decreases in rounds {toe_rounds} -> {toe_left} left; heel decreases in rounds {heel_rounds} -> {heel_left} left; "
          f"opening {opening} = {toe_left}+{straight}+{heel_left}+{straight}; leg {leg}")

print("\n== 2. which layer rejects swept inputs (all inputs are inside the UI's widget ranges)")
base = starter_design("wide_brim_curls").model_dump()
grid = {
    "height_cm": (16.0, 24.0, 36.0, 60.0),
    "head_diameter_cm": (2.0, 6.0, 12.0, 20.0),
    "palm_diameter_cm": (0.4, 1.5, 3.0, 6.0),
    "wrist_diameter_cm": (0.3, 0.9, 2.0, 4.0),
    "foot_length_cm": (1.0, 3.0, 10.0),
    "foot_width_cm": (0.5, 1.6, 8.0),
    "bodice_length_cm": (1.0, 5.4, 12.0, 30.0),
    "stitches_per_10cm": (6.0, 22.0, 40.0),
    "rows_per_10cm": (8.0, 28.0, 50.0),
}
outcomes = collections.Counter()
samples = {}
for values in itertools.product(*grid.values()):
    raw = base | dict(zip(grid, values, strict=True))
    try:
        design = DollDesign.model_validate(raw)
    except ValidationError as error:
        outcomes["input rejected by DollDesign: " + re.sub(r"[\d.]+", "N", error.errors()[0]["msg"])[:46]] += 1
        continue
    try:
        build_doll_plan(design)
        outcomes["plan built"] += 1
    except ValidationError as error:
        key = f"INTERNAL model rejected generator output ({error.title}): " + error.errors()[0]["msg"][:60]
        outcomes[key] += 1
        samples.setdefault(key, raw)
    except ValueError as error:
        key = "generator ValueError: " + re.sub(r"[\d.]+", "N", str(error))[:70]
        outcomes[key] += 1
        samples.setdefault(key, raw)
    except Exception as error:  # noqa: BLE001
        key = f"*** uncaught {type(error).__name__}: {str(error)[:70]}"
        outcomes[key] += 1
        samples.setdefault(key, raw)
for key, count in outcomes.most_common():
    print(f"   {count:6d}  {key}")
for key, raw in samples.items():
    print("   sample:", key[:60], "<-", {k: raw[k] for k in grid})
