"""Tests for crochet parameter generation."""
import pytest
from app.schemas import ImageAnalysis
from app.models.crochet_params import CrochetParamsGenerator


@pytest.fixture
def sample_analysis():
    return ImageAnalysis(
        body_type="标准",
        head_diameter_cm=9.0,
        height_cm=18.0,
        main_features=["大眼睛"],
        pose="站立",
        difficulty="easy",
        parts=["头部", "身体"]
    )


@pytest.fixture
def sample_structure():
    return {
        "parts": [
            {"name": "头部", "shape": "sphere", "diameter_cm": 9.0},
            {"name": "身体", "shape": "cylinder", "height_cm": 9.0},
        ]
    }


def test_generate_params_returns_required_keys(sample_analysis, sample_structure):
    params = CrochetParamsGenerator.generate_params(sample_analysis, sample_structure)
    assert "materials" in params
    assert "parts" in params
    assert "assembly_instructions" in params
    assert "difficulty" in params
    assert "estimated_time_minutes" in params


def test_stitch_counts_are_reasonable(sample_analysis, sample_structure):
    params = CrochetParamsGenerator.generate_params(sample_analysis, sample_structure)
    for part in params["parts"]:
        for stitch in part.rounds:
            assert 1 <= stitch.stitches <= 48, (
                f"Part '{part.name}' row {stitch.row} has {stitch.stitches} stitches, "
                f"which is outside the reasonable Amigurumi range (1-48)"
            )


def test_head_starts_with_magic_ring(sample_analysis, sample_structure):
    params = CrochetParamsGenerator.generate_params(sample_analysis, sample_structure)
    head = [p for p in params["parts"] if p.name == "头部"][0]
    assert head.magic_ring is True
    assert head.rounds[0].stitches == 6


def test_head_sphere_increase_decrease(sample_analysis, sample_structure):
    """Verify head rounds increase then stay constant then decrease."""
    params = CrochetParamsGenerator.generate_params(sample_analysis, sample_structure)
    head = [p for p in params["parts"] if p.name == "头部"][0]
    stitch_counts = [r.stitches for r in head.rounds]

    # Should start at 6, increase to 36, stay at 36, then decrease back
    assert stitch_counts[0] == 6
    max_stitches = max(stitch_counts)
    assert max_stitches == 36
    # Last stitch should be less than max (decreasing)
    assert stitch_counts[-1] < max_stitches


def test_accessory_parts_stay_smaller_than_body():
    """耳朵/尾巴不得被生成为身体级 24 针圆柱（回归：H4 分派错误）。"""
    from app.models.structure_designer import StructureDesigner

    analysis = ImageAnalysis(
        body_type="标准",
        head_diameter_cm=9.0,
        height_cm=18.0,
        main_features=[],
        pose="站立",
        difficulty="easy",
        parts=["头部", "身体", "耳朵", "尾巴"],
    )
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    by_name = {p.name: p for p in params["parts"]}
    body_max = max(r.stitches for r in by_name["身体"].rounds)
    for acc in ("耳朵", "尾巴"):
        acc_max = max(r.stitches for r in by_name[acc].rounds)
        assert acc_max < body_max, (
            f"{acc} 最大针数 {acc_max} 不应达到身体级别 {body_max}"
        )
