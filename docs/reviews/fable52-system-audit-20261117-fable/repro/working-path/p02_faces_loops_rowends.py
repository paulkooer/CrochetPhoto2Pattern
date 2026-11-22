"""Area 2: chain faces, FLO/BLO lips, row ends, corners, 'leave unworked' declarations."""
from _common import attempt, plan, route, show, span, work


def hold(id_, spans):
    return {"kind": "hold", "id": id_, "label": id_, "spans": spans}


def flat(id_, ops, expected, *, side="RS", direction="forward", turn="counterclockwise", **extra):
    return route(id_, ops, expected, mode="flat", side=side, row_direction=direction, turn=turn, **extra)


def loops(id_, source, loop):
    return {"kind": "free_loops", "id": id_, "label": id_, "source": source, "loop": loop}


def row_edges(id_, rows):
    return {"kind": "row_edges", "id": id_, "label": id_, "rows": [{"row": r, "side": s} for r, s in rows]}


def finish(id_, source, reason="finished_border"):
    return {"kind": "finish_edge", "id": id_, "label": id_, "source": source, "reason": reason}


E = [("seed", 4)]
two_rows = [flat("one", [work("seed", 1, 4)], 4),
            flat("two", [work("one", 1, 4, direction="reverse", loop="back")], 4, side="WS", direction="reverse")]

print("== 1. half loops ==")
show("free loop of a stitch whose other loop was never worked",
     plan([flat("one", [work("seed", 1, 4)], 4), loops("lip", span("one", 1, 4), "front")],
          existing=E, final=["one", "lip"]), expect="REJECT")
show("free loop on the SAME side that was worked (BLO worked, ask back)",
     plan(two_rows + [loops("lip", span("one", 1, 4), "back")], existing=E, final=["two", "lip"]), expect="REJECT")
status, result = show("two FreeLoops steps over the same front loops (both listed final)",
                      plan(two_rows + [loops("lip_a", span("one", 1, 4), "front"),
                                       loops("lip_b", span("one", 1, 4), "front")],
                           existing=E, final=["two", "lip_a", "lip_b"]), expect="REJECT")
status, result = show("two FreeLoops aliases, only one listed final",
                      plan(two_rows + [loops("lip_a", span("one", 1, 4), "front"),
                                       loops("lip_b", span("one", 1, 4), "front")],
                           existing=E, final=["two", "lip_a"]))
if status == "ACCEPT":
    print("   created:", result.created_sites, "| lip_a is lip_b:", result.edges["lip_a"] == result.edges["lip_b"],
          "| events for lip_b:", [e.stitch for e in result.events if e.route == "lip_b"])
show("work the same lips through both aliases",
     plan(two_rows + [loops("lip_a", span("one", 1, 4), "front"), loops("lip_b", span("one", 1, 4), "front"),
                      route("ra", [work("lip_a", 1, 4)], 4), route("rb", [work("lip_b", 1, 4)], 4)],
          existing=E, final=["two", "ra", "rb"]), expect="REJECT")
show("hold alias A then FreeLoops again",
     plan(two_rows + [loops("lip_a", span("one", 1, 4), "front"), hold("h", [span("lip_a", 1, 4)]),
                      loops("lip_b", span("one", 1, 4), "front")], existing=E, final=["two", "h"]), expect="REJECT")
show("split a reserved lip again (BLO of a front_loop site)",
     plan(two_rows + [loops("lip_a", span("one", 1, 4), "front"), route("ra", [work("lip_a", 1, 4, loop="back")], 4)],
          existing=E, final=["two", "ra"]), expect="REJECT")
show("FLO on a chain underside / row end",
     plan([{"kind": "foundation_chain", "id": "ch", "label": "ch", "chains": 5, "work_face": "underside",
            "other_face": "top"}, route("r", [work("ch", 1, 4, face="underside", loop="front")], 4),
           hold("o", [span("ch", 1, 4)])], final=["r", "o"]), expect="REJECT")

print("== 2. three working positions from one chain stitch (top FLO + reserved BLO + back bump) ==")
status, result = show("chain top worked FLO, BLO lip reserved, underside worked",
                      plan([{"kind": "foundation_chain", "id": "ch", "label": "ch", "chains": 5,
                             "work_face": "top", "other_face": "underside"},
                            route("r1", [work("ch", 1, 4, loop="front")], 4),
                            loops("lip", span("ch", 1, 4), "back"),
                            route("r2", [work("lip", 1, 4)], 4),
                            route("r3", [work("ch", 1, 4, face="underside")], 4)], final=["r1", "r2", "r3"]))

print("== 3. row ends ==")
show("row end of a route that is not flat (segment)",
     plan([route("one", [work("seed", 1, 4)], 4), row_edges("side", [("one", "left")])], existing=E,
          final=["one", "side"]), expect="REJECT")
show("row end of joined_rows",
     plan([route("one", [work("seed", 1, 4)], 4, mode="joined_rows", side="RS", row_direction="forward",
                 turn="counterclockwise", closure="before_turn"), row_edges("side", [("one", "left")])],
          existing=E, final=["one", "side"]), expect="REJECT")
