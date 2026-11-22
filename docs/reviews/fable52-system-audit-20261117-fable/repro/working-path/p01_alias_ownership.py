"""Area 1: raw positions, alias ownership, Hold vs EdgePath (JSON path, same as CLI/UI)."""
from _common import attempt, plan, route, show, span, work

E = [("seed", 12)]


def hold(id_, spans):
    return {"kind": "hold", "id": id_, "label": id_, "spans": spans}


def epath(id_, spans):
    return {"kind": "edge_path", "id": id_, "label": id_, "spans": spans}


print("== 1. bounds ==")
show("last beyond edge", plan([route("r", [work("seed", 1, 13)], 13)], existing=E, final=["r"]), expect="REJECT")
show("first=0", plan([route("r", [work("seed", 0, 12)], 13)], existing=E, final=["r"]), expect="REJECT")
show("first>last", plan([route("r", [work("seed", 5, 4)], 1)], existing=E, final=["r"]), expect="REJECT")
show("float position", plan([route("r", [{"kind": "work", "source": {"edge": "seed", "first": 1.0, "last": 12}}], 12)],
                            existing=E, final=["r"]), expect="REJECT")
show("string position", plan([route("r", [{"kind": "work", "source": {"edge": "seed", "first": "1", "last": 12}}], 12)],
                             existing=E, final=["r"]), expect="REJECT")
show("unknown face on edge", plan([route("r", [work("seed", 1, 12, face="underside")], 12)],
                                  existing=E, final=["r"]), expect="REJECT")

print("== 2. overlapping / double booking ==")
show("two ops overlap in one route", plan([route("r", [work("seed", 1, 6), work("seed", 6, 12)], 13)],
                                         existing=E, final=["r"]), expect="REJECT")
show("same site twice inside one hold", plan([hold("h", [span("seed", 1, 6), span("seed", 6, 12)])],
                                            existing=E, final=["h"]), expect="REJECT")
show("hold re-holds a held site", plan([hold("h1", [span("seed", 1, 6)]), hold("h2", [span("seed", 6, 12)]),
                                       hold("h3", [span("h1", 1, 2)])], existing=E, final=["h1", "h2"]), expect="REJECT")
show("hold over original name of held site", plan([hold("h1", [span("seed", 1, 6)]), hold("h3", [span("seed", 6, 6)]),
                                                  hold("h4", [span("seed", 5, 5)])], existing=E, final=["h1"]),
     expect="REJECT")

print("== 3. edge_path transfer chains ==")
base = [hold("h1", [span("seed", 1, 6)]), epath("p1", [span("h1", 1, 6, direction="reverse")]),
        epath("p2", [span("p1", 1, 3), span("seed", 7, 12)])]
show("re-path from a path (p1->p2) and partition", plan(base + [epath("p3", [span("p1", 4, 6)])],
                                                    existing=E, final=["p2", "p3"]), expect="ACCEPT")
show("old hold name after transfer (work)", plan(base + [route("r", [work("h1", 1, 3)], 3)],
                                                 existing=E, final=["p2", "r"]), expect="REJECT")
show("old path name after second transfer (work)", plan(base + [route("r", [work("p1", 1, 3)], 3)],
                                                        existing=E, final=["p2", "r"]), expect="REJECT")
show("original edge after transfer (work)", plan(base + [route("r", [work("seed", 1, 3)], 3)],
                                                 existing=E, final=["p2", "r"]), expect="REJECT")
show("hold over a path alias", plan(base + [hold("h9", [span("p2", 1, 2)])], existing=E, final=["p2"]),
     expect="REJECT")
show("edge_path takes reserved site through original name",
     plan([hold("h1", [span("seed", 1, 6)]), epath("p1", [span("seed", 1, 6)])], existing=E, final=["p1"]),
     expect="REJECT")
show("edge_path overlap between spans", plan([epath("p1", [span("seed", 1, 6), span("seed", 6, 12)])],
                                             existing=E, final=["p1"]), expect="REJECT")

