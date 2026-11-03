"""The static result types describe exactly what the models and generators produce."""
from types import UnionType
from typing import Annotated, Union, get_args, get_origin, get_type_hints

import pytest

from app.schemas import (
    RESULT_KEYS,
    CrochetPart,
    CrochetStitch,
    PartData,
    PartGauge,
    PatternParams,
    PatternResult,
    ResultData,
    RoundData,
)
from tests.test_app_smoke import _mock_result


@pytest.mark.parametrize(("typed", "model"), [(RoundData, CrochetStitch), (PartData, CrochetPart)])
def test_part_and_round_types_match_their_models(typed, model):
    assert set(get_type_hints(typed)) == set(model.model_fields)


def _serialized_type(annotation):
    """Compare model field types after stripping validation and serializing rounds."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _serialized_type(get_args(annotation)[0])
    if origin in (Union, UnionType):
        return frozenset(_serialized_type(arg) for arg in get_args(annotation))
    if origin in (dict, list):
        return origin, tuple(_serialized_type(arg) for arg in get_args(annotation))
    return RoundData if annotation is CrochetStitch else annotation


@pytest.mark.parametrize(("typed", "model", "exceptions"), [
    (RoundData, CrochetStitch, set()),
    (PartData, CrochetPart, {"gauge"}),
    (ResultData, PatternResult, {"params", "result_id", "history_id"}),
])
def test_serialized_field_types_match_their_models(typed, model, exceptions):
    for name, annotation in get_type_hints(typed).items():
        if name not in exceptions:
            assert _serialized_type(annotation) == _serialized_type(model.model_fields[name].annotation), name


def test_part_gauge_type_matches_the_serialized_model():
    assert get_type_hints(PartData)["gauge"] == dict[str, float]
    assert {name: _serialized_type(field.annotation) for name, field in PartGauge.model_fields.items()} == {
        "stitches_per_10cm": float,
        "rows_per_10cm": float,
    }
    part = CrochetPart(name="帽子", type="cylinder", color="blue", rounds=[{"row": 1, "stitches": 6}],
                       gauge={"stitches_per_10cm": 13, "rows_per_10cm": 16})
    assert part.to_data()["gauge"] == {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0}
    part.gauge = None
    assert "gauge" not in part.to_data()


def test_required_keys_for_session_shapes():
    assert RoundData.__required_keys__ == {"row", "stitches"}
    assert PartData.__required_keys__ == {"name", "rounds"}
    assert PatternParams.__required_keys__ == {"parts"}
    assert ResultData.__required_keys__ == {"analysis", "structure", "params"}


def test_result_type_matches_the_result_contract():
    session = {"result_id", "history_id", "title"}
    assert set(get_type_hints(ResultData)) == set(RESULT_KEYS) | session
    assert set(PatternResult.model_fields) - {"schema_version"} == set(RESULT_KEYS) | session


@pytest.mark.parametrize("style", [
    {}, {"one_piece": True}, {"skirt_style": "attached"}, {"skirt_style": "attached", "ruffle_hem": True},
])
def test_generated_params_use_only_declared_keys(style):
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.gauge import ShapingStyle
    from app.models.image_parser import ImageParser
    from app.models.structure_designer import StructureDesigner
    from app.services.result_logic import STYLE_DEFAULTS

    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure, style=ShapingStyle(**{**STYLE_DEFAULTS, **style}), head_opening_stitches=None)
    assert set(params) <= set(get_type_hints(PatternParams))
    for part in params["parts"]:
        assert set(part) <= set(get_type_hints(PartData))
        for rd in part["rounds"]:
            assert set(rd) <= set(get_type_hints(RoundData))


def test_crochet_part_to_data_is_its_dump():
    part = CrochetPart(**_mock_result("typed")["params"]["parts"][0])
    assert part.to_data() == part.model_dump()
