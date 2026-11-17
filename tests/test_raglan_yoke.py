"""Dimensional constraints, panel growth and explicit body/sleeve partition."""
import pytest

from app.models.raglan_yoke import YokeMethod, YokeTarget, generate_yoke, propose_yoke
from app.models.working_path import Route, compile_working_path
from app.utils.working_path_format import route_formula


def _target(**changes):
    data = dict(neck_edge_cm=21/2.6, body_span_cm=46/2.6, sleeve_circumference_cm=18/2.6,
                yoke_depth_cm=9/2.8, stitches_per_10cm=26.0, rows_per_10cm=28.0,
                gauge_basis="reference_declared")
    return YokeTarget(**(data | changes))


def test_reference_sized_inputs_are_reported_as_a_new_adjusted_design_not_a_reconstruction():
    proposal = propose_yoke(_target(), YokeMethod(prefix="test", hook_mm=3.0))
    assert proposal.layout.neck_stitches == 21
    assert proposal.layout.panels_after(0) == (4, 2, 9, 2, 4)
    assert proposal.layout.increase_rows == [2, 3, 4, 6, 7]
    assert proposal.layout.body_stitches == 47
    assert proposal.layout.sleeve_stitches == 19
    assert proposal.adjustment_stitches == {"body": 1, "sleeve": 1}
    assert proposal.estimated_cm["body_span"] == pytest.approx(47/2.6)
    assert proposal.to_dict()["source_pattern_reconstruction"] is False
    assert proposal.to_dict()["fit_verified"] is False


def test_exact_incompatible_targets_or_missing_gauge_do_not_produce_steps():
    for target, method, status in [
        (_target(), YokeMethod(prefix="test", hook_mm=3.0, stitch_adjustment=0), "unsupported"),
        (_target(rows_per_10cm=None), YokeMethod(prefix="test", hook_mm=3.0), "needs_gauge"),
        (_target(yoke_depth_cm=1.0), YokeMethod(prefix="test", hook_mm=3.0), "unsupported"),
    ]:
        proposal = propose_yoke(target, method)
        assert proposal.status == status and proposal.layout is None
        with pytest.raises(ValueError, match="约束"):
            generate_yoke(proposal)


def test_each_increase_is_at_a_panel_boundary_and_the_split_keeps_every_source():
    proposal = propose_yoke(_target(), YokeMethod(prefix="test", hook_mm=3.0))
    plan = generate_yoke(proposal)
    result = compile_working_path(plan)
    increments = [e.sources[0].position for e in result.events
                  if e.route == "test_yoke_002" and e.stitch == "inc"]
    assert increments == [18, 17, 16, 15, 7, 6, 5, 4]
    assert {name: len(sites) for name, sites in result.final_edges.items()} == {
        "test_body_001": 47, "test_opening_a": 19, "test_opening_b": 19, "test_neck_edge": 21,
    }
    a, b = result.held_edges["test_opening_a"], result.held_edges["test_opening_b"]
    assert not set(a).intersection(b)
    assert [s.face for s in a].count("corner_start") == [s.face for s in a].count("corner_end") == 1
    assert sum(s.edge == "test_bridge_a" and s.face == "top" for s in a) == 5
    body = next(s for s in plan.steps if s.id == "test_body_001")
    assert route_formula(body, events=result.events)[0] == "9X，5X（里山），19X，5X（里山），9X"
    assert not any(e.role == "retired" for e in result.events)


def test_depth_changes_increase_placement_without_changing_target_widths():
    method = YokeMethod(prefix="test", hook_mm=3.0)
    short = propose_yoke(_target(), method)
    deep = propose_yoke(_target(yoke_depth_cm=12/2.8), method)
    assert short.layout.body_stitches == deep.layout.body_stitches == 47
    assert short.layout.sleeve_stitches == deep.layout.sleeve_stitches == 19
    assert short.layout.increase_rows != deep.layout.increase_rows
    assert deep.layout.rows_to_split == 13
    assert deep.estimated_cm["yoke_depth"] == pytest.approx(13/2.8)
    compile_working_path(generate_yoke(deep))


@pytest.mark.parametrize(("front", "sleeve", "back", "increases", "depth"), [
    (2, 2, 4, 1, 4), (3, 3, 6, 3, 7), (4, 2, 9, 5, 9), (6, 4, 12, 5, 12),
])
def test_different_sizes_generate_actual_rows_and_preserve_exact_feasible_counts(front, sleeve, back,
                                                                               increases, depth):
    neck = 2*front + 2*sleeve + back
    body = 2*front + back + 4*increases + 10
    sleeve_count = sleeve + 2*increases + 7
    target = _target(neck_edge_cm=neck/2.6, body_span_cm=body/2.6,
                     sleeve_circumference_cm=sleeve_count/2.6, yoke_depth_cm=depth/2.8)
    proposal = propose_yoke(target, YokeMethod(prefix="test", hook_mm=3.0, stitch_adjustment=0))
    result = compile_working_path(generate_yoke(proposal))
    assert len(result.final_edges["test_body_001"]) == body
    assert len(result.final_edges["test_opening_a"]) == sleeve_count
    rows = [s for s in result.plan.steps if isinstance(s, Route) and s.section == "test_yoke"]
    assert len(rows) == (depth if depth % 2 else depth + 1)
    assert rows[-1].side == "RS"


def test_bridge_center_policy_cannot_silently_choose_between_two_middle_chains():
    with pytest.raises(ValueError, match="奇数"):
        YokeMethod(prefix="test", hook_mm=3.0, underarm_chains=4)
