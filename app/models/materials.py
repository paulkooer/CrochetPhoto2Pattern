"""材料清单：克重/米数估算、逐色用量聚合、安全眼与配件建议。

从 crochet_params 拆出；部件访问助手来自 parts，毛线品牌代码来自 colors。
"""
from __future__ import annotations

from typing import Any

from .colors import brand_code
from .gauge import DEFAULT as DEFAULT_GAUGE
from .gauge import Gauge
from .parts import (
    _BODY_PARTS,
    _ONE_PIECE_NAME,
    _SKIN_PARTS,
    _part_name,
    _part_quantity,
    _part_rounds,
    _round_stitches,
)


def _safety_eye_mm(head_diameter_cm: float | None) -> int:
    """头径 → 安全眼直径分档（mm）——对齐社区口径与专业图解锚点。

    r/Amigurumi 眼睛 wiki（2026-09 抓取）：迷你件 5–6mm、常规玩偶
    （15–25cm）8–12mm、大型件（30cm+）14–20mm+。专业锚点：约 10cm 头径
    均配 12mm 安全眼（Supergurumi 蜜蜂 12.6in/32cm、StringyDingDing
    袋鼠 9in/23cm）——本分档取社区区间中值偏保守，待 G4 实体试钩校准。
    """
    if head_diameter_cm is None:
        return 8
    if head_diameter_cm < 5:
        return 6
    if head_diameter_cm < 8:
        return 8
    if head_diameter_cm < 11:
        return 10
    if head_diameter_cm < 14:
        return 12
    return 14


def _materials(parts: list[dict[str, Any]], part_names: set,
                gauge: Gauge = DEFAULT_GAUGE) -> list[dict[str, str]]:
    """材料清单随实际部件生成（parts 为 dict 形态，见 _build_result）。

    克重按针数×单针克重估算；米数按针宽分档的**经验估算值**换算
    （gauge.meters_per_100g，非标准机构数据——CYC 标准不含长度信息），
    供购买参考——两者都是需试钩校准的启发式。
    除肤色系/主体色两组汇总外，另按**具体毛线色**逐色给出用量（T2，
    十字绣界按色号给量的通行惯例；跨部件同色自动合并）。
    """
    materials: list[dict[str, str]] = []
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
    color_stitches: dict[str, int] = {}
    for p in parts:
        quantity = _part_quantity(p)
        for rd in _part_rounds(p):
            c = rd.get("color") or None
            if c is None:
                c = p.get("color") or None
            if c and c not in _PLACEHOLDER_COLORS:
                color_stitches[c] = (
                    color_stitches.get(c, 0) + _round_stitches(rd) * quantity)
    for c in sorted(color_stitches, key=lambda k: -color_stitches[k]):
        grams = max(5, round(color_stitches[c] * gauge.grams_per_stitch))
        meters = round(grams / 100.0 * gauge.meters_per_100g)
        code = brand_code(c)
        item = f"毛线 · {c}" + (f"（{code}）" if code else "")
        materials.append({"item": item, "quantity": f"约 {grams}g（≈{meters}m）",
                          "color": c})
    # 一体件会把"头部/身体"合并改名"头身（一体）"；显式识别这三个
    # 语义名称，避免"头套"等附件因子串命中而误获安全眼或配重珠。
    has_head = any(
        _part_name(p) in {"头部", _ONE_PIECE_NAME} for p in parts)
    has_body = any(
        _part_name(p) in {"身体", _ONE_PIECE_NAME} for p in parts)
    if has_head:
        # 安全眼尺寸随头径分档（固定 8mm 在大/小头径下失真——社区与
        # 专业图解都按玩偶大小配眼）；无头径数据的旧结果兜底 8mm
        head = next((p for p in parts
                     if _part_name(p) in {"头部", _ONE_PIECE_NAME}), None)
        diameter = head.get("diameter_cm") if isinstance(head, dict) else None
        try:
            diameter = float(diameter) if diameter is not None else None
        except (TypeError, ValueError):
            diameter = None
        materials.append({"item": "安全眼",
                          "quantity": f"一对 ({_safety_eye_mm(diameter)}mm；"
                                      "3 岁以下儿童及宠物玩偶禁用——眼件"
                                      "可能脱落误吞，必须改用刺绣眼)"})
    materials.append({"item": "填充棉", "quantity": "适量"})
    # 配重底（可选）——Grace and Yarn 逐字：约 3/4 杯聚乙烯珠装入丝袜
    # 打结置于底部（丝袜色近玩偶防透出），在开始减针、开口尚能伸手时
    # 放入；3 岁以下勿用（珠粒可能透过针缝）；可正常水洗。
    if has_body:
        materials.append({
            "item": "配重珠（可选）",
            "quantity": "约 3/4 杯——装入丝袜打结后置底再正常填充；"
                        "3 岁以下儿童玩偶勿用",
        })
    # 可弯折四肢的定型线（可选件）——规格锚点：Crafty Intentions 设计师
    # 用纸包 18 号 18 英寸花艺线（布包同号过软不承力），r/CrochetHelp
    # 共识 16–20 号；端部折环包裹出自 Maclafersa 安全指南（端口折环 +
    # 软物缠绕，胶带单独不可靠）。儿童玩具不应使用任何硬质内骨架
    # （含竹签——可能断裂戳出），改用毛条等软质填充。
    limb_count = sum(
        _part_quantity(p) for p in parts
        if any(k in _part_name(p) for k in ("手臂", "腿", "尾")))
    if limb_count:
        materials.append({
            "item": "定型线（可选）",
            "quantity": f"18号（≈1.2mm）纸包花艺线 {limb_count} 根——"
                        "端部折回成环并包裹防戳；儿童玩具勿用任何硬质"
                        "内骨架，改毛条等软质填充",
        })
    # CYC 分档是"密度→档位"参考（见 Gauge.cyc_label）：前者是玩偶紧钩
    # 惯例的钩针建议，后者是同密度的 CYC 标准钩针区间——并列展示而非混淆。
    materials.append({
        "item": f"{gauge.hook_yarn_label}（{gauge.cyc_label}）",
        "quantity": "1 把",
    })
    materials.append({"item": "缝合针", "quantity": "1 根"})
    return materials
