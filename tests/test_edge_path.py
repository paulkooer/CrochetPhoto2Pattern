"""Composing reserved work paths must transfer ownership without duplicating fabric."""
import pytest

from app.models.working_path import (
    EdgePath,
    ExistingEdge,
    Hold,
    Route,
    Site,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)
from app.utils.working_path_export import export_working_path_markdown


def _plan():
    return WorkingPath(title="重排已有边", existing_edges=[ExistingEdge(id="seed", count=6)], steps=[
        Hold(id="old", label="旧名称", spans=[Span(edge="seed", first=1, last=4)]),
        EdgePath(id="new", label="连续新路径", spans=[
            Span(edge="old", first=1, last=4, direction="reverse"),
            Span(edge="seed", first=5, last=6),
        ]),
    ], final_edges=["new"])


def test_transfer_preserves_canonical_sites_without_creating_or_consuming_a_stitch():
    result = compile_working_path(_plan())
    assert result.final_edges["new"] == tuple(Site("seed", i) for i in [4, 3, 2, 1, 5, 6])
    assert result.created_sites == 6 and result.consumed_sites == 0
    assert all(e.role == "reference" for e in result.events)
    assert "不作钩织或缝合" in export_working_path_markdown(_plan())


def test_old_alias_cannot_keep_access_after_explicit_transfer():
    plan = _plan()
    plan.steps.append(Route(id="bad", label="旧名称重复访问", expected_sites=4,
                            operations=[Work(source=Span(edge="old", first=1, last=4))]))
    with pytest.raises(ValueError, match="须通过"):
        compile_working_path(plan)


def test_transfer_rejects_overlapping_parts_or_borrowing_someone_elses_reserved_sites():
    plan = _plan()
    plan.steps[-1].spans[-1] = Span(edge="old", first=3, last=4)
    with pytest.raises(ValueError, match="重复"):
        compile_working_path(plan)
    plan = _plan()
    plan.steps[-1].spans[0] = Span(edge="seed", first=1, last=4)
    with pytest.raises(ValueError, match="须通过"):
        compile_working_path(plan)


def test_two_explicit_transfers_can_partition_a_reserved_edge():
    plan = _plan()
    plan.steps[-1].spans = [Span(edge="old", first=1, last=2)]
    plan.steps.append(EdgePath(id="rest", label="剩余位置另有名称", spans=[
        Span(edge="old", first=3, last=4), Span(edge="seed", first=5, last=6),
    ]))
    plan.final_edges = ["new", "rest"]
    assert sum(map(len, compile_working_path(plan).final_edges.values())) == 6
