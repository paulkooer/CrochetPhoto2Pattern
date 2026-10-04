from typing import Any

from ..schemas import CrochetPart, CrochetStitch, ImageAnalysis
from .assembly import _openings_by_part, build_assembly
from .color_design import (
    PART_SPAN,
    blocks_summary_text,
    color_blocks_for_part,
    round_color,
)
from .gauge import DEFAULT as DEFAULT_GAUGE
from .gauge import (
    DEFAULT_STYLE,
    Gauge,
    ShapingStyle,
    gauge_from_mapping,
    next_shaping_stitch_count,
)
from .materials import YarnSpec, _materials, _safety_eye_mm, yarn_requirements
from .parts import _SKIN_PARTS, _part_name, _part_quantity, _part_rounds, _round_stitches
from .profile_shaping import profile_to_rounds, rounds_to_notes
from .time_estimate import (  # noqa: F401
    SECONDS_PER_ROUND_OVERHEAD,
    SECONDS_PER_STITCH,  # noqa: F401 —— trials 兼容再导出
    estimate_minutes,
    time_estimate_basis,
)
from .validator import validate_pattern

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
# 注意：四肢不再用独立的 1.2 圈/cm——行高是纱线属性，不随部件变（fable5 #15）

# ── 部件相对头径的比例假设（Q 版 Amigurumi）────────────────────────────────
BODY_HEAD_RATIO = 1.0        # 身体直径 ≈ 头径（球/圆柱等粗）
LIMB_HEAD_RATIO = 0.33       # 四肢直径 ≈ 头径 1/3（参考尺寸下恰为 12 针）
HAT_HEAD_RATIO = 1.15        # 帽围松量：太小戴不进去，太大松垮
HAT_DEPTH_RATIO = 0.6        # 帽深 ≈ 帽直径 × 0.6
SKIRT_BODY_RATIO = 1.25      # 裙摆直径相对身体放大

# 自端部起针的部件（R1 对应照片低处）：照片配色映射自底向上
_BOTTOM_UP_PARTS = frozenset({"身体", "手臂", "腿部"})



def _semantic_color(part_name: str, analysis) -> str | None:
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


def _change_note(before: int, after: int) -> str:
    """Executable six-sector notation for a gauge-dependent transition."""
    delta = after - before
    if delta == 0:
        return f"{after}X（不加不减）"
    if delta == 6:
        return _inc_note_by_before(before)
    if delta == -6:
        return _dec_note(before)
    amount = abs(delta)
    if before % 6 or after % 6 or amount % 6:
        return f"由 {before} 针均匀调整至 {after} 针"

    changes_per_sector = amount // 6
    source_per_sector = before // 6
    if delta > 0:
        plain = source_per_sector - changes_per_sector
        if plain < 0:
            return f"由 {before} 针均匀加至 {after} 针"
        operations = ([f"{plain if plain > 1 else ''}X"] if plain else [])
        operations.extend(["V"] * changes_per_sector)
        return f"({','.join(operations)})×6，均匀加{amount}针"

    plain = source_per_sector - 2 * changes_per_sector
    if plain < 0:
        return f"由 {before} 针均匀减至 {after} 针"
    operations = ([f"{plain if plain > 1 else ''}X"] if plain else [])
    operations.extend(["A"] * changes_per_sector)
    return f"({','.join(operations)})×6，均匀减{amount}针"


def _increase_rounds(max_stitches: int) -> list[dict[str, Any]]:
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


def bridge_rounds(cur: int, target: int, max_change: int = 6) -> list[int]:
    """从 cur 到 target 的中间圈针数（不含 cur、含 target）。

    F13 防线：跨圈跳变（如头部收针链直接接目标颈围）必须经此桥接，
    保证所有圈保持 6 的倍数、相邻差不超过 gauge 动态上限且每圈 V/A
    在源针数上可执行。默认 6 保持旧调用兼容。
    """
    assert cur >= 6 and target >= 6 and cur % 6 == 0 and target % 6 == 0, \
        "针数必须是正的 6 的倍数"
    if target == cur:
        return []
    out = []
    current = cur
    while current != target:
        current = next_shaping_stitch_count(current, target, max_change)
        out.append(current)
    return out