print("== 4. reserved sites reached through the original name by every consumer ==")
H = [hold("h1", [span("seed", 1, 6)])]
rest = hold("rest", [span("seed", 7, 12)])
show("work", plan(H + [route("r", [work("seed", 1, 6)], 6)], existing=E, final=["r"]), expect="REJECT")
show("finish_edge", plan(H + [{"kind": "finish_edge", "id": "f", "label": "f", "source": span("seed", 1, 6),
                               "reason": "finished_border"}], existing=E, final=[]), expect="REJECT")
show("seam left", plan(H + [{"kind": "seam", "id": "s", "label": "s", "left": span("seed", 1, 6),
                             "right": span("seed", 7, 12)}], existing=E, final=[]), expect="REJECT")
show("seam right", plan(H + [{"kind": "seam", "id": "s", "label": "s", "left": span("seed", 7, 12),
                              "right": span("seed", 1, 6)}], existing=E, final=[]), expect="REJECT")
show("foundation anchor takes_site",
     plan(H + [{"kind": "foundation_chain", "id": "c", "label": "c", "chains": 3, "work_face": "underside",
                "other_face": "top", "anchor": span("seed", 1)}], existing=E, final=[]), expect="REJECT")
show("buttonhole skipped",
     plan(H + [route("r", [work("seed", 7, 8), {"kind": "chain", "id": "bh", "count": 2, "route_face": "top",
                                                "placement": "buttonhole", "skipped": span("seed", 1, 6)},
                           work("seed", 9, 12, stitch="slst", disposition="binding")], 4)],
          existing=E, final=["r"]), expect="REJECT")
show("new_yarn anchor", plan(H + [{"kind": "new_yarn", "id": "n", "label": "n", "yarn": "y", "method": "standing_sc",
                                   "side": "RS", "anchor": span("seed", 1)}], existing=E, final=["h1"],
                             yarn_tracking=True), expect="REJECT")
show("final edge by original name", plan(H, existing=E, final=["seed"]), expect="REJECT")
show("final edge by hold name + remainder", plan(H + [rest], existing=E, final=["h1", "rest"]), expect="ACCEPT")

print("== 5. scrambled / non-adjacent hold feeding one run of stitches ==")
status, result = show("hold = seed 1-2 then seed 11-12, worked as one run",
                      plan([hold("h", [span("seed", 1, 2), span("seed", 11, 12)]),
                            route("r", [work("h", 1, 4)], 4), hold("mid", [span("seed", 3, 10)])],
                           existing=E, final=["r", "mid"]))
if status == "ACCEPT":
    from app.utils.working_path_format import route_formula
    print("   sources:", [(s.edge, s.position) for e in result.events if e.route == "r" for s in e.sources])
    print("   formula:", route_formula(result.plan.steps[1], events=result.events))

print("== 6. stale membership after transfer ==")
status, result = attempt(plan(base + [epath("p3", [span("p1", 4, 6)])], existing=E, final=["p2", "p3"]))
print("   held_edges:", {k: [s.position for s in v] for k, v in result.held_edges.items()})
payload = result.to_dict()
print("   to_dict held_edges keys:", list(payload["held_edges"]),
      "| site seed/1 listed under:", [k for k, v in payload["held_edges"].items()
                                       if {"edge": "seed", "position": 1, "face": "top"} in v])

print("== 7. positions above 1000 on a long row ==")
long_plan = plan([route("r1", [work("a", 1, 1000), work("b", 1, 1)], 1001)], existing=[("a", 1000), ("b", 1)],
                 final=["r1"])
show("1001-stitch row as final edge", long_plan, expect="ACCEPT")
show("continue the 1001-stitch row (span 1..1001)",
     plan([route("r1", [work("a", 1, 1000), work("b", 1, 1)], 1001), route("r2", [work("r1", 1, 1001)], 1001)],
          existing=[("a", 1000), ("b", 1)], final=["r2"]))
show("continue the 1001-stitch row in two ops (1..1000, 1001..1001)",
     plan([route("r1", [work("a", 1, 1000), work("b", 1, 1)], 1001),
           route("r2", [work("r1", 1, 1000), work("r1", 1001, 1001)], 1001)],
          existing=[("a", 1000), ("b", 1)], final=["r2"]))
