"""Design-to-path checks across sizes, with independent base-site accounting."""
import pytest

from app.models.attached_ribbing import (
    RibbingLayout,
    RibbingRecipe,
    RibbingTarget,
    append_attached_ribbing,
    design_attached_ribbing,
    propose_ribbing,
)
from app.models.working_path import (
    ExistingEdge,
    Hold,
    Route,
    Site,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)
from app.utils.working_path_export import step_text


def _base(count):
    # A flat source row: its last head carries the yarn loop and is retained
    # separately as a corner. Attachment starts in the adjacent preceding head.
    return WorkingPath(title="明确已有行与工作环", existing_edges=[ExistingEdge(id="seed", count=count + 1)],
                       steps=[
                           Route(id="fabric", label="基底行", expected_sites=count + 1,
                                 operations=[Work(source=Span(edge="seed", first=1, last=count + 1))]),
                           Hold(id="edge", label="反向接合边",
                                spans=[Span(edge="fabric", first=1, last=count, direction="reverse")]),
                           Hold(id="corner", label="明确不在接合范围的角",
                                spans=[Span(edge="fabric", first=count + 1, last=count + 1)]),
                       ], final_edges=["edge", "corner"])


def _recipe(count, rows, width=5, **kwargs):
    return RibbingRecipe(
        prefix="rib", title="沿边肋纹设计候选", base_edge="edge",
        current_loop=Span(edge="corner", first=1, last=1),
        layout=RibbingLayout(base_sites=count, rows=rows, width_stitches=width),
        stitch="slst", foundation_face="back_loop", foundation_turn="counterclockwise",
        hook_mm=3.0, start_side="RS",
        design_basis="独立构造练习的参数；不代表实钩或原教程复原。", **kwargs,
    )


def test_missing_rib_gauge_never_falls_back_to_regular_sc_or_reference_counts():
    proposal = propose_ribbing(RibbingTarget(base_sites=18, edge_length_cm=7.0, width_cm=3.5))
    assert proposal.status == "needs_gauge" and proposal.layout is None
    assert proposal.estimated_length_cm is None


def test_gauge_changes_the_design_and_not_only_the_printed_description():
    inputs = dict(base_sites=18, edge_length_cm=6.0, width_cm=3.5,
                  rib_stitches_per_10cm=40.0, gauge_basis="hypothetical")
    dense = propose_ribbing(RibbingTarget(**inputs, rib_rows_per_10cm=40.0))
    loose = propose_ribbing(RibbingTarget(**inputs, rib_rows_per_10cm=30.0))
    assert dense.layout == RibbingLayout(base_sites=18, rows=24, width_stitches=14)
    assert dense.layout.attachments() == (2, 1) * 6
    assert loose.layout == RibbingLayout(base_sites=18, rows=18, width_stitches=14)
    assert loose.layout.attachments() == (2,) * 9
    assert dense.estimated_length_cm == loose.estimated_length_cm == 6.0
    assert dense.to_dict()["fit_verified"] is False


def test_quantization_is_visible_and_does_not_claim_exact_target_dimensions():
    result = propose_ribbing(RibbingTarget(base_sites=18, edge_length_cm=6.2, width_cm=3.6,
                                         rib_rows_per_10cm=40.0, rib_stitches_per_10cm=40.0,
                                         gauge_basis="hypothetical"))
    assert result.layout.rows == 24 and result.layout.width_stitches == 14
    assert result.estimated_length_cm == 6.0 and result.estimated_width_cm == 3.5


def test_an_unsupported_attachment_rate_is_not_clamped_to_a_passing_layout():
    proposal = propose_ribbing(RibbingTarget(base_sites=18, edge_length_cm=6.0, width_cm=3.5,
                                           rib_rows_per_10cm=80.0, rib_stitches_per_10cm=40.0,
                                           gauge_basis="hypothetical"))
    assert proposal.status == "unsupported" and proposal.layout is None


