"""Area 4: Seam — pairing order, self-seams, held sites, loops left free, tracked start."""
from _common import attempt, plan, route, show, span, work
from app.utils.working_path_export import export_working_path_markdown


def hold(id_, spans):
    return {"kind": "hold", "id": id_, "label": id_, "spans": spans}


def flat(id_, ops, expected, *, side="RS", direction="forward", turn="counterclockwise", **extra):
    return route(id_, ops, expected, mode="flat", side=side, row_direction=direction, turn=turn, **extra)


def loops(id_, source, loop):
    return {"kind": "free_loops", "id": id_, "label": id_, "source": source, "loop": loop}


def seam(id_, left, right, **extra):
    data = {"kind": "seam", "id": id_, "label": extra.pop("label", id_), "left": left, "right": right}
    data.update(extra)
    return data


E = [("a", 4), ("b", 4)]
print("== 1. pairing order is taken as written ==")
for name, right in (("forward/forward", span("b", 1, 4)), ("forward/reverse", span("b", 1, 4, direction="reverse"))):
    status, result = show(f"a 1-4 against b ({name})", plan([seam("s", span("a", 1, 4), right)], existing=E))
    if status == "ACCEPT":
        print("   pairs:", [(e.sources[0].position, e.sources[1].position) for e in result.events])

print("== 2. a strip seamed to itself: both pairings of its own first and last rows ==")
STRIP = [
    {"kind": "foundation_chain", "id": "ch", "label": "起链", "chains": 5, "work_face": "underside", "other_face": "top"},
    flat("r1", [work("ch", 1, 4, face="underside")], 4, label="第1行"),
    flat("r2", [work("r1", 1, 4, direction="reverse", loop="back")], 4, side="WS", direction="reverse", label="第2行"),
    flat("r3", [work("r2", 1, 4, direction="reverse", loop="back")], 4, label="第3行"),
    flat("r4", [work("r3", 1, 4, direction="reverse", loop="back")], 4, side="WS", direction="reverse", turn="none",
         label="第4行"),
    loops("lip", span("r1", 1, 4), "front"),
    hold("outside", [span("ch", 1, 4)]),
]
# Geometry by construction (each row is worked back over the previous one):
#   r1 index i sits over chain slot i; r2 index i sits over r1 index 5-i; r3 index i over r2 index 5-i;
#   r4 index i over r3 index 5-i.  So r4 index i is in the same column as r1 index 5-i... chained:
#   r4[i] -> r3[5-i] -> r2[i] -> r1[5-i].  The hook is on r4 index 4, which is in the column of r1 index 1.
for name, right in (("aligned: r4 4..1 with lip 1..4", span("lip", 1, 4)),
                    ("crossed: r4 4..1 with lip 4..1", span("lip", 1, 4, direction="reverse"))):
    status, result = show(name, plan(STRIP + [seam("s", span("r4", 1, 4, direction="reverse"), right, left_loop="back")],
                                     final=["outside"], input_origin="manual_instructions"))
    if status == "ACCEPT":
        print("   pairs (r4 index, r1 index):", [(e.sources[0].position, e.sources[1].position) for e in result.events
                                                  if e.route == "s"])
        print("   text:", [l for l in export_working_path_markdown(result.plan).splitlines() if "`s`" in l][0][:400])

print("== 3. self reference / aliases ==")
show("same span on both sides", plan([seam("s", span("a", 1, 4), span("a", 1, 4))], existing=E, final=["b"]),
     expect="REJECT")
show("same sites through a hold alias", plan([hold("h", [span("a", 1, 2)]), seam("s", span("h", 1, 2), span("h", 1, 2,
                                                                                               direction="reverse"))],
                                           existing=E, final=["b"]), expect="REJECT")
show("left through alias, right through original name", plan([hold("h", [span("a", 1, 2)]),
                                                             seam("s", span("h", 1, 2), span("a", 1, 2))],
                                                            existing=E, final=["b"]), expect="REJECT")
show("an edge folded onto itself (a 1-2 against a 4-3)",
     plan([seam("s", span("a", 1, 2), span("a", 3, 4, direction="reverse"))], existing=E, final=["b"]), expect="ACCEPT")
show("overlapping halves (a 1-3 against a 3-1)",
     plan([seam("s", span("a", 1, 3), span("a", 1, 3, direction="reverse"))], existing=E, final=["b"]), expect="REJECT")
status, _ = show("a stitch's BLO seamed to the same stitch's reserved FLO (lip made by an earlier BLO row)",
                 plan([flat("r1", [work("a", 1, 4)], 4),
                       flat("r2", [work("r1", 1, 2, direction="reverse", loop="back")], 2, side="WS", direction="reverse"),
                       loops("lip", span("r1", 1, 2), "front"),
                       seam("s", span("r1", 3, 4), span("lip", 1, 2), left_loop="back"),
                       hold("rest", [span("b", 1, 4)])], existing=E, final=["r2", "rest"]))

print("== 4. unequal lengths, consumed / held sites ==")
show("3 against 4", plan([seam("s", span("a", 1, 3), span("b", 1, 4))], existing=E), expect="REJECT")
show("seam over stitches already worked", plan([route("r", [work("a", 1, 4)], 4), seam("s", span("a", 1, 4), span("b", 1, 4))],
                                               existing=E, final=["r"]), expect="REJECT")
show("seam over a binding edge of an earlier seam",
     plan([seam("s", span("a", 1, 2), span("b", 1, 2)), seam("t", span("s", 1, 2, face="binding"), span("a", 3, 4)),
           hold("rest", [span("b", 3, 4)])], existing=E, final=["rest"]), expect="REJECT")

print("== 5. loops left free by a seam ==")
status, result = show("BLO/BLO seam, then the remaining front loops of both edges reserved and worked",
                      plan([seam("s", span("a", 1, 4), span("b", 1, 4), left_loop="back", right_loop="back"),
                            loops("a_front", span("a", 1, 4), "front"), loops("b_front", span("b", 1, 4), "front"),
                            route("edge", [work("a_front", 1, 4), work("b_front", 1, 4, direction="reverse")], 8)],
                           existing=E, final=["edge"]))
show("free loop on the side the seam itself used", plan([seam("s", span("a", 1, 4), span("b", 1, 4), left_loop="back"),
                                                        loops("x", span("a", 1, 4), "back")], existing=E), expect="REJECT")
show("free loop of the side that was seamed through both loops",
     plan([seam("s", span("a", 1, 4), span("b", 1, 4), left_loop="back"), loops("x", span("b", 1, 4), "front")],
          existing=E), expect="REJECT")
status, result = show("seam leaves front loops that are never mentioned again",
                      plan([seam("s", span("a", 1, 4), span("b", 1, 4), left_loop="back", right_loop="back")], existing=E))
if status == "ACCEPT":
    print("   inventory:", result.to_dict()["inventory_accounting"], "| created/consumed:", result.created_sites,
          result.consumed_sites)
show("half-loop seam on a chain underside / reserved lip", plan([
    {"kind": "foundation_chain", "id": "ch", "label": "ch", "chains": 5, "work_face": "underside", "other_face": "top"},
    seam("s", span("ch", 1, 2, face="underside"), span("ch", 3, 4, face="underside", direction="reverse"), left_loop="back"),
    hold("o", [span("ch", 1, 4)])], final=["o"]), expect="REJECT")

print("== 6. untracked plans: seam start is not tied to anything ==")
show("untracked: seam begins at the far end of the last row",
     plan(STRIP + [seam("s", span("r4", 1, 4), span("lip", 1, 4, direction="reverse"), left_loop="back")],
          final=["outside"]))
