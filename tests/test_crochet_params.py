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
    assert "手臂对称" in asm and "腿部对称" in asm and "耳朵对称" in asm


def test_assembly_wording_follows_edited_physical_quantity():
    from app.models.crochet_params import refresh_derived

    params = _params_for(["身体", "手臂"])
    params["parts"] = [part.model_dump() for part in params["parts"]]
    arms = next(part for part in params["parts"] if part["name"] == "手臂")
    arms["quantity"] = 1
    refresh_derived(params)
    assert "手臂缝合到身体一侧上方" in params["assembly_instructions"]
    assert "手臂对称" not in params["assembly_instructions"]

    arms["quantity"] = 3
    refresh_derived(params)
    assert "手臂共 3 个" in params["assembly_instructions"]


def test_structure_v2_attachments_reach_assembly_plan():
    params = _params_for(["身体", "手臂"])
    plan = params["assembly_plan"]
    assert plan["source"] == "structure_v2"
    assert len(plan["connections"]) == 2
    assert {edge["target_part_name"] for edge in plan["connections"]} == {"身体"}
    assert "手臂对称缝合到身体两侧上方" in params["assembly_instructions"]


def test_unattached_v2_part_does_not_invent_missing_body_connection():
    params = _params_for(["手臂"])
    assert params["assembly_plan"]["connections"] == []
    assert "手臂未设置连接关系" in params["assembly_instructions"]
    assert "缝合到身体" not in params["assembly_instructions"]


def test_rewired_v2_attachment_changes_assembly_target():
    from app.models.structure_designer import StructureDesigner

    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy",
        parts=["头部", "身体", "手臂"],
    )
    structure = StructureDesigner.design_3d_structure(analysis)
    arms = next(part for part in structure["parts"] if part["name"] == "手臂")
    assert len(arms["instances"]) == 2
    for side, instance in zip(("left", "right"), arms["instances"]):  # noqa: B905
        instance["attachments"][0]["target_part_id"] = "head"
        instance["attachments"][0]["target_anchor"] = f"side_{side}"
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    assert "手臂缝合到头部的左侧、右侧" in params["assembly_instructions"]
    assert "手臂对称缝合到身体" not in params["assembly_instructions"]


def test_legacy_structure_keeps_name_based_assembly_fallback():
    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["手臂"],
    )
    legacy = {"parts": [{
        "name": "手臂", "shape": "cylinder", "length_cm": 3.0,
    }]}
    params = CrochetParamsGenerator.generate_params(analysis, legacy)
    assert "assembly_plan" not in params
    assert "手臂缝合到身体一侧上方" in params["assembly_instructions"]


def test_estimated_time_scales_with_parts():
    small = _params_for(["头部"])
    big = _params_for(["头部", "身体", "手臂", "腿部", "耳朵", "尾巴"])
    assert big["estimated_time_minutes"] > small["estimated_time_minutes"]
    assert small["estimated_time_minutes"] >= 30


def test_symmetric_part_quantity_is_included_in_all_derived_totals():
    """一份手臂圈序代表左右两件；总针数与工时必须按两份计算。"""
    params = _params_for(["身体", "手臂"])
    body, arms = params["parts"]
    assert body.quantity == 1
    assert arms.quantity == 2
    expected = (
        sum(row.stitches for row in body.rounds)
        + 2 * sum(row.stitches for row in arms.rounds)
    )
    assert params["total_stitches"] == expected


def test_legacy_structure_without_count_defaults_to_one_copy(
        sample_analysis, sample_structure):
    """旧备份没有 count/quantity 时不能被误判为成对部件。"""
    params = CrochetParamsGenerator.generate_params(sample_analysis, sample_structure)
    assert all(part.quantity == 1 for part in params["parts"])
    assert params["total_stitches"] == sum(
        row.stitches for part in params["parts"] for row in part.rounds)


def test_refresh_derived_respects_edited_quantity():
    from app.models.crochet_params import refresh_derived

    params = _params_for(["手臂"])
    edited = {**params, "parts": [params["parts"][0].model_dump()]}
    edited["parts"][0]["quantity"] = 3
    single = sum(row["stitches"] for row in edited["parts"][0]["rounds"])
    refresh_derived(edited)
    assert edited["total_stitches"] == single * 3


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
    # F36 最终口径：height_cm 只计轴向筒壁（与圆柱同判——径向盘不计高）；
    # 帽顶圈数仍含在 rounds 里（钩织时需要），但标注高度=筒深
    from app.models.crochet_params import HAT_DEPTH_RATIO
    from app.models.gauge import DEFAULT
    max_st = max(r.stitches for r in hat.rounds)
    n_up = max_st // 6
    wall_rounds = max(3, DEFAULT.rounds_for_height(hat.diameter_cm * HAT_DEPTH_RATIO))
    assert len(hat.rounds) == n_up + wall_rounds
    assert hat.height_cm == round(wall_rounds * DEFAULT.row_h_cm, 1)
    assert "筒深" in hat.notes and "不计入筒深" in hat.notes


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
    F36：帽子不再例外——帽顶盘与起底盘同为径向盘，不计入筒深标注。
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
    # F36：帽子与圆柱统一——径向盘（帽顶）不计入筒深标注；
    # 帽子 dome 用帽子自身最大针数推导（帽径 > 头径，dome 圈数不同）
    hat_dome = max(r.stitches for r in hat.rounds) // 6
    assert abs(hat.height_cm - (len(hat.rounds) - hat_dome) * DEFAULT_GAUGE.row_h_cm) < 0.06
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


