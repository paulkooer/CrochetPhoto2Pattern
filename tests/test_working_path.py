"""Independent source-site expectations and failure cases for explicit routes."""
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as hs

from app.models.working_path import (
    ChainBridge,
    ExistingEdge,
    Hold,
    Route,
    Site,
    Span,
    Work,
    WorkingPath,
    armhole_path_demo,
    compile_working_path,
)


def _sites(edge, positions, face="top"):
    return tuple(Site(edge, i, face) for i in positions)


def test_sleeves_use_reserved_yoke_sites_and_opposite_chain_side_in_declared_order():
    result = compile_working_path(armhole_path_demo())
    assert result.held_edges["left_opening"] == (
        _sites("yoke", range(5, 11)) + _sites("left_bridge", (3, 2, 1), "underside"))
    assert result.held_edges["right_opening"] == (
        _sites("yoke", range(19, 25)) + _sites("right_bridge", (3, 2, 1), "underside"))
    for side in ("left", "right"):
        sleeve = [event for event in result.events if event.route == f"{side}_sleeve"]
        assert tuple(event.sources[0] for event in sleeve) == result.held_edges[f"{side}_opening"]
        assert all(len(event.sources) == len(event.outputs) == 1 for event in sleeve)
    body = result.final_edges["body_edge"]
    assert body[4:7] == _sites("left_bridge", (1, 2, 3))
    assert body[15:18] == _sites("right_bridge", (1, 2, 3))
    assert {name: len(sites) for name, sites in result.final_edges.items()} == {
        "body_edge": 22, "left_sleeve": 9, "right_sleeve": 9,
    }
    # 28 declared sites + 16 body SC outputs + 6 two-sided chain sites + 18 sleeve outputs.
    assert result.created_sites == 74
    assert result.consumed_sites == 34
    assert sum(map(len, result.final_edges.values())) == 40
    payload = result.to_dict()
    assert payload["evidence"] == "declared_site_inventory_only"
    assert payload["physical_execution_verified"] is False
    assert payload["fit_verified"] is False and payload["photo_likeness_verified"] is False


@pytest.mark.parametrize("mutation,message", [
    # Same counts, wrong chain side: the sleeve steals sites that belong to the body.
    (lambda d: d["steps"][1]["spans"][1].update(face="top"), "已使用|保留给"),
    (lambda d: d["steps"][1]["spans"][0].update(first=4, last=9), "已使用"),
    (lambda d: d["steps"][0]["operations"][0]["source"].update(last=29), "越界"),
    (lambda d: d["steps"][0].update(expected_sites=21), "工作边应有"),
    (lambda d: d["steps"][3]["operations"][0]["source"].update(edge="yoke", first=5, last=10), "保留给"),
    (lambda d: d["steps"][1]["spans"][0].update(edge="left_sleeve"), "尚未建立"),
    (lambda d: d["steps"][1]["spans"].append(deepcopy(d["steps"][1]["spans"][0])), "重复引用"),
    (lambda d: d["steps"][2].update(id="left_opening"), "ID 不可重复"),
    (lambda d: d["final_edges"].pop(), "未声明去向"),
    (lambda d: d["final_edges"].append("left_bridge"), "别名重复"),
    (lambda d: d["final_edges"].append("body_edge"), "最终工作边不可重复"),
    (lambda d: d["final_edges"].append("missing"), "不存在"),
])
def test_wrong_routes_fail_even_when_total_stitch_counts_can_still_match(mutation, message):
    data = armhole_path_demo().model_dump()
    mutation(data)
    with pytest.raises(ValueError, match=message):
        compile_working_path(WorkingPath.model_validate(data))


def test_paused_armhole_keeps_all_sites_available_without_faking_a_completed_sleeve():
    data = armhole_path_demo().model_dump()
    data["steps"].pop()
    data["final_edges"][-1] = "right_opening"
    result = compile_working_path(WorkingPath.model_validate(data))
    assert result.final_edges["right_opening"] == result.held_edges["right_opening"]
    assert not any(event.route == "right_sleeve" for event in result.events)


def test_chain_working_face_is_declared_instead_of_assuming_body_always_uses_the_top():
    data = armhole_path_demo().model_dump()
    for operation in data["steps"][0]["operations"]:
        if operation["kind"] == "chain":
            operation["route_face"] = "underside"
    for step in data["steps"][1:3]:
        step["spans"][1]["face"] = "top"
    result = compile_working_path(WorkingPath.model_validate(data))
    assert result.final_edges["body_edge"][4:7] == _sites("left_bridge", (1, 2, 3), "underside")
    assert result.held_edges["left_opening"][-3:] == _sites("left_bridge", (3, 2, 1))


def test_missing_chain_working_face_is_not_silently_guessed():
    data = armhole_path_demo().model_dump()
    del data["steps"][0]["operations"][1]["route_face"]
    with pytest.raises(ValueError, match="route_face"):
        WorkingPath.model_validate(data)


