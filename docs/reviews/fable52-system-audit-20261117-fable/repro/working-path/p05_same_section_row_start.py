"""Same-section turned rows: order is checked, the START position is not.

check_turned_continuation (working_path.py:744-767) only requires the indices on the
previous row to be strictly decreasing.  It never compares the first source with the
place where the previous row ended (the hook).  So inside ONE section, with every
side/direction/turn declared, a row can begin k stitches away from the hook.
"""
from _common import attempt, pdf_paragraphs, plan, route, show, span, work
from app.utils.working_path_export import export_working_path_markdown
from app.utils.working_recipe_export import export_working_recipe_pdf


def hold(id_, spans, label=None):
    return {"kind": "hold", "id": id_, "label": label or id_, "spans": spans}


def panel(second_source, held, *, tracked):
    steps = []
    if tracked:
        steps.append({"kind": "new_yarn", "id": "start", "label": "起线", "yarn": "main",
                      "method": "foundation_chain", "side": "RS"})
    steps += [
        {"kind": "foundation_chain", "id": "ch", "label": "起链", "chains": 21, "work_face": "underside",
         "other_face": "top"},
        route("r1", [work("ch", 1, 20, face="underside")], 20, label="衣片 第 1 行", section="panel", row_number=1,
              mode="flat", side="RS", row_direction="forward", turn="counterclockwise", turning_chains=1),
        route("r2", [work("r1", *second_source, direction="reverse")], 10, label="衣片 第 2 行", section="panel",
              row_number=2, mode="flat", side="WS", row_direction="reverse"),
        hold("left_over", [span("r1", *held)], "第 1 行余下的 10 针"),
        hold("outside", [span("ch", 1, 20)], "起链另一侧"),
    ]
    if tracked:
        steps.append({"kind": "fasten_off", "id": "end", "label": "收线", "yarn": "main",
                      "source": span("r2", 10), "tail_cm": 15.0})
    return plan(steps, final=["r2", "left_over", "outside"], yarn_tracking=tracked,
                input_origin="manual_instructions", title="同段短行")


for tracked in (False, True):
    print(f"== yarn_tracking={tracked} ==")
    # Row 1 is worked 1..20 and ends at stitch 20 (hook there).  After turning:
    ok_status, ok = show("A  row 2 works r1 stitches 20..11 (starts under the hook, stops early)",
                         panel((11, 20), (1, 10), tracked=tracked), expect="ACCEPT")
    bad_status, bad = show("B  row 2 works r1 stitches 10..1 (starts 10 stitches away from the hook)",
                           panel((1, 10), (11, 20), tracked=tracked))
    if bad_status == "ACCEPT":
        first = next(e for e in bad.events if e.route == "r2")
        last_r1 = [e for e in bad.events if e.route == "r1"][-1]
        print("   hook after row 1 is on:", last_r1.outputs[-1], "| first stitch of row 2 goes into:", first.sources[0])
        for name, result in (("A", ok), ("B", bad)):
            _, paragraphs = pdf_paragraphs(export_working_recipe_pdf, result.plan)
            start = paragraphs.index("行")
            cells = paragraphs[start:start + 15]
            print(f"   recipe-PDF table cells for plan {name}:", cells[5:15])
        md_a = [l for l in export_working_path_markdown(ok.plan).splitlines() if "`r2`" in l][0]
        md_b = [l for l in export_working_path_markdown(bad.plan).splitlines() if "`r2`" in l][0]
        print("   markdown A:", md_a)
        print("   markdown B:", md_b)

print("== other shapes the same-section check lets through ==")
E = [("seed", 12)]


def rows(second_ops, expected, extra=(), final=("r2",)):
    return plan([
        route("r1", [work("seed", 1, 12)], 12, section="p", row_number=1, mode="flat", side="RS",
              row_direction="forward", turn="counterclockwise"),
        route("r2", second_ops, expected, section="p", row_number=2, mode="flat", side="WS", row_direction="reverse"),
        *extra], existing=E, final=list(final))


show("row 2 skips every other stitch of row 1 (12,10,8,...) with the skipped ones held",
     rows([work("r1", 12, direction="reverse"), work("r1", 10, direction="reverse"), work("r1", 8, direction="reverse")], 3,
          extra=[hold("gaps", [span("r1", 1, 7), span("r1", 9), span("r1", 11)])], final=("r2", "gaps")))
show("row 2 = two far-apart chunks (12..10 then 3..1), middle held, no chain between them",
     rows([work("r1", 10, 12, direction="reverse"), work("r1", 1, 3, direction="reverse")], 6,
          extra=[hold("mid", [span("r1", 4, 9)])], final=("r2", "mid")))
show("control: same chunks in ascending order are rejected",
     rows([work("r1", 1, 3, direction="reverse"), work("r1", 10, 12, direction="reverse")], 6,
          extra=[hold("mid", [span("r1", 4, 9)])], final=("r2", "mid")), expect="REJECT")
