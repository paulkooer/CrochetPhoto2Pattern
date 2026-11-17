"""Derived corner/row/lip sources and non-counted joins, using original small exercises."""
import pytest

from app.models.working_path import (
    ChainBridge,
    ConstructionGauge,
    ExistingEdge,
    FinishEdge,
    FoundationChain,
    FreeLoops,
    Route,
    RowEdges,
    RowEnd,
    Seam,
    Site,
    Span,
    Work,
    WorkingPath,
    armhole_path_demo,
    compile_working_path,
)


def _row(name, source, *, loop="both", direction="forward", mode="flat", side="RS", closure="none"):
    return Route(id=name, label=name, mode=mode, row_direction=direction, side=side,
                 turn="counterclockwise", closure=closure, expected_sites=source.last - source.first + 1,
                 operations=[Work(source=source, loop=loop)])


def test_corner_pickups_are_derived_from_both_bridge_junctions_and_not_invented_seeds():
    data = armhole_path_demo().model_dump()
    for operation in data["steps"][0]["operations"]:
        if operation["kind"] == "chain":
            operation["corner_sites"] = True
    for side, hold_index, route_index in [("left", 1, 3), ("right", 2, 4)]:
        data["steps"][hold_index]["spans"] += [
            {"edge": f"{side}_bridge", "first": 1, "last": 1, "face": "corner_start"},
            {"edge": f"{side}_bridge", "first": 1, "last": 1, "face": "corner_end"},
        ]
        data["steps"][route_index]["expected_sites"] = 11
        data["steps"][route_index]["operations"][0]["source"]["last"] = 11
    result = compile_working_path(WorkingPath.model_validate(data))
    corners = [event for event in result.events if event.stitch == "corner_site"]
    assert len(corners) == 4 and all(event.role == "reference" for event in corners)
    assert corners[0].sources == (Site("yoke", 4), Site("left_bridge", 1, "underside"))
    assert corners[1].sources == (Site("yoke", 11), Site("left_bridge", 3, "underside"))
    assert corners[0].outputs == (Site("left_bridge", 1, "corner_start"),)
    assert len(result.final_edges["left_sleeve"]) == len(result.final_edges["right_sleeve"]) == 11
    assert sum(event.stitch == "sc" for event in result.events) == 38
    assert result.to_dict()["physical_execution_verified"] is False


def test_corners_require_an_actual_bridge_junction_and_cannot_be_borrowed_twice():
    data = armhole_path_demo().model_dump()
    data["steps"][1]["spans"].append({"edge": "left_bridge", "first": 1, "last": 1,
                                      "face": "corner_start"})
    with pytest.raises(ValueError, match="尚未建立"):
        compile_working_path(WorkingPath.model_validate(data))


def test_foundation_preserves_the_unused_side_and_never_counts_the_skipped_chain_as_a_stitch():
    plan = WorkingPath(title="起链练习", input_origin="manual_instructions", steps=[
        FoundationChain(id="chain", label="起链", chains=4, work_face="underside", other_face="top"),
        Route(id="row", label="首行", expected_sites=3,
              operations=[Work(source=Span(edge="chain", first=1, last=3, face="underside"), stitch="slst")]),
        FinishEdge(id="outside", label="留边", source=Span(edge="chain", first=1, last=3),
                   reason="unused_chain_face"),
    ], final_edges=["row"])
    result = compile_working_path(plan)
    assert result.events[0].outputs[:3] == tuple(Site("chain", i, "underside") for i in (2, 3, 4))
    assert len(result.final_edges["row"]) == 3
    assert not any(site.position == 1 for site in result.events[0].outputs)


def test_attachment_slips_do_not_become_live_stitches_in_the_next_row():
    plan = WorkingPath(title="接合练习", existing_edges=[ExistingEdge(id="edge", count=4)], steps=[
        Route(id="rib", label="肋纹行", expected_sites=2, operations=[
            Work(source=Span(edge="edge", first=1, last=2)),
            Work(source=Span(edge="edge", first=3, last=4), stitch="slst", disposition="binding"),
        ]),
    ], final_edges=["rib"])
    result = compile_working_path(plan)
    assert result.final_edges["rib"] == (Site("rib", 1), Site("rib", 2))
    binding = [event for event in result.events if event.role == "binding"]
    assert [event.outputs for event in binding] == [(Site("rib", 1, "binding"),),
                                                  (Site("rib", 2, "binding"),)]
    assert result.created_sites - result.consumed_sites == 2


def test_row_edge_pickups_refer_to_known_physical_ends_even_after_top_heads_were_worked():
    plan = WorkingPath(title="行端练习", existing_edges=[ExistingEdge(id="edge", count=2)], steps=[
        _row("one", Span(edge="edge", first=1, last=2)),
        _row("two", Span(edge="one", first=1, last=2, direction="reverse"), direction="reverse", side="WS"),
        _row("three", Span(edge="two", first=1, last=2, direction="reverse")),
        RowEdges(id="side", label="左行端", rows=[RowEnd(row=name, side="left") for name in ("one", "two")]),
        Route(id="band", label="挑边", expected_sites=2,
              operations=[Work(source=Span(edge="side", first=1, last=2), stitch="slst")]),
    ], final_edges=["three", "band"])
    result = compile_working_path(plan)
    events = [event for event in result.events if event.stitch == "row_end_site"]
    assert [event.sources for event in events] == [(Site("one", 1),), (Site("two", 2),)]
    assert events[0].outputs == (Site("one", 1, "row_left"),)
    assert all(event.role == "reference" for event in events)


