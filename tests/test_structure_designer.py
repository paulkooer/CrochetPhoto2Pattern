"""Tests for 3D structure designer."""
import pytest

from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis


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


def test_extreme_head_to_height_ratio_never_rounds_dimensions_to_zero():
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=20.0, height_cm=10.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["身体", "手臂", "腿部", "尾巴", "裙子"],
    )
    result = StructureDesigner.design_3d_structure(analysis)
    for part in result["parts"]:
        dimensions = [part.get(key) for key in
                      ("diameter_cm", "height_cm", "length_cm")]
        assert any(value is not None and value > 0 for value in dimensions)


def test_accessories_have_dedicated_shapes():
    """耳朵/尾巴等受支持配件应有专属条目。"""
    analysis = ImageAnalysis(
        body_type="标准",
        head_diameter_cm=9.0,
        height_cm=18.0,
        main_features=[],
        pose="站立",
        difficulty="easy",
        parts=["头部", "耳朵", "尾巴"]
    )
    result = StructureDesigner.design_3d_structure(analysis)
    by_name = {p["name"]: p for p in result["parts"]}
    # 默认按长耳（兔/驴）建模：宽度窄于头径，且有独立耳长。旧口径把耳朵记成
    # 直径=头径×0.35 的球 → 生成 6 针小球，长耳玩偶的成品等于"没有耳朵"。
    assert by_name["耳朵"]["shape"] == "ear"
    assert by_name["耳朵"]["diameter_cm"] < analysis.head_diameter_cm
    assert by_name["耳朵"]["length_cm"] > by_name["耳朵"]["diameter_cm"]
    assert by_name["尾巴"]["shape"] == "cylinder"
    assert "length_cm" in by_name["尾巴"]


def _ear_analysis(**ratios):
    return ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "耳朵"], **ratios,
    )


def test_measured_round_lobe_still_becomes_a_tube():
    """轮廓判出的耳朵一律做长管：正面掩码无法区分熊的圆耳与兔的长耳，
    实测耳长又只是下界，所以量到再短也按耳长下限（2.4× 耳宽）做。"""
    ear = next(p for p in StructureDesigner.design_3d_structure(
        _ear_analysis(ear_length_ratio=0.06, ear_width_ratio=0.05))["parts"]
        if p["name"] == "耳朵")
    assert ear["shape"] == "ear"
    assert ear["length_cm"] >= 2.4 * ear["diameter_cm"]


def test_measured_long_ear_honours_the_measurement():
    """实测耳长超过下限时以实测为准；耳宽按实测占比 × 整体高度。"""
    ear = next(p for p in StructureDesigner.design_3d_structure(
        _ear_analysis(ear_length_ratio=0.45, ear_width_ratio=0.10))["parts"]
        if p["name"] == "耳朵")
    assert ear["shape"] == "ear"
    assert ear["diameter_cm"] == pytest.approx(18.0 * 0.10, abs=0.1)
    assert ear["length_cm"] == pytest.approx(18.0 * 0.45, abs=0.1)


def test_hat_is_open_cup_with_slack():
    """帽子必须是开口杯形且带松量（回归：闭口球+1.05× 松量被量化吞掉，戴不进去）。"""
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["帽子"],
    )
    result = StructureDesigner.design_3d_structure(analysis)
    hat = result["parts"][0]
    assert hat["shape"] == "cup"
    assert hat["diameter_cm"] >= 9.0 * 1.1


def test_clothing_type_skirt_adds_part():
    """LLM 判定穿裙但 parts 漏了裙子 → 结构层自动补上。"""
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"], clothing_type="裙子",
    )
    result = StructureDesigner.design_3d_structure(analysis)
    names = [p["name"] for p in result["parts"]]
    assert names == ["头部", "身体", "裙子"]
    assert result["parts"][-1]["shape"] == "cup"


def test_clothing_type_pants_no_skirt():
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"], clothing_type="裤子",
    )
    result = StructureDesigner.design_3d_structure(analysis)
    assert "裙子" not in [p["name"] for p in result["parts"]]


def test_structure_v2_has_machine_readable_coordinate_contract():
    """结构不再只是尺寸表：坐标约定和模板不确定性必须可机器读取。"""
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"],
    )
    result = StructureDesigner.design_3d_structure(analysis)
    assert result["schema_version"] == "2.0"
    assert result["coordinate_system"]["units"] == "normalized_template_space"
    assert result["coordinate_system"]["z_axis"] == "back_negative_front_positive"
    assert all(part["source"] == "template_inferred" for part in result["parts"])
    assert all(part.get("confidence") is None for part in result["parts"])


def test_symmetric_parts_have_two_mirrored_attached_instances():
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["身体", "手臂"],
    )
    result = StructureDesigner.design_3d_structure(analysis)
    arms = next(part for part in result["parts"] if part["name"] == "手臂")
    left, right = arms["instances"]
    assert arms["count"] == 2 and arms["mirror_group"] == "arms"
    assert left["position"]["x"] == -right["position"]["x"]
    assert right["mirror_of"] == left["instance_id"]
    assert left["attachments"][0]["target_part_id"] == "body"
    assert right["attachments"][0]["target_anchor"] == "upper_right"


def test_absent_attachment_target_does_not_create_dangling_edge():
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["手臂"],
    )
    result = StructureDesigner.design_3d_structure(analysis)
    assert all(not instance["attachments"]
               for instance in result["parts"][0]["instances"])


def test_structure_graph_model_rejects_dangling_attachment():
    from pydantic import ValidationError

    from app.models.geometry import StructureGeometry

    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["头部"],
    )
    result = StructureDesigner.design_3d_structure(analysis)
    result["parts"][0]["instances"][0]["attachments"] = [{
        "target_part_id": "missing",
        "target_anchor": "top",
        "self_anchor": "bottom",
        "method": "sewn",
    }]
    with pytest.raises(ValidationError):
        StructureGeometry(**result)


def test_structure_v2_rejects_duplicate_logical_names():
    from copy import deepcopy

    from pydantic import ValidationError

    from app.models.geometry import StructureGeometry

    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体"],
    )
    result = StructureDesigner.design_3d_structure(analysis)
    duplicate = deepcopy(result["parts"][0])
    duplicate["part_id"] = "other_head"
    duplicate["instances"][0]["instance_id"] = "other_head"
    result["parts"].append(duplicate)
    with pytest.raises(ValidationError):
        StructureGeometry(**result)
