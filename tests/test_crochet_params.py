"""Tests for crochet parameter generation."""
import pytest

from app.models.crochet_params import CrochetParamsGenerator
from app.schemas import ImageAnalysis


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


# ── 材料清单 / 装配说明随实际部件动态生成 ────────────────────────────────────

def _params_for(parts, head_d=9.0, height=18.0):
    from app.models.structure_designer import StructureDesigner

    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=head_d, height_cm=height,
        main_features=[], pose="站立", difficulty="easy", parts=parts,
    )
    structure = StructureDesigner.design_3d_structure(analysis)
    return CrochetParamsGenerator.generate_params(analysis, structure)


def test_materials_reflect_actual_parts():
    """只有耳朵时不应列肤色线之外的分组，也不应出现安全眼。"""
    params = _params_for(["头部", "耳朵"])
    items = [m["item"] for m in params["materials"]]
    assert "肤色系毛线" in items
    assert "主体色毛线" not in items  # 无身体/帽子/裙子/尾巴
    assert "安全眼" in items  # 有头部


def test_no_head_means_no_safety_eyes():
    params = _params_for(["身体", "腿部"])
    items = [m["item"] for m in params["materials"]]
    assert "安全眼" not in items
    assert "主体色毛线" in items
    assert "肤色系毛线" in items  # 腿部用肤色


def test_assembly_mentions_only_present_parts():
    """没有手臂/腿部时，装配说明不得再提"对称缝合到身体两侧"。"""
    params = _params_for(["头部", "身体"])
    asm = params["assembly_instructions"]
    assert "手臂" not in asm
    assert "腿部" not in asm
    assert "头部" in asm


def test_assembly_covers_all_part_kinds_when_present():
    params = _params_for(["头部", "身体", "手臂", "腿部", "耳朵", "尾巴"])
    asm = params["assembly_instructions"]
    for token in ("手臂", "腿部", "耳朵", "尾巴", "安全眼"):
        assert token in asm


def test_estimated_time_scales_with_parts():
    small = _params_for(["头部"])
    big = _params_for(["头部", "身体", "手臂", "腿部", "耳朵", "尾巴"])
    assert big["estimated_time_minutes"] > small["estimated_time_minutes"]
    assert small["estimated_time_minutes"] >= 30


def test_rows_always_matches_rounds():
    params = _params_for(["头部", "身体"])
    for part in params["parts"]:
        assert part.rows == len(part.rounds)


# ── 加减针说明：按真实发布图解的通行规范锁定 ────────────────────────────────
#
# 依据（网络查证，非自行设计）：
# - mstinacrochet.com《六个基础勾针织法》：环起/短针/加针/减针/引拔即够钩玩偶
# - zhuanlan.zhihu.com/p/2397749055：X=短针 V=加针(1针目钩2短针) A=减针(2并1)
# - pipsrainbow.com Crocheting in the Round："decrease in 6's: 36,30,24,18,12,6"
# - 发布图解书写惯例：系数 1 省略——(X,V)×6 而非 (1X,V)×6

STANDARD_TABLE = [
    # (上一圈针数, 本圈针数, 期望隔数, 期望符号)
    (6, 12, 0, "V×6"),     # 每针都加
    (12, 18, 1, "(X,V)×6"),
    (18, 24, 2, "(2X,V)×6"),
    (30, 36, 4, "(4X,V)×6"),
    (36, 30, 4, "(4X,A)×6"),   # ← 镜面对称圈，同样隔 4
    (30, 24, 3, "(3X,A)×6"),
    (18, 12, 1, "(X,A)×6"),
    (12, 6, 0, "A×6"),     # 每2针并1针
]


def test_standard_inc_dec_table():
    """逐条对照通行标准：符号记法与"隔N针"必须与发布图解完全一致。"""
    import re

    from app.models.crochet_params import _sphere_rounds
    rounds = _sphere_rounds(36)
    transitions = {}
    prev = None
    for r in rounds:
        if prev is not None:
            transitions[(prev, r["stitches"])] = r["notes"]
        prev = r["stitches"]
    for before, after, expected_gap, expected_sym in STANDARD_TABLE:
        notes = transitions[(before, after)]
        assert expected_sym in notes, (before, after, notes)
        if expected_gap == 0:
            assert ("每针都加" in notes) if after > before else ("每2针并1针" in notes), notes
        else:
            m = re.search(r"隔(\d+)针", notes)
            assert m and int(m.group(1)) == expected_gap, (before, after, notes)


