"""Canonical part identity must not reinterpret custom names in saved structures."""
import pytest

from app.models.crochet_params import CrochetParamsGenerator
from app.schemas import ImageAnalysis, PartKind, part_kind_from_name


@pytest.mark.parametrize(("name", "kind"), [
    ("头部", PartKind.HEAD), ("身体", PartKind.BODY),
    ("手臂", PartKind.ARMS), ("腿部", PartKind.LEGS),
    ("尾巴", PartKind.TAIL), ("耳朵", PartKind.EARS),
    ("帽子", PartKind.HAT), ("裙子", PartKind.SKIRT),
])
def test_saved_canonical_names_resolve_to_domain_identity(name, kind):
    assert part_kind_from_name(name) is kind


@pytest.mark.parametrize("name", ["head", "Head", "装饰球", "", None, [], {}])
def test_unknown_or_malformed_names_are_not_canonicalized(name):
    assert part_kind_from_name(name) is None


@pytest.mark.parametrize("name", ["head", "Head", "装饰球"])
def test_explicit_legacy_custom_cylinder_keeps_name_shape_and_opening_rules(name):
    analysis = ImageAnalysis(
        body_type="未评估", head_diameter_cm=8.3, height_cm=24,
        main_features=[], pose="站立", difficulty="medium", parts=["头部"],
    )
    structure = {"parts": [{"name": name, "shape": "cylinder", "length_cm": 3.8,
                             "diameter_cm": 1.5}]}
    part = CrochetParamsGenerator.generate_params(analysis, structure)["parts"][0]
    assert (part["name"], part["type"], len(part["rounds"]), part["color"]) == (name, "cylinder", 7, "body")
    with pytest.raises(ValueError, match="独立头部"):
        CrochetParamsGenerator.generate_params(analysis, structure, head_opening_stitches=6)