@pytest.mark.parametrize("seam_count", [3, 4])
def test_seam_requires_a_previously_reserved_half_loop_and_matching_sides(seam_count):
    plan = WorkingPath(title="接缝练习", existing_edges=[ExistingEdge(id="edge", count=4)], steps=[
        _row("one", Span(edge="edge", first=1, last=4)),
        _row("two", Span(edge="one", first=1, last=4, direction="reverse"),
             direction="reverse", side="WS", loop="back"),
        FreeLoops(id="start_lip", label="预留前半针", source=Span(edge="one", first=1, last=4), loop="front"),
        Seam(id="seam", label="接合", left=Span(edge="two", first=1, last=4), left_loop="back",
             right=Span(edge="start_lip", first=1, last=seam_count, direction="reverse")),
    ])
    if seam_count == 3:
        with pytest.raises(ValueError, match="不一致"):
            compile_working_path(plan)
    else:
        result = compile_working_path(plan)
        seam = [event for event in result.events if event.route == "seam"]
        assert len(seam) == 4 and all(event.role == "binding" for event in seam)
        assert seam[0].sources == (Site("two", 1), Site("one", 4, "front_loop"))
        assert seam[0].source_loops == ("back", "both")
        assert result.created_sites == result.consumed_sites


def test_half_loops_cannot_be_created_after_both_loops_were_used():
    plan = WorkingPath(title="错误预留", existing_edges=[ExistingEdge(id="edge", count=2)], steps=[
        _row("row", Span(edge="edge", first=1, last=2)),
        FreeLoops(id="imagined", label="不存在的半针",
                  source=Span(edge="edge", first=1, last=2), loop="front"),
    ], final_edges=["row"])
    with pytest.raises(ValueError, match="没有被"):
        compile_working_path(plan)


def test_invisible_joins_record_before_after_turn_without_adding_working_stitches():
    plan = WorkingPath(title="闭合行", existing_edges=[ExistingEdge(id="edge", count=3)], steps=[
        _row("rs", Span(edge="edge", first=1, last=3), mode="joined_rows", closure="before_turn"),
        _row("ws", Span(edge="rs", first=1, last=3, direction="reverse"), mode="joined_rows",
             direction="reverse", side="WS", closure="after_turn"),
    ], final_edges=["ws"])
    result = compile_working_path(plan)
    assert [event.note for event in result.events if event.role == "closure"] == ["before_turn", "after_turn"]
    assert len(result.final_edges["ws"]) == 3
    with pytest.raises(ValueError, match="正面先"):
        _row("bad", Span(edge="edge", first=1, last=3), mode="joined_rows", closure="after_turn")


def test_gauge_is_phase_specific_and_unknown_or_fabricated_measurements_fail():
    with pytest.raises(ValueError, match="实测"):
        ConstructionGauge(id="rib", method="引拔肋纹", hook_mm=3.0, basis="unmeasured", rows_per_10cm=28)
    plan = WorkingPath(title="密度引用", existing_edges=[ExistingEdge(id="edge", count=2)], steps=[
        Route(id="row", label="密度缺失", gauge="missing", expected_sites=2,
              operations=[Work(source=Span(edge="edge", first=1, last=2))]),
    ], final_edges=["row"])
    with pytest.raises(ValueError, match="密度不存在"):
        compile_working_path(plan)


def test_v1_inputs_remain_readable_but_cannot_silently_gain_v2_construction():
    data = armhole_path_demo().model_dump()
    data["schema_version"] = "working-path-v1"
    assert compile_working_path(WorkingPath.model_validate(data))
    data["steps"][0]["operations"][1]["corner_sites"] = True
    with pytest.raises(ValueError, match="v2"):
        compile_working_path(WorkingPath.model_validate(data))


def test_buttonhole_declares_skipped_stitches_without_turning_them_into_decreases():
    plan = WorkingPath(title="扣眼练习", existing_edges=[ExistingEdge(id="rib", count=3),
                                                      ExistingEdge(id="body", count=2)], steps=[
        Route(id="hole", label="扣眼行", expected_sites=3, operations=[
            Work(source=Span(edge="rib", first=1, last=1), stitch="slst", loop="back"),
            ChainBridge(id="hole_chain", count=2, route_face="top", placement="buttonhole",
                        skipped=Span(edge="rib", first=2, last=3)),
            Work(source=Span(edge="body", first=1, last=2), stitch="slst", disposition="binding"),
        ]),
    ], final_edges=["hole"])
    result = compile_working_path(plan)
    assert len(result.final_edges["hole"]) == 3
    assert any(event.stitch == "buttonhole_boundary" and event.role == "retired" for event in result.events)
    assert not any(event.stitch == "dec" for event in result.events)
    with pytest.raises(ValueError, match="旧针位"):
        ChainBridge(id="hole", count=2, route_face="top", placement="buttonhole")


def test_continuing_a_yarn_loop_does_not_consume_the_head_that_will_be_worked_later():
    plan = WorkingPath(title="接续工作环", existing_edges=[ExistingEdge(id="seed", count=2)], steps=[
        _row("row", Span(edge="seed", first=1, last=2)),
        FoundationChain(id="extension", label="接续", chains=3, work_face="underside", other_face="top",
                        anchor=Span(edge="row", first=2, last=2), anchor_mode="continues_loop"),
    ], final_edges=["row"])
    # All extension sites must still be explicitly finished or worked.
    data = plan.model_dump()
    for face in ("top", "underside"):
        data["steps"].append({"kind": "finish_edge", "id": f"finish_{face}", "label": "边",
                              "source": {"edge": "extension", "first": 1, "last": 2, "face": face},
                              "reason": "unused_chain_face"})
    assert len(compile_working_path(WorkingPath.model_validate(data)).final_edges["row"]) == 2
    data["steps"][1]["anchor"]["first"] = data["steps"][1]["anchor"]["last"] = 1
    with pytest.raises(ValueError, match="当前工作环"):
        compile_working_path(WorkingPath.model_validate(data))
