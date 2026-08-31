"""Tests for Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.schemas import CrochetPart, CrochetStitch, ImageAnalysis


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
    with pytest.raises(ValidationError):
        ImageAnalysis(body_type="标准")  # missing required fields


def test_crochet_stitch():
    stitch = CrochetStitch(row=1, stitches=6, increase=0, notes="魔法环")
    assert stitch.row == 1
    assert stitch.stitches == 6


def test_crochet_part():
    rounds = [CrochetStitch(row=i, stitches=6 * i) for i in range(1, 4)]
    part = CrochetPart(
        name="头部", type="sphere",
        rounds=rounds, color="skin", magic_ring=True
    )
    assert part.name == "头部"
    assert len(part.rounds) == 3
    assert part.magic_ring is True
    assert part.quantity == 1


def test_crochet_part_quantity_is_bounded():
    rounds = [CrochetStitch(row=1, stitches=6)]
    assert CrochetPart(
        name="手臂", type="cylinder", quantity=2,
        rounds=rounds, color="skin").quantity == 2
    with pytest.raises(ValidationError):
        CrochetPart(name="手臂", type="cylinder", quantity=0,
                    rounds=rounds, color="skin")


def test_crochet_part_rows_is_derived_not_stored():
    """rows 一律由 len(rounds) 派生：不留存储字段，杜绝两者失同步。"""
    rounds = [CrochetStitch(row=i, stitches=6 * i) for i in range(1, 4)]
    part = CrochetPart(name="头部", type="sphere", rounds=rounds, color="skin")
    assert part.rows == 3
    assert "rows" not in part.model_dump()  # 序列化结果也不包含 rows


def test_crochet_part_ignores_stale_rows_in_legacy_json():
    """历史 JSON 里残留的 rows 值应被忽略而非报错/复活。"""
    rounds = [CrochetStitch(row=1, stitches=6)]
    part = CrochetPart(name="头部", type="sphere", rows=99,
                       rounds=rounds, color="skin")
    assert part.rows == 1


def test_duplicate_parts_are_deduped_preserving_order():
    """LLM 输出重复部件名必须去重（重名会生成冲突 widget key 使 UI 崩溃）。"""
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体", "头部", "手臂", "身体"],
    )
    assert analysis.parts == ["头部", "身体", "手臂"]


def test_semantic_color_fields_optional_and_parsed():
    """LLM 语义配色字段：默认 None；JSON 携带时解析透传。"""
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["头部"],
    )
    assert analysis.hair_color is None and analysis.clothing_type is None
    rich = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["头部", "裙子"],
        hair_color="深棕色", top_color="蓝色", bottom_color="红色", clothing_type="裙子",
    )
    assert rich.hair_color == "深棕色" and rich.clothing_type == "裙子"
