from typing import Any, Dict, List, Optional

from ..schemas import CrochetPart, CrochetStitch, ImageAnalysis
from .color_design import (
    PART_SPAN,
    blocks_summary_text,
    color_blocks_for_part,
    round_color,
)
from .gauge import DEFAULT as DEFAULT_GAUGE
from .gauge import Gauge
from .profile_shaping import profile_to_rounds, rounds_to_notes

# 圈针说明依据的通行规范（非自行设计）：
# - 加针表 R1环起6X → 6V → (X,V)×6 → (2X,V)×6 → …（每圈+6）
# - 减针表 (4X,A)×6 → (3X,A)×6 → … → A×6（每圈-6，36/30/24/18/12/6）
# - 符号：X=短针 V=加针(1针目钩2短针) A=减针(2针并1针)
#   CH=锁针 SL=引拔 W=1针放3针 M=3并1（本图解仅用 X/V/A）
# 参考：mstinacrochet.com 六个基础针法；zhuanlan.zhihu.com/p/2397749055
# 符号对照；pipsrainbow.com 圈钩加减针规律。

# ── 密度单一来源：gauge（小样）——详见 app/models/gauge.py ─────────────────
# 下列常量为默认 gauge（经典图解规格）的兼容视图，新代码请直接用 Gauge。
HEAD_REF_DIAMETER_CM = 9.0
STITCHES_PER_CM = DEFAULT_GAUGE.stitches_per_cm_diameter  # ≈ 4.1 针/cm(直径)
BODY_ROUNDS_PER_CM = 1.0 / DEFAULT_GAUGE.row_h_cm         # ≈ 1.6 圈/cm
MINUTES_PER_ROUND = 2.5      # 单圈平均耗时（分钟），用于总时长估算
# 注意：四肢不再用独立的 1.2 圈/cm——行高是纱线属性，不随部件变（fable5 #15）

# ── 部件相对头径的比例假设（Q 版 Amigurumi）────────────────────────────────
BODY_HEAD_RATIO = 1.0        # 身体直径 ≈ 头径（球/圆柱等粗）
LIMB_HEAD_RATIO = 0.33       # 四肢直径 ≈ 头径 1/3（参考尺寸下恰为 12 针）
HAT_HEAD_RATIO = 1.15        # 帽围松量：太小戴不进去，太大松垮
HAT_DEPTH_RATIO = 0.6        # 帽深 ≈ 帽直径 × 0.6
SKIRT_BODY_RATIO = 1.25      # 裙摆直径相对身体放大

# 自端部起针的部件（R1 对应照片低处）：照片配色映射自底向上
_BOTTOM_UP_PARTS = frozenset({"身体", "手臂", "腿部"})


def _semantic_color(part_name: str, analysis) -> Optional[str]:
    """LLM 语义色 → 部件基准色（发色/上衣/下装）。

    有语义色时整段单色（色带近似让位：模型说"红裙"比像素分层更可信）；
    未提供（本地/手动路径）返回 None，走色带或单色降级。
    """
    hair = getattr(analysis, "hair_color", None)
    top = getattr(analysis, "top_color", None)
    bottom = getattr(analysis, "bottom_color", None)
    if part_name == "头部":
        return hair
    if part_name in ("身体", "手臂"):
        return top
    if part_name in ("裙子", "腿部"):
        return bottom or top
    return None

# 材料分组：哪些部件用肤色线 / 主体色线
_SKIN_PARTS = frozenset({"头部", "手臂", "腿部", "耳朵"})
_BODY_PARTS = frozenset({"身体", "帽子", "裙子", "尾巴"})


def _stitches_for_diameter(diameter_cm: float, gauge: Gauge = DEFAULT_GAUGE) -> int:
    """直径(cm) → 6 的倍数针数（半步向上取整，避免银行家舍入偏偶）。"""
    return gauge.stitches_for_diameter(diameter_cm)


def _inc_note_by_before(before: int) -> str:
    """加针圈说明（before → before+6 针），通行"隔N针"口径。

    标准对应：(aX,V)×6，隔 a 针加 1 针，其中 a = before//6 − 1
    （V 耗 1 针出 2 针：a·6 + 6 = 上一圈针数，a·6 + 12 = 本圈针数）。
    """
    plain = before // 6 - 1
    if plain <= 0:
        return "加针×6（V×6，每针都加）"
    coef = "" if plain == 1 else str(plain)  # 发布图解习惯省略系数 1：(X,V)×6
    return f"({coef}X,V)×6，隔{plain}针加1针"