show("row end of a row not yet made", plan([row_edges("side", [("one", "left")]), flat("one", [work("seed", 1, 4)], 4)],
                                            existing=E, final=["one", "side"]), expect="REJECT")
show("same row end twice inside one RowEdges",
     plan([flat("one", [work("seed", 1, 4)], 4), row_edges("side", [("one", "left"), ("one", "left")])],
          existing=E, final=["one", "side"]), expect="REJECT")
status, result = show("same row end under two step ids (alias), one listed final",
                      plan([flat("one", [work("seed", 1, 4)], 4), row_edges("side_a", [("one", "left")]),
                            row_edges("side_b", [("one", "left")])], existing=E, final=["one", "side_a"]))
if status == "ACCEPT":
    print("   created:", result.created_sites, "| same site:", result.edges["side_a"] == result.edges["side_b"])
show("same row end worked through both aliases",
     plan([flat("one", [work("seed", 1, 4)], 4), row_edges("side_a", [("one", "left")]),
           row_edges("side_b", [("one", "left")]), route("ra", [work("side_a", 1)], 1),
           route("rb", [work("side_b", 1)], 1)], existing=E, final=["one", "ra", "rb"]), expect="REJECT")

# A row whose far end is joined to the base by binding slip stitches: is that end still a free row end?
status, result = show("row end taken at the end that is slip-stitched to the base (attached ribbing shape)",
                      plan([flat("rib1", [work("rib", 1, 3), work("body", 1, 2, stitch="slst", disposition="binding")], 3),
                            row_edges("joined_end", [("rib1", "right")]), route("pick", [work("joined_end", 1)], 1),
                            hold("rest", [span("body", 3, 6)])],
                           existing=[("rib", 3), ("body", 6)], final=["rib1", "pick", "rest"]))
if status == "ACCEPT":
    print("   row_end_site event:", [(e.sources, e.outputs) for e in result.events if e.stitch == "row_end_site"])

# A row buried in the middle of the fabric: rows one..three, then the middle row's end is used twice over
status, result = show("row ends listed in zig-zag order across both sides",
                      plan([flat("one", [work("seed", 1, 4)], 4),
                            flat("two", [work("one", 1, 4, direction="reverse")], 4, side="WS", direction="reverse"),
                            flat("three", [work("two", 1, 4, direction="reverse")], 4, turn="none"),
                            row_edges("zig", [("one", "left"), ("three", "right"), ("two", "left"), ("one", "right")]),
                            route("band", [work("zig", 1, 4)], 4)], existing=E, final=["three", "band"]))
if status == "ACCEPT":
    from app.utils.working_path_export import step_text
    print("   markdown step text:", step_text(result.plan.steps[3]))

print("== 4. corners ==")
show("corner face without corner_sites", plan([route("r", [work("seed", 1, 1), {"kind": "chain", "id": "br", "count": 2,
                                                                        "route_face": "top"}, work("seed", 4, 4)], 4),
                                               hold("h", [span("seed", 2, 3), span("br", 1, 2, face="underside"),
                                                          span("br", 1, 1, face="corner_start")])],
                                              existing=E, final=["r", "h"]), expect="REJECT")
status, result = show("corner sites on a bridge that skips nothing (adjacent stitches)",
                      plan([route("r", [work("seed", 1, 2), {"kind": "chain", "id": "br", "count": 2, "route_face": "top",
                                                             "corner_sites": True}, work("seed", 3, 4)], 6),
                            hold("h", [span("br", 1, 2, face="underside"), span("br", 1, 1, face="corner_start"),
                                       span("br", 1, 1, face="corner_end")]),
                            route("sleeve", [work("h", 1, 4)], 4)], existing=E, final=["r", "sleeve"]))
show("corner sites must be accounted for", plan([route("r", [work("seed", 1, 1), {"kind": "chain", "id": "br",
                                                                               "count": 2, "route_face": "top",
                                                                               "corner_sites": True},
                                                             work("seed", 4, 4)], 4),
                                                 hold("h", [span("seed", 2, 3), span("br", 1, 2, face="underside")])],
                                                existing=E, final=["r", "h"]), expect="REJECT")

print("== 5. 'leave unworked' declarations ==")
chain = {"kind": "foundation_chain", "id": "ch", "label": "ch", "chains": 9, "work_face": "underside",
         "other_face": "top"}
status, result = show("both faces of the same chain stitches retired as 'unused chain face' in mid-row",
                      plan([chain, route("r", [work("ch", 1, 3, face="underside"), work("ch", 6, 8, face="underside")], 6),
                            finish("gap_under", span("ch", 4, 5, face="underside"), "unused_chain_face"),
                            finish("all_top", span("ch", 1, 8), "unused_chain_face")], final=["r"]))
if status == "ACCEPT":
    print("   inventory:", result.to_dict()["inventory_accounting"])
    from app.utils.working_path_format import route_formula
    print("   formula of r:", route_formula(result.plan.steps[1], events=result.events))
show("ordinary stitch heads retired as unused chain face",
     plan([finish("f", span("seed", 1, 4), "unused_chain_face")], existing=E), expect="REJECT")
status, result = show("a whole live row retired as finished_border, plan closes with nothing left",
                      plan([flat("one", [work("seed", 1, 4)], 4), finish("f", span("one", 1, 4))], existing=E))
