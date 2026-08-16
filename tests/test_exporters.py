"""Tests for Markdown export (previously uncovered module)."""
from app.models.crochet_params import CrochetParamsGenerator
from app.models.image_parser import ImageParser
from app.models.structure_designer import StructureDesigner
from app.utils.exporters import export_markdown


def _sample_params():
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    return CrochetParamsGenerator.generate_params(analysis, structure), analysis.model_dump()


def test_export_contains_all_sections():
    params, analysis = _sample_params()
    md = export_markdown(params, analysis)
    assert "# 🧶 Amigurumi 钩织图解" in md
    assert "## 🧵 所需材料" in md
    assert "## 🔧 装配说明" in md
    assert analysis["body_type"] in md  # analysis header line


def test_export_rounds_table_rows_match_len_rounds():
    """部件标题圈数 = len(rounds)（rows 派生后的渲染一致性）。"""
    params, _ = _sample_params()
    md = export_markdown(params)
    head = [p for p in params["parts"] if p.name == "头部"][0]
    assert f"## 🧶 头部 ({len(head.rounds)} 圈)" in md
    # 表格行数 = 圈数（表头 2 行除外）
    table_rows = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert len(table_rows) >= sum(len(p.rounds) for p in params["parts"]) + 2 * len(params["parts"])


def test_export_accepts_dict_parts_after_json_edit():
    """局部修正路径存回的是 dict 形态的 parts，导出必须同样可用。"""
    params, analysis = _sample_params()
    edited = {
        **{k: v for k, v in params.items() if k != "parts"},
        "parts": [p.model_dump() for p in params["parts"]],
    }
    md = export_markdown(edited, analysis)
    assert "## 🧶 头部" in md


def test_export_survives_broken_material_entries():
    """用户在 JSON 编辑器改坏材料结构时，导出降级为 '?' 而非 KeyError。"""
    params, _ = _sample_params()
    params["materials"].append({"item": "缺数量"})
    md = export_markdown(params)
    assert "**缺数量**：?" in md


def test_export_without_analysis():
    params, _ = _sample_params()
    md = export_markdown(params, analysis=None)
    assert "所需材料" in md
