"""Hook travel must agree with the declared facing side, whatever a step is called."""
from typing import Literal

import pytest

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
from app.utils.working_path_export import CHECK_SCOPE


def _two_rows(second: Route, *, count: int = 4, rest: tuple[int, int] | None = None) -> WorkingPath:
    steps: list = [
        Route(id="r1", label="第1行", section="a", row_number=1, mode="flat", side="RS",
              row_direction="forward", operations=[Work(source=Span(edge="base", first=1, last=count))],
              expected_sites=count, turn="counterclockwise", turning_chains=1),
        second,
    ]
    final = ["r2"]
    if rest is not None:
        steps.append(Hold(id="rest", label="未钩部分", spans=[Span(edge="r1", first=rest[0], last=rest[1])]))
        final.append("rest")
    return WorkingPath(title="方向探针", existing_edges=[ExistingEdge(id="base", count=count)],
                       steps=steps, final_edges=final)


def _second(*, direction="reverse", first=1, last=4, **extra) -> Route:
    return Route(id="r2", label="第2行", mode="flat", side="WS", row_direction="reverse",
                 operations=[Work(source=Span(edge="r1", first=first, last=last, direction=direction))],
                 expected_sites=last - first + 1, **extra)


def test_a_turned_row_worked_back_over_the_previous_row_is_accepted():
    compile_working_path(_two_rows(_second(section="a", row_number=2)))
    compile_working_path(_two_rows(_second(section="b", row_number=1)))
    compile_working_path(_two_rows(_second()))


@pytest.mark.parametrize("naming", [
    {"section": "a", "row_number": 2},
    {"section": "b", "row_number": 1},
    {},
])
def test_wrong_direction_after_a_turn_is_rejected_whatever_the_section_is_called(naming):
    # Working forward again after the turn also starts three stitches from the
    # loop, so either rule may be the one that reports it; none may let it pass.
    with pytest.raises(ValueError, match="反向工作|朝向不符|首针离当前工作环"):
        compile_working_path(_two_rows(_second(direction="forward", **naming)))


def _starts_at_the_loop_then(direction: Literal["forward", "reverse"], *, edge: str = "r1",
                             **naming) -> Route:
    """Row 2 whose first stitch is the one holding the loop; only the order of the rest varies."""
    return Route(id="r2", label="第2行", mode="flat", side="WS", row_direction="reverse", expected_sites=4,
                 operations=[Work(source=Span(edge=edge, first=4, last=4)),
                             Work(source=Span(edge=edge, first=1, last=3, direction=direction))], **naming)


@pytest.mark.parametrize("naming", [
    {"section": "a", "row_number": 2},
    {"section": "b", "row_number": 1},
    {},
])
def test_the_direction_rule_alone_rejects_a_wrong_order_whatever_the_section_is_called(naming):
    compile_working_path(_two_rows(_starts_at_the_loop_then("reverse", **naming)))
    with pytest.raises(ValueError, match="反向工作|朝向不符"):
        compile_working_path(_two_rows(_starts_at_the_loop_then("forward", **naming)))


def test_wrong_direction_is_rejected_through_an_edge_alias():
    def plan(direction):
        made = _two_rows(_starts_at_the_loop_then(direction, edge="alias"))
        made.steps.insert(1, Hold(id="alias", label="换个名字", spans=[Span(edge="r1", first=1, last=4)]))
        return made
    compile_working_path(plan("reverse"))
    with pytest.raises(ValueError, match="朝向不符"):
        compile_working_path(plan("forward"))


def test_a_far_start_is_rejected_through_an_edge_alias():
    plan = _two_rows(Route(
        id="r2", label="第2行", mode="flat", side="WS", row_direction="reverse", expected_sites=4,
        operations=[Work(source=Span(edge="alias", first=1, last=4))]))
    plan.steps.insert(1, Hold(id="alias", label="换个名字", spans=[Span(edge="r1", first=1, last=4)]))
    with pytest.raises(ValueError, match="首针离当前工作环"):
        compile_working_path(plan)
    plan.steps[2].operations[0].source.direction = "reverse"
    compile_working_path(plan)