def test_symbolic_pattern_arithmetic_is_executable():
    """符号记法必须可执行且自洽：(aX,V)×6 耗 (a+1)·6 针；(aX,A)×6 耗 (a+2)·6 针。

    系数省略规则：括号内 X 前无数字 = 1（如 (X,V)×6 即 (1X,V)×6）。
    """
    import re

    from app.models.crochet_params import _cylinder_rounds, _sphere_rounds
    checked = 0
    for rounds in (_sphere_rounds(36), _sphere_rounds(24), _cylinder_rounds(24, 5)):
        for r in rounds:
            notes = r["notes"] or ""
            m = re.search(r"\((\d*)X,([VA])\)×6", notes)
            if not m:
                continue
            a = int(m.group(1) or 1)  # 空系数 = 1
            op = m.group(2)
            if op == "V":  # 加针圈：耗 (a+1)·6 = 上一圈；产 (a+2)·6 = 本圈
                assert (a + 1) * 6 == r["stitches"] - 6, r
                assert (a + 2) * 6 == r["stitches"], r
            else:          # 减针圈：耗 (a+2)·6 = 上一圈；产 (a+1)·6 = 本圈
                assert (a + 2) * 6 == r["stitches"] + 6, r
                assert (a + 1) * 6 == r["stitches"], r
            checked += 1
    assert checked >= 10  # 覆盖了绝大多数加减针圈


def test_special_rounds_notes():
    from app.models.crochet_params import _sphere_rounds
    rounds = _sphere_rounds(36)
    by_row = {r["row"]: r for r in rounds}
    assert by_row[1]["notes"] == "魔法环起6针（X×6）"
    assert by_row[2]["notes"] == "加针×6（V×6，每针都加）"          # 6→12
    # 连续加针圈带错开半组提示（PlanetJune 技法，M2.9）
    assert by_row[3]["notes"].startswith("(X,V)×6，隔1针加1针")   # 12→18
    assert "错开半组" in by_row[3]["notes"]
    assert by_row[6]["notes"].startswith("(4X,V)×6，隔4针加1针")  # 30→36
    assert by_row[13]["notes"].startswith("(4X,A)×6，隔4针减1针")  # 36→30
    assert by_row[16]["notes"].startswith("(X,A)×6，隔1针减1针")   # 18→12
    assert by_row[17]["notes"].startswith("减针×6（A×6，每2针并1针）")  # 12→6
    assert "36X（不加不减）" in by_row[7]["notes"]                  # 直钩段带针数


def test_pattern_level_conventions_present():
    """图解级技法说明：螺旋钩/记号扣/隐形减针（真实图解惯例）。"""
    params = _params_for(["头部"])
    notes = params["notes"]
    for token in ("螺旋钩法", "记号扣", "隐形减针"):
        assert token in notes, token


# ── B1/B2/B3 回归：帽形开口、针数缩放、标注高度自洽 ─────────────────────────

def test_hat_is_open_cup_larger_than_head():
    """帽子必须开口（末圈=最大针数、无减针）且帽围>头围。"""
    params = _params_for(["头部", "帽子"])
    head, hat = params["parts"][0], params["parts"][1]
    assert hat.type == "cup"
    assert hat.rounds[-1].decrease == 0
    assert hat.rounds[-1].stitches == max(r.stitches for r in hat.rounds)
    assert hat.diameter_cm > head.diameter_cm
    assert max(r.stitches for r in hat.rounds) > max(r.stitches for r in head.rounds)
    assert "不收口" in hat.notes
    # 帽高（含帽顶）约为帽直径 × 0.6，不能罩到脖子（回归：旧公式 +80%）
    from app.models.crochet_params import HAT_DEPTH_RATIO
    assert abs(hat.height_cm - hat.diameter_cm * HAT_DEPTH_RATIO) < 0.8


