"""Round 2 (2026-11-19): whole-plan direction check for the mirrored-band decision.

Rule used (independent of the model's own check and of left/right-handedness):
with one face of the fabric toward the maker, travel around every edge of that
fabric has one rotational sense; with the other face toward the maker, the
opposite sense. Written per kind of edge, for a later row worked with side S:

  top of a row R (worked with side S_R, in increasing position order)
      S == S_R -> increasing positions        S != S_R -> decreasing
  unused face of a chain whose other face was worked/laid by row R1
      S == S_R1 -> against R1's direction     S != S_R1 -> along it
  row ends on the edge where right-side rows END
      S == RS -> toward earlier rows          S == WS -> toward later rows
  row ends on the edge where right-side rows BEGIN
      S == RS -> toward later rows            S == WS -> toward earlier rows

The script applies this to every stitch and every attachment of every generated
cardigan plan (yoke, body, armholes, sleeves, hem, band, cuffs), plus junction
adjacency inside the band path, for three generators:
  as_committed / two_orders (cuff base + neck direction) / three_parts (those
  two + band always turns and starts opposite the last hem row).
Nothing in the repository is modified.

Usage: python r2_side_rule_sweep.py <cardigan-open.json> <dir with packaged example plans>
"""
from __future__ import annotations

import collections
import inspect
import itertools
import json
import sys
import textwrap
from pathlib import Path

import app
import app.models.cardigan_design as cd
from app.models.cardigan_design import CardiganRequest
from app.models.working_path import FoundationChain, Route, WorkingPath, compile_working_path

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
STITCHES = ("sc", "standing_sc", "inc", "dec", "slst")


def build(patches):
    source = SRC
    for old, new in patches:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    namespace = dict(vars(cd))
    exec(compile(source, "<patched assemble_cardigan>", "exec"), namespace)
    return namespace["assemble_cardigan"]


def side_rule_findings(plan: WorkingPath) -> list[str]:
    """Return one label per (working section, edge kind) that breaks the rule."""
    compiled = compile_working_path(plan)
    routes = {s.id: s for s in plan.steps if isinstance(s, Route)}
    order = {s.id: i for i, s in enumerate(plan.steps)}
    chains = {s.id: s for s in plan.steps if isinstance(s, FoundationChain)}
    row_of = {}
    for rid in routes:
        for index, site in enumerate(compiled.edges[rid]):
            row_of[site] = (rid, index)
    bridge_owner = {}
    for rid, route in routes.items():
        for op in route.operations:
            if getattr(op, "kind", "") == "chain":
                bridge_owner[op.id] = rid
    # which route worked each chain's work face, and in which position order
    chain_worker = {}
    sequence = 0
    seen = collections.defaultdict(list)
    for event in compiled.events:
        if event.stitch in STITCHES and event.sources:
            for site in event.sources:
                sequence += 1
                if site.edge in chains and site.face == chains[site.edge].work_face:
                    seen[site.edge].append((sequence, site.position, event.route))
    for chain_id, items in seen.items():
        if len(items) >= 2:
            direction = 1 if items[1][1] > items[0][1] else -1
            chain_worker[chain_id] = (items[0][2], direction)
    row_end_anchor = {e.outputs[0]: e.sources[0] for e in compiled.events if e.stitch == "row_end_site"}

    def classify(site):
        if site in row_of:
            rid, index = row_of[site]
            return ("top", rid, index)
        if site.face in ("row_left", "row_right"):
            row = routes[site.edge]
            begins = (site.face == "row_left") == (row.row_direction == "forward")
            rs_begin_edge = begins == (row.side == "RS")
            return ("rowend", "rs_rows_begin" if rs_begin_edge else "rs_rows_end", order[site.edge])
        if site.edge in chains and site.face == chains[site.edge].other_face:
            return ("chain_other", site.edge, site.position)
        if site.edge in bridge_owner and site.face in ("top", "underside"):
            return ("bridge_other", site.edge, site.position)
        return ("other", site.edge, site.position)

    def sign(kind, a, b, line):
        if kind == "top" and routes[line].closure != "none":
            n = len(compiled.edges[line])
            if n > 2 and (b - a) % n == 1:
                return 1
            if n > 2 and (a - b) % n == 1:
                return -1
        return 1 if b > a else -1

    def expected(kind, line, side):
        if kind == "top":
            row = routes[line]
            return None if row.side is None else (1 if side == row.side else -1)
        if kind == "chain_other":
            if line not in chain_worker:
                return None
            worker, direction = chain_worker[line]
            return None if routes[worker].side is None else (
                -direction if side == routes[worker].side else direction)
        if kind == "bridge_other":
            worker = routes[bridge_owner[line]]
            return None if worker.side is None else (-1 if side == worker.side else 1)
        if kind == "rowend":
            toward_later = (line == "rs_rows_begin") == (side == "RS")
            return 1 if toward_later else -1
        return None

    findings = set()

    def compare(a, b, side, label):
        ka, kb = classify(a), classify(b)
        if ka[0] != kb[0] or ka[0] == "other":
            return
        if ka[0] == "rowend" and ka[1] != kb[1]:
            findings.add(f"{label}: consecutive row ends lie on different front edges")
            return
        if ka[1] != kb[1]:
            return
        want = expected(ka[0], ka[1], side)
        if want is None or ka[2] == kb[2]:
            return
        if sign(ka[0], ka[2], kb[2], ka[1]) != want:
            if ka[0] == "top":
                where = f"top of {routes[ka[1]].section or ka[1]}"
            elif ka[0] == "rowend":
                where = "front row ends"
            elif ka[0] == "chain_other":
                where = f"unused face of {ka[1]}"
            else:
                where = "unused face of an underarm chain"
            findings.add(f"{label} travels the wrong way over {where}")

    # (1) stitches inside one row; (2) attachments of one section in order across its rows
    last_binding = {}
    for step in plan.steps:
        if not isinstance(step, Route) or step.side is None:
            continue
        label = step.section or step.id
        working, binding = [], []
        for event in compiled.events:
            if event.route == step.id and event.stitch in STITCHES and event.sources:
                (binding if event.role == "binding" else working).extend(event.sources)
        for a, b in itertools.pairwise(working):
            compare(a, b, step.side, label)
        if binding:
            previous = last_binding.get(label)
            if previous is not None:
                compare(previous, binding[0], step.side, label + " attachments")
            for a, b in itertools.pairwise(binding):
                compare(a, b, step.side, label + " attachments")
            last_binding[label] = binding[-1]

    # (3) junctions inside each re-ordered edge: row end <-> neck chain position
    neck_over = {}
    for event in compiled.events:
        if event.stitch in STITCHES and event.sources and event.sources[0].edge in chains:
            for output in event.outputs:
                neck_over[output] = event.sources[0]
    for name, sites in compiled.edges.items():
        for a, b in itertools.pairwise(sites):
            for row_end, chain_site in ((a, b), (b, a)):
                if row_end.face in ("row_left", "row_right") and chain_site.edge in chains:
                    below = neck_over.get(row_end_anchor[row_end])
                    if below is not None and below.edge == chain_site.edge and below.position != chain_site.position:
                        findings.add(f"{name}: path jumps {abs(below.position - chain_site.position)} "
                                     "chain positions between a front edge and the neckline")
    return sorted(findings)