def test_attaching_slip_stitches_follow_the_same_direction_rule():
    def plan(direction):
        return _two_rows(Route(
            id="r2", label="第2行", section="a", row_number=2, mode="flat", side="WS",
            row_direction="reverse", expected_sites=1, operations=[
                Work(source=Span(edge="r1", first=4, last=4)),
                Work(source=Span(edge="r1", first=1, last=3, direction=direction),
                     stitch="slst", disposition="binding"),
            ]))
    compile_working_path(plan("reverse"))
    with pytest.raises(ValueError, match="朝向不符"):
        compile_working_path(plan("forward"))


def test_a_row_cannot_start_away_from_the_stitch_holding_the_loop():
    far = _two_rows(_second(first=1, last=3, section="a", row_number=2), count=6, rest=(4, 6))
    with pytest.raises(ValueError, match="首针离当前工作环"):
        compile_working_path(far)
    near = _two_rows(_second(first=4, last=6, section="a", row_number=2), count=6, rest=(1, 3))
    compile_working_path(near)


def test_a_flat_row_may_skip_the_one_stitch_beside_the_loop():
    # An edge decrease: the first stitch is held, the row starts on its neighbour.
    plan = _two_rows(_second(first=1, last=5, section="a", row_number=2), count=6, rest=(6, 6))
    compile_working_path(plan)


def test_segments_without_a_declared_side_keep_their_inventory_only_scope():
    plan = WorkingPath(title="旧式分段", existing_edges=[ExistingEdge(id="base", count=4)], steps=[
        Route(id="r1", label="一段", expected_sites=4,
              operations=[Work(source=Span(edge="base", first=1, last=4))]),
        Route(id="r2", label="另一段", expected_sites=4,
              operations=[Work(source=Span(edge="r1", first=1, last=4))]),
    ], final_edges=["r2"])
    compile_working_path(plan)


def _row(id_: str, *operations, sites: int, **extra) -> Route:
    return Route(id=id_, label=id_, operations=list(operations), expected_sites=sites, **extra)


def _flat(id_: str, side: str, *operations, sites: int, **extra) -> Route:
    return _row(id_, *operations, sites=sites, mode="flat", side=side,
                row_direction="forward" if side == "RS" else "reverse", **extra)


def _flat_row_after_a_turned_segment_row(side: Literal["RS", "WS"]) -> WorkingPath:
    # Turns after r1 and after r2 put the right side toward the maker again before r3.
    return WorkingPath(title="分段行翻面", yarn_tracking=True, steps=[
        NewYarn(id="start", label="起针", yarn="y", method="foundation_chain", side="RS"),
        FoundationChain(id="ch", label="起链", chains=7, work_face="underside", other_face="top"),
        _flat("r1", "RS", Work(source=Span(edge="ch", first=1, last=6, face="underside")), sites=6,
              section="a", row_number=1, turn="counterclockwise", turning_chains=1),
        _row("r2", Work(source=Span(edge="r1", first=1, last=6, direction="reverse")), sites=6,
             mode="segment", turn="clockwise", turning_chains=1),
        _flat("r3", side, Work(source=Span(edge="r2", first=1, last=6, direction="reverse")), sites=6,
              section="c", row_number=1),
        Hold(id="other", label="起链另一侧", spans=[Span(edge="ch", first=1, last=6, face="top")]),
        FastenOff(id="cut", label="断线", yarn="y", source=Span(edge="r3", first=6, last=6), tail_cm=10.0),
        WeaveEnds(id="weave", label="藏线", yarn="y", ends="both"),
    ], final_edges=["r3", "other"])


