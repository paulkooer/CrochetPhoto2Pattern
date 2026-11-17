"""Original parametric recipes built from explicit SC stitch inventories.

Geometric dimensions select candidate counts; they do not establish fabric fit.
"""
from __future__ import annotations

import math
from typing import Literal

from app.models.gauge import Gauge

from .models import Component, Foundation, WorkStep


def expression_for_change(before: int, after: int) -> str:
    """Distribute only X/V/A, consuming each available stitch exactly once."""
    if before == after:
        return f"{before}X"
    change = abs(after - before)
    plain = before - change if after > before else before - 2 * change
    if plain < 0:
        raise ValueError("该过渡需要额外桥接圈")
    base, extra = divmod(plain, change)
    symbol = "V" if after > before else "A"
    groups = []
    for width, repeats in ((base, change - extra), (base + 1, extra)):
        if repeats:
            body = f"{width}X,{symbol}" if width else symbol
            groups.append(f"({body})×{repeats}" if repeats > 1 else body)
    return ",".join(groups)


class RoundBuilder:
    def __init__(self, gauge: Gauge, first: int = 6):
        self.gauge = gauge
        self.steps = [WorkStep(number=1, section="起针", expression=f"{first}X", stitches=first)]

    @property
    def current(self) -> int:
        return self.steps[-1].stitches

    def step(self, target: int, section: str, *, note: str = "",
             loops: Literal["both", "front", "back"] = "both") -> None:
        if not 1 <= target <= 1000:
            raise ValueError("部件围度超出可生成范围")
        while True:
            before = self.current
            cap = min(self.gauge.max_shaping_change,
                      before if target > before else before // 2)
            after = (before + min(target - before, cap) if target >= before
                     else before - min(before - target, cap))
            if after == before and target != before:
                raise ValueError("针目不足以继续加减针")
            self.steps.append(WorkStep(
                number=len(self.steps) + 1, section=section,
                expression=expression_for_change(before, after), stitches=after,
                loops=loops, note=note if after == target else "过渡圈，完成后继续本段",
            ))
            if after == target:
                break

    def hold(self, rows: int, section: str, *, loops: Literal["both", "front", "back"] = "both") -> None:
        for _ in range(max(0, rows)):
            self.step(self.current, section, loops=loops)


def circular(id: str, name: str, role: str, builder: RoundBuilder, *, color: str,
             quantity: int = 1, finish: str, fitting: list[str] | None = None,
             foundation: Foundation | None = None) -> Component:
    return Component(id=id, name=name, role=role, quantity=quantity, work="rounds",
                     foundation=foundation or Foundation(kind="magic_ring"),
                     steps=builder.steps, finish=finish, fitting=fitting or [], color=color)


def panel(id: str, name: str, role: str, width: int, rows: int, *, color: str,
          quantity: int = 1, loops: Literal["both", "front", "back"] = "both",
          finish: str = "断线留缝合线，不填充") -> Component:
    if width < 1 or rows < 1 or rows > 600:
        raise ValueError("片钩尺寸超出范围")
    return Component(
        id=id, name=name, role=role, quantity=quantity, work="rows",
        foundation=Foundation(kind="flat_chain", chains=width + 1), color=color,
        steps=[WorkStep(number=i, section=role, expression=f"{width}X", stitches=width,
                        turning_chain=int(i > 1), loops=loops)
               for i in range(1, rows + 1)], finish=finish,
    )


def strand(id: str, name: str, chains: int, quantity: int, *, curled: bool, color: str) -> Component:
    count = chains - 1
    return Component(
        id=id, name=name, role="发束", quantity=quantity, work="rows",
        foundation=Foundation(kind="flat_chain", chains=chains), color=color,
        steps=[WorkStep(number=1, section="卷发回钩" if curled else "直发回钩",
                        expression=f"V×{count}" if curled else f"{count}X",
                        stitches=count * (2 if curled else 1))],
        finish="断线，两端留线头；发束逐根缝到发帽，勿把每根拉成相同直线长度",
        fitting=["先做 1 根检查垂长与卷曲程度；锁针数不等于成品发长，确认后再做其余发束"],
    )


def count_for_diameter(diameter: float, gauge: Gauge, minimum: int = 4) -> int:
    return max(minimum, int(math.pi * diameter / gauge.stitch_w_cm + 0.5))


def open_cap(id: str, name: str, rim: int, depth_rows: int, gauge: Gauge, *, color: str,
             role: str = "帽身") -> Component:
    builder = RoundBuilder(gauge)
    while builder.current < rim:
        builder.step(min(rim, builder.current + 6), "帽顶")
    builder.hold(depth_rows, role)
    return circular(id, name, role, builder, color=color,
                    finish="帽口不收口，不填棉；断线留线头，先试戴后固定",
                    fitting=["试戴时须包含头发/发帽的厚度，过紧应改设计并重做该部件"])


def brim_cap(rim: int, depth_rows: int, brim_rows: int, gauge: Gauge, *, color: str) -> Component:
    cap = open_cap("hat", "宽檐帽", rim, depth_rows, gauge, color=color)
    builder = RoundBuilder(gauge)
    builder.steps = cap.steps[:]
    for i in range(brim_rows):
        builder.step(builder.current + 6, "帽檐", loops="front" if i == 0 else "both",
                     note="从帽身转入帽檐；帽檐平整程度须试钩" if i == 0 else "")
    return circular("hat", "宽檐帽", "帽身与帽檐", builder, color=color,
                    finish="帽檐不收口、不填棉，断线藏头；先试戴再选择是否缝合固定",
                    fitting=["帽檐采用每圈加 6 针的候选节奏；起伏或塌软须根据实际线材调整，未验证平整度"])


def segmented_arm(length_cm: float, palm: int, wrist: int, upper: int, gauge: Gauge) -> Component:
    if palm <= wrist:
        raise ValueError("当前尺寸和密度下，手掌与手腕被量化成相同针数；请加大掌腕差异或提高密度")
    builder = RoundBuilder(gauge, first=4)
    builder.step(palm, "手掌")
    builder.hold(1, "手掌")
    builder.step(wrist, "手腕")
    builder.hold(1, "手腕")
    builder.step(upper, "前臂")
    builder.hold(max(2, round(length_cm / gauge.row_h_cm) - len(builder.steps)), "前臂")
    return circular("arms", "手掌与手臂", "掌—腕—前臂分段", builder, quantity=2, color="肤色",
                    finish="手掌少量填棉，手腕少填；肩端留口与长线头，用于连接身体",
                    fitting=["手掌为无分指轮廓，尚无拇指或独立手指；先核对掌宽、腕宽及袖口能否穿过"])


def leg(length_cm: float, circumference: int, gauge: Gauge) -> Component:
    builder = RoundBuilder(gauge)
    builder.step(circumference, "腿部围度")
    builder.hold(max(2, round(length_cm / gauge.row_h_cm)), "腿部")
    return circular("legs", "腿部", "独立腿段", builder, quantity=2, color="肤色/袜色",
                    finish="下端为闭合起底，上端留口；适量填棉，留线用于连接身体")


def oval_boot(length_cm: float, width_cm: float, leg_stitches: int, gauge: Gauge) -> Component:
    chains = max(3, round((length_cm - width_cm) / gauge.stitch_w_cm) + 3)
    straight = chains - 3
    rounds = max(2, round(width_cm / (2 * gauge.row_h_cm)))
    middle = f",{straight}X" if straight else ""
    steps = [WorkStep(number=1, section="鞋底", expression=f"W{middle},W{middle}",
                      stitches=2 * chains,
                      note="两端各在同一锁针钩 3 短针，中段沿锁针两侧分别钩；不可扭转")]
    for row in range(2, rounds + 1):
        end = "V×3" if row == 2 else f"({row - 2}X,V)×3"
        steps.append(WorkStep(number=len(steps) + 1, section="鞋底",
                              expression=f"{end}{middle},{end}{middle}",
                              stitches=steps[-1].stitches + 6))
    builder = RoundBuilder(gauge)
    builder.steps = steps
    builder.hold(1, "鞋底转鞋面", loops="back")
    builder.hold(1, "鞋面")
    toe, heel = rounds * 3, rounds * 3
    target = max(leg_stitches + 2, 2 * straight + 4)
    # Targeted toe decreases come before heel decreases: a foot is not another tube.
    for section in ("鞋头收窄", "鞋跟与鞋口"):
        while builder.current > target and (toe if section == "鞋头收窄" else heel) > 2:
            arc = toe if section == "鞋头收窄" else heel
            decrease = min(3, arc // 2, arc - 2, builder.current - target)
            if decrease < 1:
                break
            changed = expression_for_change(arc, arc - decrease)
            tail = f",{straight}X" if straight else ""
            expression = (f"{changed}{tail},{heel}X{tail}" if section == "鞋头收窄"
                          else f"{toe}X{tail},{changed}{tail}")
            builder.steps.append(WorkStep(number=len(builder.steps) + 1, section=section,
                                          expression=expression, stitches=builder.current - decrease,
                                          note="起圈点保持在鞋头弧段；不可把减针移到整个鞋口平均分配"))
            if section == "鞋头收窄":
                toe -= decrease
            else:
                heel -= decrease
    builder.hold(2, "鞋口/短靴筒")
    return circular("shoes", "椭圆底鞋靴", "鞋底—鞋头—鞋跟—鞋口", builder, quantity=2,
                    color="鞋色", foundation=Foundation(kind="oval_chain", chains=chains),
                    finish="鞋口保持开放，不把鞋底填成球；先试穿腿部，再少量填充鞋头并固定",
                    fitting=["在鞋底首圈标明鞋头与鞋跟；两只鞋采用相同标记方向，装配时左右对应",
                             "量鞋底长宽及鞋口围度；本方案是钩针鞋靴近似，不推断原作的鞋面材料"])


def skirt(id: str, name: str, waist: int, hem: int, rows: int, gauge: Gauge,
          *, color: str) -> Component:
    builder = RoundBuilder(gauge, first=waist)
    for i in range(1, rows):
        target = round(waist + (hem - waist) * i / max(1, rows - 1))
        builder.step(target, "裙身展开")
    return circular(id, name, "独立开放裙层", builder, color=color,
                    foundation=Foundation(kind="chain_ring", chains=waist),
                    finish="上下均留开口，不填棉；先套到未装配身体，再决定腰位固定方式",
                    fitting=["先做腰部起针环试套身体，锁针起环须避免过紧；未验证穿着余量"])
