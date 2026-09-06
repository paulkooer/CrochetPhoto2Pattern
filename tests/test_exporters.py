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
    head = [p for p in params["parts"] if p["name"] == "头部"][0]
    assert f"## 🧶 头部 ({len(head['rounds'])} 圈)" in md
    # 表格行数 = 圈数（表头 2 行除外）
    table_rows = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert len(table_rows) >= sum(len(p["rounds"]) for p in params["parts"]) + 2 * len(params["parts"])


def test_export_accepts_dict_parts_after_json_edit():
    """局部修正路径存回的是 dict 形态的 parts，导出必须同样可用。"""
    params, analysis = _sample_params()
    edited = {
        **{k: v for k, v in params.items() if k != "parts"},
        "parts": list(params["parts"]),
    }
    md = export_markdown(edited, analysis)
    assert "## 🧶 头部" in md


def test_export_states_symmetric_part_copy_count():
    params, analysis = _sample_params()
    arms = next(p for p in params["parts"] if p["name"] == "手臂")
    assert arms["quantity"] == 2
    md = export_markdown(params, analysis)
    assert "手臂 × 2 个" in md
    assert "制作数量**：2 个相同部件" in md


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


def test_export_difficulty_aligned_with_cyc_project_levels():
    """导出的难度标签按 CYC Project Levels 对齐（不再裸显英文枚举值）。"""
    params, analysis = _sample_params()  # mock analysis 难度恒为 easy
    md = export_markdown(params, analysis)
    assert "难度：简单（CYC Basic）" in md
    assert "难度：easy" not in md


def test_difficulty_label_fallback_keeps_legacy_values():
    """旧结果里可能存了未知难度值——兜底原样显示而非 KeyError。"""
    from app.schemas import difficulty_label
    assert difficulty_label("easy") == "简单（CYC Basic）"
    assert difficulty_label("easy", zh=False) == "Easy (CYC Basic)"
    assert difficulty_label("mystery") == "mystery"
    assert difficulty_label("—") == "—"


def test_repeat_notation_uniform_and_uneven():
    """聚合计数 → 专业重复写法；非均匀/不自洽返回 None；单次增减渲染为不带 ×n 的分组。"""
    from app.utils.exporters import _repeat_notation
    assert _repeat_notation(18, 12, 6, 0) == "(X,V)×6"
    assert _repeat_notation(12, 6, 6, 0) == "(V)×6"       # 环起首圈全增
    assert _repeat_notation(6, 12, 0, 6) == "(A)×6"       # 每组消费 2 针
    assert _repeat_notation(21, 18, 3, 0) == "(5X,V)×3"   # 非 6 等分组
    assert _repeat_notation(16, 12, 4, 0) == "(2X,V)×4"
    assert _repeat_notation(24, 24, 0, 0) is None          # 平针圈无重复语义
    assert _repeat_notation(13, 12, 1, 0) == "(11X,V)"     # 单次增（与 parade 单分组同口径）
    assert _repeat_notation(11, 12, 0, 1) == "(10X,A)"     # 单次减同理消费 2 针
    assert _repeat_notation(25, 24, 6, 0) is None          # 聚合不自洽


def test_round_table_shows_professional_repeat_column():
    """圈表新增"针法写法"列——聚合数翻译为图例约定的重复记号。"""
    params, analysis = _sample_params()
    md = export_markdown(params, analysis)
    assert "| 圈数 | 针数 | 加针 | 减针 | 针法写法 | 配色 | 说明 |" in md
    assert "(V)×6" in md and "(X,V)×6" in md


def test_markdown_preamble_includes_ring_start_alternative():
    """工艺前言补环起替代法（Supergurumi ch-4 引拔成环 / 社区 ch-2 写法）。

    来源：Supergurumi 蜜蜂图解 "Chain 4, sl st into the first ch to form
    a ring"；Hobbii《Easy Alternative to the Magic Ring》与 r/Amigurumi
    常见建议的 ch-2 变体。
    """
    params, analysis = _sample_params()
    md = export_markdown(params, analysis)
    assert "环起困难的替代法" in md
    assert "锁 4 针引拔成环" in md and "锁 2 针" in md


def test_preamble_mentions_joined_rounds_convention():
    """导出前言注明引拔圈（中文社区主流）与螺旋钩等价——跨社区钩法桥接。"""
    params, analysis = _sample_params()
    md = export_markdown(params, analysis)
    assert "引拔圈钩法" in md and "针数节奏完全一致" in md


def test_preamble_mentions_increase_offset_rule():
    """螺旋钩加针点自动漂移 vs 引拔圈需手动错开——toruyuri 日语法则
    （奇数段段尾/偶数段段中），固定同点加针会成六角形。"""
    params, analysis = _sample_params()
    md = export_markdown(params, analysis)
    assert "自动漂移" in md and "六角形" in md and "段尾" in md