@pytest.mark.parametrize(("sites", "rows", "width"), [(1, 2, 1), (7, 8, 3), (18, 24, 14),
                                                       (19, 26, 6), (60, 60, 5), (24, 32, 14)])
def test_generated_rows_attach_each_base_site_once_and_preserve_the_corners(sites, rows, width):
    base = _base(sites)
    original = base.model_dump_json()
    plan = append_attached_ribbing(base, _recipe(sites, rows, width, keep_start_loops=True))
    result = compile_working_path(plan)
    bindings = [e for e in result.events if e.role == "binding"]
    assert [s for e in bindings for s in e.sources] == [Site("fabric", i) for i in range(sites, 0, -1)]
    assert len(result.final_edges[f"rib_{rows:03d}"]) == width
    assert result.final_edges["corner"] == (Site("fabric", sites + 1),)
    assert len(result.final_edges["rib_start_loops"]) == width
    assert len(result.final_edges["rib_outside"]) == width
    assert not any(e.role == "retired" for e in result.events)
    assert sum(e.route.startswith("rib_") and e.role == "working" and e.stitch == "slst"
               for e in result.events) == rows * width
    assert result.to_dict()["physical_execution_verified"] is False
    assert base.model_dump_json() == original


def test_sc_selvedge_is_kept_at_the_same_physical_outer_column_after_each_turn():
    recipe = _recipe(6, 8, width=3, outer_edge_both=True)
    recipe.stitch = "sc"
    recipe.foundation_face = "underside"
    result = compile_working_path(append_attached_ribbing(_base(6), recipe))
    even = [e for e in result.events if e.route == "rib_002" and e.role == "working"]
    odd = [e for e in result.events if e.route == "rib_003" and e.role == "working"]
    assert [e.source_loops for e in even] == [("back",), ("back",), ("both",)]
    assert [e.source_loops for e in odd] == [("both",), ("back",), ("back",)]


def test_source_count_and_live_loop_are_verified_against_the_existing_plan():
    recipe = _recipe(18, 24)
    with pytest.raises(ValueError, match="数量"):
        append_attached_ribbing(_base(17), recipe)
    recipe.current_loop = Span(edge="edge", first=1, last=1)
    with pytest.raises(ValueError, match="当前工作环"):
        append_attached_ribbing(_base(18), recipe)


def test_odd_rows_or_claiming_unreserved_loops_are_rejected():
    with pytest.raises(ValueError, match="偶数"):
        RibbingLayout(base_sites=18, rows=23, width_stitches=14)
    with pytest.raises(ValueError, match="前半针"):
        _recipe(18, 24, keep_start_loops=True, outer_edge_both=True)


def test_dimensions_generate_different_actual_rows_without_reentering_a_row_count():
    from app.models.attached_ribbing import RibbingMethod

    recipe = _recipe(18, 24, width=14)
    method = RibbingMethod.model_validate(recipe.model_dump(exclude={"layout"}))
    for gauge, expected in [(30.0, 18), (40.0, 24)]:
        target = RibbingTarget(base_sites=18, edge_length_cm=6.0, width_cm=3.5,
                               rib_rows_per_10cm=gauge, rib_stitches_per_10cm=40.0,
                               gauge_basis="hypothetical")
        proposal, plan = design_attached_ribbing(_base(18), method, target)
        result = compile_working_path(plan)
        assert proposal.layout.rows == expected
        assert sum(e.role == "working" and e.stitch == "slst" for e in result.events) == expected * 14
        assert len([step for step in plan.steps if isinstance(step, Route)]) == expected + 1


def test_foundation_turn_is_separate_from_last_base_row_and_visible_in_instructions():
    recipe = _recipe(6, 8)
    plan = append_attached_ribbing(_base(6), recipe)
    foundation = next(step for step in plan.steps if step.id == "rib_chain")
    assert "起链后逆时针翻面" in step_text(foundation)