def test_params_carry_generation_gauge():
    """params 必须携带生成时的 gauge（JSON 修正/备份导入的单一来源）。"""
    from app.models.gauge import PRESETS
    from app.models.structure_designer import StructureDesigner

    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                             main_features=[], pose="站立", difficulty="easy",
                             parts=["头部", "身体"])
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure, gauge=PRESETS["fine"])
    assert params["gauge"] == {"stitches_per_10cm": 20.0, "rows_per_10cm": 16.0}


def test_refresh_derived_preserves_generation_gauge():
    """非默认 gauge 的结果经 JSON 修正后，材料克数/钩针标签不得漂移。

    回归（N2）：旧版 refresh_derived 用 DEFAULT_GAUGE 重算材料——fine
    密度生成 65g/2.0–2.5mm 针，修正后变 100g/"4–5mm 特粗珊瑚绒线"。
    """
    from app.models.crochet_params import refresh_derived
    from app.models.gauge import PRESETS
    from app.models.structure_designer import StructureDesigner

    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                             main_features=[], pose="站立", difficulty="easy",
                             parts=["头部", "身体"])
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure, gauge=PRESETS["fine"])
    hook_labels = [m["item"] for m in params["materials"] if "钩针" in m["item"]]
    assert any("2.0–2.5mm" in h for h in hook_labels)  # fine 密度的正确标签

    edited = {**{k: v for k, v in params.items() if k != "parts"},
              "parts": [p.model_dump() for p in params["parts"]]}
    out = refresh_derived(edited)
    assert out["materials"] == params["materials"], \
        "JSON 修正后材料清单不得随默认密度漂移"


def test_refresh_derived_clamps_bad_gauge_values():
    """JSON 里把 gauge 数值改坏时钳到合法区间/回退默认，不崩溃。"""
    from app.models.crochet_params import refresh_derived

    params = _params_for(["头部"])
    edited = {**{k: v for k, v in params.items() if k != "parts"},
              "parts": [p.model_dump() for p in params["parts"]],
              "gauge": {"stitches_per_10cm": 999.0, "rows_per_10cm": 1.0}}
    out = refresh_derived(edited)
    assert out["materials"]  # 钳制后正常算出材料

    edited["gauge"] = "garbage"  # 完全非法 → 回退默认
    out = refresh_derived(edited)
    assert out["materials"]


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


# ── M2.6/M2.7 理想球与蛋形头 ───────────────────────────────────────────────

def test_ideal_sphere_shape_and_constraints():
    from app.models.crochet_params import _ideal_sphere_rounds
    from app.models.gauge import DEFAULT as default_gauge
    r = _ideal_sphere_rounds(9.0)
    sts = [x["stitches"] for x in r]
    assert max(sts) == 36                       # 与阶梯球同锚点
    assert sts[0] == 6 and sts[-1] <= 12       # 默认密度末极停在 ≤12，直接勒紧收口
    assert all(n % 6 == 0 for n in sts)
    assert all(abs(b - a) <= default_gauge.max_shaping_change
               for a, b in zip(sts, sts[1:]))  # noqa: B905 - adjacent pairs truncate by design
    # 近似对称（球）：上半镜像与下半差 ≤ 每侧 1 档
    half = len(sts) // 2
    assert abs(sum(sts[:half]) - sum(sts[-half:])) <= 36
    assert any("勒紧收口" in (x["notes"] or "") for x in r)


def test_generalized_change_notes_are_executable_by_six_sectors():
    from app.models.crochet_params import _change_note

    assert _change_note(18, 30) == "(X,V,V)×6，均匀加12针"
    assert _change_note(24, 12) == "(A,A)×6，均匀减12针"


