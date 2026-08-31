"""Metric sizing must be chosen explicitly, never inferred from one photo."""
import math

import pytest

from app.models.sizing import scale_analysis_to_target_height
from app.schemas import ImageAnalysis


def _analysis(head=4.0, height=20.0):
    return ImageAnalysis(
        body_type="标准", head_diameter_cm=head, height_cm=height,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"],
    )


def test_target_height_preserves_photo_ratio_not_reference_centimetres():
    scaled, meta = scale_analysis_to_target_height(
        _analysis(), 30.0, source="test_target")
    assert scaled.height_cm == 30.0
    assert scaled.head_diameter_cm == 6.0
    assert meta["photo_head_to_height_ratio"] == 0.2
    assert meta["applied_head_to_height_ratio"] == 0.2
    assert meta["absolute_scale_from_photo"] is False
    assert meta["source"] == "test_target"


def test_implausible_parser_ratio_is_clamped_before_sizing():
    scaled, meta = scale_analysis_to_target_height(
        _analysis(head=20.0, height=10.0), 18.0, source="test_target")
    assert scaled.height_cm == 18.0
    assert scaled.head_diameter_cm == 9.0
    assert meta["ratio_clamped"] is True


@pytest.mark.parametrize("height", [9.9, 60.1, math.nan, math.inf])
def test_photo_target_height_has_explicit_product_bounds(height):
    with pytest.raises(ValueError, match="目标高度"):
        scale_analysis_to_target_height(_analysis(), height, source="test")
