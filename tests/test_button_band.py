"""Dimensional hole placement must stay on the intended front edge."""
import pytest

from app.models.attached_ribbing import RibbingMethod
from app.models.button_band import ButtonBandTarget, design_button_band, propose_button_band
from app.models.working_path import (
    ChainBridge,
    ExistingEdge,
    Hold,
    Route,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)


def _target(**changes):
    data = dict(base_sites=30, edge_length_cm=7.5, width_cm=1.0, first_front_sites=12,
                buttonhole_positions_cm=[0.75, 1.75], rib_rows_per_10cm=40.0,
                rib_stitches_per_10cm=40.0, gauge_basis="hypothetical")
    return ButtonBandTarget(**(data | changes))


def _base_and_method():
    plan = WorkingPath(title="已明确顺序的基底", existing_edges=[ExistingEdge(id="seed", count=31)], steps=[
        Route(id="fabric", label="已有行", expected_sites=31,
              operations=[Work(source=Span(edge="seed", first=1, last=31))]),
        Hold(id="edge", label="基底", spans=[Span(edge="fabric", first=1, last=30, direction="reverse")]),
        Hold(id="root", label="根部另行保留", spans=[Span(edge="fabric", first=31, last=31)]),
    ], final_edges=["edge", "root"])
    method = RibbingMethod(prefix="band", title="门襟设计候选", base_edge="edge",
                           current_loop=Span(edge="root", first=1, last=1), stitch="slst",
                           foundation_face="underside", foundation_turn="counterclockwise",
                           hook_mm=3.0, start_side="RS", outer_turning_chain=1,
                           design_basis="这是独立参数设计，非原教程复原。")
    return plan, method


def test_positions_quantize_to_explicit_rows_and_mirrored_buttons():
    proposal = propose_button_band(_target())
    assert proposal.hole_rows == (3, 7)
    assert proposal.opposing_button_rows == (28, 24)
    assert proposal.estimated_hole_positions_cm == (.625, 1.625)
    plan, method = _base_and_method()
    proposal, generated = design_button_band(plan, method, _target())
    result = compile_working_path(generated)
    holes = [op for step in generated.steps if isinstance(step, Route)
             for op in step.operations if isinstance(op, ChainBridge) and op.placement == "buttonhole"]
    assert [h.id for h in holes] == ["band_hole_003", "band_hole_007"]
    assert all(h.count == 2 and h.skipped.first == 1 and h.skipped.last == 2 for h in holes)
    assert len(result.final_edges["band_030"]) == 4
    assert sum(e.stitch == "buttonhole_boundary" for e in result.events) == 2
    assert proposal.to_dict()["physical_execution_verified"] is False


@pytest.mark.parametrize("changes", [
    {"buttonhole_positions_cm": [0.1]},
    {"buttonhole_positions_cm": [0.75, 0.9]},
    {"buttonhole_positions_cm": [3.0]},
    {"buttonhole_positions_cm": [9.0]},
])
def test_wrong_front_too_close_or_out_of_range_is_not_silently_corrected(changes):
    target = _target(**changes)
    proposal = propose_button_band(target)
    assert proposal.status == "unsupported"
    plan, method = _base_and_method()
    assert design_button_band(plan, method, target)[1] is None


def test_missing_gauge_and_too_narrow_band_do_not_create_a_false_pattern():
    assert propose_button_band(_target(rib_rows_per_10cm=None)).status == "needs_gauge"
    plan, method = _base_and_method()
    proposal, generated = design_button_band(plan, method, _target(width_cm=.5))
    assert proposal.status == "unsupported" and generated is None
