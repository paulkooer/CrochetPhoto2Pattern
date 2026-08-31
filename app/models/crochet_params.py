from typing import Any, Dict, List, Optional

from ..schemas import CrochetPart, CrochetStitch, ImageAnalysis
from .color_design import (
    PART_SPAN,
    blocks_summary_text,
    color_blocks_for_part,
    round_color,
)
from .gauge import DEFAULT as DEFAULT_GAUGE
from .gauge import (
    Gauge,
    ShapingStyle,
    gauge_from_mapping,
    next_shaping_stitch_count,
)
from .profile_shaping import profile_to_rounds, rounds_to_notes, strip_dome
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
# U23（升级版，按 Opus 5 校准）：时长 = 针数×单针 + 圈数×每圈固定开销
# （起头/记号扣/换线等固定动作）。物理驱动量是针数（每针一个手部动作）；
# 单针耗时跨密度近似恒定。结构 v2 后，classic 默认玩偶按头/身各一件、
# 手/腿各两件计为 1224 针/66 个实际圈次，约 144 分钟；旧版 121 分钟
# 漏算了第二只手臂和腿。跨密度仍使用同一物理模型。
# 数值为经验估算，不署名任何标准机构（V6 教训）。
SECONDS_PER_STITCH = 6.5
SECONDS_PER_ROUND_OVERHEAD = 10.0
# 注意：四肢不再用独立的 1.2 圈/cm——行高是纱线属性，不随部件变（fable5 #15）

# ── 部件相对头径的比例假设（Q 版 Amigurumi）────────────────────────────────
BODY_HEAD_RATIO = 1.0        # 身体直径 ≈ 头径（球/圆柱等粗）
LIMB_HEAD_RATIO = 0.33       # 四肢直径 ≈ 头径 1/3（参考尺寸下恰为 12 针）
HAT_HEAD_RATIO = 1.15        # 帽围松量：太小戴不进去，太大松垮
HAT_DEPTH_RATIO = 0.6        # 帽深 ≈ 帽直径 × 0.6
SKIRT_BODY_RATIO = 1.25      # 裙摆直径相对身体放大

# 自端部起针的部件（R1 对应照片低处）：照片配色映射自底向上
_BOTTOM_UP_PARTS = frozenset({"身体", "手臂", "腿部"})

# 头身一体件：粗略计入两组用线（实际占比取决于配色，可试钩后修正）
_ONE_PIECE_NAME = "头身（一体）"


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


def bridge_rounds(cur: int, target: int, max_change: int = 6) -> List[int]:
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