def test_one_source_cannot_be_consumed_again_via_an_alias_edge():
    data = armhole_path_demo().model_dump()
    duplicate = deepcopy(data["steps"][3])
    duplicate["id"] = "left_again"
    duplicate["operations"][0]["source"].update(edge="left_bridge", first=1, last=3, face="underside")
    duplicate["expected_sites"] = 3
    data["steps"].append(duplicate)
    with pytest.raises(ValueError, match="已使用"):
        compile_working_path(WorkingPath.model_validate(data))


def test_inc_dec_and_reverse_work_keep_exact_parents_instead_of_adjusting_only_totals():
    plan = WorkingPath(title="针位示例", existing_edges=[ExistingEdge(id="edge", count=4)], steps=[
        Route(id="shaped", label="加减", expected_sites=4, operations=[
            Work(source=Span(edge="edge", first=1, last=1)),
            Work(source=Span(edge="edge", first=2, last=2), stitch="inc"),
            Work(source=Span(edge="edge", first=3, last=4, direction="reverse"), stitch="dec"),
        ]),
    ], final_edges=["shaped"])
    result = compile_working_path(plan)
    assert [(event.stitch, event.sources, event.outputs) for event in result.events] == [
        ("sc", _sites("edge", [1]), _sites("shaped", [1])),
        ("inc", _sites("edge", [2]), _sites("shaped", [2, 3])),
        ("dec", _sites("edge", [4, 3]), _sites("shaped", [4])),
    ]


@pytest.mark.parametrize("operation", [
    {"kind": "work", "source": {"edge": "edge", "first": 1, "last": 3}, "stitch": "dec"},
    {"kind": "work", "source": {"edge": "edge", "first": 1, "last": 4}, "stitch": "fptr"},
    {"kind": "work", "source": {"edge": "edge", "first": True, "last": 4}},
    {"kind": "work", "source": {"edge": "edge", "first": 4, "last": 1}},
    {"kind": "work", "source": {"edge": "edge", "first": 1, "last": 4, "face": "post"}},
    {"kind": "chain", "id": "unanchored", "count": 3, "route_face": "top"},
])
def test_incomplete_and_unsupported_operations_are_rejected(operation):
    with pytest.raises(ValueError):
        data = {"title": "无效", "existing_edges": [{"id": "edge", "count": 4}],
                "steps": [{"kind": "route", "id": "next", "label": "无效", "expected_sites": 4,
                           "operations": [operation]}], "final_edges": ["next"]}
        compile_working_path(WorkingPath.model_validate(data))


def test_mutated_models_are_revalidated_and_compilation_does_not_mutate_inputs():
    plan = armhole_path_demo()
    before = plan.model_dump_json()
    first = compile_working_path(plan).to_dict()
    assert compile_working_path(plan).to_dict() == first
    assert plan.model_dump_json() == before
    plan.steps[0].expected_sites = True
    with pytest.raises(ValueError):
        compile_working_path(plan)


def test_site_budget_is_enforced_during_building(monkeypatch):
    monkeypatch.setattr("app.models.working_path.MAX_SITES", 30)
    with pytest.raises(ValueError, match="上限"):
        compile_working_path(armhole_path_demo())


@given(hs.lists(hs.integers(min_value=1, max_value=12), min_size=7, max_size=7))
def test_disjoint_yoke_partitions_conserve_sites_across_varying_bridge_and_armhole_sizes(counts):
    front_a, arm_a, back, arm_b, front_b, chain_a, chain_b = counts
    total = sum(counts[:5])
    arm1 = (front_a + 1, front_a + arm_a)
    middle = (arm1[1] + 1, arm1[1] + back)
    arm2 = (middle[1] + 1, middle[1] + arm_b)
    route = Route(id="body", label="分路", expected_sites=front_a + back + front_b + chain_a + chain_b,
                  operations=[
                      Work(source=Span(edge="seed", first=1, last=front_a)),
                      ChainBridge(id="bridge_a", count=chain_a, route_face="top"),
                      Work(source=Span(edge="seed", first=middle[0], last=middle[1])),
                      ChainBridge(id="bridge_b", count=chain_b, route_face="top"),
                      Work(source=Span(edge="seed", first=arm2[1] + 1, last=total)),
                  ])
    held = [Hold(id=name, label=name, spans=[Span(edge="seed", first=bounds[0], last=bounds[1]),
                                           Span(edge=bridge, first=1, last=n, face="underside")])
            for name, bounds, bridge, n in [("arm_a", arm1, "bridge_a", chain_a),
                                            ("arm_b", arm2, "bridge_b", chain_b)]]
    plan = WorkingPath(title="独立分区算例", existing_edges=[ExistingEdge(id="seed", count=total)],
                       steps=[route, *held], final_edges=["body", "arm_a", "arm_b"])
    result = compile_working_path(plan)
    assert [len(result.final_edges[key]) for key in plan.final_edges] == [
        front_a + back + front_b + chain_a + chain_b, arm_a + chain_a, arm_b + chain_b,
    ]
    all_sites = [site for sites in result.final_edges.values() for site in sites]
    assert len(set(all_sites)) == len(all_sites)
    assert len(all_sites) == total + 2 * (chain_a + chain_b)
