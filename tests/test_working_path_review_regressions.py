"""Counterexamples found while reviewing the manually transcribed garment path."""
import pytest

from app.models.working_path import (
    ExistingEdge,
    FinishEdge,
    FoundationChain,
    Hold,
    Route,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)


def _turned_rows(spans, *, side="WS", alias=None):
    steps = [Route(
        id="first", label="首行", section="panel", row_number=1,
        mode="flat", side="RS", row_direction="forward", turn="counterclockwise",
        expected_sites=6, operations=[Work(source=Span(edge="seed", first=1, last=6))],
    )]
    if alias is not None:
        steps.append(Hold(id="alias", label="上一行的别名", spans=alias))
    steps.append(Route(
        id="second", label="翻面后第二行", section="panel", row_number=2,
        mode="flat", side=side, row_direction="reverse", expected_sites=6,
        operations=[Work(source=span) for span in spans],
    ))
    return WorkingPath(title="连续翻面", existing_edges=[ExistingEdge(id="seed", count=6)],
                       steps=steps, final_edges=["second"])


def test_reversing_each_span_does_not_make_a_scrambled_row_continuous():
    plan = _turned_rows([
        Span(edge="first", first=1, last=3, direction="reverse"),
        Span(edge="first", first=4, last=6, direction="reverse"),
    ])
    with pytest.raises(ValueError, match="来源顺序"):
        compile_working_path(plan)


def test_a_hold_alias_cannot_hide_scrambled_continuation_order():
    plan = _turned_rows([Span(edge="alias", first=1, last=6)], alias=[
        Span(edge="first", first=1, last=3, direction="reverse"),
        Span(edge="first", first=4, last=6, direction="reverse"),
    ])
    with pytest.raises(ValueError, match="来源顺序"):
        compile_working_path(plan)


@pytest.mark.parametrize("split", range(1, 6))
def test_correct_reverse_traversal_can_be_partitioned_at_any_stitch(split):
    plan = _turned_rows([
        Span(edge="first", first=split + 1, last=6, direction="reverse"),
        Span(edge="first", first=1, last=split, direction="reverse"),
    ])
    result = compile_working_path(plan)
    assert [s.position for e in result.events if e.route == "second" for s in e.sources] == [6, 5, 4, 3, 2, 1]


def test_declared_turn_must_alternate_fabric_side_as_well_as_direction():
    plan = _turned_rows([Span(edge="first", first=1, last=6, direction="reverse")], side="RS")
    with pytest.raises(ValueError, match="正反面"):
        compile_working_path(plan)


def test_a_chain_continuation_requires_the_current_loop_anchor():
    with pytest.raises(ValueError, match="当前工作环"):
        FoundationChain(id="chain", label="缺少当前环", chains=3,
                        work_face="underside", other_face="top", anchor_mode="continues_loop")


@pytest.mark.parametrize("alias", [False, True])
def test_ordinary_heads_cannot_be_retired_as_unused_chain_faces(alias):
    steps = []
    if alias:
        steps.append(Hold(id="alias", label="普通针目的别名", spans=[Span(edge="seed", first=1, last=2)]))
    steps.append(FinishEdge(id="finish", label="错误原因",
                            source=Span(edge="alias" if alias else "seed", first=1, last=2),
                            reason="unused_chain_face"))
    plan = WorkingPath(title="错误归类", existing_edges=[ExistingEdge(id="seed", count=2)], steps=steps)
    with pytest.raises(ValueError, match="锁针"):
        compile_working_path(plan)


def test_declaring_a_border_finished_is_reported_separately_from_working_it():
    plan = WorkingPath(title="只声明留边", existing_edges=[ExistingEdge(id="seed", count=2)], steps=[
        FinishEdge(id="finish", label="声明留边", source=Span(edge="seed", first=1, last=2),
                   reason="finished_border"),
    ])
    result = compile_working_path(plan)
    assert result.created_sites == result.consumed_sites == 2
    accounting = result.to_dict()["inventory_accounting"]
    assert accounting["retired_without_work"] == 2
    assert accounting["retirement_declarations"] == [
        {"step": "finish", "reason": "finished_border", "sites": 2},
    ]
    assert result.to_dict()["physical_execution_verified"] is False
