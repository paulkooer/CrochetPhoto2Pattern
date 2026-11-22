"""Model-level probes for app.models.working_path: what does a passing compile guarantee?

Each case is a tiny hand-written plan. The script prints whether the model
accepts it and, for accepted plans, where the working loop was left and where
the next stitch is declared. Nothing here certifies physical behaviour; it only
shows which contradictions the checker does and does not reject.
"""
from __future__ import annotations

from pathlib import Path

import app
from app.models.working_path import (
    ChainBridge,
    ExistingEdge,
    FastenOff,
    FinishEdge,
    FoundationChain,
    Hold,
    NewYarn,
    Route,
    Span,
    WeaveEnds,
    Work,
    WorkingPath,
    compile_working_path,
)

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
assert Path(app.__file__).resolve().is_relative_to(REPO), app.__file__


def span(edge, first, last, *, face="top", direction="forward"):
    return Span(edge=edge, first=first, last=last, face=face, direction=direction)


def start(count=6):
    return [
        NewYarn(id="start_yarn", label="起针", yarn="y", method="foundation_chain", side="RS"),
        FoundationChain(id="ch", label="起链", chains=count + 1, work_face="underside", other_face="top"),
        Route(id="r1", label="第1行", section="a", row_number=1, mode="flat", side="RS",
              row_direction="forward", operations=[Work(source=span("ch", 1, count, face="underside"))],
              expected_sites=count, turn="counterclockwise", turning_chains=1),
    ]


def finish(last_row, count=6, extra_final=()):
    return [
        Hold(id="chain_other_side", label="起链另一侧", spans=[span("ch", 1, count, face="top")]),
        FastenOff(id="cut", label="断线", yarn="y", source=span(last_row, count, count), tail_cm=10.0),
        WeaveEnds(id="weave", label="藏线", yarn="y", ends="both"),
    ]


def attempt(name, plan_factory, physical):
    print(f"\n=== {name}")
    print(f"    physical reading: {physical}")
    try:
        result = compile_working_path(plan_factory())
    except Exception as error:  # noqa: BLE001 - report whatever the checker says
        print(f"    MODEL REJECTS: {type(error).__name__}: {str(error)[:300]}")
        return None
    accounting = result.to_dict()["inventory_accounting"]
    print(f"    MODEL ACCEPTS: created={result.created_sites} consumed={result.consumed_sites} "
          f"unconsumed={accounting['unconsumed_sites']} retired_without_work={accounting['retired_without_work']}")
    return result


def loop_then_next(result, previous_row, next_row):
    done = [e for e in result.events if e.route == previous_row and e.role == "working"]
    following = [e for e in result.events if e.route == next_row and e.role == "working"]
    last, first = done[-1].outputs[-1], following[0].sources[0]
    print(f"    working loop after {previous_row}: on its stitch {last.position}; "
          f"first stitch of {next_row} goes into {first.edge} stitch {first.position}")


# 1. Control: within one section the same-order row is rejected.
attempt(
    "T1 control - turned row, same section, previous row worked in the SAME order",
    lambda: WorkingPath(title="t1", input_origin="manual_instructions", yarn_tracking=True, steps=[
        *start(),
        Route(id="r2", label="第2行", section="a", row_number=2, mode="flat", side="WS", row_direction="reverse",
              operations=[Work(source=span("r1", 1, 6))], expected_sites=6),
        *finish("r2"),
    ], final_edges=["r2", "chain_other_side"]),
    "after turning, the loop is on stitch 6 of row 1; a row cannot begin in stitch 1 at the far end",
)

# 2. The same contradiction passes once the row carries a different section name.
r = attempt(
    "T2 - identical steps, but the second row is given a new section name",
    lambda: WorkingPath(title="t2", input_origin="manual_instructions", yarn_tracking=True, steps=[
        *start(),
        Route(id="r2", label="第2行", section="b", row_number=1, mode="flat", side="WS", row_direction="reverse",
              operations=[Work(source=span("r1", 1, 6))], expected_sites=6),
        *finish("r2"),
    ], final_edges=["r2", "chain_other_side"]),
    "same as T1: 6 stitches in, 6 out, but the yarn is at the other end of the row and no cut/rejoin is declared",
)
if r:
    loop_then_next(r, "r1", "r2")

# 3. Same contradiction with no section at all (plain flat rows).
r = attempt(
    "T3 - identical steps with no section on the second row",
    lambda: WorkingPath(title="t3", input_origin="manual_instructions", yarn_tracking=True, steps=[
        *start(),
        Route(id="r2", label="第2行", mode="flat", side="WS", row_direction="reverse",
              operations=[Work(source=span("r1", 1, 6))], expected_sites=6),
        *finish("r2"),
    ], final_edges=["r2", "chain_other_side"]),
    "same as T1",
)
if r:
    loop_then_next(r, "r1", "r2")