def test_egg_head_narrower_bottom_and_eye():
    from app.models.crochet_params import _ideal_sphere_rounds
    egg = [x["stitches"] for x in _ideal_sphere_rounds(9.0, egg=True)]
    ball = [x["stitches"] for x in _ideal_sphere_rounds(9.0)]
    # 蛋形下半更早收窄：下半针数和 < 球的下半
    half = len(egg) // 2
    assert sum(egg[half:]) < sum(ball[len(ball) - half:]) or egg[-1] < ball[-1]
    r = _ideal_sphere_rounds(9.0, egg=True)
    assert 2 <= r[0]["eye_round"] <= len(r)     # 几何化眼睛定位


def test_head_mode_ideal_via_style():
    from app.models.gauge import ShapingStyle
    params = CrochetParamsGenerator.generate_params(
        *_sd(["头部"]), style=ShapingStyle(sphere_mode="ideal"))
    head = params["parts"][0]
    assert "理想球形" in head.notes
    params2 = CrochetParamsGenerator.generate_params(
        *_sd(["头部"]), style=ShapingStyle(sphere_mode="egg"))
    assert "蛋形" in params2["parts"][0].notes


def _sd(parts, **kw):
    from app.models.structure_designer import StructureDesigner
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=parts, **kw)
    return a, StructureDesigner.design_3d_structure(a)


# ── M2.10 头身一体钩 ───────────────────────────────────────────────────────

def test_one_piece_merge():
    from app.models.gauge import ShapingStyle
    params = CrochetParamsGenerator.generate_params(
        *_sd(["头部", "身体", "手臂"]), style=ShapingStyle(one_piece=True))
    names = [p.name for p in params["parts"]]
    assert "头身（一体）" in names and "头部" not in names and "身体" not in names
    op = [p for p in params["parts"] if p.name == "头身（一体）"][0]
    sts = [r.stitches for r in op.rounds]
    assert sts[0] == 6                                  # 头顶起针
    assert sts[-1] == 6                                 # 底部收口
    assert max(sts) >= 30                               # 含头部最宽圈
    notes = "".join(r.notes or "" for r in op.rounds)
    assert "颈部" in notes and "勒紧收口" in notes
    assert any("错开半组" in (r.notes or "") for r in op.rounds)
    # 装配：一体件有分阶段填充，且无头身缝合步骤
    asm = params["assembly_instructions"]
    assert "分阶段填充" in asm and "接合到身体顶部" not in asm
    # 手臂等其余部件保留
    assert "手臂" in names


# ── M2.11 裙子做法与波浪摆 ────────────────────────────────────────────────

def test_skirt_attached_style_and_ruffle():
    from app.models.gauge import ShapingStyle
    params = CrochetParamsGenerator.generate_params(
        *_sd(["身体", "裙子"]),
        style=ShapingStyle(skirt_style="attached", ruffle_hem=True))
    skirt = [p for p in params["parts"] if p.name == "裙子"][0]
    assert "后半针" in skirt.rounds[0].notes
    last = skirt.rounds[-1]
    assert last.stitches == skirt.rounds[-2].stitches * 2    # 波浪摆翻倍
    assert "波浪裙摆" in (last.notes or "") and "免缝合" in skirt.notes


# ── M3.13 语义色与色带融合 ────────────────────────────────────────────────

def test_semantic_color_snaps_nearest_band_segment():
    """红裙白边：白色带保留，蓝色带吸附为语义红色。"""
    bands = [{"start": 0.0, "end": 0.7, "color": "蓝色"},
             {"start": 0.7, "end": 1.0, "color": "白色"}]
    a, struct = _sd(["裙子"], bottom_color="红色")
    params = CrochetParamsGenerator.generate_params(
        a, struct, color_bands=bands)
    skirt = params["parts"][0]
    colors = [r.color for r in skirt.rounds]
    assert "红色" in colors and "白色" in colors     # 分段保留
    assert "蓝色" not in colors                       # 主色段被吸附
    assert any("换线" in (r.notes or "") for r in skirt.rounds)
    assert "校正" in (skirt.notes or "")


def test_semantic_snap_targets_dominant_segment_not_nearest():
    """吸附目标是占比最大的主色段，不是色距最近的段（O1b）。

    语义字段描述的是服装主色（"红裙子"）——主色 = 覆盖圈数最多的段；
    色距最近的段可能是小面积边饰（且 CIEDE2000 下红↔白 45.8 < 红↔蓝
    50.8，纯色距会把白边吸成红，与"边饰保留"的设计意图相反）。
    """
    bands = [{"start": 0.0, "end": 0.7, "color": "蓝色"},
             {"start": 0.7, "end": 1.0, "color": "白色"}]
    a, struct = _sd(["裙子"], bottom_color="红色")
    params = CrochetParamsGenerator.generate_params(a, struct, color_bands=bands)
    colors = [r.color for r in params["parts"][0].rounds]
    # 主色段（蓝，占 70%）整体吸附为红；白边段保留
    assert colors.count("红色") == 3 and colors.count("白色") == 2
    assert "蓝色" not in colors
