"""Gauge（小样密度）—— 全系统针法几何的单一事实来源。

为什么需要：此前 params 层与 grid 层各有一套隐含几何且互相矛盾
（params：针宽 0.785cm×行高 0.625cm → w/h=1.26；grid：sc w/h=0.75，
差 1.68×）。短针物理上高>宽（外部实务数据 w/h≈0.67–0.83），且
"36 针=9cm 头"隐含 12.7 针/10cm = 特粗线规格，与材料表"2.5mm+中细"
标签冲突（fable5 第三轮审核 #3/校准预判，已联网+本地复核坐实）。

解法：密度一律由"10cm 小样针数×行数"推导（真实图解的通行做法：
先钩小样再对照图解）；两个旧口径成为两种合法 preset——经典图解
（粗线，36 针≈9cm 头，保持默认行为不变）与紧密玩偶规格（2.5mm+中细）。
钩针/线材标签按 gauge 推导，不再写死。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

BASE_GRAMS_PER_STITCH = 0.08
BASE_STITCH_AREA_CM2 = 0.785 * 0.625


@dataclass(frozen=True)
class Gauge:
    stitches_per_10cm: float  # 10cm 宽度内的短针数
    rows_per_10cm: float      # 10cm 高度内的行/圈数

    @property
    def stitch_w_cm(self) -> float:
        return 10.0 / self.stitches_per_10cm

    @property
    def row_h_cm(self) -> float:
        return 10.0 / self.rows_per_10cm

    @property
    def aspect_wh(self) -> float:
        """针宽/行高——grid 层比例补偿与 params 层共用此值。"""
        return self.stitch_w_cm / self.row_h_cm

    @property
    def stitches_per_cm_diameter(self) -> float:
        """针数 / 直径 cm（历史 STITCHES_PER_CM 口径：π/针宽）。"""
        import math
        return math.pi / self.stitch_w_cm

    def stitches_for_diameter(self, diameter_cm: float) -> int:
        """直径 → 6 的倍数针数（半步向上取整，避免银行家舍入）。"""
        import math
        raw_groups = math.pi * diameter_cm / self.stitch_w_cm / 6
        return max(6, int(raw_groups + 0.5) * 6)

    def rounds_for_height(self, height_cm: float) -> int:
        """高度 → 圈数（行高是纱线属性，不随部件变——统一口径）。"""
        return max(1, int(height_cm / self.row_h_cm + 0.5))

    @property
    def shaping_continuous_delta(self) -> float:
        """Geometric circumference change represented by one row.

        For a locally 45° surface, radius changes by approximately one row
        height, so ``ΔN = 2π × row_height / stitch_width``.  This is a
        continuous value; published patterns in this project keep six-way
        symmetry and therefore need a separate six-stitch quantization.
        """
        import math
        return 2.0 * math.pi * self.row_h_cm / self.stitch_w_cm

    @property
    def max_shaping_change(self) -> int:
        """Six-way upper quantization of :attr:`shaping_continuous_delta`.

        Ceiling is intentional: alternating +6/+12 rounds can approximate a
        continuous rate near 8 while preserving six-sector stitch notation.
        Classic's 5.1 remains +6; DK/fine's 7.6–7.9 permit up to +12.
        """
        import math
        groups = math.ceil((self.shaping_continuous_delta - 1e-9) / 6.0)
        return max(6, groups * 6)

    @property
    def hook_yarn_label(self) -> str:
        """按针宽推导钩针/线材标签（替代写死的"2.5mm+中细"）。"""
        w = self.stitch_w_cm
        if w < 0.52:
            return "2.0–2.5mm 钩针 + 中细/4股棉线"
        if w < 0.6:
            return "2.5–3.5mm 钩针 + DK/中粗线"
        if w < 0.7:
            return "3.5–4mm 钩针 + 粗线"
        return "4–5mm 钩针 + 特粗/珊瑚绒线"

    @property
    def meters_per_100g(self) -> float:
        """按针宽分档的纱线米数估算（V6 署名纠正）。

        如实声明：sport≈320、DK≈250、worsted≈200、chunky≈140 是**实务
        经验估算值**，不是任何标准机构的数据——CYC Standard Yarn Weight
        System 只规定密度与针号区间，**不含 m/100g**（曾经核实并误署名
        给 CYC，Opus 5 审查指出）。且同档不同纤维差异大（丝光棉明显短于
        羊毛）。数值用于材料清单的量级参考，购买请以实际线标为准。
        """
        w = self.stitch_w_cm
        if w < 0.52:
            return 320.0
        if w < 0.6:
            return 250.0
        if w < 0.7:
            return 200.0
        return 140.0

    @property
    def grams_per_stitch(self) -> float:
        """单针克重按织物面积相对默认粗线规格缩放。"""
        return (
            BASE_GRAMS_PER_STITCH
            * (self.stitch_w_cm * self.row_h_cm)
            / BASE_STITCH_AREA_CM2
        )


def next_shaping_stitch_count(current: int, target: int,
                              max_change: int) -> int:
    """Move one feasible six-sector round from ``current`` toward ``target``.

    Besides the gauge-derived cap, increases cannot exceed the number of
    source stitches (one V per source stitch) and decreases cannot exceed half
    the source stitches (one A consumes two).  Both endpoints must stay in the
    project's six-stitch topology.
    """
    if current < 6 or target < 6 or current % 6 or target % 6:
        raise ValueError("current and target must be positive multiples of 6")
    if current == target:
        return current
    cap = max(6, int(max_change) // 6 * 6)
    distance = abs(target - current)
    if target > current:
        feasible = current  # every source stitch may be increased once
        change = min(distance, cap, feasible)
        return current + max(6, change // 6 * 6)
    feasible = (current // 2) // 6 * 6  # A consumes two source stitches
    change = min(distance, cap, feasible)
    return current - max(6, change // 6 * 6)


# 预设：默认保持既有行为（经典图解锚点 36 针≈9cm 头）
# 短针高>宽（w/h≈0.67–0.83，外部实务）⇒ 针数/10cm > 行数/10cm。
# classic 是已发布图解的隐含几何（w/h≈1.23，超物理区间）——保留作默认
# 以维持 36针=9cm头 的经典锚点，属"图解惯例 vs 物理"的已知取舍。
PRESETS: Dict[str, Gauge] = {
    "classic": Gauge(13.0, 16.0),   # 经典图解（粗线）：w 0.77 × h 0.63（w/h 1.23）
    "dk":      Gauge(17.0, 14.0),   # DK 中粗（≈3mm）：w 0.59 × h 0.71（w/h 0.82）
    "fine":    Gauge(20.0, 16.0),   # 紧密玩偶（2.5mm+中细）：w 0.50 × h 0.63（w/h 0.79）
}

DEFAULT = PRESETS["classic"]


def gauge_from_mapping(raw: Optional[Mapping[str, Any]]) -> Gauge:
    """Deserialize a gauge payload with the same bounds as the UI.

    Generated results, JSON edits, imports and validation all pass through
    this function so an invalid payload cannot create a different geometry in
    each consumer.  Missing or malformed legacy payloads use classic gauge.
    """
    data = raw or {}
    try:
        stitches = max(6.0, min(40.0, float(data["stitches_per_10cm"])))
        rows = max(8.0, min(50.0, float(data["rows_per_10cm"])))
        return Gauge(stitches, rows)
    except (KeyError, TypeError, ValueError):
        return DEFAULT


def gauge_from_ui(preset: str, stitches: Optional[float],
                  rows: Optional[float]) -> Gauge:
    """侧栏输入 → Gauge；custom 时用数字输入，异常值回退默认。"""
    if preset in PRESETS and preset != "custom":
        return PRESETS[preset]
    if not stitches or not rows:
        return DEFAULT  # custom 但没填数 → 默认
    return gauge_from_mapping({
        "stitches_per_10cm": stitches,
        "rows_per_10cm": rows,
    })


@dataclass(frozen=True)
class ShapingStyle:
    """塑形风格（侧栏可调，模型层透传）。

    - sphere_mode: 头部球体生成方式。ladder=经典阶梯球（发布图解通行做法，
      默认）；ideal=理想球（逐圈针数 ∝ sinθ，mspremiseconclusion 2010，
      布料量分布更接近真球）；egg=蛋形（下半提前收窄的 sin 变体，玩偶头
      主流形状；安全眼定位取最大围下一两圈）。
    - one_piece: 头身一体钩（头收针到颈围不断线直接钩身体，免缝合更牢固）。
    - skirt_style: ring=独立裙筒（腰部环起）；attached=挑后半针法（身体腰圈
      只挑前半针，裙子直接钩在预留后半针上——发布图解更常见的做法）。
    - ruffle_hem: 波浪裙摆（裙末圈每针放 2 针）。
    """

    sphere_mode: str = "ladder"
    one_piece: bool = False
    skirt_style: str = "ring"
    ruffle_hem: bool = False

    def __post_init__(self) -> None:
        if self.sphere_mode not in ("ladder", "ideal", "egg"):
            object.__setattr__(self, "sphere_mode", "ladder")
        if self.skirt_style not in ("ring", "attached"):
            object.__setattr__(self, "skirt_style", "ring")


DEFAULT_STYLE = ShapingStyle()
