"""Static structure types cover normalized v2 graphs and permissive legacy data."""
from copy import deepcopy
from typing import assert_type, get_type_hints

from app.models.geometry import (
    AttachmentSpec,
    EulerRotation,
    NormalizedPosition,
    PartGeometry,
    PartInstance,
    StructureGeometry,
    normalize_structure,
)
from app.models.image_parser import ImageParser
from app.models.structure_designer import StructureDesigner
from app.schemas import (
    StructureAttachmentData,
    StructureData,
    StructureInstanceData,
    StructurePartData,
    StructureVectorData,
)


def test_structure_types_track_model_field_names():
    assert set(get_type_hints(StructureData)) == set(StructureGeometry.model_fields)
    assert set(get_type_hints(StructurePartData)) == set(PartGeometry.model_fields) | {"type"}
    assert set(get_type_hints(StructureInstanceData)) == set(PartInstance.model_fields)
    assert set(get_type_hints(StructureAttachmentData)) == set(AttachmentSpec.model_fields)
    assert set(get_type_hints(StructureVectorData)) == set(NormalizedPosition.model_fields)
    assert set(get_type_hints(StructureVectorData)) == set(EulerRotation.model_fields)
    assert StructureData.__required_keys__ == {"parts"}
    assert StructurePartData.__required_keys__ == {"name"}


def test_nested_v2_field_types_match_serialized_models():
    for model in (NormalizedPosition, EulerRotation, AttachmentSpec):
        typed = StructureAttachmentData if model is AttachmentSpec else StructureVectorData
        assert get_type_hints(typed) == {name: field.annotation for name, field in model.model_fields.items()}
    instance = get_type_hints(StructureInstanceData)
    assert instance["instance_id"] is str
    assert instance["position"] is StructureVectorData
    assert instance["rotation_deg"] is StructureVectorData
    assert instance["attachments"] == list[StructureAttachmentData]
    # exclude_none=True omits a missing mirror rather than serializing null.
    assert instance["mirror_of"] is str
    assert StructureInstanceData.__required_keys__ == {
        "instance_id", "position", "rotation_deg", "attachments"}
    part = get_type_hints(StructurePartData)
    assert part["diameter_cm"] is part["height_cm"] is part["length_cm"] is float
    assert part["count"] is int and part["part_id"] is object
    assert part["instances"] == list[StructureInstanceData]


def test_v2_structure_data_keeps_the_existing_serialization():
    generated = StructureDesigner.design_3d_structure(ImageParser._mock_analysis())
    model = StructureGeometry.model_validate(generated)
    assert type(generated) is dict
    assert generated == model.model_dump(exclude_none=True) == model.to_data()
    assert normalize_structure(generated) == generated


def test_legacy_structure_preserves_unvalidated_metadata_and_normalizes_numbers():
    legacy = {
        "schema_version": {"legacy": 1},
        "proportions": ["custom"],
        "notes": {"custom": "preserve"},
        "parts": [{"name": "头部", "shape": 7, "color": None, "height_cm": "8.5", "count": "2",
                   "part_id": {"legacy": "custom"}, "extra": ["preserve"]}],
    }
    snapshot = deepcopy(legacy)
    normalized = normalize_structure(legacy)
    assert legacy == snapshot
    assert normalized == {
        **snapshot,
        "parts": [{**snapshot["parts"][0], "height_cm": 8.5, "count": 2}],
    }


def test_structure_fields_are_statically_typed() -> None:
    structure = StructureDesigner.design_3d_structure(ImageParser._mock_analysis())
    assert_type(structure["parts"], list[StructurePartData])
    part = structure["parts"][0]
    assert_type(part["name"], str)
    assert_type(part.get("diameter_cm"), float | None)
    assert_type(part.get("part_id"), object)
    instances = part.get("instances", [])
    assert_type(instances, list[StructureInstanceData])
    assert_type(instances[0]["position"]["x"], float)
    assert_type(instances[0]["attachments"], list[StructureAttachmentData])