def test_stitches_scale_with_head_diameter():
    """身体/四肢针数随头径缩放（回归：旧硬编码 24/12 针）。"""
    big = _params_for(["头部", "身体", "手臂"], head_d=20.0, height=45.0)
    by_name = {p.name: p for p in big["parts"]}
    # 20cm 头 → 默认 gauge（0.769cm/针）下 84 针（旧 0.785 锚点为 78）
    assert max(r.stitches for r in by_name["身体"].rounds) == 84
    assert 18 <= max(r.stitches for r in by_name["手臂"].rounds) <= 30  # 6.6cm 直径

    small = _params_for(["头部", "身体", "手臂"], head_d=5.0, height=12.0)
    by_name = {p.name: p for p in small["parts"]}
    assert max(r.stitches for r in by_name["身体"].rounds) == 18  # 5cm 头 → 缩小
    assert max(r.stitches for r in by_name["手臂"].rounds) >= 6


def test_annotated_height_excludes_base_dome():
    """标注高度只计竖直筒壁圈（直钩+收针）：起底加针段是水平圆盘不计高。

    回归（fable5 F3）：旧口径把圆盘 6 圈计入，4.5cm 身体被标成 9.4cm。
    帽子例外：帽顶圆盘本来就占据帽高（外部可见），仍按总圈数计。
    """
    from app.models.crochet_params import (
        BODY_HEAD_RATIO,
        DEFAULT_GAUGE,
        LIMB_HEAD_RATIO,
        _stitches_for_diameter,
    )
    params = _params_for(["头部", "身体", "手臂", "帽子"])
    by_name = {p.name: p for p in params["parts"]}
    body = by_name["身体"]
    n_dome = _stitches_for_diameter(9.0 * BODY_HEAD_RATIO) // 6
    # 四肢与身体统一行高（旧 1.2/1.6 差异已取消——行高是纱线属性）
    assert body.height_cm == round(
        (len(body.rounds) - n_dome) * DEFAULT_GAUGE.row_h_cm, 1)
    arm = by_name["手臂"]
    n_dome_arm = _stitches_for_diameter(9.0 * LIMB_HEAD_RATIO) // 6
    assert arm.height_cm == round(
        (len(arm.rounds) - n_dome_arm) * DEFAULT_GAUGE.row_h_cm, 1)
    hat = by_name["帽子"]
    assert abs(hat.height_cm - len(hat.rounds) * DEFAULT_GAUGE.row_h_cm) < 0.06
    # 头+身体标注不超过输入总高（旧版 9 + 9.4 > 18）
    assert 9.0 + body.height_cm <= 18.0 + 0.5
    # 身体 notes 明示"另含底部圆盘"
    assert "底部圆盘" in body.notes


def test_finishing_notes_present():
    from app.models.crochet_params import _cylinder_rounds, _sphere_rounds
    assert "勒紧收口" in _sphere_rounds(36)[-1]["notes"]
    assert "缝合" in _cylinder_rounds(24, 5)[-1]["notes"]


def test_skirt_is_open_and_wider_than_body():
    """裙子两端都开口：腰部开口起针（≈腰围针数），裙摆不收口（fable5 F1 回归：
    旧版复用 _cup_rounds，腰部是 6 针闭口圆盘，物理上套不进身体）。"""
    from app.models.crochet_params import BODY_HEAD_RATIO, _stitches_for_diameter
    params = _params_for(["身体", "裙子"])
    body, skirt = params["parts"]
    assert skirt.type == "cup"
    waist = _stitches_for_diameter(9.0 * BODY_HEAD_RATIO)
    assert skirt.rounds[0].stitches == waist          # R1 = 腰围开口（非魔法环 6 针）
    assert skirt.magic_ring is False
    assert "腰部环形起针" in skirt.rounds[0].notes
    assert skirt.rounds[-1].decrease == 0             # 裙摆不收口
    assert max(r.stitches for r in skirt.rounds) > max(r.stitches for r in body.rounds)
    assert "套入身体" in skirt.notes


# ── refresh_derived（局部修正后的派生量重算）────────────────────────────────

def test_refresh_derived_recomputes_after_edit():
    params = _params_for(["头部"])
    before_time = params["estimated_time_minutes"]
    edited = {**{k: v for k, v in params.items() if k != "parts"},
              "parts": [p.model_dump() for p in params["parts"]]}
    edited["parts"][0]["rounds"] = edited["parts"][0]["rounds"] * 3  # 圈数×3
    from app.models.crochet_params import refresh_derived
    out = refresh_derived(edited)
    assert out["estimated_time_minutes"] > before_time
    assert out["total_stitches"] == sum(
        r["stitches"] for r in out["parts"][0]["rounds"])
    assert out["materials"] and all(
        isinstance(m, dict) and "item" in m and "quantity" in m for m in out["materials"])


