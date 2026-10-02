"""Edited/loaded counts must keep their meaning before derived totals are built."""
from copy import deepcopy

import pytest

from app.models.validator import validate_pattern
from app.schemas import CrochetPart, CrochetStitch
from app.ui.result_logic import rebuild_params


def _params():
    return {"parts": [{"name": "手臂", "type": "cylinder", "color": "红色",
                       "rounds": [{"row": 1, "stitches": 6}]}]}


@pytest.mark.parametrize("field", ["row", "stitches", "increase", "decrease"])
@pytest.mark.parametrize("value", [True, False, 1.5, float("inf"), float("nan")])
def test_invalid_round_counts_cannot_be_normalized_into_valid_edits(field, value):
    params = _params()
    params["parts"][0]["rounds"][0][field] = value
    with pytest.raises(ValueError):
        rebuild_params(params)
    assert not validate_pattern(params)["ok"]


@pytest.mark.parametrize("value", [True, False, 1.5, float("inf")])
def test_invalid_quantity_cannot_change_material_totals(value):
    params = _params()
    params["parts"][0]["quantity"] = value
    with pytest.raises(ValueError):
        rebuild_params(params)
    assert not validate_pattern(params)["ok"]


@pytest.mark.parametrize("value", ["6", 6.0, 6])
def test_integer_legacy_counts_survive_rebuild(value):
    params = _params()
    params["parts"][0]["rounds"][0]["stitches"] = value
    params["parts"][0]["quantity"] = "2"
    out = rebuild_params(params)
    assert out["total_stitches"] == 12
    assert validate_pattern(out)["ok"]


@pytest.mark.parametrize("kind", ["no_parts", "no_rounds", "duplicate_parts", "duplicate_rows"])
def test_unrenderable_structure_is_rejected_before_rebuild(kind):
    params = _params()
    if kind == "no_parts":
        params["parts"] = []
    elif kind == "no_rounds":
        params["parts"][0]["rounds"] = []
    elif kind == "duplicate_parts":
        params["parts"].append(deepcopy(params["parts"][0]))
    else:
        params["parts"][0]["rounds"].append({"row": 1, "stitches": 6})
    before = deepcopy(params)
    with pytest.raises(ValueError):
        rebuild_params(params)
    assert params == before


def test_part_schema_rejects_empty_rounds_directly():
    with pytest.raises(ValueError):
        CrochetPart(name="手臂", type="cylinder", color="红色", rounds=[])


def test_part_schema_rejects_bool_quantity_directly():
    with pytest.raises(ValueError):
        CrochetPart(name="手臂", type="cylinder", color="红色", quantity=True,
                    rounds=[CrochetStitch(row=1, stitches=6)])


def test_structure_count_cannot_hide_a_boolean_as_one_instance():
    from app.models.geometry import PartGeometry

    with pytest.raises(ValueError):
        PartGeometry(part_id="head", name="头部", shape="sphere", diameter_cm=9,
                     count=True, instances=[{"instance_id": "head",
                                            "position": {"x": 0, "y": 0.5, "z": 0}}])


def test_rebuild_keeps_algebra_errors_visible_for_further_editing():
    params = _params()
    params["parts"][0]["rounds"].append({"row": 2, "stitches": 12})
    out = rebuild_params(params)
    assert out["parts"][0]["rounds"][1]["increase"] == 0
    assert not validate_pattern(out)["ok"]


def test_rebuild_rejects_pathological_part_counts():
    params = _params()
    params["parts"] = [deepcopy(params["parts"][0]) for _ in range(65)]
    for index, part in enumerate(params["parts"]):
        part["name"] = f"部件{index}"
    with pytest.raises(ValueError):
        rebuild_params(params)


def test_part_schema_caps_round_count():
    rounds = [{"row": row, "stitches": 6} for row in range(1, 2001)]
    part = CrochetPart(name="围巾", type="cylinder", color="红色", rounds=rounds)
    assert part.rows == 2000
    rounds.append({"row": 2001, "stitches": 6})
    with pytest.raises(ValueError):
        CrochetPart(name="围巾", type="cylinder", color="红色", rounds=rounds)
