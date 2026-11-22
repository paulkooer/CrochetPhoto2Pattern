"""Sweep the parametric cardigan over sizes; report geometry contradictions and exception types.

Part 1: for body/sleeve row parities, count plans the model accepts whose band or
cuff path contradicts simple physical adjacency / turn rules (same independent
rules as band_cuff_continuity.py and ribbing_start_direction.py).
Part 2: feed boundary inputs through assemble_cardigan and record how each one
ends: staged result, ValueError (handled by UI/CLI), or any other exception
type (would surface as an uncaught error in the Streamlit entry).
"""
from __future__ import annotations

import collections
import itertools
import json
import sys
from pathlib import Path

import app
from app.models.cardigan_design import CardiganRequest, assemble_cardigan
from app.models.working_path import FoundationChain, Route, compile_working_path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__
BASE = json.loads(Path(sys.argv[1]).read_text())


def request(**changes):
    raw = json.loads(json.dumps(BASE))
    for key, value in changes.items():
        target = raw
        *parents, leaf = key.split("__")
        for parent in parents:
            target = target[parent]
        target[leaf] = value
    return CardiganRequest.model_validate(raw)


def contradictions(result):
    plan = result.plan
    compiled = compile_working_path(plan)
    prefix = result.request.method.prefix
    routes = {s.id: s for s in plan.steps if isinstance(s, Route)}
    chains = {s.id: s for s in plan.steps if isinstance(s, FoundationChain)}
    found = []
    # (a) neckline junctions of the band path
    on_chain = {e.outputs[0]: e.sources[0].position for e in compiled.events
                if e.route == f"{prefix}_yoke_001" and e.role == "working"}
    anchors = {e.outputs[0]: e.sources[0] for e in compiled.events if e.stitch == "row_end_site"}
    sites = compiled.edges.get(f"{prefix}_band_base", ())
    for before, after in zip(sites, sites[1:], strict=False):
        if before.face.startswith("row_") and after.edge == f"{prefix}_neck_chain":
            if on_chain[anchors[before]] != after.position:
                found.append("band_jumps_across_neckline")
        if before.edge == f"{prefix}_neck_chain" and after.face.startswith("row_"):
            if on_chain[anchors[after]] != before.position:
                found.append("band_jumps_across_neckline")
    # (b) start direction of each ribbing against the declared turns
    for name in ("hem", "band", "cuff_a", "cuff_b"):
        chain = chains.get(f"{prefix}_{name}_chain")
        if chain is None:
            continue
        loop_site = compiled.edges[chain.anchor.edge][chain.anchor.first - 1]
        loop_row = routes[loop_site.edge]
        index = {site: i for i, site in enumerate(compiled.edges[loop_row.id])}
        attached = [e.sources[0] for e in compiled.events
                    if e.route.startswith(f"{prefix}_{name}_") and e.role == "binding"]
        order = [index[s] for s in attached if s in index][:2]
        if len(order) < 2:
            continue
        travels_reverse = order[0] > order[1]
        turns = int(loop_row.turn != "none") + int(chain.turn_after_chain != "none")
        if travels_reverse != bool(turns % 2):
            found.append(f"{name}_direction_vs_turn")
    return sorted(set(found))


print("== Part 1: parity sweep (rows are quantised from cm at 28 rows/10cm)")
table = collections.Counter()
examples = {}
for body_rows, sleeve_rows in itertools.product(range(2, 42), (17, 18)):
    result = assemble_cardigan(request(body_length_cm=body_rows * 10 / 28, sleeve_length_cm=sleeve_rows * 10 / 28))
    assert result.stages["body"]["rows"] == body_rows and result.stages["body"]["sleeve_rows"] == sleeve_rows
    if result.stage != "integrated_open_cuffs":
        table[(body_rows % 2, sleeve_rows % 2, "stage:" + result.stage)] += 1
        continue
    key = (body_rows % 2, sleeve_rows % 2, ",".join(contradictions(result)) or "none")
    table[key] += 1
    examples.setdefault(key, (body_rows, sleeve_rows))
for (body_parity, sleeve_parity, what), count in sorted(table.items()):
    print(f"  body rows {'odd ' if body_parity else 'even'} / sleeve rows {'odd ' if sleeve_parity else 'even'}: "
          f"{count:3d} accepted plans -> {what}   (e.g. body={examples.get((body_parity, sleeve_parity, what), ('-', '-'))[0]})")

