"""End-to-end construction composition, including honest partial outputs."""
import json

import pytest

from app.cardigan_design import main, write_cardigan
from app.models.cardigan_design import CardiganRequest, RibGauge, assemble_cardigan
from app.models.raglan_yoke import YokeMethod, YokeTarget
from app.models.working_path import (
    ChainBridge,
    FastenOff,
    FoundationChain,
    NewYarn,
    ParkYarn,
    Route,
    Seam,
    Site,
    compile_working_path,
)
from app.utils.working_path_export import scope_note
from app.working_paths import read_path


def _request(**changes):
    request = CardiganRequest(
        dimension_basis="hypothetical",
        yoke=YokeTarget(neck_edge_cm=21/2.6, body_span_cm=46/2.6, sleeve_circumference_cm=18/2.6,
                        yoke_depth_cm=9/2.8, stitches_per_10cm=26.0, rows_per_10cm=28.0,
                        gauge_basis="reference_declared"),
        method=YokeMethod(prefix="design", hook_mm=3.0), body_length_cm=7.5, sleeve_length_cm=6.4,
        hem_width_cm=1.9, band_width_cm=1.0, cuff_width_cm=3.5,
        buttonhole_positions_cm=[1.0, 3.0, 5.0],
        hem_gauge=RibGauge(stitches_per_10cm=26.0, rows_per_10cm=26.0, basis="hypothetical"),
        band_gauge=RibGauge(stitches_per_10cm=40.0, rows_per_10cm=40.0, basis="hypothetical"),
        cuff_gauge=RibGauge(stitches_per_10cm=40.0, rows_per_10cm=40.0, basis="hypothetical"),
    )
    return CardiganRequest.model_validate(request.model_dump() | changes)


def test_all_stages_are_generated_and_pending_cuff_edges_remain_explicit():
    request = _request()
    before = request.model_dump_json()
    result = assemble_cardigan(request)
    assert result.stage == "integrated_open_cuffs"
    assert set(result.stages) == {"yoke", "body", "hem", "band", "cuff_a", "cuff_b"}
    assert result.stages["band"]["hole_rows"] == (5, 13, 21)
    compiled = compile_working_path(result.plan)
    assert compiled.created_sites - compiled.consumed_sites == 94
    assert len(compiled.final_edges["design_body_corner"]) == 1
    assert len(compiled.final_edges["design_band_corner"]) == 1
    for side in ("a", "b"):
        assert len(compiled.final_edges[f"design_cuff_{side}_start_loops"]) == 14
        assert len(compiled.final_edges[f"design_cuff_{side}_030"]) == 14
    assert not any(isinstance(step, Seam) for step in result.plan.steps)
    gauges = {g.id: g for g in result.plan.gauges}
    assert gauges["design_sc"].basis == "reference_declared"
    assert gauges["design_band_gauge"].basis == "hypothetical"
    assert gauges["design_band_gauge"].rows_per_10cm == 40.0
    assert sum(isinstance(op, ChainBridge) and op.placement == "buttonhole"
               for step in result.plan.steps if isinstance(step, Route) for op in step.operations) == 3
    assert result.to_dict()["ready_for_whole_garment_trial"] is False
    yarns = result.to_dict()["yarn_accounting"]
    assert yarns["segments"]["design_body_yarn"]["declared_status"] == "closed"
    assert yarns["segments"]["design_sleeve_a_yarn"]["declared_status"] == "parked"
    assert yarns["all_fasten_off_steps_present"] is False
    assert "人工指定的尺寸和做法生成" in scope_note(result.plan)
    assert request.model_dump_json() == before


@pytest.mark.parametrize(("changed", "stage"), [
    ({"hem_gauge": {}}, "hem_blocked"),
    ({"band_gauge": {}}, "band_blocked"),
    ({"band_width_cm": .5}, "band_blocked"),
    ({"buttonhole_positions_cm": [20.0]}, "band_blocked"),
    ({"cuff_gauge": {}}, "cuff_a_blocked"),
])
def test_missing_inputs_or_invalid_geometry_leave_a_named_partial_stage(changed, stage):
    result = assemble_cardigan(_request(**changed))
    assert result.stage == stage and result.unresolved
    assert result.plan is not None
    compile_working_path(result.plan)
    assert result.to_dict()["ready_for_whole_garment_trial"] is False


def test_no_gauge_at_the_start_means_no_default_template():
    request = _request()
    request.yoke.rows_per_10cm = None
    result = assemble_cardigan(request)
    assert result.stage == "yoke_blocked" and result.plan is None