def _one_chain_buttonhole_skips_ten_stitches_elsewhere() -> WorkingPath:
    return WorkingPath(title="扣眼", existing_edges=[ExistingEdge(id="base", count=4),
                                                   ExistingEdge(id="elsewhere", count=10)], steps=[
        _row("row", Work(source=Span(edge="base", first=1, last=2)),
             ChainBridge(id="hole", count=1, route_face="top", placement="buttonhole",
                         skipped=Span(edge="elsewhere", first=1, last=10)),
             Work(source=Span(edge="base", first=3, last=4), stitch="slst", disposition="binding"), sites=3),
    ], final_edges=["row"])


def _two_separated_runs_without_a_chain() -> WorkingPath:
    # Stitches 4-9 are written off by declaration; the row goes from stitch 10 to stitch 3 with no chain.
    return WorkingPath(title="行内跳位", existing_edges=[ExistingEdge(id="base", count=12)], steps=[
        _flat("r1", "RS", Work(source=Span(edge="base", first=1, last=12)), sites=12, section="p",
              row_number=1, turn="counterclockwise"),
        FinishEdge(id="write_off", label="声明收边", source=Span(edge="r1", first=4, last=9),
                   reason="finished_border"),
        _flat("r2", "WS", Work(source=Span(edge="r1", first=10, last=12, direction="reverse")),
              Work(source=Span(edge="r1", first=1, last=3, direction="reverse")), sites=6,
              section="p", row_number=2),
    ], final_edges=["r2"])


def _stitches_after_attaching_slip_stitches(fasten_at: Span) -> WorkingPath:
    # The hook ends on the fourth stitch of the row, after two attaching slip stitches.
    return WorkingPath(title="接合后续钩", yarn_tracking=True, existing_edges=[
        ExistingEdge(id="rib", count=4), ExistingEdge(id="body", count=6)], steps=[
        NewYarn(id="join", label="接线", yarn="main", method="standing_sc", side="RS",
                anchor=Span(edge="rib", first=1, last=1)),
        _flat("band", "RS", Work(source=Span(edge="rib", first=1, last=1), stitch="standing_sc"),
              Work(source=Span(edge="body", first=1, last=2), stitch="slst", disposition="binding"),
              Work(source=Span(edge="rib", first=2, last=4)), sites=4),
        FastenOff(id="end", label="收线", yarn="main", source=fasten_at, tail_cm=15.0),
        Hold(id="rest", label="未接合部分", spans=[Span(edge="body", first=3, last=6)]),
    ], final_edges=["band", "rest"])


@pytest.mark.parametrize(("named_as", "plan"), [
    ("扣眼的锁针数", _one_chain_buttonhole_skips_ten_stitches_elsewhere),
    ("相隔的两段", _two_separated_runs_without_a_chain),
    ("只凭声明注销", _two_separated_runs_without_a_chain),
])
def test_every_shape_the_scope_statement_names_is_one_the_checker_still_accepts(named_as, plan):
    # The statement is shown beside every checked plan. A shape that gains a rule
    # must leave the statement in the same change, and this test with it.
    assert named_as in CHECK_SCOPE
    compile_working_path(plan())


def test_a_turn_on_a_segment_row_still_leaves_the_recorded_side_unchanged():
    assert "分段行（segment）上声明的翻面不改变记录的朝向" in CHECK_SCOPE
    compile_working_path(_flat_row_after_a_turned_segment_row("WS"))
    with pytest.raises(ValueError, match="当前织物朝向与下一行正反面不一致"):
        compile_working_path(_flat_row_after_a_turned_segment_row("RS"))


def test_the_loop_is_still_recorded_on_the_last_attaching_slip_stitch():
    assert "工作环记在最后一个接合引拔上" in CHECK_SCOPE
    on_slip_stitch = Span(edge="band", first=2, last=2, face="binding")
    compile_working_path(_stitches_after_attaching_slip_stitches(on_slip_stitch))
    with pytest.raises(ValueError, match="不等于当前工作环"):
        compile_working_path(_stitches_after_attaching_slip_stitches(Span(edge="band", first=4, last=4)))
