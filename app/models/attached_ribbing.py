"""Design an attached ribbing strip, then lower it to explicit working paths.

The attachment policy is deliberately narrow: one or two consecutive base
sites on each return to the base. Dimensions are linear swatch estimates;
neither this policy nor the resulting fabric has been physically validated.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.models.working_path import (
    ChainBridge,
    ConstructionGauge,
    FoundationChain,
    FreeLoops,
    Hold,
    Identifier,
    Operation,
    PathModel,
    Route,
    Span,
    Work,
    WorkingPath,
    compile_working_path,
)

Positive = Annotated[float, Field(gt=0, le=1000)]


class RibbingLayout(PathModel):
    base_sites: Annotated[int, Field(strict=True, ge=1, le=1000)]
    width_stitches: Annotated[int, Field(strict=True, ge=1, le=40)]
    rows: Annotated[int, Field(strict=True, ge=2, le=200)]

    @model_validator(mode="after")
    def supported_attachment_rate(self) -> RibbingLayout:
        if self.rows % 2:
            raise ValueError("本模块以往返两行为一组，须给出偶数行")
        if not self.rows // 2 <= self.base_sites <= self.rows:
            raise ValueError("每次回到基底只支持接合1或2位；当前行数与基底数量不相容")
        return self

    def attachments(self) -> tuple[int, ...]:
        """Evenly distribute attachment counts with an integer error bound <1."""
        pairs = self.rows // 2
        cumulative = [(index * self.base_sites + pairs - 1) // pairs for index in range(pairs + 1)]
        return tuple(b - a for a, b in zip(cumulative, cumulative[1:], strict=False))


class RibbingTarget(PathModel):
    base_sites: Annotated[int, Field(strict=True, ge=1, le=1000)]
    edge_length_cm: Positive
    width_cm: Positive
    rib_rows_per_10cm: Positive | None = None
    rib_stitches_per_10cm: Positive | None = None
    gauge_basis: Literal["user_entered_swatch", "hypothetical"] | None = None

    @model_validator(mode="after")
    def identify_gauge_basis(self) -> RibbingTarget:
        if (self.rib_rows_per_10cm is not None or self.rib_stitches_per_10cm is not None
                ) and self.gauge_basis is None:
            raise ValueError("输入肋纹密度时须说明来自用户小样还是假设值")
        return self


@dataclass(frozen=True)
class RibbingProposal:
    status: Literal["needs_gauge", "unsupported", "design_candidate"]
    target: RibbingTarget
    layout: RibbingLayout | None
    reasons: tuple[str, ...]
    estimated_length_cm: float | None = None
    estimated_width_cm: float | None = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["target"] = self.target.model_dump()
        result["layout"] = None if self.layout is None else self.layout.model_dump()
        result["physical_execution_verified"] = False
        result["fit_verified"] = False
        result["dimension_basis"] = "linear_swatch_estimate_only"
        return result


def propose_ribbing(target: RibbingTarget) -> RibbingProposal:
    target = RibbingTarget.model_validate(target.model_dump())
    if target.rib_rows_per_10cm is None or target.rib_stitches_per_10cm is None:
        return RibbingProposal("needs_gauge", target, None,
                               ("缺少此种肋纹的行密度或针密度，不能套用衣身短针密度。",))
    rows = 2 * math.floor(target.edge_length_cm * target.rib_rows_per_10cm / 20 + .5)
    width = math.floor(target.width_cm * target.rib_stitches_per_10cm / 10 + .5)
    try:
        layout = RibbingLayout(base_sites=target.base_sites, width_stitches=width, rows=rows)
    except ValueError:
        return RibbingProposal("unsupported", target, None, (
            f"尺寸换算得到{rows}行、{width}针宽；超出本模块的偶数行、1–40针宽、"
            "最多200行或每次接合1–2位的范围。没有静默改成另一密度或另一行数。",
        ))
    return RibbingProposal(
        "design_candidate", target, layout,
        ("接合均匀分配是本模块的设计选择；尺寸仅按输入小样线性换算，未验证弹性、转角或合身。",),
        estimated_length_cm=rows * 10 / target.rib_rows_per_10cm,
        estimated_width_cm=width * 10 / target.rib_stitches_per_10cm,
    )


class RibbingMethod(PathModel):
    prefix: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
    title: str = Field(min_length=1, max_length=120)
    base_edge: Identifier
    current_loop: Span
    stitch: Literal["sc", "slst"]
    foundation_face: Literal["underside", "back_loop"]
    foundation_turn: Literal["none", "clockwise", "counterclockwise"]
    hook_mm: Annotated[float, Field(gt=0, le=20)]
    start_side: Literal["RS", "WS"]
    outer_edge_both: bool = False
    outer_turning_chain: Annotated[int, Field(strict=True, ge=0, le=1)] = 0
    keep_start_loops: bool = False
    buttonhole_rows: list[Annotated[int, Field(strict=True, ge=3, le=199)]] = Field(
        default_factory=list, max_length=20)
    buttonhole_chains: Annotated[int, Field(strict=True, ge=1, le=20)] = 2
    design_basis: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def explicit_seam_preparation(self) -> RibbingMethod:
        if self.keep_start_loops and self.outer_edge_both:
            raise ValueError("外缘挑双半针时不能声称整条首行前半针均为接缝保留")
        if self.buttonhole_rows:
            if self.stitch != "slst" or self.outer_edge_both:
                raise ValueError("本版扣眼须为全部BLO的引拔肋纹")
            if self.buttonhole_rows != sorted(set(self.buttonhole_rows)) or any(
                    not row % 2 for row in self.buttonhole_rows):
                raise ValueError("扣眼行须递增、不重复，并位于返回基底的奇数行")
        return self


class RibbingRecipe(RibbingMethod):
    layout: RibbingLayout

    @model_validator(mode="after")
    def holes_fit_strip(self) -> RibbingRecipe:
        if self.buttonhole_rows and (self.buttonhole_rows[-1] >= self.layout.rows
                                    or self.buttonhole_chains >= self.layout.width_stitches):
            raise ValueError("扣眼须留出后续一行以及至少一个普通肋纹针位")
        return self


def design_attached_ribbing(plan: WorkingPath, method: RibbingMethod,
                           target: RibbingTarget) -> tuple[RibbingProposal, WorkingPath | None]:
    """Convert dimensional inputs into a recipe, without hand-entered row counts."""
    method = RibbingMethod.model_validate(method.model_dump())
    proposal = propose_ribbing(target)
    if proposal.layout is None:
        return proposal, None
    recipe = RibbingRecipe(**method.model_dump(), layout=proposal.layout)
    generated = append_attached_ribbing(plan, recipe)
    target = proposal.target
    assert target.gauge_basis is not None
    gauge = next(g for g in generated.gauges if g.id == f"{method.prefix}_gauge")
    gauge.basis = target.gauge_basis
    gauge.stitches_per_10cm = target.rib_stitches_per_10cm
    gauge.rows_per_10cm = target.rib_rows_per_10cm
    generated.review_notes.append(
        f"{method.title}：输入目标边长{target.edge_length_cm:g}cm、肋纹宽{target.width_cm:g}cm；"
        f"肋纹密度{target.rib_stitches_per_10cm:g}针/{target.rib_rows_per_10cm:g}行每10cm，"
        f"来源{target.gauge_basis}。整数量化后{proposal.layout.rows}行、"
        f"{proposal.layout.width_stitches}针宽；线性估算{proposal.estimated_length_cm:g}cm × "
        f"{proposal.estimated_width_cm:g}cm，非实测成品尺寸。")
    return proposal, WorkingPath.model_validate(generated.model_dump())


def append_attached_ribbing(plan: WorkingPath, recipe: RibbingRecipe) -> WorkingPath:
    """Consume a whole, ordered final edge; preserve all other declared edges.

    The caller supplies the attachment order and current yarn loop. Skipped
    corners remain separately declared in the prefix; this function never
    retires sites to force a pass, closes a seam, or guesses physical orientation.
    """
    plan = WorkingPath.model_validate(plan.model_dump())
    recipe = RibbingRecipe.model_validate(recipe.model_dump())
    before = compile_working_path(plan)
    base = before.final_edges.get(recipe.base_edge)
    if base is None or len(base) != recipe.layout.base_sites:
        raise ValueError("基底须是一条完整的最终保留边，且数量与设计一致；部分边请先明确分段")
    prefix, width = recipe.prefix, recipe.layout.width_stitches
    chain, outside, gauge_id = f"{prefix}_chain", f"{prefix}_outside", f"{prefix}_gauge"
    other_face: Literal["top", "front_loop"] = (
        "top" if recipe.foundation_face == "underside" else "front_loop")
    plan.steps.append(FoundationChain(
        id=chain, label="沿边肋纹起链", chains=width + 1,
        work_face=recipe.foundation_face, other_face=other_face,
        anchor=recipe.current_loop, anchor_mode="continues_loop",
        turn_after_chain=recipe.foundation_turn,
        note="接续当前工作环，不把起链计作额外使用一个基底针目。",
    ))
    plan.gauges.append(ConstructionGauge(id=gauge_id, method="沿边肋纹：" + recipe.stitch,
                                        hook_mm=recipe.hook_mm, basis="unmeasured"))
    # Layout may be count-based or based on externally entered swatches. Do not
    # turn either provenance into a fabricated measured ConstructionGauge.
    cursor = 1
    attachments = recipe.layout.attachments()
    for number in range(1, recipe.layout.rows + 1):
        identifier = f"{prefix}_{number:03d}"
        previous = f"{prefix}_{number-1:03d}"
        operations: list[Operation]
        if number in recipe.buttonhole_rows:
            hole = recipe.buttonhole_chains
            operations = [
                Work(source=Span(edge=previous, first=hole+1, last=width, direction="reverse"),
                     stitch="slst", loop="back"),
                ChainBridge(id=f"{prefix}_hole_{number:03d}", count=hole, route_face="top",
                            placement="buttonhole",
                            skipped=Span(edge=previous, first=1, last=hole, direction="reverse")),
            ]
        elif number == 1:
            operations = [Work(source=Span(edge=chain, first=1, last=width, face=recipe.foundation_face),
                               stitch=recipe.stitch)]
        elif not recipe.outer_edge_both:
            operations = [Work(source=Span(edge=previous, first=1, last=width, direction="reverse"),
                               stitch=recipe.stitch, loop="back")]
        else:
            operations = []
            if number % 2:
                operations.append(Work(source=Span(edge=previous, first=width, last=width),
                                       stitch=recipe.stitch))
            if width > 1:
                operations.append(Work(
                    source=Span(edge=previous, first=1 if number % 2 else 2,
                                last=width - 1 if number % 2 else width, direction="reverse"),
                    stitch=recipe.stitch, loop="back"))
            if not number % 2:
                operations.append(Work(source=Span(edge=previous, first=1, last=1), stitch=recipe.stitch))
        if number % 2:
            take = attachments[(number - 1) // 2]
            operations.append(Work(source=Span(edge=recipe.base_edge, first=cursor, last=cursor + take - 1),
                                   stitch="slst", disposition="binding"))
            cursor += take
        side: Literal["RS", "WS"] = recipe.start_side
        if not number % 2:
            side = "WS" if side == "RS" else "RS"
        last_row = number == recipe.layout.rows
        plan.steps.append(Route(
            id=identifier, label=f"沿边肋纹 第 {number} 行", section=prefix, row_number=number,
            mode="flat", row_direction="forward" if side == "RS" else "reverse", side=side,
            operations=operations, expected_sites=width,
            turn="none" if last_row else "counterclockwise",
            turning_chains=recipe.outer_turning_chain if not number % 2 and not last_row else 0,
            gauge=gauge_id,
        ))
    plan.steps.append(Hold(id=outside, label="起链未用侧保留，后续用途未自动决定",
                           spans=[Span(edge=chain, first=1, last=width, face=other_face)]))
    plan.final_edges = [edge for edge in plan.final_edges if edge != recipe.base_edge]
    plan.final_edges += [f"{prefix}_{recipe.layout.rows:03d}", outside]
    if recipe.keep_start_loops:
        start = f"{prefix}_start_loops"
        plan.steps.append(FreeLoops(id=start, label="首行前半针保留，接缝方向另行决定",
                                   source=Span(edge=f"{prefix}_001", first=1, last=width), loop="front"))
        plan.final_edges.append(start)
    plan.title = recipe.title
    plan.review_notes = list(dict.fromkeys([*plan.review_notes, recipe.design_basis,
        "本段由参数生成，基底每次接合1或2位；未自动收掉剩余边，也未自动闭合两端。"
        "接缝朝向、转角、密度及尺寸仍需核实，不等于从照片恢复工艺或实体通过。"]))
    compile_working_path(plan)
    return plan
