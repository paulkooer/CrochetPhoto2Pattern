"""Tests for 3D structure designer."""
from app.schemas import ImageAnalysis
from app.models.structure_designer import StructureDesigner


def test_design_produces_parts():
    analysis = ImageAnalysis(
        body_type="标准",
        head_diameter_cm=9.0,
        height_cm=18.0,
        main_features=["大眼睛"],
        pose="站立",
        difficulty="easy",
        parts=["头部", "身体", "手臂", "腿部"]
    )
    result = StructureDesigner.design_3d_structure(analysis)
    assert "parts" in result
    assert len(result["parts"]) == 4


def test_head_is_sphere():
    analysis = ImageAnalysis(
        body_type="标准",
        head_diameter_cm=9.0,
        height_cm=18.0,
        main_features=[],
        pose="站立",
        difficulty="easy",
        parts=["头部"]
    )
    result = StructureDesigner.design_3d_structure(analysis)
    head = result["parts"][0]
    assert head["shape"] == "sphere"
    assert head["diameter_cm"] == 9.0


def test_proportions_use_analysis_values():
    analysis = ImageAnalysis(
        body_type="标准",
        head_diameter_cm=7.0,
        height_cm=20.0,
        main_features=[],
        pose="站立",
        difficulty="medium",
        parts=["头部", "身体"]
    )
    result = StructureDesigner.design_3d_structure(analysis)
    head = [p for p in result["parts"] if p["name"] == "头部"][0]
    assert head["diameter_cm"] == 7.0


def test_accessories_have_dedicated_shapes():
    """耳朵/尾巴等配件应有专属条目，未知部件默认小球而非身体级圆柱。"""
    analysis = ImageAnalysis(
        body_type="标准",
        head_diameter_cm=9.0,
        height_cm=18.0,
        main_features=[],
        pose="站立",
        difficulty="easy",
        parts=["头部", "耳朵", "尾巴", "未知部件"]
    )
    result = StructureDesigner.design_3d_structure(analysis)
    by_name = {p["name"]: p for p in result["parts"]}
    assert by_name["耳朵"]["shape"] == "sphere"
    assert by_name["耳朵"]["diameter_cm"] < analysis.head_diameter_cm
    assert by_name["尾巴"]["shape"] == "cylinder"
    assert "length_cm" in by_name["尾巴"]
    assert by_name["未知部件"]["shape"] == "sphere"
    assert by_name["未知部件"]["diameter_cm"] < analysis.head_diameter_cm
