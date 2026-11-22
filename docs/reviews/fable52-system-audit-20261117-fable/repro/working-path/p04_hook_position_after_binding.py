"""Where does the model think the hook is? (current_loop after a row that contains binding slip stitches)

Route.route() ends with:
    self.current_loop = binding_sites[-1] if binding_sites else output[-1]      (working_path.py:738)
so the "live loop" is put on the LAST BINDING slip stitch whenever the row contains any,
even when working stitches were made after it.
"""
from _common import attempt, plan, route, show, span, work
from app.utils.working_path_export import export_working_path_markdown


def new_yarn(id_, yarn, *, method="foundation_chain", side="RS", anchor=None):
    data = {"kind": "new_yarn", "id": id_, "label": id_, "yarn": yarn, "method": method, "side": side}
    if anchor is not None:
        data["anchor"] = anchor
    return data


def fasten(id_, yarn, source):
    return {"kind": "fasten_off", "id": id_, "label": "收线", "yarn": yarn, "source": source, "tail_cm": 15.0}


def hold(id_, spans):
    return {"kind": "hold", "id": id_, "label": id_, "spans": spans}


# A band row that first slip-stitches into 2 base stitches (joins), then works 3 sc along the band.
# Physically the hook finishes on the 3rd sc (band_row/3).
def band(fasten_source):
    steps = [
        new_yarn("join", "main", method="standing_sc", anchor=span("rib", 1)),
        route("band_row", [
            work("rib", 1, stitch="standing_sc"),
            work("body", 1, 2, stitch="slst", disposition="binding"),
            work("rib", 2, 4),
        ], 4, label="接合后沿肋纹返回", mode="flat", side="RS", row_direction="forward"),
        fasten("end", "main", fasten_source),
        hold("rest", [span("body", 3, 6)]),
    ]
    return plan(steps, existing=[("rib", 4), ("body", 6)], final=["band_row", "rest"], yarn_tracking=True,
                input_origin="manual_instructions")


print("row = standing sc, 2 binding slip stitches into the base, then 3 more sc (hook ends on the 4th stitch)")
show("fasten off at the last stitch actually made (band_row/4)", band(span("band_row", 4)))
status, result = show("fasten off 'at' the 2nd binding slip stitch (band_row binding/2)",
                      band(span("band_row", 2, face="binding")))
if status == "ACCEPT":
    seg = result.yarn_accounting["segments"]["main"]
    print("   recorded loop_reference:", seg["loop_reference"])
    order = [(e.stitch, e.role, [(s.edge, s.position, s.face) for s in e.outputs]) for e in result.events
             if e.route == "band_row"]
    print("   event order in the row:", order)
    text = export_working_path_markdown(result.plan)
    print("   exported fasten-off line:", [line for line in text.splitlines() if "收线" in line][0])

# Same thing for the other consumers of current_loop.
def tail(extra_steps, final):
    steps = [
        new_yarn("join", "main", method="standing_sc", anchor=span("rib", 1)),
        route("band_row", [
            work("rib", 1, stitch="standing_sc"),
            work("body", 1, 2, stitch="slst", disposition="binding"),
            work("rib", 2, 4),
        ], 4, mode="flat", side="RS", row_direction="forward"),
        hold("rest", [span("body", 3, 6)]),
    ] + extra_steps
    return plan(steps, existing=[("rib", 4), ("body", 6)], final=final, yarn_tracking=True)


ext = {"kind": "foundation_chain", "id": "ext", "label": "ext", "chains": 3, "work_face": "underside",
       "other_face": "top", "anchor_mode": "continues_loop"}
show("continue a chain from the last stitch actually made",
     tail([dict(ext, anchor=span("band_row", 4)),
           route("r2", [work("ext", 1, 2, face="underside")], 2, mode="flat", side="RS", row_direction="forward"),
           hold("o", [span("ext", 1, 2)])], ["band_row", "rest", "r2", "o"]))
show("continue a chain from the binding slip stitch",
     tail([dict(ext, anchor=span("band_row", 2, face="binding")),
           route("r2", [work("ext", 1, 2, face="underside")], 2, mode="flat", side="RS", row_direction="forward"),
           hold("o", [span("ext", 1, 2)])], ["band_row", "rest", "r2", "o"]))
show("park at the last stitch actually made",
     tail([{"kind": "park_yarn", "id": "p", "label": "p", "yarn": "main", "source": span("band_row", 4)}],
          ["band_row", "rest"]))
show("seam starting at the last stitch actually made",
     tail([{"kind": "seam", "id": "s", "label": "s", "left": span("band_row", 3, 4, direction="reverse"),
            "right": span("rest", 1, 2)}], ["band_row", "rest"]))

print("-- control: binding slip stitches last in the row (what the shipped generators emit) --")
steps = [new_yarn("join", "main", method="standing_sc", anchor=span("rib", 1)),
         route("band_row", [work("rib", 1, stitch="standing_sc"), work("rib", 2, 4),
                            work("body", 1, 2, stitch="slst", disposition="binding")], 4,
               mode="flat", side="RS", row_direction="forward"),
         fasten("end", "main", span("band_row", 2, face="binding")), hold("rest", [span("body", 3, 6)])]
show("binding last, fasten off at the binding stitch",
     plan(steps, existing=[("rib", 4), ("body", 6)], final=["band_row", "rest"], yarn_tracking=True), expect="ACCEPT")