class PatternGenerationError(RuntimeError):
    """生成器自检失败——阻止代数矛盾的图解成为可下载产物（F13）。"""


def _mark_staggered(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """连续加针圈提示错开半组（避免六边形棱线；PlanetJune 实证技法）。"""
    for i in range(1, len(rounds)):
        if rounds[i].get("increase") and rounds[i - 1].get("increase"):
            rounds[i]["notes"] = (
                (rounds[i].get("notes") or "")
                + "；加针位置与上一圈错开半组"
            )
    return rounds


def _sphere_rounds(max_stitches: int = 36) -> list[dict[str, Any]]:
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
        last["notes"] = (last.get("notes") or "") + (
            "；断线留10cm，穿末圈每针前半针后拉紧藏线头"
            "（无痕收口，社区/PlanetJune fastening off 通行技法）")
    return rounds


def _ideal_sphere_rounds(
    diameter_cm: float,
    gauge: Gauge = DEFAULT_GAUGE,
    egg: bool = False,
    egg_e: float = 0.12,
) -> list[dict[str, Any]]:
    """理想球/蛋形（M2.6/M2.7）：逐圈针数 ∝ sin(极角)。

    依据：The Ideal Crochet Sphere（mspremiseconclusion, 2010，已核实原文）——
    每行 = 固定极角 Δθ，θ 处圆周长 ∝ sin(θ)，针数 N = C/s
    （C = π·D·sinθ = 截面圆周长，s = 针宽；原文 "Pi*r^2" 为笔误）。
    经典阶梯球沿经线布料量偏少（+6 阶梯只在极点附近密集），理想球分布
    均匀、填充后更圆。
    egg=True：宽度乘 (1 + e·cosθ)（θ 自顶极点），上略宽下略窄的蛋形——
    玩偶头主流形状；返回值附 eye_round（最大围行，眼睛在其下一两圈）。
    原文工艺警告：收尾不要按标准减针收到 6 针（底部过尖）——保持约
    12 针左右直接穿线无痕收口（穿末圈前半针拉紧）；动态塑形上限仍受
    单圈可执行性约束。
    """
    import math

    n = max(5, int(diameter_cm / gauge.row_h_cm + 0.5))
    row_h = gauge.row_h_cm
    targets = []
    for j in range(1, n + 1):
        y = (j - 0.5) * row_h
        theta = math.pi * min(y, diameter_cm) / max(diameter_cm, 1e-9)
        w = diameter_cm * math.sin(theta)
        if egg:
            w *= (1.0 + egg_e * math.cos(theta))
        st = math.pi * w / gauge.stitch_w_cm
        targets.append(max(6, int(round(st / 6.0)) * 6))
    # 连续几何变化率按 gauge 计算，并上量化到六等分针法。
    clamped = [targets[0]]
    for t in targets[1:]:
        prev = clamped[-1]
        clamped.append(next_shaping_stitch_count(
            prev, max(6, t), gauge.max_shaping_change))
    rounds: list[dict[str, Any]] = [{
        "row": 1, "stitches": clamped[0],
        "notes": f"魔法环起{clamped[0]}针（X×{clamped[0]}）",
    }]
    for i in range(1, len(clamped)):
        before, cur = clamped[i - 1], clamped[i]
        note = _change_note(before, cur)
        rounds.append({
            "row": i + 1, "stitches": cur,
            "increase": max(0, cur - before),
            "decrease": max(0, before - cur),
            "notes": note,
        })
    rounds = _mark_staggered(rounds)
    if rounds:
        last = rounds[-1]
        # 原文工艺：不要继续减针收到 6 针（底部过尖）——穿前半针收口
        last["notes"] = (last.get("notes") or "") + (
            "；断线留10cm，穿末圈每针前半针后拉紧（无痕收口）藏线头"
            "（勿再减针收成6针，底部会过尖）")
    # 眼睛：最大围所在圈（蛋形时上移），再往下 1 圈
    eye_idx = max(range(len(clamped)), key=lambda i: clamped[i])
    rounds[0]["eye_round"] = min(len(rounds), eye_idx + 2)  # 附带信息，CrochetStitch 会忽略
    return rounds


def _cylinder_rounds(max_stitches: int = 24, body_rounds: int = 15) -> list[dict[str, Any]]:
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


def _cup_rounds(max_stitches: int, depth_rounds: int) -> list[dict[str, Any]]:
    """Open cup (hat/skirt): increase to max, straight to depth — NO closing.

    帽子/裙子必须开口：走 sphere 收口到 6 针的成品根本无法佩戴。
    """
    n_up = max_stitches // 6
    constant = [
        {"row": n_up + i, "stitches": max_stitches, "notes": f"{max_stitches}X（不加不减）"}
        for i in range(1, max(1, depth_rounds) + 1)
    ]
    return _increase_rounds(max_stitches) + constant




def structure_connection_plan(structure: dict[str, Any]) -> dict[str, Any] | None:
    """Project StructureGeometry v2 attachments into a stable assembly IR.

    Legacy structures return ``None`` so callers can preserve the historical
    name-based assembly fallback.  The plan intentionally stores names as well
    as IDs: parameter JSON remains understandable and can be rebuilt without
    requiring the top-level structure object.
    """
    if not isinstance(structure, dict) or structure.get("schema_version") != "2.0":
        return None
    raw_parts = structure.get("parts") or []
    id_to_name = {
        part.get("part_id"): part.get("name")
        for part in raw_parts
        if isinstance(part, dict) and part.get("part_id") and part.get("name")
    }
    connections: list[dict[str, str]] = []
    for part in raw_parts:
        if not isinstance(part, dict):
            continue
        source_id = part.get("part_id")
        source_name = part.get("name")
        if not source_id or not source_name:
            continue
        for instance in part.get("instances") or []:
            if not isinstance(instance, dict):
                continue
            for attachment in instance.get("attachments") or []:
                if not isinstance(attachment, dict):
                    continue
                target_id = attachment.get("target_part_id")
                target_name = id_to_name.get(target_id)
                if not target_name:
                    continue
                connections.append({
                    "source_part_id": str(source_id),
                    "source_part_name": str(source_name),
                    "source_instance_id": str(instance.get("instance_id") or source_id),
                    "self_anchor": str(attachment.get("self_anchor") or "unspecified"),
                    "target_part_id": str(target_id),
                    "target_part_name": str(target_name),
                    "target_anchor": str(attachment.get("target_anchor") or "unspecified"),
                    "method": str(attachment.get("method") or "sewn"),
                })
    return {
        "schema_version": "1.0",
        "source": "structure_v2",
        "connections": connections,
    }


def _gauge_from_params(params: dict) -> Gauge:
    """从 params 恢复生成时的 gauge（JSON 修正/备份导入路径的单一来源）。

    用户可能在 JSON 里把数值改坏：钳到与侧栏相同的区间（6–40 / 8–50 针数
    /行数），缺失或非法时回退默认——与 gauge_from_ui 的兜底口径一致。
    """
    return gauge_from_mapping(params.get("gauge"))


def _shaping_meta(gauge: Gauge) -> dict[str, Any]:
    """Serializable explanation of the gauge-dependent shaping constraint."""
    return {
        "continuous_delta": round(gauge.shaping_continuous_delta, 2),
        "max_stitch_change": gauge.max_shaping_change,
        "quantization": "ceil_to_six_stitch_sectors",
        "note": "连续几何变化率按六等分针法向上量化；实际圈可使用更小的6针步长",
    }


def refresh_derived(params: dict) -> dict:
    """局部修正（JSON 编辑）后按编辑过的 parts 重算派生量。

    estimated_time_minutes / total_stitches / 材料克数都是 parts 的函数，
    用户改完圈数若不重算，图解头部信息与正文会失同步。
    """
    parts = params.get("parts", [])
    total_stitches = sum(
        _round_stitches(rd) * _part_quantity(p)
        for p in parts for rd in _part_rounds(p))
    params["estimated_time_minutes"] = estimate_minutes(parts)
    params["time_estimate_basis"] = time_estimate_basis()
    params["total_stitches"] = total_stitches
    # 材料克数/钩针标签依赖 gauge：必须用生成时的密度（存在 params 里），
    # 否则非默认密度下 JSON 修正后克重漂移、钩针标签换成错误规格
    gauge = _gauge_from_params(params)
    if params.get("gauge"):
        params["gauge"] = {"stitches_per_10cm": gauge.stitches_per_10cm,
                           "rows_per_10cm": gauge.rows_per_10cm}
    if params.get("yarn_spec") is not None:
        params["yarn_spec"] = YarnSpec.model_validate(params["yarn_spec"]).model_dump()
    params["materials"] = _materials(
        parts, {_part_name(p) for p in parts}, gauge=gauge, yarn_spec=params.get("yarn_spec"))
    params["material_summary"] = yarn_requirements(parts, gauge, params.get("yarn_spec"))[1]
    params["shaping"] = _shaping_meta(gauge)
    # 装配说明同样是 parts 的函数：删部件后不得残留对应步骤（F5）；
    # 裙子做法按生成时的口径保留
    quantities = {_part_name(p): _part_quantity(p) for p in parts}
    params["assembly_instructions"] = build_assembly(
        set(quantities), params.get("skirt_style", "ring"), quantities,
        params.get("assembly_plan"), openings=_openings_by_part(parts))
    return params





class CrochetParamsGenerator:
    """Generate crochet parameters for each part."""

    @staticmethod
    def generate_params(
        analysis: ImageAnalysis,
        structure: dict,
        color_bands: list[dict] | None = None,
        body_profile: list[float] | None = None,
        gauge: Gauge = DEFAULT_GAUGE,
        style: ShapingStyle | None = None,
        spans: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate crochet parameters using structure data for dimensions.

        圈数（rows）一律由 len(rounds) 派生；圆柱/帽的标注高度按圈数反推，
        保证"标注高度 = 实际钩出高度"；材料/装配/时长随实际部件动态生成。

        color_bands：照片纵向色带 → 逐圈配色（无图则单色降级）。
        body_profile：照片宽度剖面 → 身体筒壁逐圈针数（AmiGo 旋转体范式的
        单图简化；None 时降级为模板圆柱）。
        gauge：小样密度（针宽/行高单一来源，参数与网格层共用）。
        style：塑形风格（理想球/蛋形头、头身一体、裙子做法、波浪摆）。
        spans（S1）：姿态关键点实测部件占比；None 回退 PART_SPAN 先验。
        """
        style = style or DEFAULT_STYLE
        if "parts" in structure:
            from .geometry import normalize_structure
            structure = normalize_structure(structure)
        struct_parts: dict[str, dict] = {
            p["name"]: p for p in structure.get("parts", [])
        }
        head_d = analysis.head_diameter_cm

        crochet_parts: list[CrochetPart] = []

        # Explicit structure edits are authoritative, including deletion of all
        # parts (the generation gate then reports an empty pattern).
        part_order = ([p["name"] for p in structure["parts"]]
                      if "parts" in structure else analysis.parts)
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
                eye_extra = None
                if is_head and style.sphere_mode in ("ideal", "egg"):
                    # 理想球/蛋形（M2.6/M2.7）：sinθ 分布 + 几何化眼睛定位
                    rounds_raw = _ideal_sphere_rounds(
                        diameter, gauge, egg=(style.sphere_mode == "egg"))
                    eye_extra = rounds_raw[0].pop("eye_round", None)
                    max_st = max(r["stitches"] for r in rounds_raw)
                else:
                    rounds_raw = _sphere_rounds(max_stitches=max_st)
                if is_head:
                    color = sp.get("color", "skin")
                    eye_round = eye_extra or max(2, len(rounds_raw) * 2 // 3)
                    eye_gap = max(4, max_st // 6)
                    # 安全眼直径与材料清单同口径（_safety_eye_mm 按头径分档），
                    # 文案不得写死——否则与清单冲突
                    eye_mm = _safety_eye_mm(diameter)
                    shape_label = {"ideal": "理想球形（sinθ 分布）",
                                   "egg": "蛋形（下半收窄）"}.get(
                                       style.sphere_mode, "标准球形")
                    notes = (
                        f"{shape_label}，最大 {max_st} 针。"
                        # 眼位锚定在最大围附近（专业图解以鼻线/眼窝等地标
                        # 定位——Supergurumi 蜜蜂"鼻线后2行"；本生成器无
                        # 地标，用几何近似）
                        f"第 {eye_round} 圈（最大围附近）安装安全眼（{eye_mm}mm，"
                        f"两眼间隔约 {eye_gap} 针，可依眼径与脸型调整）。"
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
                body_d = struct_parts.get("身体", {}).get("diameter_cm") or head_d * BODY_HEAD_RATIO
                waist_st = _stitches_for_diameter(body_d, gauge)
                hem_st = _stitches_for_diameter(
                    sp.get("diameter_cm") or body_d * SKIRT_BODY_RATIO, gauge)
                shaping = bridge_rounds(waist_st, hem_st)
                flare = len(shaping)
                total_target = max(flare + 2, gauge.rounds_for_height(length))
                straight = total_target - flare
                rounds_raw = [{
                    "row": 1,
                    "stitches": waist_st,
                    "notes": f"腰部环形起针{waist_st}X成环（引拔连接，开口勿收口）",
                }]
                before = waist_st
                for i, stitches in enumerate(shaping, 1):
                    rounds_raw.append({
                        "row": i + 1,
                        "stitches": stitches,
                        "increase": max(0, stitches - before),
                        "decrease": max(0, before - stitches),
                        "notes": _change_note(before, stitches),
                    })
                    before = stitches
                for j in range(1, straight + 1):
                    rounds_raw.append({
                        "row": flare + 1 + j,
                        "stitches": hem_st,
                        "notes": f"{hem_st}X（不加不减）",
                    })
                if style.skirt_style == "attached":
                    # 挑后半针法：身体腰圈只挑前半针，裙子钩在预留后半针上
                    rounds_raw[0]["notes"] = (
                        f"在身体腰部（身体最上 1–2 圈）挑后半针起针{waist_st}X"
                        "（身体该圈钩时只挑前半针，留后半针给裙子）"
                    )
                if style.ruffle_hem:
                    rounds_raw.append({
                        "row": len(rounds_raw) + 1,
                        "stitches": hem_st * 2,
                        "increase": hem_st,
                        # V2：装饰性宽跳变显式白名单（工艺正确，豁免
                        # 平盘 |Δ|≤6 物理极限；validator 认此标志）
                        "allow_wide_jump": True,
                        "notes": f"波浪裙摆：每针放2针（V×{hem_st}）",
                    })
                actual_h = round(len(rounds_raw) * gauge.row_h_cm, 1)
                skirt_notes = (
                    f"开口裙筒（腰 {waist_st} 针开口起针 → 裙摆 {hem_st} 针），"
                    f"实际高约 {actual_h}cm。"
                )
                if style.skirt_style == "attached":
                    skirt_notes += "腰部挑后半针钩织，免缝合更服帖。"
                else:
                    skirt_notes += "腰部套入身体后缝合固定。"
                if style.ruffle_hem:
                    skirt_notes += "末圈波浪裙摆。"
                part = CrochetPart(
                    name=part_name,
                    type="cup",
                    height_cm=actual_h,
                    diameter_cm=round(hem_st * gauge.stitch_w_cm / 3.14159, 1),
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "body"),
                    magic_ring=False,  # 腰部开口起针，非魔法环
                    notes=skirt_notes,
                )

            elif part_name == "帽子" or shape == "cup":
                # 开口帽形：加针到帽围后直钩至帽深，不收口
                diameter = sp.get("diameter_cm", round(head_d * HAT_HEAD_RATIO, 1))
                max_st = _stitches_for_diameter(diameter, gauge)
                # F18：帽顶（加针段，径向成顶）与侧壁（轴向覆盖深度）分开
                # 计算——旧口径"总目标 − 加针段"在 dk/fine 下侧壁只剩 1 圈
                # （0.6–0.7cm，无法佩戴）。侧壁深度 = 直径×0.6 的轴向高度，
                # 下限 3 圈保证可佩戴。
                wall_rounds = max(3, gauge.rounds_for_height(
                    sp.get("height_cm") or sp.get("length_cm") or diameter * HAT_DEPTH_RATIO))
                rounds_raw = _cup_rounds(max_stitches=max_st,
                                         depth_rounds=wall_rounds)
                # F36：高度口径与圆柱统一——只计轴向筒壁。帽顶加针段是
                # 径向圆盘（§8.6 同判：圆柱把起底盘算进高度会把 4.5cm
                # 标成 9.4cm，帽子同理虚高 ~70%）
                actual_h = round(wall_rounds * gauge.row_h_cm, 1)
                crown_rounds = len(rounds_raw) - wall_rounds
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
                        f"筒深 {wall_rounds} 圈 ≈ {actual_h}cm"
                        f"（另有帽顶 {crown_rounds} 圈径向加针盘，不计入筒深）。"
                    ),
                )

            elif part_name == "身体" and body_profile:
                # 照片驱动身体（M1.2）：剖面 + 圆形截面 = 旋转体，逐圈针数
                # 随照片宽度变化（梨形/收腰不再是等粗圆柱）。
                height = sp.get("height_cm", 9.0)
                ref_st = _stitches_for_diameter(
                    sp.get("diameter_cm") or head_d * BODY_HEAD_RATIO, gauge)
                body_span = (spans or PART_SPAN).get(
                    "身体", PART_SPAN["身体"])
                wall = profile_to_rounds(
                    body_profile, body_span, height, gauge, ref_st,
                    direction="bottom_up",
                )
                dome = _increase_rounds(wall[0])   # 底部圆盘：魔法环→首圈针数
                wall_notes = rounds_to_notes(wall)
                wall_dicts = [
                    {"row": i + 1, "stitches": n, "notes": wall_notes[i],
                     **({"increase": n - wall[i - 1]}
                        if i and n > wall[i - 1] else {}),
                     **({"decrease": wall[i - 1] - n}
                        if i and n < wall[i - 1] else {})}
                    for i, n in enumerate(wall)
                ]
                wall_dicts = _mark_staggered(wall_dicts)
                for i, wd in enumerate(wall_dicts):
                    wd["row"] = len(dome) + i + 1
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
                        f"剖面变化；底部另含圆盘）。末圈保持颈部开口不收针："
                        f"填充棉花后断线留 15cm，与头部开口边逐针缝合成闭口。"
                    ),
                )

            elif part_name == "身体":
                height = sp.get("height_cm", 9.0)
                # 身体针数随头径缩放（旧硬编码 24 针在头 20cm 时严重比例失调）
                max_st = _stitches_for_diameter(
                    sp.get("diameter_cm") or head_d * BODY_HEAD_RATIO, gauge)
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
                max_st = _stitches_for_diameter(
                    sp.get("diameter_cm") or head_d * LIMB_HEAD_RATIO, gauge)
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
            _sem_in_table = False
            if sem:
                from .colors import YARN_COLORS
                _sem_in_table = sem in {name for _rgb, name in YARN_COLORS}
            explicit_color = sp.get("color")
            if explicit_color and explicit_color not in ("skin", "body"):
                # Structure color edits are user intent; photo observations
                # remain fallback inputs for the template placeholders only.
                part.color = explicit_color
                for rd in part.rounds:
                    rd.color = explicit_color
            elif (sem and color_bands and _sem_in_table
                    and part.name in (spans or PART_SPAN)):
                # M3.13 融合：分段结构保留，最近段吸附为语义色（红裙白边）
                CrochetParamsGenerator._apply_color_plan(part, color_bands,
                                                         snap_color=sem,
                                                         spans=spans)
                part.notes = (part.notes or "") + f" 主色按照片语义校正为 {sem}。"
            elif sem:
                # 语义色不在色表 / 无色带：整段单色
                for rd in part.rounds:
                    rd.color = sem
                part.color = sem
                part.notes = (part.notes or "") + f" 配色（照片语义）：{sem}。"
            elif color_bands:
                CrochetParamsGenerator._apply_color_plan(part, color_bands,
                                                         spans=spans)
            # Structure v2 uses one logical pattern plus a physical copy count
            # for symmetric pairs.  Clamp also keeps hand-authored legacy
            # structures from creating unbounded derived totals.
            part.quantity = _part_quantity({"quantity": sp.get("count", 1)})
            crochet_parts.append(part)

        if style.one_piece:
            # 延迟导入：onepiece 引用本模块针法代数（bridge_rounds 等）
            from .onepiece import merge_head_body

            crochet_parts = merge_head_body(
                crochet_parts, gauge)

        return CrochetParamsGenerator._build_result(
            analysis, crochet_parts, gauge, style, structure)


    @staticmethod
    def _apply_color_plan(part: CrochetPart, bands: list[dict],
                          snap_color: str | None = None,
                          spans: dict[str, Any] | None = None) -> None:
        """把照片色带按部件纵向占比铺到每一圈（原地），并生成换线说明。

        snap_color（M3.13 语义融合）：提供时保留色带分段结构，把与该语义色
        最接近的段"吸附"为语义色本身（红裙白边 → 白边保留、红段吸附为正红）；
        语义色不在毛线色表中时由调用方退化为整段单色。
        spans（S1）：实测部件占比，None 回退 PART_SPAN 先验。
        """
        blocks = color_blocks_for_part(bands, part.name, spans=spans)
        if not blocks:
            return  # 该部件无占比（先验/实测均无）→ 保持单色
        span = (spans or PART_SPAN).get(part.name) or PART_SPAN.get(
            part.name, (0.0, 1.0))
        span_s, span_e = span
        span_len = span_e - span_s
        n = len(part.rounds)
        # 钩织方向：身体/四肢自端部起针（R1=脚底/手端/胯部=照片低处），
        # 末圈才缝合到躯干——这些部件的照片色带映射必须自底向上。
        bottom_up = part.name in _BOTTOM_UP_PARTS
        colors: list[str | None] = []
        for j in range(n):
            frac = (span_e - span_len * (j + 0.5) / n) if bottom_up else (
                span_s + span_len * (j + 0.5) / n
            )
            colors.append(round_color(frac, blocks))

        # 语义吸附：占比最大的段（该部件的主色段）→ 替换为语义色。
        # 吸附目标用"主色段"而非"色距最近段"：LLM 语义字段描述的是服装主色
        # （"红裙子"），主色对应照片中覆盖圈数最多的段；边/饰条段天然更小，
        # 应保留（红裙白边 → 蓝主体段吸附为红、白边不动）。色距只做平局
        # 裁决（CIEDE2000；旧版用色距选段，在蓝/中性区会吸错小段）。
        if snap_color:
            from .colors import YARN_COLORS, color_distance

            rgb_by_name = {
                name: (rgb[0], rgb[1], rgb[2]) for rgb, name in YARN_COLORS}
            snap_rgb = rgb_by_name.get(snap_color)
            if snap_rgb is not None:
                candidates = {c for c in colors if c in rgb_by_name}
                if candidates:
                    dominant = max(
                        candidates,
                        key=lambda c: (colors.count(c),
                                       -color_distance(rgb_by_name[c], snap_rgb)))
                    colors = [snap_color if c == dominant else c for c in colors]

        prev: str | None = None
        if len(part.rounds) != len(colors):
            raise RuntimeError("round color count does not match generated rounds")
        for rd, c in zip(part.rounds, colors):  # noqa: B905 - length checked above
            rd.color = c
            if prev is not None and c != prev:
                # jogless 换色：前一针最后一次挂线即改用新色，消除螺旋台阶
                rd.notes = (rd.notes or "") + (
                    f"；换线：{c}（前一针最后一次挂线改用新色，避免螺旋台阶）"
                )
            prev = c
        if len(set(colors)) > 1:
            part.notes = (part.notes or "") + f" 配色（自上而下）：{blocks_summary_text(colors)}。"
        # 主色回写：部件基准色取该部件占比最大的色段（round_color 在
        # blocks 非空时恒返回色名，调用方已保证；过滤只满足 str 类型）
        named = [c for c in colors if c is not None]
        part.color = max(set(named), key=colors.count)

    @staticmethod
    def _build_result(analysis: ImageAnalysis, parts: list[CrochetPart],
                      gauge: Gauge = DEFAULT_GAUGE,
                      style: "ShapingStyle | None" = None,
                      structure: dict[str, Any] | None = None) -> dict[str, Any]:
        """Assemble the result dict: materials / assembly / time scale with parts.

        双态收敛出口：parts 以 CrochetPart 模型参与构造、配色与校验，
        在此统一 dump 为 dict——params["parts"] 的内存形态与落盘/分享/
        历史形态一致，_part_* helper 只需处理 dict。
        """
        style = style or DEFAULT_STYLE
        part_dicts = [p.model_dump() for p in parts]
        part_names = {p["name"] for p in part_dicts}
        total_stitches = sum(
            r["stitches"] * _part_quantity(p)
            for p in part_dicts for r in p["rounds"])

        quantities = {p["name"]: _part_quantity(p) for p in part_dicts}
        assembly_plan = structure_connection_plan(structure or {})
        assembly = build_assembly(
            part_names, style.skirt_style, quantities, assembly_plan,
            openings=_openings_by_part(part_dicts))

        # F13 生成门禁：生成器自己产出的图解必须通过自检，代数矛盾
        # 在此处拦截（而不是等到结果页才显示警告）
        gauge_payload = {"stitches_per_10cm": gauge.stitches_per_10cm,
                         "rows_per_10cm": gauge.rows_per_10cm}
        validation = validate_pattern({
            "parts": part_dicts,
            "gauge": gauge_payload,
        })
        if not validation["ok"]:
            raise PatternGenerationError(
                "生成的图解未通过自检: " + "；".join(validation["issues"]))

        result = {
            "materials": _materials(part_dicts, part_names, gauge),
            "material_summary": yarn_requirements(part_dicts, gauge)[1],
            "parts": part_dicts,
            "assembly_instructions": assembly,
            "difficulty": analysis.difficulty,
            "estimated_time_minutes": estimate_minutes(part_dicts),
            "time_estimate_basis": time_estimate_basis(),
            "total_stitches": total_stitches,
            "skirt_style": style.skirt_style,  # refresh_derived 保留裙子做法口径
            # gauge 随 params 序列化：refresh_derived（JSON 修正/备份导入）
            # 按它重算材料，否则退回默认密度导致克重/钩针标签漂移
            "gauge": gauge_payload,
            "shaping": _shaping_meta(gauge),
            "notes": (
                "螺旋钩法：全程不引拔、不翻转，每圈第一针挂记号扣；"
                "减针建议用隐形减针（只挑两针目的前半针）更平整。"
                "基于单图推理生成，比例可能需要试钩调整。"
            ),
        }
        if assembly_plan is not None:
            result["assembly_plan"] = assembly_plan
        return result