# 4. No turn declared at all, next row still claims the opposite side is facing: side bookkeeping.
attempt(
    "T4 - row 1 declares no turn, row 2 (new section) claims WS",
    lambda: WorkingPath(title="t4", input_origin="manual_instructions", yarn_tracking=True, steps=[
        NewYarn(id="start_yarn", label="起针", yarn="y", method="foundation_chain", side="RS"),
        FoundationChain(id="ch", label="起链", chains=7, work_face="underside", other_face="top"),
        Route(id="r1", label="第1行", section="a", row_number=1, mode="flat", side="RS", row_direction="forward",
              operations=[Work(source=span("ch", 1, 6, face="underside"))], expected_sites=6),
        Route(id="r2", label="第2行", section="b", row_number=1, mode="flat", side="WS", row_direction="reverse",
              operations=[Work(source=span("r1", 1, 6, direction="reverse"))], expected_sites=6),
        *finish("r2"),
    ], final_edges=["r2", "chain_other_side"]),
    "without turning, the wrong side cannot be facing",
)

# 5. A 'segment' route carries a turn but no side: does the facing side flip?
r = attempt(
    "T5 - a segment-mode row with turn=clockwise sits between two flat rows",
    lambda: WorkingPath(title="t5", input_origin="manual_instructions", yarn_tracking=True, steps=[
        *start(),                                    # RS row, turned -> WS expected
        Route(id="r2", label="第2行(segment)", mode="segment", turn="clockwise", turning_chains=1,
              operations=[Work(source=span("r1", 1, 6, direction="reverse"))], expected_sites=6),
        Route(id="r3", label="第3行", section="c", row_number=1, mode="flat", side="WS", row_direction="reverse",
              operations=[Work(source=span("r2", 1, 6, direction="reverse"))], expected_sites=6),
        *finish("r3"),
    ], final_edges=["r3", "chain_other_side"]),
    "two turns were made (after r1 and after r2), so RS is facing again; r3 declares WS",
)

# 6. An unrelated run of stitches is written off as a buttonhole boundary by a 1-chain 'buttonhole'.
r = attempt(
    "T6 - 1 chain declared as a buttonhole that skips 10 stitches on another edge",
    lambda: WorkingPath(title="t6", input_origin="manual_instructions", existing_edges=[
        ExistingEdge(id="base", count=4), ExistingEdge(id="elsewhere", count=10)],
        steps=[Route(id="row", label="一行", expected_sites=3, operations=[
            Work(source=span("base", 1, 2)),
            ChainBridge(id="hole", count=1, route_face="top", placement="buttonhole",
                        skipped=span("elsewhere", 1, 10)),
            Work(source=span("base", 3, 4), stitch="slst", disposition="binding"),
        ])], final_edges=["row"]),
    "a buttonhole spans the stitches it skips; 1 chain cannot stand in for 10 stitches on a different edge",
)

# 7. finished_border retires any stitches by declaration, including a live edge mid-fabric.
r = attempt(
    "T7 - half of a live row is retired as 'finished_border', the rest worked",
    lambda: WorkingPath(title="t7", input_origin="manual_instructions", existing_edges=[
        ExistingEdge(id="base", count=10)],
        steps=[FinishEdge(id="write_off", label="声明收边", source=span("base", 4, 7), reason="finished_border"),
               Route(id="row", label="一行", expected_sites=6, operations=[
                   Work(source=span("base", 1, 3)), Work(source=span("base", 8, 10))])],
        final_edges=["row"]),
    "stitches 4-7 sit between worked stitches 3 and 8; the row jumps a 4-stitch gap with no chain",
)

# 8. Yarn never fastened off: is that a compile error or only a report flag?
r = attempt(
    "T8 - tracked yarn is never fastened off or woven in",
    lambda: WorkingPath(title="t8", input_origin="manual_instructions", yarn_tracking=True, steps=[
        *start(),
        Hold(id="chain_other_side", label="起链另一侧", spans=[span("ch", 1, 6, face="top")]),
    ], final_edges=["r1", "chain_other_side"]),
    "the piece ends with a live loop and two loose ends",
)
if r:
    report = r.yarn_accounting
    print("    yarn report:", {k: report[k] for k in ("all_fasten_off_steps_present", "all_weave_steps_present")},
          {k: v["declared_status"] for k, v in report["segments"].items()})