def _inc_note(r: int) -> str:
    """第 r 圈加针说明（6(r-1) → 6r 针）——按上一圈针数委托给通用形式。"""
    return _inc_note_by_before(6 * (r - 1))


def _dec_note(stitches_before: int) -> str:
    """减针圈说明（stitches_before → -6 针），同"隔N针"口径。

    标准对应：减针圈 (aX,A)×6，隔 a 针减 1 针，其中 a = before//6 - 2
    （A 耗 2 针出 1 针：(a+2)·6 = 上一圈针数，(a+1)·6 = 本圈针数）。
    镜面对称圈加/减针的"隔"数相同：30→36 与 36→30 都是隔 4 针。
    """
    plain = stitches_before // 6 - 2
    if plain <= 0:
        return "减针×6（A×6，每2针并1针）"
    coef = "" if plain == 1 else str(plain)
    return f"({coef}X,A)×6，隔{plain}针减1针"


def _increase_rounds(max_stitches: int) -> List[Dict[str, Any]]:
    """Increase rounds shared by sphere/cylinder/cup: magic ring 6 → max_stitches.

    max_stitches must be a positive multiple of 6.
    """
    step = 6
    n_up = max_stitches // step
    return _mark_staggered([
        {
            "row": r,
            "stitches": step * r,
            "increase": step if r > 1 else 0,
            "notes": "魔法环起6针（X×6）" if r == 1 else _inc_note(r),
        }
        for r in range(1, n_up + 1)
    ])