print("\n== Part 2: boundary inputs -> how assemble_cardigan ends")
cases = {
    "defaults": {},
    "body_length 0.01cm (0 rows)": {"body_length_cm": 0.01},
    "body_length 0.2cm (1 row)": {"body_length_cm": 0.2},
    "body_length 50cm (140 rows)": {"body_length_cm": 50.0},
    "sleeve_length 0.2cm (1 row)": {"sleeve_length_cm": 0.2},
    "sleeve_length 50cm": {"sleeve_length_cm": 50.0},
    "hem_width 0.1cm (0 st)": {"hem_width_cm": 0.1},
    "hem_width 0.4cm (1 st)": {"hem_width_cm": 0.4},
    "band_width 0.3cm (1 st)": {"band_width_cm": 0.3},
    "band_width 0.5cm (2 st)": {"band_width_cm": 0.5},
    "cuff_width 0.3cm (1 st)": {"cuff_width_cm": 0.3},
    "cuff_width 10cm (40 st)": {"cuff_width_cm": 10.0},
    "buttonholes unsorted": {"buttonhole_positions_cm": [5.0, 3.0, 1.0]},
    "buttonholes duplicated": {"buttonhole_positions_cm": [3.0, 3.0]},
    "buttonhole at 0.2cm": {"buttonhole_positions_cm": [0.2]},
    "buttonhole at 90cm": {"buttonhole_positions_cm": [90.0]},
    "buttonhole_chains 10": {"buttonhole_chains": 10},
    "neck 2cm (5 st)": {"yoke__neck_edge_cm": 2.0},
    "neck 100cm": {"yoke__neck_edge_cm": 100.0},
    "yoke depth 0.5cm": {"yoke__yoke_depth_cm": 0.5},
    "yoke depth 28cm (79 rows)": {"yoke__yoke_depth_cm": 28.2},
    "sleeve circ 2.7cm (7 st)": {"yoke__sleeve_circumference_cm": 2.7},
    "sleeve circ 40cm": {"yoke__sleeve_circumference_cm": 40.0},
    "body span 100cm": {"yoke__body_span_cm": 100.0},
    "adult-ish (neck 40, body 100, sleeve 30, depth 20, lengths 35)": {
        "yoke__neck_edge_cm": 40.0, "yoke__body_span_cm": 100.0, "yoke__sleeve_circumference_cm": 30.0,
        "yoke__yoke_depth_cm": 20.0, "body_length_cm": 28.0, "sleeve_length_cm": 28.0},
    "underarm_chains 15": {"method__underarm_chains": 15},
    "underarm_chains 3": {"method__underarm_chains": 3},
    "stitch_adjustment 0": {"method__stitch_adjustment": 0},
    "stitch_adjustment 3": {"method__stitch_adjustment": 3},
    "gauge 100/100": {"yoke__stitches_per_10cm": 100.0, "yoke__rows_per_10cm": 100.0},
    "gauge 5/5": {"yoke__stitches_per_10cm": 5.0, "yoke__rows_per_10cm": 5.0},
    "hem gauge rows 100": {"hem_gauge__rows_per_10cm": 100.0},
    "hem gauge rows 5": {"hem_gauge__rows_per_10cm": 5.0},
    "band gauge 5/5": {"band_gauge__stitches_per_10cm": 5.0, "band_gauge__rows_per_10cm": 5.0},
    "cuff gauge 100/100": {"cuff_gauge__stitches_per_10cm": 100.0, "cuff_gauge__rows_per_10cm": 100.0},
    "prefix 20 chars": {"method__prefix": "a" * 20},
    "seamed cuffs": {"cuff_seam": "blo_to_reserved_flo"},
    "seamed cuffs, cuff_width 0.3cm": {"cuff_seam": "blo_to_reserved_flo", "cuff_width_cm": 0.3},
}
for label, changes in cases.items():
    try:
        result = assemble_cardigan(request(**changes))
        steps = "-" if result.plan is None else len(result.plan.steps)
        reason = result.unresolved[0][:60] if result.stage.endswith("blocked") else ""
        report = result.to_dict()
        flags = [k for k in ("physical_execution_verified", "fit_verified", "ready_for_whole_garment_trial")
                 if report[k] is not False]
        print(f"  {label}: stage={result.stage} steps={steps} {reason}{' FLAGS TRUE: ' + str(flags) if flags else ''}")
    except ValueError as error:
        first = str(error).splitlines()
        print(f"  {label}: ValueError[{type(error).__name__}] {first[0][:70]} | {first[-1][:90] if len(first) > 1 else ''}")
    except Exception as error:  # noqa: BLE001 - the point is to see non-ValueError types
        print(f"  {label}: *** {type(error).__name__}: {str(error)[:120]}")