def band_facts(plan: WorkingPath, prefix: str) -> str:
    compiled = compile_working_path(plan)
    routes = {s.id: s for s in plan.steps if isinstance(s, Route)}
    chain = next(s for s in plan.steps if s.id == f"{prefix}_band_chain")
    first_end = next(site for site in compiled.edges[f"{prefix}_band_base"]
                     if site.face in ("row_left", "row_right"))
    row = routes[first_end.edge]
    begins = (first_end.face == "row_left") == (row.row_direction == "forward")
    front = "RS-rows-BEGIN edge" if begins == (row.side == "RS") else "RS-rows-END edge"
    holes = sorted({e.route for e in compiled.events if e.stitch == "buttonhole_boundary"})
    hem1 = routes[f"{prefix}_hem_001"]
    return (f"hem attached with {hem1.side} facing; band chain turn={chain.turn_after_chain}; "
            f"band attached with {routes[f'{prefix}_band_001'].side} facing; buttonhole front = {front}; "
            f"buttonhole rows = {[int(h[-3:]) for h in holes]}")


def main() -> None:
    base = json.loads(Path(sys.argv[1]).read_text())
    prefix = base["method"]["prefix"]
    generators = {name: build(patches) for name, patches in VARIANTS.items()}

    print("== 0. packaged example plans (as committed) under the same rule")
    for path in sorted(Path(sys.argv[2]).glob("*/path-plan.json")):
        plan = WorkingPath.model_validate(json.loads(path.read_text()))
        found = side_rule_findings(plan)
        print(f"   {path.parent.name:28s} {len(found)} finding(s)" + "".join(f"\n      - {f}" for f in found))

    print("\n== 1. sweep: body rows 2-41 x sleeve rows 17/18 x cuff mode (open / seamed), 28 rows per 10 cm")
    stages = collections.defaultdict(dict)
    for variant, generate in generators.items():
        table = collections.Counter()
        complete = 0
        for body_rows, sleeve_rows, cuff in itertools.product(range(2, 42), (17, 18),
                                                              ("open_review", "blo_to_reserved_flo")):
            raw = dict(base, body_length_cm=body_rows * 10 / 28, sleeve_length_cm=sleeve_rows * 10 / 28,
                       cuff_seam=cuff)
            result = generate(CardiganRequest.model_validate(raw))
            assert result.stages["body"]["rows"] == body_rows
            assert result.stages["body"]["sleeve_rows"] == sleeve_rows
            stages[(body_rows, sleeve_rows, cuff)][variant] = result.stage
            parity = f"body {'odd ' if body_rows % 2 else 'even'}"
            if not result.stage.startswith("integrated"):
                table[(parity, "(not generated: " + result.stage + ")")] += 1
                continue
            complete += 1
            found = side_rule_findings(result.plan)
            table[(parity, "; ".join(found) or "no contradiction")] += 1
        print(f"\n   --- {variant}: {complete} complete plans")
        for (parity, what), count in sorted(table.items()):
            print(f"   {parity}: {count:3d} plans -> {what}")
    changed = [key for key, value in stages.items() if len(set(value.values())) > 1]
    print(f"\n   inputs whose stage differs between the three generators: {len(changed)} of {len(stages)}")

    print("\n== 2. what the three-part variant produces (default 21 rows vs 20 rows)")
    for body in (7.5, 7.1):
        for variant in ("as_committed", "three_parts"):
            result = generators[variant](CardiganRequest.model_validate(dict(base, body_length_cm=body)))
            print(f"   body {body} cm ({result.stages['body']['rows']} rows) {variant:13s}: "
                  f"{band_facts(result.plan, prefix)}")


if __name__ == "__main__":
    main()
