"""Area 3: yarn control state machine (yarn_tracking=true), through the JSON loader."""
from _common import attempt, plan, route, show, span, work


def hold(id_, spans):
    return {"kind": "hold", "id": id_, "label": id_, "spans": spans}


def flat(id_, ops, expected, *, side="RS", direction="forward", turn="none", **extra):
    return route(id_, ops, expected, mode="flat", side=side, row_direction=direction, turn=turn, **extra)


def new_yarn(id_, yarn, *, method="foundation_chain", side="RS", anchor=None):
    data = {"kind": "new_yarn", "id": id_, "label": id_, "yarn": yarn, "method": method, "side": side}
    if anchor is not None:
        data["anchor"] = anchor
    return data


def chain(id_, n=4, **extra):
    data = {"kind": "foundation_chain", "id": id_, "label": id_, "chains": n, "work_face": "underside",
            "other_face": "top"}
    data.update(extra)
    return data


def fasten(id_, yarn, source, tail=15.0):
    return {"kind": "fasten_off", "id": id_, "label": id_, "yarn": yarn, "source": source, "tail_cm": tail}


def park(id_, yarn, source):
    return {"kind": "park_yarn", "id": id_, "label": id_, "yarn": yarn, "source": source}


def resume(id_, yarn):
    return {"kind": "resume_yarn", "id": id_, "label": id_, "yarn": yarn}


def weave(id_, yarn, ends):
    return {"kind": "weave_ends", "id": id_, "label": id_, "yarn": yarn, "ends": ends}


def finish(id_, source, reason="finished_border"):
    return {"kind": "finish_edge", "id": id_, "label": id_, "source": source, "reason": reason}


START = [new_yarn("n1", "main"), chain("ch"),
         flat("row", [work("ch", 1, 3, face="underside")], 3), hold("outside", [span("ch", 1, 3)])]
FINAL = ["row", "outside"]


def tracked(steps, final=FINAL, **extra):
    return plan(steps, final=final, yarn_tracking=True, **extra)


print("== baseline ==")
show("baseline chain + row", tracked(START), expect="ACCEPT")

print("== new yarn / anchors ==")
show("work with no yarn at all", tracked(START[1:]), expect="REJECT")
show("cut immediately after NewYarn (no chain, no stitch)",
     tracked([new_yarn("n1", "main"), fasten("f", "main", span("seed", 1))], final=["seed"], existing=[("seed", 3)]),
     expect="REJECT")
show("cut after only the foundation chain", tracked([new_yarn("n1", "main"), chain("ch"),
                                                     fasten("f", "main", span("ch", 1, face="underside")),
                                                     hold("a", [span("ch", 1, 3)]),
                                                     hold("b", [span("ch", 1, 3, face="underside")])], final=["a", "b"]),
     expect="REJECT")
show("park after only the foundation chain", tracked([new_yarn("n1", "main"), chain("ch"),
                                                      park("p", "main", span("ch", 1, face="underside")),
                                                      hold("a", [span("ch", 1, 3)]),
                                                      hold("b", [span("ch", 1, 3, face="underside")])], final=["a", "b"]),
     expect="REJECT")
show("NewYarn then nothing (dangling 'ready' strand)",
     tracked(START + [fasten("f", "main", span("row", 3)), new_yarn("n2", "ghost")]))
show("re-use a closed strand name", tracked(START + [fasten("f", "main", span("row", 3)), new_yarn("n2", "main")]),
     expect="REJECT")
show("re-use a parked strand name", tracked(START + [park("p", "main", span("row", 3)), new_yarn("n2", "main")]),
     expect="REJECT")
show("second strand while first is live", tracked(START + [new_yarn("n2", "other")]), expect="REJECT")
show("standing sc at a different site than declared",
     tracked(START + [fasten("f", "main", span("row", 3)),
                      new_yarn("n2", "b", method="standing_sc", anchor=span("row", 1)),
                      route("r2", [work("row", 2, stitch="standing_sc"), work("row", 3)], 2),
                      hold("left", [span("row", 1)])], final=["r2", "left", "outside"]), expect="REJECT")
