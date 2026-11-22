"""Does each attached ribbing start in the direction the declared turns allow?

Rule used (handedness-independent, and the same rule the model enforces inside
one section in `_Compiler.check_turned_continuation`): after an odd number of
turns the next stitches travel over the previous row in REVERSE order; after an
even number of turns they travel in the SAME order.

For every generated ribbing (hem, band, cuff a/b) the script finds the row the
working loop is on, the declared turns between that row and ribbing row 1, and
the order in which the first attachments travel over that row. It then asks the
model itself the same question by appending one ordinary row that uses exactly
the cuff's attachment order to the sleeve section.

Usage: python ribbing_start_direction.py <cardigan-request.json> <body_length_cm> <sleeve_length_cm>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import app
from app.models.cardigan_design import CardiganRequest, assemble_cardigan
from app.models.working_path import (
    FoundationChain,
    Route,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def main() -> int:
    raw = json.loads(Path(sys.argv[1]).read_text())
    raw["body_length_cm"], raw["sleeve_length_cm"] = float(sys.argv[2]), float(sys.argv[3])
    result = assemble_cardigan(CardiganRequest.model_validate(raw))
    assert result.plan is not None
    plan, prefix = result.plan, raw["method"]["prefix"]
    compiled = compile_working_path(plan)
    routes = {step.id: step for step in plan.steps if isinstance(step, Route)}
    chains = {step.id: step for step in plan.steps if isinstance(step, FoundationChain)}
    print(f"stage={result.stage} body_rows={result.stages['body']['rows']} "
          f"sleeve_rows={result.stages['body']['sleeve_rows']} (model accepted the plan)")

    contradictions = 0
    for name in ("hem", "band", "cuff_a", "cuff_b"):
        ribbing = f"{prefix}_{name}"
        chain = chains[f"{ribbing}_chain"]
        loop_site = compiled.edges[chain.anchor.edge][chain.anchor.first - 1]
        loop_row = routes[loop_site.edge]
        row_sites = compiled.edges[loop_row.id]
        index = {site: i for i, site in enumerate(row_sites)}
        first_row = routes[f"{ribbing}_001"]
        attached = [e.sources[0] for e in compiled.events
                    if e.route.startswith(ribbing + "_") and e.role == "binding"]
        on_loop_row = [index[s] + 1 for s in attached if s in index][:4]
        travels = "REVERSE" if on_loop_row[0] > on_loop_row[1] else "SAME"
        turns = int(loop_row.turn != "none") + int(chain.turn_after_chain != "none")
        needed = "REVERSE" if turns % 2 else "SAME"
        verdict = "consistent" if travels == needed else "CONTRADICTION"
        contradictions += travels != needed
        print(f"  {name:6s}: loop on {loop_row.id} stitch {loop_site.position} "
              f"(row side {loop_row.side}, row turn={loop_row.turn}, closure={loop_row.closure}); "
              f"chain turn={chain.turn_after_chain}; ribbing row 1 side={first_row.side}; "
              f"first attachments over that row: stitches {on_loop_row} = {travels} order; "
              f"declared turns={turns} -> needs {needed} order => {verdict}")

    # Ask the model: one more ordinary round in the sleeve section, in the cuff's order.
    sleeve = sorted(k for k in routes if k.startswith(f"{prefix}_sleeve_a_"))
    last = routes[sleeve[-1]]
    cut = next(i for i, step in enumerate(plan.steps) if step.id == f"{prefix}_cuff_a_base")
    count = last.expected_sites
    side = "RS" if last.side == "WS" else "WS"
    extra = Route(id="probe_extra_round", label="探针：按袖口接合顺序再钩一圈", section=last.section,
                  row_number=last.row_number + 1, mode="joined_rows", side=side,
                  row_direction="forward" if side == "RS" else "reverse",
                  operations=[Work(source=Span(edge=last.id, first=2, last=count)),
                              Work(source=Span(edge=last.id, first=1, last=1))],
                  expected_sites=count, turn="counterclockwise",
                  closure="before_turn" if side == "RS" else "after_turn")
    probe = WorkingPath.model_validate(plan.model_dump() | {
        "steps": [s.model_dump() for s in plan.steps[:cut]] + [extra.model_dump()], "final_edges": []})
    try:
        compile_working_path(probe)
        print("  model on an ordinary round using the cuff's order (2..n, 1): accepted")
    except ValueError as error:
        print(f"  model on an ordinary round using the cuff's order (2..n, 1): REJECTED -> {str(error)[:120]}")
    print(f"contradictions: {contradictions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
