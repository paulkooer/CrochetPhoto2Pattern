"""Remaining model probes: split-row 'row ends', self-referencing bridge, piece-to-piece jumps with one
uncut strand, exposing the generic 'route start is never tied to the hook' root cause in tracked mode."""
from _common import attempt, plan, route, show, span, work
from app.utils.working_path_export import export_working_path_markdown
from app.utils.working_path_format import route_formula


def hold(id_, spans):
    return {"kind": "hold", "id": id_, "label": id_, "spans": spans}


def flat(id_, ops, expected, *, side="RS", direction="forward", turn="none", **extra):
    return route(id_, ops, expected, mode="flat", side=side, row_direction=direction, turn=turn, **extra)


def row_edges(id_, rows):
    return {"kind": "row_edges", "id": id_, "label": id_, "rows": [{"row": r, "side": s} for r, s in rows]}


print("== 1. 'row ends' in the interior of one physical row ==")
# seed has 10 stitches. Route a works 1-5, route b works 6-10, same side, same direction, no cut:
# physically ONE row of 10 written as two steps.  a's far end and b's near end touch each other.
status, result = show("row-end sites taken at the junction of two halves of the same row",
                      plan([flat("a", [work("seed", 1, 5)], 5), flat("b", [work("seed", 6, 10)], 5),
                            row_edges("inner", [("a", "right"), ("b", "left")]),
                            route("picked", [work("inner", 1, 2)], 2)],
                           existing=[("seed", 10)], final=["a", "b", "picked"]))
if status == "ACCEPT":
    print("   row-end anchors:", [(e.sources[0].edge, e.sources[0].position, e.outputs[0].face)
                                 for e in result.events if e.stitch == "row_end_site"])
    print("   created sites:", result.created_sites, "(10 seed + 10 row + 2 'row ends' + 2 picked)")

print("== 2. bridge whose far end lands on its own underside ==")
status, result = show("ch 3 'bridge' followed by work into the same chain's underside",
                      plan([route("r", [work("seed", 1, 2),
                                        {"kind": "chain", "id": "br", "count": 3, "route_face": "top"},
                                        work("br", 1, 3, face="underside", direction="reverse"),
                                        work("seed", 3, 4)], 10)], existing=[("seed", 4)], final=["r"]))
if status == "ACCEPT":
    print("   formula:", route_formula(result.plan.steps[0], events=result.events))

print("== 3. tracked strand jumps between unconnected pieces without cutting ==")
steps = [
    {"kind": "new_yarn", "id": "join", "label": "接线", "yarn": "main", "method": "standing_sc", "side": "RS",
     "anchor": span("piece_a", 1)},
    flat("on_a", [work("piece_a", 1, stitch="standing_sc"), work("piece_a", 2, 6)], 6, label="织片A上的一行"),
    flat("on_b", [work("piece_b", 1, 6)], 6, label="织片B上的一行"),
    {"kind": "fasten_off", "id": "end", "label": "收线", "yarn": "main", "source": span("on_b", 6), "tail_cm": 15.0},
]
status, result = show("row on piece A, then row on separate piece B with the same uncut strand",
                      plan(steps, existing=[("piece_a", 6), ("piece_b", 6)], final=["on_a", "on_b"],
                           yarn_tracking=True, input_origin="manual_instructions"))
if status == "ACCEPT":
    text = export_working_path_markdown(result.plan)
    for line in text.splitlines():
        if line[:2] in ("1.", "2.", "3.", "4."):
            print("   ", line)
    print("   yarn ids on events:", sorted({e.yarn_id for e in result.events if e.role == "working"}))

print("== 4. same thing after a resume: hook is on row/3, next stitches are made elsewhere ==")
steps = [
    {"kind": "new_yarn", "id": "n1", "label": "n1", "yarn": "main", "method": "foundation_chain", "side": "RS"},
    {"kind": "foundation_chain", "id": "ch", "label": "ch", "chains": 4, "work_face": "underside", "other_face": "top"},
    flat("row", [work("ch", 1, 3, face="underside")], 3),
    {"kind": "park_yarn", "id": "p", "label": "p", "yarn": "main", "source": span("row", 3)},
    {"kind": "resume_yarn", "id": "r", "label": "r", "yarn": "main"},
    flat("far", [work("other", 1, 5)], 5),
    hold("outside", [span("ch", 1, 3)]),
]
show("resume at row/3, then work a row on an unrelated edge",
     plan(steps, existing=[("other", 5)], final=["row", "far", "outside"], yarn_tracking=True))
