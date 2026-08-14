"""Tests for Pydantic schemas."""
import pytest
from app.schemas import ImageAnalysis, CrochetStitch, CrochetPart, CrochetPattern


def test_image_analysis_valid():
    analysis = ImageAnalysis(
        body_type="标准",
        head_diameter_cm=9.0,
        height_cm=18.0,
        main_features=["大眼睛", "小鼻子"],
        pose="站立",
        difficulty="easy",
        parts=["头部", "身体"]
    )
    assert analysis.body_type == "标准"
    assert analysis.head_diameter_cm == 9.0
    assert len(analysis.parts) == 2


def test_image_analysis_missing_field():
    with pytest.raises(Exception):
        ImageAnalysis(body_type="标准")  # missing required fields


def test_crochet_stitch():
    stitch = CrochetStitch(row=1, stitches=6, increase=0, notes="魔法环")
    assert stitch.row == 1
    assert stitch.stitches == 6


def test_crochet_part():
    rounds = [CrochetStitch(row=i, stitches=6 * i) for i in range(1, 4)]
    part = CrochetPart(
        name="头部", type="sphere", rows=3,
        rounds=rounds, color="skin", magic_ring=True
    )
    assert part.name == "头部"
    assert len(part.rounds) == 3
    assert part.magic_ring is True
