"""Construction boundaries: start edges, stitch inventory, shapes and assembly."""
from copy import deepcopy
from itertools import product

import pytest

from app.models.dressed_doll import DollDesign, DollPlan, build_doll_plan, starter_design
from app.models.dressed_doll.models import Component, Foundation, WorkStep
from app.models.dressed_doll.recipes import oval_boot, panel, strand
from app.models.gauge import Gauge


@pytest.mark.parametrize("height,gauge,hat,hair,outfit,layers", list(product(
    (16, 24, 36), (Gauge(13, 16), Gauge(22, 28)),
    ("wide_brim", "folded_band"), ("curls", "straight"),
    ("dress", "jacket_skirt"), (1, 2),
)))
def test_design_variations_keep_construction_types(height, gauge, hat, hair, outfit, layers):
    d = starter_design("wide_brim_curls", height_cm=height, gauge=gauge).model_dump()
    d.update(hat=hat, hair=hair, outfit=outfit, skirt_layers=layers)
    plan = build_doll_plan(DollDesign.model_validate(d))
    parts = {p.id: p for p in plan.components}
    assert plan.status == "unverified_prototype" and plan.input_origin == "manual_design"
    assert parts["hair"].work == "rows" and parts["hair"].quantity == plan.design.hair_strands
    assert parts["shoes"].foundation.kind == "oval_chain"
    assert {s.section for s in parts["shoes"].steps} >= {"鞋底", "鞋面", "鞋头收窄"}
    palm = [s.stitches for s in parts["arms"].steps if s.section == "手掌"]
    wrist = [s.stitches for s in parts["arms"].steps if s.section == "手腕"]
    assert max(palm) > min(wrist)
    assert parts["sleeves"].foundation.kind == "chain_ring"
    assert "内裙层" in parts["skirt_1"].name
    assert ("skirt_2" in parts) == (layers == 2)
    assert ("hat_band" in parts) == (hat == "folded_band")
    assert all(p.foundation.chains == 0 for p in parts.values() if p.foundation.kind == "magic_ring")
    assert DollPlan.model_validate_json(plan.model_dump_json()).model_dump() == plan.model_dump()


def test_foundation_chains_and_turns_are_counted_without_becoming_working_stitches():
    piece = panel("panel", "衣片", "试验", 12, 3, color="白色")
    assert piece.foundation.chains == 13
    assert [s.stitches for s in piece.steps] == [12, 12, 12]
    assert [s.turning_chain for s in piece.steps] == [0, 1, 1]
    assert piece.operations_per_copy == 13 + 36 + 2
    straight = strand("hair", "发束", 10, 4, curled=False, color="发色")
    curl = strand("hair", "发束", 10, 4, curled=True, color="发色")
    assert straight.steps[0].stitches == 9 and straight.operations_per_copy == 19
    assert curl.steps[0].stitches == 18 and curl.operations_per_copy == 28


def test_oval_sole_has_two_end_arcs_and_targets_toe_decreases_before_heel():
    boot = oval_boot(3, 1.6, 7, Gauge(22, 28))
    chains = boot.foundation.chains
    sole = [s for s in boot.steps if s.section == "鞋底"]
    assert sole[0].stitches == 2 * chains
    assert [s.stitches for s in sole] == [2 * chains + 6 * i for i in range(len(sole))]
    toe = [s.number for s in boot.steps if s.section == "鞋头收窄"]
    heel = [s.number for s in boot.steps if s.section == "鞋跟与鞋口"]
    assert max(toe) < min(heel)
    assert boot.steps[-1].stitches >= 7 + 2  # candidate clearance, not a fit certification
    assert boot.quantity == 2


@pytest.mark.parametrize("mutate", [
    lambda p: p["steps"][1].update(expression="V×5", stitches=10),
    lambda p: p["steps"][1].update(turning_chain=0),
    lambda p: p["steps"][0].update(turning_chain=1),
    lambda p: p["foundation"].update(chains=12),
    lambda p: p["steps"][1].update(expression="12F"),
    lambda p: p.update(work="rounds"),
    lambda p: p.update(quantity=True),
    lambda p: p["steps"][0].update(number=2),
])
def test_corrupt_recipe_is_rejected(mutate):
    data = panel("panel", "衣片", "试验", 12, 3, color="白色").model_dump()
    mutate(data)
    with pytest.raises(ValueError):
        Component.model_validate(data)


def test_oval_foundation_cannot_be_reinterpreted_as_plain_circle():
    data = oval_boot(3, 1.6, 7, Gauge(22, 28)).model_dump()
    data["steps"][0].update(expression=f'{data["steps"][0]["stitches"]}X')
    with pytest.raises(ValueError, match="起针工作边|椭圆首圈"):
        Component.model_validate(data)
    with pytest.raises(ValueError):
        Foundation(kind="magic_ring", chains=10)


@pytest.mark.parametrize("changes", [
    {"height_cm": float("nan")}, {"height_cm": float("inf")}, {"height_cm": True},
    {"neck_diameter_cm": 5}, {"palm_diameter_cm": 0.8},
    {"foot_length_cm": 1}, {"hair_strands": 21}, {"hair_strands": True},
    {"skirt_layers": True},
    {"schema_version": "dressed-doll-design-v2"}, {"unrecognized": 1},
])
def test_invalid_dimensions_and_unknown_input_are_not_silently_clamped(changes):
    data = DollDesign().model_dump() | changes
    with pytest.raises(ValueError):
        DollDesign.model_validate(data)


def test_unresolvable_palm_wrist_difference_is_reported():
    d = DollDesign(palm_diameter_cm=2, wrist_diameter_cm=1.99)
    with pytest.raises(ValueError, match="量化成相同针数"):
        build_doll_plan(d)


def test_sleeve_cannot_silently_exceed_available_armhole_height():
    d = DollDesign(bodice_length_cm=1)
    with pytest.raises(ValueError, match="袖窿.*上衣片"):
        build_doll_plan(d)


@pytest.mark.parametrize("kind", ["dangling", "cycle", "orphan", "duplicate", "verified"])
def test_plan_cannot_lose_joins_or_upgrade_its_evidence_level(kind):
    data = build_doll_plan(DollDesign()).model_dump()
    if kind == "dangling":
        data["joins"][0]["target"] = "missing"
    elif kind == "cycle":
        data["joins"].append({"source": "body", "target": "head", "placement": "循环"})
    elif kind == "orphan":
        data["joins"].pop()
    elif kind == "duplicate":
        data["joins"].append(deepcopy(data["joins"][0]))
    else:
        data["status"] = "physically_verified"
    with pytest.raises(ValueError):
        DollPlan.model_validate(data)


def test_plan_is_deterministic_and_excludes_unrequested_flower_modules():
    d = starter_design("folded_cap_layers")
    a, b = build_doll_plan(d), build_doll_plan(d)
    assert a.model_dump_json() == b.model_dump_json()
    assert all("flower" not in p.id for p in a.components)
    assert not any("照片实测" in p.finish for p in a.components)
    assert any("不填棉" in p.finish for p in a.components if p.id == "bag")
    assert any("两条短边" in p.finish for p in a.components if p.id == "hat_band")


def test_steps_are_immutable_at_export_boundary_even_after_model_construct():
    from app.utils.dressed_doll_export import export_doll_markdown

    plan = build_doll_plan(DollDesign())
    invalid = plan.model_copy(deep=True)
    invalid.components[0].steps[1] = WorkStep(number=2, section="错误", expression="1X", stitches=1)
    with pytest.raises(ValueError):
        export_doll_markdown(invalid)
