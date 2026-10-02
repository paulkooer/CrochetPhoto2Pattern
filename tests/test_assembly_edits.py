"""Assembly text must describe the edited edges, including per-copy differences."""
from copy import deepcopy

import pytest

from app.models.crochet_params import CrochetParamsGenerator, refresh_derived
from app.models.gauge import ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis


def _scene():
    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=9, height_cm=18,
                             main_features=[], pose="站立", difficulty="easy",
                             parts=["头部", "身体", "手臂", "耳朵", "帽子", "裙子", "尾巴"])
    return analysis, StructureDesigner.design_3d_structure(analysis)


@pytest.mark.parametrize("name", ["头部", "手臂", "耳朵", "帽子", "裙子", "尾巴"])
def test_changed_target_anchor_reaches_assembly(name):
    analysis, structure = _scene()
    part = next(p for p in structure["parts"] if p["name"] == name)
    for instance in part["instances"]:
        instance["attachments"][0]["target_anchor"] = "front"
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    step = next(line for line in params["assembly_instructions"].splitlines()
                if name in line and "前方" in line)
    assert "前方" in step
    refreshed = refresh_derived(deepcopy(params))
    assert refreshed["assembly_instructions"] == params["assembly_instructions"]


def test_asymmetric_arms_keep_instance_to_anchor_mapping():
    analysis, structure = _scene()
    arms = next(p for p in structure["parts"] if p["name"] == "手臂")
    arms["instances"][0]["attachments"][0].update(target_anchor="back", self_anchor="tip")
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    assembly = params["assembly_instructions"]
    assert "手臂对称缝合" not in assembly
    assert "左手臂" in assembly and "末端" in assembly and "后方" in assembly
    assert "右手臂" in assembly and "右侧上方" in assembly


def test_hat_sewn_method_does_not_claim_it_is_only_worn():
    analysis, structure = _scene()
    hat = next(p for p in structure["parts"] if p["name"] == "帽子")
    hat["instances"][0]["attachments"][0]["method"] = "sewn"
    assembly = CrochetParamsGenerator.generate_params(analysis, structure)["assembly_instructions"]
    assert "帽子的开口缝合到头部的顶部" in assembly
    assert "直接戴在头部" not in assembly
    assert "hat" not in assembly


def test_internal_instance_ids_do_not_leak_and_lone_instance_merges():
    analysis, structure = _scene()
    tail = next(p for p in structure["parts"] if p["name"] == "尾巴")
    tail["instances"][0]["attachments"][0]["target_anchor"] = "front"
    assembly = CrochetParamsGenerator.generate_params(analysis, structure)["assembly_instructions"]
    assert "tail" not in assembly
    tail_lines = [line for line in assembly.splitlines()
                  if "尾巴" in line and "缝合" in line]
    assert len(tail_lines) == 1
    assert "根部" in tail_lines[0] and "前方" in tail_lines[0]


def test_lone_side_instance_merges_summary_into_one_line():
    analysis, structure = _scene()
    tail = next(p for p in structure["parts"] if p["name"] == "尾巴")
    tail["instances"][0]["instance_id"] = "tail_left"
    tail["instances"][0]["attachments"][0]["target_anchor"] = "front"
    assembly = CrochetParamsGenerator.generate_params(analysis, structure)["assembly_instructions"]
    assert "tail" not in assembly
    assert "左尾巴的根部缝合到身体的前方" in assembly


def test_multiple_edited_copies_keep_distinguishable_ids():
    analysis, structure = _scene()
    arms = next(p for p in structure["parts"] if p["name"] == "手臂")
    arms["instances"][0]["instance_id"] = "copy_a"
    arms["instances"][1]["instance_id"] = "copy_b"
    arms["instances"][1]["mirror_of"] = "copy_a"
    for instance, anchor in zip(arms["instances"], ("front", "back"), strict=True):
        instance["attachments"][0]["target_anchor"] = anchor
    assembly = CrochetParamsGenerator.generate_params(analysis, structure)["assembly_instructions"]
    assert "手臂（copy_a）的内端缝合到身体的前方" in assembly
    assert "手臂（copy_b）的内端缝合到身体的后方" in assembly


def test_crossed_left_right_connections_are_not_collapsed_to_default_pair():
    analysis, structure = _scene()
    arms = next(p for p in structure["parts"] if p["name"] == "手臂")
    arms["instances"][0]["attachments"][0]["target_anchor"] = "upper_right"
    arms["instances"][1]["attachments"][0]["target_anchor"] = "upper_left"
    assembly = CrochetParamsGenerator.generate_params(analysis, structure)["assembly_instructions"]
    assert "左手臂的内端缝合到身体的右侧上方" in assembly
    assert "右手臂的内端缝合到身体的左侧上方" in assembly
    assert "手臂对称缝合" not in assembly


def test_one_piece_keeps_head_and_body_attachment_regions_distinct():
    analysis, structure = _scene()
    ears = next(p for p in structure["parts"] if p["name"] == "耳朵")
    ears["instances"][0]["attachments"][0]["target_anchor"] = "back"
    assembly = CrochetParamsGenerator.generate_params(
        analysis, structure, style=ShapingStyle(one_piece=True))["assembly_instructions"]
    assert "一体件头部段的后方" in assembly
    assert "耳朵对称" not in assembly
