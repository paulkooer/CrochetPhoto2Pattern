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
from typing import Dict, Optional


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
    def grams_per_stitch(self) -> float:
        """单针克重按织物面积相对默认粗线规格缩放。"""
        base = 0.08  # 默认规格（0.785×0.625cm²）的单针克重
        base_area = 0.785 * 0.625
        return base * (self.stitch_w_cm * self.row_h_cm) / base_area


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


def gauge_from_ui(preset: str, stitches: Optional[float],
                  rows: Optional[float]) -> Gauge:
    """侧栏输入 → Gauge；custom 时用数字输入，异常值回退默认。"""
    if preset in PRESETS and preset != "custom":
        return PRESETS[preset]
    if not stitches or not rows:
        return DEFAULT  # custom 但没填数 → 默认
    try:
        st = max(6.0, min(40.0, float(stitches)))
        rw = max(8.0, min(50.0, float(rows)))
        return Gauge(st, rw)
    except (TypeError, ValueError):
        return DEFAULT


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
