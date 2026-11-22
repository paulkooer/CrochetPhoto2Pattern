"""Hook travel must agree with the declared facing side, whatever a step is called."""
from typing import Literal

import pytest

from app.models.working_path import (
    ExistingEdge,
    Hold,
    Route,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)


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
