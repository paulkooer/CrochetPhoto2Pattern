"""Geometric continuity probe for the parametric cardigan's band and cuffs.

Independent of the model's own validator: it only reads the compiled events and
asks whether consecutive pieces of the band's attachment path touch each other,
and whether the cuff's attachment order agrees with the side declared as facing.

Usage: python band_cuff_continuity.py <cardigan-request.json> <body_length_cm> [<sleeve_length_cm>]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import app
from app.models.cardigan_design import CardiganRequest, assemble_cardigan
from app.models.working_path import EdgePath, Route, compile_working_path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def main() -> None:
    raw = json.loads(Path(sys.argv[1]).read_text())
    raw["body_length_cm"] = float(sys.argv[2])
    if len(sys.argv) > 3:
        raw["sleeve_length_cm"] = float(sys.argv[3])
    result = assemble_cardigan(CardiganRequest.model_validate(raw))
    print(f"stage={result.stage} body_rows={result.stages['body']['rows']} "
          f"sleeve_rows={result.stages['body']['sleeve_rows']}")
    assert result.plan is not None
    plan = result.plan
    compiled = compile_working_path(plan)   # the model accepts the plan
    prefix = raw["method"]["prefix"]
    routes = {step.id: step for step in plan.steps if isinstance(step, Route)}

    # Which stitch of yoke row 1 sits on which neck-chain position.
    chain = f"{prefix}_neck_chain"
    on_chain = {}
    for event in compiled.events:
        if event.route == f"{prefix}_yoke_001" and event.role == "working":
            on_chain[event.outputs[0]] = event.sources[0].position
    row_end_anchor = {event.outputs[0]: event.sources[0]
                      for event in compiled.events if event.stitch == "row_end_site"}

    band_base = next(step for step in plan.steps if isinstance(step, EdgePath)
                     and step.id == f"{prefix}_band_base")
    sites = compiled.edges[band_base.id]
    print("band_base spans:", [(s.edge, s.first, s.last, s.direction) for s in band_base.spans])
    last_body = routes[sorted(k for k in routes if k.startswith(f"{prefix}_body_"))[-1]]
    print(f"last body row {last_body.id}: side={last_body.side} direction={last_body.row_direction}")
    hem_rows = sorted(k for k in routes if k.startswith(f"{prefix}_hem_"))
    band_rows = sorted(k for k in routes if k.startswith(f"{prefix}_band_"))
    hem_last = routes[hem_rows[-1]]
    foundation = next(step for step in plan.steps if step.id == f"{prefix}_band_chain")
    print(f"hem last row {hem_last.id}: side={hem_last.side} turn={hem_last.turn}; "
          f"band chain turn_after_chain={foundation.turn_after_chain}; "
          f"band row 1 side={routes[band_rows[0]].side}")

    # Walk the band path and report every junction between differently named edges.
    problems = 0
    for before, after in zip(sites, sites[1:], strict=False):
        if before.edge == after.edge and before.face == after.face:
            continue
        note = ""
        if before.face in ("row_left", "row_right") and after.edge == chain:
            anchor = row_end_anchor[before]
            touching = on_chain[anchor]
            ok = touching == after.position
            note = (f"row end of {before.edge} ({before.face}) sits over neck-chain position {touching}; "
                    f"path continues at neck-chain position {after.position}"
                    f" -> {'adjacent' if ok else 'NOT ADJACENT: jumps ' + str(abs(touching - after.position)) + ' chains along the neckline'}")
            problems += not ok
        elif before.edge == chain and after.face in ("row_left", "row_right"):
            anchor = row_end_anchor[after]
            touching = on_chain[anchor]
            ok = touching == before.position
            note = (f"path leaves the neckline at chain position {before.position}; next row end "
                    f"{after.edge} ({after.face}) sits over chain position {touching}"
                    f" -> {'adjacent' if ok else 'NOT ADJACENT: jumps ' + str(abs(touching - before.position)) + ' chains along the neckline'}")
            problems += not ok
        if note:
            print("  junction:", note)
    print(f"band neckline junction problems: {problems}")

    # Cuffs: attachment order along the last sleeve round versus declared facing.
    for name in ("a", "b"):
        sleeve = sorted(k for k in routes if k.startswith(f"{prefix}_sleeve_{name}_"))
        last = routes[sleeve[-1]]
        cuff = sorted(k for k in routes if k.startswith(f"{prefix}_cuff_{name}_") and k[-3:].isdigit())
        first_cuff = routes[cuff[0]]
        base = compiled.edges[f"{prefix}_cuff_{name}_base"]
        order = [site.position for site in base]
        increasing = order[:3] == sorted(order[:3])
        print(f"sleeve {name}: last round {last.id} side={last.side} turn={last.turn} closure={last.closure}; "
              f"cuff row 1 side={first_cuff.side}; cuff base order over that round starts {order[:4]} ... ends {order[-2:]}")
        same_facing = first_cuff.side == last.side
        print(f"   attachment travels in the {'SAME' if increasing else 'OPPOSITE'} direction as the last round was worked, "
              f"while the declared facing side is {'the SAME as' if same_facing else 'OPPOSITE to'} that round")
        if increasing != same_facing:
            print("   -> CONTRADICTION: same direction of travel needs the same side facing "
                  "(the model's own turned-row rule: reverse order <=> turned)")


if __name__ == "__main__":
    main()