def _mark_staggered(rounds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """连续加针圈提示错开半组（避免六边形棱线；PlanetJune 实证技法）。"""
    for i in range(1, len(rounds)):
        if rounds[i].get("increase") and rounds[i - 1].get("increase"):
            rounds[i]["notes"] = (
                (rounds[i].get("notes") or "")
                + "；加针位置与上一圈错开半组"
            )
    return rounds


def _sphere_rounds(max_stitches: int = 36) -> List[Dict[str, Any]]:
    """Increase -> constant -> decrease rounds for an Amigurumi sphere.
    max_stitches must be a positive multiple of 6.
    """
    step = 6
    n_up = max_stitches // step

    constant = [
        {"row": n_up + i, "stitches": max_stitches, "notes": f"{max_stitches}X（不加不减）"}
        for i in range(1, n_up + 1)
    ]
    decrease = []
    for i in range(1, n_up):
        remaining = max_stitches - step * i
        if remaining <= 0:
            break
        decrease.append({
            "row": n_up * 2 + i,
            "stitches": remaining,
            "decrease": step,
            "notes": _dec_note(remaining + step),  # before = 本圈减针前的针数
        })

    rounds = _increase_rounds(max_stitches) + constant + decrease
    if rounds:
        last = rounds[-1]
        last["notes"] = (last.get("notes") or "") + "；断线留10cm，勒紧收口藏线头"
    return rounds


def _cylinder_rounds(max_stitches: int = 24, body_rounds: int = 15) -> List[Dict[str, Any]]:
    """Generate cylinder: increase to max_stitches, hold, then 2 taper rounds."""
    step = 6
    n_up = max_stitches // step

    constant = [
        {"row": n_up + i, "stitches": max_stitches, "notes": f"{max_stitches}X（不加不减）"}
        for i in range(1, body_rounds + 1)
    ]
    decrease = []
    for i in range(1, 3):
        remaining = max_stitches - step * i
        if remaining > 0:
            decrease.append({
                "row": n_up + body_rounds + i,
                "stitches": remaining,
                "decrease": step,
                "notes": _dec_note(remaining + step),  # before = 本圈减针前的针数
            })

    rounds = _increase_rounds(max_stitches) + constant + decrease
    if rounds:
        last = rounds[-1]
        last["notes"] = (last.get("notes") or "") + "；断线留15cm用于缝合"
    return rounds


def _cup_rounds(max_stitches: int, depth_rounds: int) -> List[Dict[str, Any]]:
    """Open cup (hat/skirt): increase to max, straight to depth — NO closing.

    帽子/裙子必须开口：走 sphere 收口到 6 针的成品根本无法佩戴。
    """
    n_up = max_stitches // 6
    constant = [
        {"row": n_up + i, "stitches": max_stitches, "notes": f"{max_stitches}X（不加不减）"}
        for i in range(1, max(1, depth_rounds) + 1)
    ]
    return _increase_rounds(max_stitches) + constant


def _part_name(part: Any) -> str:
    return part["name"] if isinstance(part, dict) else part.name


def _part_rounds(part: Any) -> List[Any]:
    return part.get("rounds", []) if isinstance(part, dict) else part.rounds


def _round_stitches(rd: Any) -> int:
    return rd.get("stitches", 0) if isinstance(rd, dict) else rd.stitches


def _materials(parts: List[Any], part_names: set,
                gauge: Gauge = DEFAULT_GAUGE) -> List[Dict[str, str]]:
    """材料清单随实际部件生成；parts 元素可为 CrochetPart 或 dict（JSON 修正路径）。"""
    materials: List[Dict[str, str]] = []
    for group, label in ((_SKIN_PARTS, "肤色系毛线"), (_BODY_PARTS, "主体色毛线")):
        group_parts = [p for p in parts if _part_name(p) in group]
        if not group_parts:
            continue
        grams = max(20, round(sum(_round_stitches(rd) for p in group_parts
                                  for rd in _part_rounds(p)) * gauge.grams_per_stitch))
        materials.append({"item": label, "quantity": f"约 {grams}g"})
    if "头部" in part_names:
        materials.append({"item": "安全眼", "quantity": "一对 (8mm)"})
    materials.append({"item": "填充棉", "quantity": "适量"})
    materials.append({"item": gauge.hook_yarn_label, "quantity": "1 把"})
    materials.append({"item": "缝合针", "quantity": "1 根"})
    return materials


def refresh_derived(params: dict) -> dict:
    """局部修正（JSON 编辑）后按编辑过的 parts 重算派生量。

    estimated_time_minutes / total_stitches / 材料克数都是 parts 的函数，
    用户改完圈数若不重算，图解头部信息与正文会失同步。
    """
    parts = params.get("parts", [])
    total_rounds = sum(len(_part_rounds(p)) for p in parts)
    total_stitches = sum(_round_stitches(rd) for p in parts for rd in _part_rounds(p))
    params["estimated_time_minutes"] = max(30, round(total_rounds * MINUTES_PER_ROUND))
    params["total_stitches"] = total_stitches
    params["materials"] = _materials(parts, {_part_name(p) for p in parts})
    # 装配说明同样是 parts 的函数：删部件后不得残留对应步骤（F5）
    params["assembly_instructions"] = build_assembly({_part_name(p) for p in parts})
    return params


def build_assembly(part_names) -> str:
    """装配说明：只提及实际存在的部件（generate 与 refresh_derived 共用）。"""
    steps: List[str] = ["各部件分别完成并填充棉花"]
    if "头部" in part_names:
        steps.append("头部安装安全眼（第2/3高度处）")
        steps.append("用黑色毛线绣鼻子和嘴巴")
        if "身体" in part_names:
            steps.append("用隐形缝合法将头部接合到身体顶部")
    if "手臂" in part_names:
        steps.append("手臂对称缝合到身体两侧上方")
    if "腿部" in part_names:
        steps.append("腿部对称缝合到身体底部")
    if "耳朵" in part_names:
        steps.append("耳朵对称缝合在头部两侧")
    if "帽子" in part_names:
        steps.append("帽口不收口，直接戴在头部（试戴后可缝合固定）")
    if "裙子" in part_names:
        steps.append("裙筒腰部套入身体后缝合固定（腰部为开口起针）")
    if "尾巴" in part_names:
        steps.append("尾巴缝合在身体后方")
    return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))