show("standing sc anchor reached through reversed span of length 1 (same site)",
     tracked(START + [fasten("f", "main", span("row", 3)),
                      new_yarn("n2", "b", method="standing_sc", anchor=span("row", 1)),
                      route("r2", [work("row", 1, direction="reverse", stitch="standing_sc"), work("row", 2, 3)], 3),
                      fasten("f2", "b", span("r2", 3))], final=["r2", "outside"]), expect="ACCEPT")
show("first stitch after standing-sc join is a plain sc instead",
     tracked(START + [fasten("f", "main", span("row", 3)),
                      new_yarn("n2", "b", method="standing_sc", anchor=span("row", 1)),
                      route("r2", [work("row", 1, 3)], 3)], final=["r2", "outside"]), expect="REJECT")
show("standing sc in the middle of a live strand",
     tracked(START + [route("r2", [work("row", 3, direction="reverse"), work("row", 2, stitch="standing_sc"),
                                   work("row", 1)], 3, side="RS")], final=["r2", "outside"]), expect="REJECT")
show("anchor retired between NewYarn and its first stitch",
     tracked(START + [fasten("f", "main", span("row", 3)),
                      new_yarn("n2", "b", method="standing_sc", anchor=span("row", 1)),
                      finish("fin", span("row", 1)),
                      route("r2", [work("row", 1, stitch="standing_sc"), work("row", 2, 3)], 3)],
             final=["r2", "outside"]), expect="REJECT")
show("independent chain while a strand is live", tracked(START + [chain("ch2")]), expect="REJECT")
show("new independent chain borrowing an old stitch as root (takes_site)",
     tracked(START + [fasten("f", "main", span("row", 3)), new_yarn("n2", "b"),
                      chain("ch2", anchor=span("row", 1))], final=FINAL), expect="REJECT")

print("== park / resume ==")
PARKED = START + [park("p", "main", span("row", 3))]
show("work directly from a parked strand", tracked(PARKED + [flat("r2", [work("row", 1, 3)], 3)], final=["r2", "outside"]),
     expect="REJECT")
show("resume a strand that was never parked", tracked(START + [resume("r", "main")]), expect="REJECT")
show("resume a closed strand", tracked(START + [fasten("f", "main", span("row", 3)), resume("r", "main")]), expect="REJECT")
show("park at a site that is not the live loop", tracked(START + [park("p", "main", span("row", 1))]), expect="REJECT")
show("fasten off a parked strand without resuming", tracked(PARKED + [fasten("f", "main", span("row", 3))]),
     expect="REJECT")
show("weave the finishing end of a parked strand", tracked(PARKED + [weave("w", "main", "finishing")]), expect="REJECT")

status, result = show(
    "resume a strand whose loop stitch was meanwhile worked over by another strand, then chain on from it",
    tracked(PARKED + [new_yarn("n2", "b", method="standing_sc", anchor=span("row", 1)),
                      flat("over", [work("row", 1, stitch="standing_sc"), work("row", 2, 3)], 3),
                      fasten("f2", "b", span("over", 3)),
                      resume("res", "main"),
                      chain("ext", 3, anchor=span("row", 3), anchor_mode="continues_loop"),
                      flat("tail", [work("ext", 1, 2, face="underside")], 2),
                      fasten("f1", "main", span("tail", 2)),
                      hold("ext_out", [span("ext", 1, 2)])],
            final=["over", "tail", "outside", "ext_out"]))
if status == "ACCEPT":
    print("   parked loop site consumed by:", [e.route for e in result.events
                                              if any(s.edge == "row" and s.position == 3 for s in e.sources)
                                              and e.role == "working"])

print("== fasten off / weave ==")
show("fasten off at the wrong stitch", tracked(START + [fasten("f", "main", span("row", 1))]), expect="REJECT")
show("fasten off twice", tracked(START + [fasten("f", "main", span("row", 3)), fasten("g", "main", span("row", 3))]),
     expect="REJECT")
show("weave finishing end before cutting", tracked(START + [weave("w", "main", "finishing")]), expect="REJECT")
show("weave starting end, then 'both'", tracked(START + [weave("w", "main", "starting"),
                                                        fasten("f", "main", span("row", 3)),
                                                        weave("w2", "main", "both")]), expect="REJECT")
show("weave 'both', then starting again", tracked(START + [fasten("f", "main", span("row", 3)),
                                                          weave("w", "main", "both"), weave("w2", "main", "starting")]),
     expect="REJECT")
