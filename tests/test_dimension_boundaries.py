"""Reject invalid physical inputs before any shape allocation or preview."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import Gauge
from app.models.geometry import PartGeometry, normalize_structure
from app.models.image_parser import ImageParser
from app.models.structure_designer import StructureDesigner
from app.schemas import CrochetPart
from app.ui.result_logic import import_backup


@pytest.mark.parametrize("field", ["diameter_cm", "height_cm", "length_cm"])
@pytest.mark.parametrize("value", [True, 0, -1, float("inf"), float("nan"), 201, 1e100])
def test_structure_dimensions_are_bounded_before_generation(field, value):
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    structure["parts"][0][field] = value
    with pytest.raises(ValueError):
        normalize_structure(structure)
    with (patch("app.models.crochet_params._sphere_rounds", side_effect=AssertionError("allocated")),
          pytest.raises(ValueError)):
        CrochetParamsGenerator.generate_params(analysis, structure)


@pytest.mark.parametrize("value", [True, -1, 0, float("inf"), float("nan"), 201])
def test_legacy_dimension_validation_rejects_invalid_input(value):
    structure = {"parts": [{"name": "头部", "shape": "sphere", "diameter_cm": value}]}
    with pytest.raises(ValueError):
        normalize_structure(structure)


def test_legacy_numeric_strings_and_null_optional_dimensions_are_normalized():
    analysis = ImageParser._mock_analysis()
    legacy = {"parts": [{"name": "头部", "shape": "sphere", "diameter_cm": "9",
                         "height_cm": None, "count": "2"}]}
    snapshot = deepcopy(legacy)
    normalized = normalize_structure(legacy)
    assert normalized["parts"][0]["diameter_cm"] == 9.0
    assert "height_cm" not in normalized["parts"][0]
    assert normalized["parts"][0]["count"] == 2
    assert legacy == snapshot
    params = CrochetParamsGenerator.generate_params(analysis, legacy)
    assert params["parts"][0]["quantity"] == 2


@pytest.mark.parametrize("field", ["stitches_per_10cm", "rows_per_10cm"])
@pytest.mark.parametrize("value", [True, 0, -1, float("nan"), float("inf"), 1e100])
def test_direct_gauge_construction_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        Gauge(**{"stitches_per_10cm": 13, "rows_per_10cm": 16, field: value})


def test_supported_dimension_and_density_endpoints_remain_usable():
    part = PartGeometry(part_id="body", name="身体", shape="cylinder", height_cm=200,
                        instances=[{"instance_id": "body", "position": {"x": 0, "y": 0, "z": 0}}])
    assert part.height_cm == 200
    assert Gauge(40, 50).rounds_for_height(part.height_cm) == 1000
    assert Gauge(6, 8).row_h_cm == 1.25


def test_direct_gauge_and_legacy_mapping_agree_for_valid_numeric_strings():
    from app.models.gauge import gauge_from_mapping

    raw = {"stitches_per_10cm": "20", "rows_per_10cm": "16"}
    assert Gauge(**raw) == gauge_from_mapping(raw)


def test_legacy_null_diameter_uses_the_existing_template_fallback():
    analysis = ImageParser._mock_analysis()
    legacy = {"parts": [{"name": "头部", "shape": "sphere", "diameter_cm": None}]}
    params = CrochetParamsGenerator.generate_params(analysis, legacy)
    assert params["parts"][0]["diameter_cm"] == analysis.head_diameter_cm


@pytest.mark.parametrize("field", ["diameter_cm", "height_cm"])
@pytest.mark.parametrize("value", [True, 0, -1, float("inf"), float("nan"), 201, 1e100])
def test_import_rejects_invalid_pattern_dimensions(field, value):
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    params["parts"][0][field] = value
    with pytest.raises(ValueError):
        CrochetPart(**params["parts"][0])
    with pytest.raises(ValueError):
        import_backup({"analysis": analysis.model_dump(), "structure": structure, "params": params}, "bad")


def test_structure_part_count_is_bounded():
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    structure["parts"].extend(
        {"name": f"部件{i}", "shape": "sphere"} for i in range(64))
    with pytest.raises(ValueError):
        normalize_structure(structure)


def test_legacy_duplicate_part_names_are_rejected():
    legacy = {"parts": [{"name": "头部", "shape": "sphere"},
                        {"name": "头部", "shape": "sphere"}]}
    with pytest.raises(ValueError):
        normalize_structure(legacy)
