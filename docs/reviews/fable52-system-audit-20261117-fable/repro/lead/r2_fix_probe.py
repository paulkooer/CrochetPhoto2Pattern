"""Round 2 (2026-11-19): check GPT Pro's re-review of the cardigan P1 findings.

For 2 body parities x 2 sleeve parities x every cardigan example input this
prints, for the generator as committed and for two in-memory patched variants:
  - whether the plan still compiles, and the site inventory totals;
  - neckline junctions inside the band path (row end over chain position X,
    path continues at / leaves from chain position Y);
  - whether each ribbing's first attachments travel in the direction that the
    declared turns allow (odd number of turns <=> reverse order).

Variant "two_orders"  = reverse the cuff base + pick the neck direction from the
                        entry end (the two-order fix described in the re-review).
Variant "three_parts" = the same, plus the band always turns and starts on the
                        side opposite the last hem row.

It also runs small checker probes (section rename, start far from the loop).
Nothing in the repository is modified; patches are applied to a copy of the
function source in memory.

Usage: python r2_fix_probe.py <dir with cardigan-*.json example inputs>
"""
from __future__ import annotations

import inspect
import json
import sys
import textwrap
from pathlib import Path

import app
import app.models.cardigan_design as cd
from app.models.cardigan_design import CardiganRequest
from app.models.working_path import (
    ExistingEdge,
    FoundationChain,
    Hold,
    Route,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__
assert Path(cd.__file__).resolve().is_relative_to(REPO), cd.__file__

SRC = textwrap.dedent(inspect.getsource(cd.assemble_cardigan))
CUFF = ('Span(edge=previous, first=2, last=yoke.layout.sleeve_stitches),',
        'Span(edge=previous, first=2, last=yoke.layout.sleeve_stitches, direction="reverse"),')
NECK = ('first=1, last=yoke.layout.neck_stitches, direction="reverse"),',
        'first=1, last=yoke.layout.neck_stitches, '
        'direction="reverse" if side == "right" else "forward"),')
BAND_TURN = ('foundation_turn="counterclockwise" if hem_route.side == "WS" else "none",',
             'foundation_turn="counterclockwise",')
BAND_SIDE = ('hook_mm=hook, start_side="RS", outer_turning_chain=1,',
             'hook_mm=hook, start_side=_opposite(hem_route.side), outer_turning_chain=1,')
VARIANTS = {"as_committed": [], "two_orders": [CUFF, NECK],
            "three_parts": [CUFF, NECK, BAND_TURN, BAND_SIDE]}


def build(patches):
    source = SRC
    for old, new in patches:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    namespace = dict(vars(cd))
    exec(compile(source, "<patched assemble_cardigan>", "exec"), namespace)
    return namespace["assemble_cardigan"]


def analyse(plan, prefix):
    compiled = compile_working_path(plan)
    routes = {s.id: s for s in plan.steps if isinstance(s, Route)}
    chains = {s.id: s for s in plan.steps if isinstance(s, FoundationChain)}
    neck_chain = f"{prefix}_neck_chain"
    over = {}
    for event in compiled.events:
        if event.route == f"{prefix}_yoke_001" and event.role == "working":
            for output in event.outputs:
                over[output] = event.sources[0].position
    anchor = {e.outputs[0]: e.sources[0] for e in compiled.events if e.stitch == "row_end_site"}
    sites = compiled.edges[f"{prefix}_band_base"]
    junctions = []
    for a, b in zip(sites, sites[1:], strict=False):
        if a.face in ("row_left", "row_right") and b.edge == neck_chain:
            junctions.append(("enter", over[anchor[a]], b.position))
        elif a.edge == neck_chain and b.face in ("row_left", "row_right"):
            junctions.append(("leave", a.position, over[anchor[b]]))
    direction = {}
    for name in ("hem", "band", "cuff_a", "cuff_b"):
        rib = f"{prefix}_{name}"
        chain = chains[f"{rib}_chain"]
        loop = compiled.edges[chain.anchor.edge][chain.anchor.first - 1]
        row = routes[loop.edge]
        index = {site: i + 1 for i, site in enumerate(compiled.edges[row.id])}
        order = [index[e.sources[0]] for e in compiled.events
                 if e.route.startswith(rib + "_") and e.role == "binding" and e.sources[0] in index]
        travels = "reverse" if order[0] > order[1] else "same"
        turns = int(row.turn != "none") + int(chain.turn_after_chain != "none")
        needed = "reverse" if turns % 2 else "same"
        direction[name] = {
            "loop": f"{row.id}#{loop.position}", "row_side": row.side, "row_turn": row.turn,
            "closure": row.closure, "chain_turn": chain.turn_after_chain,
            "rib_row1_side": routes[f"{rib}_001"].side,
            "order": f"{order[:3]}..{order[-2:]}", "travels": travels, "needed": needed,
            "ok": travels == needed}
    inventory = {"created": compiled.created_sites, "consumed": compiled.consumed_sites,
                 "final": {k: len(v) for k, v in compiled.final_edges.items()}}
    return junctions, direction, inventory


def cardigans(inputs: Path) -> None:
    generators = {name: build(patches) for name, patches in VARIANTS.items()}
    for path in sorted(inputs.glob("cardigan-*.json")):
        raw0 = json.loads(path.read_text())
        same = (generators["as_committed"](CardiganRequest.model_validate(raw0)).to_dict()
                == cd.assemble_cardigan(CardiganRequest.model_validate(raw0)).to_dict())
        print(f"\n######## {path.name}  (in-memory copy == module function: {same})")
        for body in (7.5, 7.1):
            for sleeve in (6.4, 6.1):
                raw = dict(raw0, body_length_cm=body, sleeve_length_cm=sleeve)
                baseline = None
                for name, generate in generators.items():
                    try:
                        result = generate(CardiganRequest.model_validate(raw))
                    except Exception as error:  # report, never hide
                        print(f"  {name:13s} RAISED {type(error).__name__}: {str(error)[:200]}")
                        continue
                    if name == "as_committed":
                        rows = result.stages.get("body", {})
                        print(f"\n=== body {body} cm -> {rows.get('rows')} rows; sleeve {sleeve} cm -> "
                              f"{rows.get('sleeve_rows')} rows; stage={result.stage}")
                    if result.plan is None or not result.stage.startswith("integrated"):
                        print(f"  {name:13s} stage={result.stage}: not a complete plan, skipped")
                        continue
                    junctions, direction, inventory = analyse(result.plan, raw["method"]["prefix"])
                    baseline = baseline or inventory
                    bad_junctions = sum(x != y for _, x, y in junctions)
                    bad_direction = [k for k, v in direction.items() if not v["ok"]]
                    print(f"  {name:13s} compiles=yes created={inventory['created']} "
                          f"consumed={inventory['consumed']} inventory_same_as_committed={inventory == baseline} "
                          f"neck_junctions={junctions} mismatched={bad_junctions} "
                          f"direction_contradictions={bad_direction or 'none'}")
                    for key in ("band", "cuff_a"):
                        v = direction[key]
                        print(f"      {key}: loop {v['loop']} row_side={v['row_side']} row_turn={v['row_turn']} "
                              f"closure={v['closure']} chain_turn={v['chain_turn']} rib_row1_side={v['rib_row1_side']} "
                              f"attach order over that row {v['order']} = {v['travels']}; needs {v['needed']}")


def tiny(section, number, *, source_direction="forward", first=1, last=4, count=4):
    extra = {} if section is None else {"section": section, "row_number": number}
    steps = [
        Route(id="r1", label="第1行", section="a", row_number=1, mode="flat", side="RS",
              row_direction="forward", operations=[Work(source=Span(edge="base", first=1, last=count))],
              expected_sites=count, turn="counterclockwise", turning_chains=1),
        Route(id="r2", label="第2行", mode="flat", side="WS", row_direction="reverse",
              operations=[Work(source=Span(edge="r1", first=first, last=last, direction=source_direction))],
              expected_sites=last - first + 1, **extra),
    ]
    final = ["r2"]
    if last < count:
        steps.append(Hold(id="rest", label="未钩部分", spans=[Span(edge="r1", first=last + 1, last=count)]))
        final.append("rest")
    return WorkingPath(title="四针探针", existing_edges=[ExistingEdge(id="base", count=count)],
                       steps=steps, final_edges=final)


def checker_probes() -> None:
    print("\n######## checker probes (row 1: 4 sc, RS, then a declared turn; loop is on stitch 4)")
    cases = [
        ("control: row 2 same section, takes 4,3,2,1", tiny("a", 2, source_direction="reverse")),
        ("row 2 same section, takes 1,2,3,4 after the turn", tiny("a", 2)),
        ("same wrong row 2, section renamed to 'b'", tiny("b", 1)),
        ("same wrong row 2, no section at all", tiny(None, None)),
        ("6-stitch row; row 2 same section takes 3,2,1 (starts 3 stitches from the loop)",
         tiny("a", 2, source_direction="reverse", first=1, last=3, count=6)),
    ]
    for label, plan in cases:
        try:
            compile_working_path(plan)
            print(f"  ACCEPTED  {label}")
        except ValueError as error:
            print(f"  REJECTED  {label} -> {str(error)[:90]}")


if __name__ == "__main__":
    cardigans(Path(sys.argv[1]))
    checker_probes()
