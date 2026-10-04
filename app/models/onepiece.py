"""头身一体钩（M2.10）：头部与身体合并为一件连续钩织的图解。

从 CrochetParamsGenerator._merge_head_body 拆出为纯函数；针法代数
（bridge_rounds/_change_note/_mark_staggered）仍以 crochet_params 为单一
来源——crochet_params 在调用点延迟导入本模块以避免导入环。
"""
from __future__ import annotations

from typing import Any

from ..schemas import CrochetPart, CrochetStitch
from .crochet_params import _change_note, _mark_staggered, bridge_rounds
from .gauge import Gauge, next_shaping_stitch_count
from .parts import _ONE_PIECE_NAME
from .profile_shaping import strip_dome


def merge_head_body(parts: list[CrochetPart], gauge: Gauge) -> list[CrochetPart]:
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
    head_kept: list[int] = []
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

    rounds_raw: list[dict[str, Any]] = []
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
    last["notes"] = (last.get("notes") or "") + (
        "；断线留10cm，穿末圈每针前半针后拉紧（无痕收口）藏线头")

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