def test_odd_sleeve_length_changes_cuff_start_side_without_an_extra_turn():
    result = assemble_cardigan(_request(sleeve_length_cm=17/2.8))
    plan = result.plan
    sleeve_end = next(s for s in plan.steps if s.id == "design_sleeve_a_017")
    cuff_chain = next(s for s in plan.steps if s.id == "design_cuff_a_chain")
    cuff_start = next(s for s in plan.steps if s.id == "design_cuff_a_001")
    assert sleeve_end.closure == "before_turn" and sleeve_end.turning_chains == 0
    assert isinstance(cuff_chain, FoundationChain) and cuff_chain.turn_after_chain == "none"
    assert cuff_start.side == "WS"
    compile_working_path(plan)


def test_another_size_changes_panels_hem_and_band_counts():
    original = _request()
    resized = original.model_dump()
    resized["yoke"].update(neck_edge_cm=26/2.6, body_span_cm=50/2.6,
                            sleeve_circumference_cm=20/2.6, yoke_depth_cm=11/2.8)
    resized["method"]["stitch_adjustment"] = 0
    result = assemble_cardigan(CardiganRequest.model_validate(resized))
    assert result.stage == "integrated_open_cuffs"
    assert result.stages["yoke"]["estimated_cm"]["body_span"] == pytest.approx(50/2.6)
    assert result.stages["hem"]["layout"]["rows"] == 50
    assert result.stages["band"]["ribbing"]["layout"]["rows"] != 130
    compile_working_path(result.plan)


def test_cli_roundtrip_does_not_mislabel_generation_as_source_transcription(tmp_path):
    request = _request()
    (tmp_path / "request.json").write_text(request.model_dump_json())
    out = tmp_path / "output"
    assert main(["--design", str(tmp_path / "request.json"), "--out-dir", str(out)]) == 0
    plan = read_path((out / "path-plan.json").read_bytes())
    assert plan.input_origin == "parametric_design"
    assert json.loads((out / "design-report.json").read_text())["stage"] == "integrated_open_cuffs"


def test_export_failure_does_not_leave_a_half_written_combined_design(tmp_path, monkeypatch):
    def fail(_):
        raise ValueError("布局失败")

    monkeypatch.setattr("app.cardigan_design.export_working_recipe_pdf", fail)
    with pytest.raises(ValueError, match="布局"):
        write_cardigan(_request(), tmp_path / "failed", pdf=True)
    assert not (tmp_path / "failed").exists()


def test_blocked_start_writes_only_request_and_report(tmp_path):
    request = _request()
    request.method.stitch_adjustment = 0
    files = write_cardigan(request, tmp_path / "blocked")
    assert {p.name for p in files} == {"design-request.json", "design-report.json"}


def test_explicit_new_seam_starts_at_the_live_loop_and_pairs_corresponding_columns():
    result = assemble_cardigan(_request(cuff_seam="blo_to_reserved_flo"))
    assert result.stage == "integrated_cuff_seam_candidate"
    compiled = compile_working_path(result.plan)
    seam = [e for e in compiled.events if e.route == "design_cuff_a_seam"]
    assert seam[0].sources == (Site("design_cuff_a_030", 14), Site("design_cuff_a_001", 1, "front_loop"))
    assert seam[-1].sources == (Site("design_cuff_a_030", 1), Site("design_cuff_a_001", 14, "front_loop"))
    assert compiled.created_sites - compiled.consumed_sites == 38
    assert result.to_dict()["ready_for_whole_garment_trial"] is False
    yarns = result.to_dict()["yarn_accounting"]
    assert len(yarns["segments"]) == 3
    assert yarns["all_fasten_off_steps_present"] is True
    assert yarns["all_weave_steps_present"] is True
    assert sum(isinstance(step, FastenOff) for step in result.plan.steps) == 3
    assert sum(isinstance(step, NewYarn) for step in result.plan.steps) == 3
    assert not any(isinstance(step, ParkYarn) for step in result.plan.steps)
    assert {e.yarn_id for e in compiled.events if e.route == "design_cuff_a_seam"} == {"design_sleeve_a_yarn"}


def test_missing_cut_and_weave_cannot_silently_jump_from_band_to_sleeve():
    result = assemble_cardigan(_request())
    result.plan.steps = [s for s in result.plan.steps if s.id not in (
        "design_finish_body_yarn", "design_weave_body_yarn")]
    with pytest.raises(ValueError, match="收掉或暂停"):
        compile_working_path(result.plan)


def test_missing_foundation_turn_is_detected_across_construction_sections():
    result = assemble_cardigan(_request())
    chain = next(s for s in result.plan.steps if s.id == "design_hem_chain")
    chain.turn_after_chain = "none"
    with pytest.raises(ValueError, match="朝向"):
        compile_working_path(result.plan)