show("weave an unknown strand", tracked(START + [weave("w", "nope", "starting")]), expect="REJECT")
show("weave starting end of a strand that only chained",
     tracked([new_yarn("n1", "main"), chain("ch"), weave("w", "main", "starting"),
              flat("row", [work("ch", 1, 3, face="underside")], 3), hold("outside", [span("ch", 1, 3)])]),
     expect="REJECT")
status, result = show("border declared finished in place of fastening off (live loop retired, never cut)",
                      tracked(START + [finish("border", span("row", 1, 3)),
                                       finish("chain_border", span("outside", 1, 3), "unused_chain_face")], final=[]))
if status == "ACCEPT":
    print("   yarn_accounting:", {k: v for k, v in result.yarn_accounting.items() if k != "segments"},
          result.yarn_accounting["segments"]["main"]["declared_status"])
status, result = show("live loop stitch retired, then the strand still fastens off 'at' the retired stitch",
                      tracked(START + [finish("border", span("row", 1, 3)), fasten("f", "main", span("row", 3)),
                                       weave("w", "main", "both")], final=["outside"]))

print("== facing side ==")
show("next row on the other side with no turn declared",
     tracked(START + [flat("r2", [work("row", 1, 3, direction="reverse")], 3, side="WS", direction="reverse")],
             final=["r2", "outside"]), expect="REJECT")
status, result = show(
    "NewYarn says RS; chain turns; first row therefore has to be declared WS",
    tracked([new_yarn("n1", "main", side="RS"), chain("ch", turn_after_chain="clockwise"),
             flat("row", [work("ch", 1, 3, face="underside")], 3, side="WS"),
             hold("outside", [span("ch", 1, 3)])]))
show("  ... and the same plan with the first row declared RS",
     tracked([new_yarn("n1", "main", side="RS"), chain("ch", turn_after_chain="clockwise"),
              flat("row", [work("ch", 1, 3, face="underside")], 3, side="RS"),
              hold("outside", [span("ch", 1, 3)])]), expect="REJECT")
show("extension chain from the row end, no turn, then working back along chain and row on the same side",
     tracked(START + [chain("ext", 3, anchor=span("row", 3), anchor_mode="continues_loop"),
                      flat("r2", [work("ext", 1, 2, face="underside"), work("row", 1, 3, direction="reverse")], 5,
                           side="RS", direction="reverse"),
                      hold("ext_out", [span("ext", 1, 2)])], final=["r2", "outside", "ext_out"]))

print("== seam start ==")
RIB = [new_yarn("n1", "main"), chain("ch"),
       flat("r1", [work("ch", 1, 3, face="underside")], 3, turn="counterclockwise"),
       flat("r2", [work("r1", 1, 3, direction="reverse", loop="back")], 3, side="WS", direction="reverse"),
       {"kind": "free_loops", "id": "lip", "label": "lip", "source": span("r1", 1, 3), "loop": "front"},
       hold("outside", [span("ch", 1, 3)])]
show("seam starting at the far end of the last row",
     tracked(RIB + [{"kind": "seam", "id": "s", "label": "s", "left": span("r2", 1, 3),
                     "right": span("lip", 1, 3, direction="reverse")}], final=["outside"]), expect="REJECT")
show("seam started with a brand-new strand (standing join) instead of the live loop",
     tracked(RIB + [fasten("f", "main", span("r2", 3)),
                    new_yarn("n2", "sew", method="standing_sc", anchor=span("r2", 3)),
                    {"kind": "seam", "id": "s", "label": "s", "left": span("r2", 1, 3, direction="reverse"),
                     "right": span("lip", 1, 3)}], final=["outside"]), expect="REJECT")
show("seam from the live loop (declared order A: left reverse / right forward)",
     tracked(RIB + [{"kind": "seam", "id": "s", "label": "s", "left": span("r2", 1, 3, direction="reverse"),
                     "right": span("lip", 1, 3)}, fasten("f", "main", span("s", 3, face="binding"))],
             final=["outside"]), expect="ACCEPT")
show("seam from the live loop (declared order B: left reverse / right reverse)",
     tracked(RIB + [{"kind": "seam", "id": "s", "label": "s", "left": span("r2", 1, 3, direction="reverse"),
                     "right": span("lip", 1, 3, direction="reverse")},
                    fasten("f", "main", span("s", 3, face="binding"))], final=["outside"]))
