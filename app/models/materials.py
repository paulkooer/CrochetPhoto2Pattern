"""材料清单：克重/米数估算、逐色用量聚合、安全眼与配件建议。

从 crochet_params 拆出；部件访问助手来自 parts，毛线品牌代码来自 colors。
"""
from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .colors import brand_code
from .gauge import DEFAULT as DEFAULT_GAUGE
from .gauge import Gauge
from .parts import (
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


class YarnSpec(BaseModel):
    """One yarn specification shared by all colours; swatch must use that yarn."""
    ball_weight_g: float = Field(gt=0, le=2000, allow_inf_nan=False)
    ball_length_m: float = Field(gt=0, le=10000, allow_inf_nan=False)
    swatch_weight_g: float | None = Field(default=None, gt=0, le=2000, allow_inf_nan=False)
    swatch_stitches: int | None = Field(default=None, ge=1, le=1000, strict=True)
    swatch_rows: int | None = Field(default=None, ge=1, le=1000, strict=True)
    waste_percent: float = Field(default=10, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def complete_swatch(self):
        fields = (self.swatch_weight_g, self.swatch_stitches, self.swatch_rows)
        if any(x is not None for x in fields) and not all(x is not None for x in fields):
            raise ValueError("试片必须同时提供克重、每行针数和行数")
        return self


def yarn_requirements(parts: list[dict], gauge: Gauge = DEFAULT_GAUGE,
                      yarn_spec: dict | None = None) -> tuple[list[dict], dict]:
    """Count every stitch exactly once; the summary is not another purchase item."""
    spec = YarnSpec.model_validate(yarn_spec) if yarn_spec is not None else None
    per_stitch = gauge.grams_per_stitch
    if spec and spec.swatch_weight_g is not None:
        assert spec.swatch_stitches is not None and spec.swatch_rows is not None
        per_stitch = spec.swatch_weight_g / (spec.swatch_stitches * spec.swatch_rows)
    meters_per_g = spec.ball_length_m / spec.ball_weight_g if spec else gauge.meters_per_100g / 100
    waste = spec.waste_percent / 100 if spec else 0.1
    color_stitches: dict[str, int] = {}
    for part in parts:
        for rd in _part_rounds(part):
            color = rd.get("color") or part.get("color")
            if not color or color in ("skin", "body"):
                skin = color == "skin" or (not color and _part_name(part) in _SKIN_PARTS)
                color = "肤色（待选色）" if skin else "主体色（待选色）"
            color_stitches[color] = color_stitches.get(color, 0) + _round_stitches(rd) * _part_quantity(part)
    rows: list[dict[str, Any]] = []
    for color, stitches in sorted(color_stitches.items(), key=lambda pair: -pair[1]):
        grams = stitches * per_stitch * (1 + waste)
        meters = grams * meters_per_g
        code = brand_code(color)
        item = f"毛线 · {color}" + (f"（{code}）" if code else "")
        balls = math.ceil(grams / spec.ball_weight_g) if spec else None
        quantity = f"约 {grams:.1f}g（≈{meters:.1f}m）"
        if balls is not None and spec is not None:
            quantity += f"，购买 {balls} 团（每团 {spec.ball_weight_g:g}g）"
        rows.append({"item": item, "quantity": quantity, "color": color,
                     "stitches": stitches, "grams": round(grams, 2),
                     "meters": round(meters, 2), "balls": balls})
    summary = {"total_stitches": sum(color_stitches.values()),
               "grams": round(sum(row["grams"] for row in rows), 2),
               "meters": round(sum(row["meters"] for row in rows), 2),
               "balls": sum(row["balls"] for row in rows) if spec else None,
               "waste_percent": round(waste * 100, 2),
               "basis": "measured_swatch" if spec and spec.swatch_weight_g else "heuristic",
               "note": "小计已含下列逐色毛线，请勿重复购买；试片与线标适用于所有颜色"}
    return rows, summary


def _materials(parts: list[dict[str, Any]], part_names: set,
                gauge: Gauge = DEFAULT_GAUGE, yarn_spec: dict | None = None) -> list[dict[str, Any]]:
    """One purchasable yarn list, followed by accessories. No duplicate group totals."""
    materials, _ = yarn_requirements(parts, gauge, yarn_spec)
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


def material_summary_text(params: dict) -> str:
    summary = params.get("material_summary")
    if not isinstance(summary, dict) or not summary:
        return ""
    basis = "实测试片" if summary.get("basis") == "measured_swatch" else "经验估算，未经校准"
    return (f"毛线小计：{summary.get('grams')}g / {summary.get('meters')}m；"
            f"含 {summary.get('waste_percent')}% 预留，依据：{basis}。"
            "小计已含下列逐色毛线，请勿重复购买；线标与试片适用于所有颜色。")