def _ideal_sphere_rounds(
    diameter_cm: float,
    gauge: Gauge = DEFAULT_GAUGE,
    egg: bool = False,
    egg_e: float = 0.12,
) -> List[Dict[str, Any]]:
    """理想球/蛋形（M2.6/M2.7）：逐圈针数 ∝ sin(极角)。

    依据：The Ideal Crochet Sphere（mspremiseconclusion, 2010，已核实原文）——
    每行 = 固定极角 Δθ，θ 处圆周长 ∝ sin(θ)，针数 N = C/s
    （C = π·D·sinθ = 截面圆周长，s = 针宽；原文 "Pi*r^2" 为笔误）。
    经典阶梯球沿经线布料量偏少（+6 阶梯只在极点附近密集），理想球分布
    均匀、填充后更圆。
    egg=True：宽度乘 (1 + e·cosθ)（θ 自顶极点），上略宽下略窄的蛋形——
    玩偶头主流形状；返回值附 eye_round（最大围行，眼睛在其下一两圈）。
    原文工艺警告：收尾不要按标准减针收到 6 针（底部过尖）——保持约
    12 针左右直接穿线勒紧收口；动态塑形上限仍受单圈可执行性约束。
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
    rounds: List[Dict[str, Any]] = [{
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
        # 原文工艺：不要继续减针收到 6 针（底部过尖）——穿线勒紧收口
        last["notes"] = (last.get("notes") or "") + (
            "；断线留10cm，穿过后圈每针勒紧收口藏线头"
            "（勿再减针收成6针，底部会过尖）")
    # 眼睛：最大围所在圈（蛋形时上移），再往下 1 圈
    eye_idx = max(range(len(clamped)), key=lambda i: clamped[i])
    rounds[0]["eye_round"] = min(len(rounds), eye_idx + 2)  # 附带信息，CrochetStitch 会忽略
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


def _part_quantity(part: Any) -> int:
    """Physical copies represented by one logical part pattern (legacy = 1)."""
    raw = part.get("quantity", 1) if isinstance(part, dict) else getattr(
        part, "quantity", 1)
    try:
        return max(1, min(20, int(raw)))
    except (TypeError, ValueError):
        return 1


def _round_stitches(rd: Any) -> int:
    return rd.get("stitches", 0) if isinstance(rd, dict) else rd.stitches


def structure_connection_plan(structure: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
    connections: List[Dict[str, str]] = []
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


def _materials(parts: List[Any], part_names: set,
                gauge: Gauge = DEFAULT_GAUGE) -> List[Dict[str, str]]:
    """材料清单随实际部件生成；parts 元素可为 CrochetPart 或 dict（JSON 修正路径）。

    克重按针数×单针克重估算；米数按针宽分档的**经验估算值**换算
    （gauge.meters_per_100g，非标准机构数据——CYC 标准不含长度信息），
    供购买参考——两者都是需试钩校准的启发式。
    除肤色系/主体色两组汇总外，另按**具体毛线色**逐色给出用量（T2，
    十字绣界按色号给量的通行惯例；跨部件同色自动合并）。
    """
    materials: List[Dict[str, str]] = []
    _skin = _SKIN_PARTS | {_ONE_PIECE_NAME}
    _body = _BODY_PARTS | {_ONE_PIECE_NAME}
    for group, label in ((_skin, "肤色系毛线"), (_body, "主体色毛线")):
        group_parts = [p for p in parts if _part_name(p) in group]
        if not group_parts:
            continue
        grams = max(20, round(sum(
            _round_stitches(rd) * _part_quantity(p)
            for p in group_parts for rd in _part_rounds(p)
        ) * gauge.grams_per_stitch))
        meters = round(grams / 100.0 * gauge.meters_per_100g)
        materials.append({"item": label, "quantity": f"约 {grams}g（≈{meters}m）"})

    # T2：逐色用量（跨部件聚合；色来自逐圈配色）。内部占位符不是毛线
    # 色名（单色部件回退 p.color 会把 "skin"/"body" 写进材料清单）——排除
    _PLACEHOLDER_COLORS = {"skin", "body"}
    color_stitches: Dict[str, int] = {}
    for p in parts:
        quantity = _part_quantity(p)
        for rd in _part_rounds(p):
            c = (rd.get("color") if isinstance(rd, dict) else rd.color) \
                or None
            if c is None:
                c = p.get("color") if isinstance(p, dict) else p.color
            if c and c not in _PLACEHOLDER_COLORS:
                color_stitches[c] = (
                    color_stitches.get(c, 0) + _round_stitches(rd) * quantity)
    from .colors import brand_code
    for c in sorted(color_stitches, key=lambda k: -color_stitches[k]):
        grams = max(5, round(color_stitches[c] * gauge.grams_per_stitch))
        meters = round(grams / 100.0 * gauge.meters_per_100g)
        code = brand_code(c)
        item = f"毛线 · {c}" + (f"（{code}）" if code else "")
        materials.append({"item": item, "quantity": f"约 {grams}g（≈{meters}m）",
                          "color": c})
    if "头部" in part_names:
        materials.append({"item": "安全眼", "quantity": "一对 (8mm)"})
    materials.append({"item": "填充棉", "quantity": "适量"})
    materials.append({"item": gauge.hook_yarn_label, "quantity": "1 把"})
    materials.append({"item": "缝合针", "quantity": "1 根"})
    return materials


def _gauge_from_params(params: dict) -> Gauge:
    """从 params 恢复生成时的 gauge（JSON 修正/备份导入路径的单一来源）。

    用户可能在 JSON 里把数值改坏：钳到与侧栏相同的区间（6–40 / 8–50 针数
    /行数），缺失或非法时回退默认——与 gauge_from_ui 的兜底口径一致。
    """
    return gauge_from_mapping(params.get("gauge"))


def _shaping_meta(gauge: Gauge) -> Dict[str, Any]:
    """Serializable explanation of the gauge-dependent shaping constraint."""
    return {
        "continuous_delta": round(gauge.shaping_continuous_delta, 2),
        "max_stitch_change": gauge.max_shaping_change,
        "quantization": "ceil_to_six_stitch_sectors",
        "note": "连续几何变化率按六等分针法向上量化；实际圈可使用更小的6针步长",
    }


def estimate_minutes(parts: List[Any]) -> int:
    """U23：共用时长估算（refresh_derived 与 _build_result 共用，消除
    两份重复实现的失同步风险）。时长 = 针数×单针 + 圈数×每圈固定开销；
    下限 30 分钟（含备料/收针/藏线头等固定开销——极小样本上线性模型
    必然低估）。经验估算值。"""
    total_stitches = sum(
        _round_stitches(rd) * _part_quantity(p)
        for p in parts for rd in _part_rounds(p))
    total_rounds = sum(
        len(_part_rounds(p)) * _part_quantity(p) for p in parts)
    return max(30, round((total_stitches * SECONDS_PER_STITCH
                          + total_rounds * SECONDS_PER_ROUND_OVERHEAD) / 60.0))


def time_estimate_basis() -> Dict[str, Any]:
    """Describe the deliberately narrow, currently uncalibrated time model."""
    return {
        "scope": "round_crochet_baseline",
        "confidence": "low_uncalibrated",
        "included": ["stitch_count", "physical_round_overhead"],
        "excluded": [
            "assembly",
            "stuffing",
            "color_changes",
            "embroidery",
            "rework",
            "breaks",
        ],
        "seconds_per_stitch": SECONDS_PER_STITCH,
        "seconds_per_round_overhead": SECONDS_PER_ROUND_OVERHEAD,
        "minimum_minutes": 30,
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
    params["materials"] = _materials(
        parts, {_part_name(p) for p in parts}, gauge=gauge)
    params["shaping"] = _shaping_meta(gauge)
    # 装配说明同样是 parts 的函数：删部件后不得残留对应步骤（F5）；
    # 裙子做法按生成时的口径保留
    quantities = {_part_name(p): _part_quantity(p) for p in parts}
    params["assembly_instructions"] = build_assembly(
        set(quantities), params.get("skirt_style", "ring"), quantities,
        params.get("assembly_plan"))
    return params


def build_assembly(part_names, skirt_style: str = "ring",
                   quantities: Optional[Dict[str, int]] = None,
                   assembly_plan: Optional[Dict[str, Any]] = None) -> str:
    """Build assembly text from the v2 graph, with a legacy name fallback."""
    quantities = quantities or {}

    def placement(name: str, paired: str, single: str, many: str) -> str:
        quantity = max(1, int(quantities.get(name, 1)))
        if quantity == 1:
            return single
        if quantity == 2:
            return paired
        return f"{name}共 {quantity} 个，{many}"

    one_piece = _ONE_PIECE_NAME in part_names
    steps: List[str] = ["按各部件标注数量分别完成并填充棉花"]
    if one_piece:
        steps.append("一体件钩完头部后先填充头部再继续钩身体（分阶段填充）")
    if "头部" in part_names or one_piece:
        steps.append("头部安装安全眼（第2/3高度处）")
        steps.append("用黑色毛线绣鼻子和嘴巴")

    # Old backups have no graph.  Keep their established name-based behavior
    # rather than pretending to infer missing connection nodes during import.
    if assembly_plan is None:
        if "头部" in part_names and "身体" in part_names and not one_piece:
            steps.append("用隐形缝合法将头部接合到身体顶部")
        if "手臂" in part_names:
            steps.append(placement(
                "手臂", "手臂对称缝合到身体两侧上方",
                "手臂缝合到身体一侧上方", "均匀缝合到身体上部"))
        if "腿部" in part_names:
            steps.append(placement(
                "腿部", "腿部对称缝合到身体底部",
                "腿部缝合到身体底部", "均匀缝合到身体底部"))
        if "耳朵" in part_names:
            steps.append(placement(
                "耳朵", "耳朵对称缝合在头部两侧",
                "耳朵缝合在头部一侧", "均匀缝合在头部周围"))
        if "帽子" in part_names:
            steps.append("帽口不收口，直接戴在头部（试戴后可缝合固定）")
        if "裙子" in part_names:
            if skirt_style == "attached":
                steps.append("裙子已挑后半针钩在身体腰部，无需缝合")
            else:
                steps.append("裙筒腰部套入身体后缝合固定（腰部为开口起针）")
        if "尾巴" in part_names:
            steps.append("尾巴缝合在身体后方")
        return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))

    def effective_name(name: str) -> str:
        if one_piece and name in ("头部", "身体"):
            return _ONE_PIECE_NAME
        return name

    raw_connections = (assembly_plan.get("connections", [])
                       if isinstance(assembly_plan, dict) else [])
    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for connection in raw_connections:
        if not isinstance(connection, dict):
            continue
        source = effective_name(str(connection.get("source_part_name") or ""))
        target = effective_name(str(connection.get("target_part_name") or ""))
        if (not source or not target or source == target
                or source not in part_names or target not in part_names):
            continue
        key = (source, target, str(connection.get("method") or "sewn"))
        grouped.setdefault(key, []).append(connection)

    connected_sources = set()
    anchor_labels = {
        "top": "顶部", "bottom": "底部", "back": "后方", "front": "前方",
        "waist": "腰部", "side_left": "左侧", "side_right": "右侧",
        "upper_left": "左侧上方", "upper_right": "右侧上方",
        "bottom_left": "左侧底部", "bottom_right": "右侧底部",
    }
    for (source, target, method), connections in grouped.items():
        connected_sources.add(source)
        target_label = "一体件身体段" if target == _ONE_PIECE_NAME else target
        if source == "头部" and target == "身体":
            steps.append("用隐形缝合法将头部接合到身体顶部")
        elif source == "手臂" and target in ("身体", _ONE_PIECE_NAME):
            steps.append(placement(
                "手臂", f"手臂对称缝合到{target_label}两侧上方",
                f"手臂缝合到{target_label}一侧上方",
                f"均匀缝合到{target_label}上部"))
        elif source == "腿部" and target in ("身体", _ONE_PIECE_NAME):
            steps.append(placement(
                "腿部", f"腿部对称缝合到{target_label}底部",
                f"腿部缝合到{target_label}底部",
                f"均匀缝合到{target_label}底部"))
        elif source == "耳朵" and target in ("头部", _ONE_PIECE_NAME):
            steps.append(placement(
                "耳朵", "耳朵对称缝合在头部两侧",
                "耳朵缝合在头部一侧", "均匀缝合在头部周围"))
        elif source == "帽子" and target in ("头部", _ONE_PIECE_NAME):
            steps.append("帽口不收口，直接戴在头部（试戴后可缝合固定）")
        elif source == "裙子" and target in ("身体", _ONE_PIECE_NAME):
            if skirt_style == "attached":
                steps.append(f"裙子已挑后半针钩在{target_label}腰部，无需缝合")
            else:
                steps.append(f"裙筒腰部套入{target_label}后缝合固定（腰部为开口起针）")
        elif source == "尾巴" and target in ("身体", _ONE_PIECE_NAME):
            steps.append(f"尾巴缝合在{target_label}后方")
        else:
            anchors = list(dict.fromkeys(
                anchor_labels.get(str(item.get("target_anchor")),
                                  str(item.get("target_anchor") or "指定位置"))
                for item in connections))
            action = {
                "sewn": "缝合到",
                "worn": "佩戴到",
                "crocheted_or_sewn": "挑针钩接或缝合到",
            }.get(method, "连接到")
            steps.append(
                f"{source}{action}{target_label}的{'、'.join(anchors)}")

    roots = {_ONE_PIECE_NAME, "身体"}
    if "身体" not in part_names and not one_piece:
        roots.add("头部")
    for name in sorted(part_names - roots - connected_sources):
        steps.append(f"{name}未设置连接关系，暂按独立部件保留")
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
        style: ShapingStyle = None,
        spans: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        from .gauge import DEFAULT_STYLE
        style = style or DEFAULT_STYLE
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
                    shape_label = {"ideal": "理想球形（sinθ 分布）",
                                   "egg": "蛋形（下半收窄）"}.get(
                                       style.sphere_mode, "标准球形")
                    notes = (
                        f"{shape_label}，最大 {max_st} 针。"
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
                    diameter * HAT_DEPTH_RATIO))
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
                ref_st = _stitches_for_diameter(head_d * BODY_HEAD_RATIO, gauge)
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
                        f"剖面变化；底部另含圆盘）。末圈保持颈部开口不收针："
                        f"填充棉花后断线留 15cm，与头部开口边逐针缝合成闭口。"
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
            _sem_in_table = False
            if sem:
                from .colors import YARN_COLORS
                _sem_in_table = sem in {name for _rgb, name in YARN_COLORS}
            if (sem and color_bands and _sem_in_table
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
            crochet_parts = CrochetParamsGenerator._merge_head_body(
                crochet_parts, gauge)

        return CrochetParamsGenerator._build_result(
            analysis, crochet_parts, gauge, style, structure)

    @staticmethod
    def _merge_head_body(parts: List[CrochetPart], gauge: Gauge) -> List[CrochetPart]:
        """头身一体钩（M2.10）：头顶起针→颈部不断线→身体向下→底部收口。

        头部保留到颈围（与身体顶端口径一致的减针链），身体筒壁反转成自顶
        向下（几何不变，加减针说明按新方向重算），末端补收口圆盘。
        配色退化为整段单色（一体件的分段配色映射口径复杂，后续再议）。
        """
        head = next((p for p in parts if p.name == "头部"), None)
        body = next((p for p in parts if p.name == "身体"), None)
        if head is None or body is None:
            return parts

        body_sts = [r.stitches for r in body.rounds]
        # F16：dome 剥离必须用 strip_dome（+6 前缀），不能用
        # body_sts[0]//6——首圈是魔法环 6 针，恒得 1（N4 同款错误），
        # 会把 dome 加针圈混进"筒壁"，一体件底部出现第二个假 dome。
        wall = strip_dome(body_sts)                    # 自底向上
        neck = wall[-1] if wall else 24                # 身体顶端（近颈）针数

        # 头部保留至减针链中 ≥ neck 的最后一圈，丢弃更小的收口圈
        head_kept: List[int] = []
        for r in head.rounds:
            head_kept.append(r.stitches)
            if r.stitches >= neck and (r.decrease or 0) > 0:
                break
        while len(head_kept) > 1 and head_kept[-1] < neck:
            head_kept.pop()
        if head_kept[-1] != neck:
            # F13：颈围对齐必须按当前密度逐圈桥接，禁止无依据直接跳变（旧实现
            # head_kept.append(neck) 会产生 42→30 之类的 12 针跳变，
            # 且 increase/decrease 字段只声明 6——文字/针数/代数三方矛盾）
            head_kept.extend(bridge_rounds(
                head_kept[-1], neck, gauge.max_shaping_change))

        # 身体壁自顶向下 = wall 反转，首圈对齐颈围后按动态上限重钳制
        top_down = [neck] + list(reversed(wall[:-1])) if len(wall) > 1 else [neck]
        merged_sts = head_kept[:]
        for t in top_down[1:]:
            prev = merged_sts[-1]
            merged_sts.append(next_shaping_stitch_count(
                prev, max(6, t), gauge.max_shaping_change))
        # 底部收口：向下递减到 6
        while merged_sts[-1] > 6:
            merged_sts.append(next_shaping_stitch_count(
                merged_sts[-1], 6, gauge.max_shaping_change))

        rounds_raw: List[Dict[str, Any]] = []
        for i, n in enumerate(merged_sts):
            if i == 0:
                notes = f"魔法环起{n}针（X×{n}）"
            else:
                before = merged_sts[i - 1]
                notes = _change_note(before, n)
                if i == len(head_kept) - 1 and i > 0:
                    notes += "；此处为颈部，不断线直接钩身体"
            rounds_raw.append({
                "row": i + 1, "stitches": n, "notes": notes,
                "increase": max(0, n - merged_sts[i - 1]) if i else 0,
                "decrease": max(0, merged_sts[i - 1] - n) if i else 0,
            })
        rounds_raw = _mark_staggered(rounds_raw)
        last = rounds_raw[-1]
        last["notes"] = (last.get("notes") or "") + "；断线留10cm，勒紧收口藏线头"

        eye_round = next((i + 1 for i, r in enumerate(rounds_raw)
                          if r["stitches"] == max(merged_sts)), 2) + 1
        # F16：高度口径与独立身体一致——只计轴向堆叠圈（头部成品到颈 +
        # 筒壁），底部收口圈是径向圆盘不计高。merged 结构 = head_kept +
        # top_down[1:] + 收口（top_down[0]=颈围与 head_kept[-1] 同圈）。
        _axial_rounds = len(head_kept) + max(0, len(top_down) - 1)
        merged = CrochetPart(
            name=_ONE_PIECE_NAME,
            type="onepiece",
            height_cm=round(_axial_rounds * gauge.row_h_cm, 1),
            rounds=[CrochetStitch(**r) for r in rounds_raw],
            color=head.color,
            magic_ring=True,
            notes=(
                f"头身一体钩（最大 {max(merged_sts)} 针）：头顶起针钩至颈部后"
                f"不断线直接向下钩身体，末端收口；第 {eye_round} 圈安装安全眼。"
                "钩完头部先填充再继续。配色为整段单色（一体件分段换线建议自行规划）。"
            ),
        )
        return [merged] + [p for p in parts if p.name not in ("头部", "身体")]

    @staticmethod
    def _apply_color_plan(part: CrochetPart, bands: List[Dict],
                          snap_color: Optional[str] = None,
                          spans: Optional[Dict[str, Any]] = None) -> None:
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
        colors: List[Optional[str]] = []
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

            rgb_by_name = {name: tuple(rgb) for rgb, name in YARN_COLORS}
            snap_rgb = rgb_by_name.get(snap_color)
            if snap_rgb is not None:
                candidates = {c for c in colors if c in rgb_by_name}
                if candidates:
                    dominant = max(
                        candidates,
                        key=lambda c: (colors.count(c),
                                       -color_distance(rgb_by_name[c], snap_rgb)))
                    colors = [snap_color if c == dominant else c for c in colors]

        prev: Optional[str] = None
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
        # 主色回写：部件基准色取该部件占比最大的色段
        part.color = max(set(colors), key=colors.count)

    @staticmethod
    def _build_result(analysis: ImageAnalysis, parts: List[CrochetPart],
                      gauge: Gauge = DEFAULT_GAUGE,
                      style: "ShapingStyle" = None,
                      structure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Assemble the result dict: materials / assembly / time scale with parts."""
        part_names = {p.name for p in parts}
        total_stitches = sum(
            r.stitches * _part_quantity(p) for p in parts for r in p.rounds)

        quantities = {p.name: _part_quantity(p) for p in parts}
        assembly_plan = structure_connection_plan(structure or {})
        assembly = build_assembly(
            part_names, style.skirt_style, quantities, assembly_plan)

        # F13 生成门禁：生成器自己产出的图解必须通过自检，代数矛盾
        # 在此处拦截（而不是等到结果页才显示警告）
        gauge_payload = {"stitches_per_10cm": gauge.stitches_per_10cm,
                         "rows_per_10cm": gauge.rows_per_10cm}
        validation = validate_pattern({
            "parts": [p.model_dump() for p in parts],
            "gauge": gauge_payload,
        })
        if not validation["ok"]:
            raise PatternGenerationError(
                "生成的图解未通过自检: " + "；".join(validation["issues"]))

        result = {
            "materials": _materials(parts, part_names, gauge),
            "parts": parts,
            "assembly_instructions": assembly,
            "difficulty": analysis.difficulty,
            "estimated_time_minutes": estimate_minutes(parts),
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