class CrochetParamsGenerator:
    """Generate crochet parameters for each part."""

    @staticmethod
    def generate_params(
        analysis: ImageAnalysis,
        structure: Dict,
        color_bands: Optional[List[Dict]] = None,
        body_profile: Optional[List[float]] = None,
        gauge: Gauge = DEFAULT_GAUGE,
    ) -> Dict[str, Any]:
        """Generate crochet parameters using structure data for dimensions.

        圈数（rows）一律由 len(rounds) 派生；圆柱/帽的标注高度按圈数反推，
        保证"标注高度 = 实际钩出高度"；材料/装配/时长随实际部件动态生成。

        color_bands：照片纵向色带 → 逐圈配色（无图则单色降级）。
        body_profile：照片宽度剖面 → 身体筒壁逐圈针数（AmiGo 旋转体范式的
        单图简化；None 时降级为模板圆柱）。
        gauge：小样密度（针宽/行高单一来源，参数与网格层共用）。
        """
        struct_parts: Dict[str, Dict] = {
            p["name"]: p for p in structure.get("parts", [])
        }
        head_d = analysis.head_diameter_cm

        crochet_parts: List[CrochetPart] = []

        # 以结构层部件清单为准（structure 可能按 clothing_type 补了裙子，
        # 只遍历 analysis.parts 会漏掉）；结构为空时回退 analysis.parts。
        part_order = [p["name"] for p in structure.get("parts", [])] or analysis.parts
        for part_name in part_order:
            sp = struct_parts.get(part_name, {})
            is_head = part_name == "头部"
            shape = sp.get("shape", "sphere" if is_head else "cylinder")

            if is_head or shape == "sphere":
                # Head, ears and other roundish closed parts — sized by diameter
                fallback_d = (
                    head_d if is_head else round(head_d * 0.4, 1)
                )
                diameter = sp.get("diameter_cm", fallback_d)
                max_st = _stitches_for_diameter(diameter, gauge)
                rounds_raw = _sphere_rounds(max_stitches=max_st)
                if is_head:
                    color = sp.get("color", "skin")
                    eye_round = max(2, len(rounds_raw) * 2 // 3)
                    eye_gap = max(4, max_st // 6)
                    notes = (
                        f"标准球形，最大 {max_st} 针。"
                        f"第 {eye_round} 圈安装安全眼（8mm，两眼间隔约 {eye_gap} 针）。"
                        "建议先钩小样测试张力。"
                    )
                else:
                    color = sp.get("color", "body")
                    notes = f"小球形部件（直径 {diameter}cm），完成后缝合到主体。"
                part = CrochetPart(
                    name=part_name,
                    type="sphere",
                    diameter_cm=diameter,
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=color,
                    magic_ring=True,
                    notes=notes,
                )

            elif part_name == "裙子":
                # F1 修复：裙子必须腰部开口（闭口圆盘套不进身体）。
                # 构造方向：腰部环形开口起针 → 逐圈+6 展开到裙摆 → 直钩。
                length = sp.get("height_cm") or sp.get("length_cm") or 5.0
                waist_st = _stitches_for_diameter(head_d * BODY_HEAD_RATIO, gauge)
                hem_st = _stitches_for_diameter(head_d * BODY_HEAD_RATIO * SKIRT_BODY_RATIO, gauge)
                flare = max(0, (hem_st - waist_st) // 6)  # 每圈+6 的展开圈数
                total_target = max(flare + 2, gauge.rounds_for_height(length))
                straight = total_target - flare
                rounds_raw = [{
                    "row": 1,
                    "stitches": waist_st,
                    "notes": f"腰部环形起针{waist_st}X成环（引拔连接，开口勿收口）",
                }]
                for i in range(1, flare + 1):
                    rounds_raw.append({
                        "row": i + 1,
                        "stitches": waist_st + 6 * i,
                        "increase": 6,
                        "notes": _inc_note_by_before(waist_st + 6 * (i - 1)),
                    })
                for j in range(1, straight + 1):
                    rounds_raw.append({
                        "row": flare + 1 + j,
                        "stitches": hem_st,
                        "notes": f"{hem_st}X（不加不减）",
                    })
                actual_h = round(len(rounds_raw) * gauge.row_h_cm, 1)
                part = CrochetPart(
                    name=part_name,
                    type="cup",
                    height_cm=actual_h,
                    diameter_cm=round(hem_st / STITCHES_PER_CM, 1),
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "body"),
                    magic_ring=False,  # 腰部开口起针，非魔法环
                    notes=(
                        f"开口裙筒（腰 {waist_st} 针开口起针 → 裙摆 {hem_st} 针），"
                        f"实际高约 {actual_h}cm，腰部套入身体后缝合固定。"
                    ),
                )

            elif part_name == "帽子" or shape == "cup":
                # 开口帽形：加针到帽围后直钩至帽深，不收口
                diameter = sp.get("diameter_cm", round(head_d * HAT_HEAD_RATIO, 1))
                max_st = _stitches_for_diameter(diameter, gauge)
                n_up = max_st // 6
                # HAT_DEPTH_RATIO 针对的是帽子的总高度（含帽顶加针段）：
                # 目标总圈数 = 直径×0.6×密度，直钩段 = 目标 − 加针段。
                total_rounds = max(
                    n_up + 1,
                    gauge.rounds_for_height(diameter * HAT_DEPTH_RATIO),
                )
                depth_rounds = max(1, total_rounds - n_up)
                rounds_raw = _cup_rounds(max_stitches=max_st, depth_rounds=depth_rounds)
                actual_h = round(len(rounds_raw) * gauge.row_h_cm, 1)
                part = CrochetPart(
                    name=part_name,
                    type="cup",
                    diameter_cm=diameter,
                    height_cm=actual_h,
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "body"),
                    magic_ring=True,
                    notes=(
                        f"开口帽形（帽围 {max_st} 针 > 头围，不收口可直接佩戴），"
                        f"帽高约 {actual_h}cm（含帽顶）。"
                    ),
                )

            elif part_name == "身体" and body_profile:
                # 照片驱动身体（M1.2）：剖面 + 圆形截面 = 旋转体，逐圈针数
                # 随照片宽度变化（梨形/收腰不再是等粗圆柱）。
                height = sp.get("height_cm", 9.0)
                ref_st = _stitches_for_diameter(head_d * BODY_HEAD_RATIO, gauge)
                wall = profile_to_rounds(
                    body_profile, PART_SPAN["身体"], height, gauge, ref_st,
                    direction="bottom_up",
                )
                dome = _increase_rounds(wall[0])   # 底部圆盘：魔法环→首圈针数
                wall_notes = rounds_to_notes(wall)
                wall_dicts = [
                    {"row": i + 1, "stitches": n, "notes": wall_notes[i],
                     **({"increase": 6} if i and n > wall[i - 1] else {}),
                     **({"decrease": 6} if i and n < wall[i - 1] else {})}
                    for i, n in enumerate(wall)
                ]
                wall_dicts = _mark_staggered(wall_dicts)
                for i, rd in enumerate(wall_dicts):
                    rd["row"] = len(dome) + i + 1
                rounds_raw = dome + wall_dicts
                actual_h = round(len(wall) * gauge.row_h_cm, 1)
                part = CrochetPart(
                    name=part_name,
                    type="profile",
                    height_cm=actual_h,
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "body"),
                    notes=(
                        f"照片驱动轮廓身体（筒壁高约 {actual_h}cm，逐圈针数随照片"
                        f"剖面变化；底部另含圆盘）。收针前填充棉花。"
                    ),
                )

            elif part_name == "身体":
                height = sp.get("height_cm", 9.0)
                # 身体针数随头径缩放（旧硬编码 24 针在头 20cm 时严重比例失调）
                max_st = _stitches_for_diameter(head_d * BODY_HEAD_RATIO, gauge)
                body_r = max(4, gauge.rounds_for_height(height))
                rounds_raw = _cylinder_rounds(max_stitches=max_st, body_rounds=body_r)
                # 标注高度只计"竖直筒壁"圈（直钩+收针）：起底加针段是水平
                # 圆盘，贡献直径不贡献高度（计入会把 4.5cm 的身体标成 9.4cm）。
                n_dome = max_st // 6
                actual_h = round((len(rounds_raw) - n_dome) * gauge.row_h_cm, 1)
                part = CrochetPart(
                    name=part_name,
                    type="cylinder",
                    height_cm=actual_h,
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "body"),
                    notes=(
                        f"圆柱身体（筒壁高约 {actual_h}cm，另含底部圆盘直径 "
                        f"{round(max_st * gauge.stitch_w_cm / 3.14159, 1)}cm）。"
                        "收针前填充棉花。"
                    ),
                )

            else:
                # Limbs, tails and any other slim cylinder: sized from head
                # diameter (旧硬编码 12 针不随尺寸缩放)。
                length = sp.get("length_cm") or sp.get("height_cm") or 5.0
                max_st = _stitches_for_diameter(head_d * LIMB_HEAD_RATIO, gauge)
                limb_r = max(2, gauge.rounds_for_height(length))
                rounds_raw = _cylinder_rounds(max_stitches=max_st, body_rounds=limb_r)
                n_dome = max_st // 6  # 起底圆盘圈不计高度（同身体口径）
                actual_h = round((len(rounds_raw) - n_dome) * gauge.row_h_cm, 1)
                part = CrochetPart(
                    name=part_name,
                    type="cylinder",
                    height_cm=actual_h,
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "skin" if part_name in _SKIN_PARTS else "body"),
                    notes=f"{part_name}（筒壁长约 {actual_h}cm，另含底部小圆盘），两端留线头便于缝合。",
                )

            sem = _semantic_color(part_name, analysis)
            if sem:
                # 语义色优先：整段单色 + 说明（模型语义比像素分层可信）
                for rd in part.rounds:
                    rd.color = sem
                part.color = sem
                part.notes = (part.notes or "") + f" 配色（照片语义）：{sem}。"
            elif color_bands:
                CrochetParamsGenerator._apply_color_plan(part, color_bands)
            crochet_parts.append(part)

        return CrochetParamsGenerator._build_result(analysis, crochet_parts, gauge)

    @staticmethod
    def _apply_color_plan(part: CrochetPart, bands: List[Dict]) -> None:
        """把照片色带按部件纵向占比铺到每一圈（原地），并生成换线说明。"""
        blocks = color_blocks_for_part(bands, part.name)
        if not blocks:
            return  # 该部件无占比先验（未知部件）→ 保持单色
        span_s, span_e = PART_SPAN.get(part.name, (0.0, 1.0))
        span_len = span_e - span_s
        colors: List[Optional[str]] = []
        prev: Optional[str] = None
        n = len(part.rounds)
        # 钩织方向：身体/四肢自端部起针（R1=脚底/手端/胯部=照片低处），
        # 末圈才缝合到躯干——这些部件的照片色带映射必须自底向上。
        bottom_up = part.name in _BOTTOM_UP_PARTS
        for j, rd in enumerate(part.rounds):
            frac = (span_e - span_len * (j + 0.5) / n) if bottom_up else (
                span_s + span_len * (j + 0.5) / n
            )
            c = round_color(frac, blocks)
            colors.append(c)
            rd.color = c
            if prev is not None and c != prev:
                # jogless 换色：前一针最后一次挂线即改用新色，消除螺旋台阶
                rd.notes = (rd.notes or "") + (
                    f"；换线：{c}（前一针最后一次挂线改用新色，避免螺旋台阶）"
                )
            prev = c
        if len(set(colors)) > 1:
            part.notes = (part.notes or "") + f" 配色（自上而下）：{blocks_summary_text(colors)}。"
        # 主色回写：部件基准色取该部件占比最大的色段
        part.color = max(set(colors), key=colors.count)

    @staticmethod
    def _build_result(analysis: ImageAnalysis, parts: List[CrochetPart],
                      gauge: Gauge = DEFAULT_GAUGE) -> Dict[str, Any]:
        """Assemble the result dict: materials / assembly / time scale with parts."""
        part_names = {p.name for p in parts}
        total_rounds = sum(p.rows for p in parts)
        total_stitches = sum(r.stitches for p in parts for r in p.rounds)

        assembly = build_assembly(part_names)

        return {
            "materials": _materials(parts, part_names, gauge),
            "parts": parts,
            "assembly_instructions": assembly,
            "difficulty": analysis.difficulty,
            "estimated_time_minutes": max(30, round(total_rounds * MINUTES_PER_ROUND)),
            "total_stitches": total_stitches,
            "notes": (
                "螺旋钩法：全程不引拔、不翻转，每圈第一针挂记号扣；"
                "减针建议用隐形减针（只挑两针目的前半针）更平整。"
                "基于单图推理生成，比例可能需要试钩调整。"
            ),
        }