# ── fable5 F2 回归：端部起针部件的照片配色自底向上 ─────────────────────────

def test_color_direction_bottom_up_for_limbs_and_body():
    """鞋在照片底部（黑带 0.75–1.0）→ 腿部 R1（脚底）应为黑，腿根为蓝。"""
    bands = [{"start": 0.0, "end": 0.75, "color": "蓝色"},
             {"start": 0.75, "end": 1.0, "color": "黑色"}]
    params = _params_for(["腿部", "身体"], )
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.structure_designer import StructureDesigner
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["腿部", "身体", "头部"])
    params = CrochetParamsGenerator.generate_params(
        a, StructureDesigner.design_3d_structure(a), color_bands=bands)
    by = {p.name: p for p in params["parts"]}
    leg_colors = [r.color for r in by["腿部"].rounds]
    assert leg_colors[0] == "黑色", f"脚底应取鞋色，实际 {leg_colors}"
    assert leg_colors[-1] == "蓝色"
    body_colors = [r.color for r in by["身体"].rounds]
    assert body_colors[0] != body_colors[-1] or all(c == "蓝色" for c in body_colors)
    # 头部自顶起针：R1 仍取照片顶部色（蓝）
    assert by["头部"].rounds[0].color == "蓝色"


def test_assembly_rebuilt_after_json_edit():
    """refresh_derived 删掉帽子后装配说明不得残留帽子步骤（fable5 F5）。"""
    params = _params_for(["头部", "身体", "帽子"])
    edited = {**{k: v for k, v in params.items() if k != "parts"},
              "parts": [p.model_dump() for p in params["parts"] if p.name != "帽子"]}
    from app.models.crochet_params import refresh_derived
    out = refresh_derived(edited)
    assert "帽" not in out["assembly_instructions"]
    assert "头部" in out["assembly_instructions"]  # 其余步骤仍在


# ── LLM 语义配色：优先于照片色带（fable5 P2）─────────────────────────────

def test_semantic_color_overrides_bands():
    """模型说"深棕头发/蓝上衣"→ 头部/身体整段单色，色带让位。"""
    from app.models.structure_designer import StructureDesigner
    bands = [{"start": 0.0, "end": 1.0, "color": "白色"}]  # 与语义冲突的色带
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体"],
                      hair_color="深棕色", top_color="蓝色")
    params = CrochetParamsGenerator.generate_params(
        a, StructureDesigner.design_3d_structure(a), color_bands=bands)
    by = {p.name: p for p in params["parts"]}
    assert {r.color for r in by["头部"].rounds} == {"深棕色"}
    assert {r.color for r in by["身体"].rounds} == {"蓝色"}
    assert "照片语义" in by["头部"].notes
    assert "换线" not in (by["头部"].notes or "")


def test_no_semantic_falls_back_to_bands():
    from app.models.structure_designer import StructureDesigner
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["身体"])
    bands = [{"start": 0.0, "end": 1.0, "color": "蓝色"}]
    params = CrochetParamsGenerator.generate_params(
        a, StructureDesigner.design_3d_structure(a), color_bands=bands)
    assert {r.color for r in params["parts"][0].rounds} == {"蓝色"}
    assert "照片语义" not in (params["parts"][0].notes or "")


def test_structure_added_skirt_reaches_params():
    """结构层按 clothing_type 补的裙子必须进入参数层（回归：generate_params
    曾只遍历 analysis.parts，结构层补件被丢弃）。"""
    from app.models.structure_designer import StructureDesigner
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体"], clothing_type="连衣裙",
                      bottom_color="红色")
    params = CrochetParamsGenerator.generate_params(
        a, StructureDesigner.design_3d_structure(a))
    names = [p.name for p in params["parts"]]
    assert names == ["头部", "身体", "裙子"]
    skirt = params["parts"][-1]
    assert skirt.rounds[0].stitches == 36  # 腰部开口起针
    assert "裙" in params["assembly_instructions"]
