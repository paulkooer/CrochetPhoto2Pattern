"""Place ribbed-band buttonholes on an explicitly ordered perimeter."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.models.attached_ribbing import (
    RibbingMethod,
    RibbingProposal,
    RibbingRecipe,
    RibbingTarget,
    append_attached_ribbing,
    propose_ribbing,
)
from app.models.working_path import WorkingPath


class ButtonBandTarget(RibbingTarget):
    first_front_sites: Annotated[int, Field(strict=True, ge=1, le=1000)]
    buttonhole_positions_cm: list[Annotated[float, Field(gt=0, le=1000)]] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def ordered_positions(self) -> ButtonBandTarget:
        if self.first_front_sites > self.base_sites:
            raise ValueError("第一侧前襟的基底范围超过整条工作边")
        if self.buttonhole_positions_cm != sorted(set(self.buttonhole_positions_cm)):
            raise ValueError("扣眼位置须从工作路径起点起递增且不重复")
        return self


@dataclass(frozen=True)
class ButtonBandProposal:
    status: Literal["needs_gauge", "unsupported", "design_candidate"]
    target: ButtonBandTarget
    ribbing: RibbingProposal
    hole_rows: tuple[int, ...]
    opposing_button_rows: tuple[int, ...]
    estimated_hole_positions_cm: tuple[float, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"status": self.status, "target": self.target.model_dump(),
                "ribbing": self.ribbing.to_dict(), "hole_rows": self.hole_rows,
                "opposing_button_rows": self.opposing_button_rows,
                "estimated_hole_positions_cm": self.estimated_hole_positions_cm,
                "reasons": self.reasons, "physical_execution_verified": False, "fit_verified": False}


def propose_button_band(target: ButtonBandTarget) -> ButtonBandProposal:
    target = ButtonBandTarget.model_validate(target.model_dump())
    rib = propose_ribbing(RibbingTarget.model_validate(target.model_dump(
        exclude={"first_front_sites", "buttonhole_positions_cm"})))

    def blocked(status, reason):
        return ButtonBandProposal(status, target, rib, (), (), (), (reason,))

    if rib.layout is None:
        return blocked(rib.status, "门襟未生成：" + "；".join(rib.reasons))
    gr = target.rib_rows_per_10cm
    assert gr is not None
    # Positions refer to nominal row centres, measured along the band from its
    # first end. They are not measurements of curved or stretched fabric.
    rows = tuple(2 * math.floor((position * gr / 10 - .5) / 2 + .5) + 1
                 for position in target.buttonhole_positions_cm)
    if (rows[0] < 3 or rows[-1] >= rib.layout.rows
            or any(b-a < 4 for a, b in zip(rows, rows[1:], strict=False))):
        return blocked("unsupported", "扣眼量化后过近、处于首行或超出门襟；不会静默合并或移动扣眼。")
    covered, ends = 0, []
    for take in rib.layout.attachments():
        covered += take
        ends.append(covered)
    if any(ends[(row - 1) // 2] > target.first_front_sites for row in rows):
        return blocked("unsupported", "扣眼已越过第一侧前襟，落入领口或另一侧；须调整设计位置。")
    return ButtonBandProposal(
        "design_candidate", target, rib, rows, tuple(rib.layout.rows+1-row for row in rows),
        tuple((row-.5)*10/gr for row in rows),
        ("扣眼只放在第一侧返回基底的行；对应纽扣行号按两端距离镜像给出，须实物别针对齐。",
         "扣眼锁针数由做法指定，未用引拔针密度估算可容纳的纽扣直径。"),
    )


def design_button_band(plan: WorkingPath, method: RibbingMethod,
                       target: ButtonBandTarget) -> tuple[ButtonBandProposal, WorkingPath | None]:
    method = RibbingMethod.model_validate(method.model_dump())
    if method.buttonhole_rows:
        raise ValueError("按尺寸设计扣眼时，不再同时输入固定扣眼行号")
    proposal = propose_button_band(target)
    if proposal.status != "design_candidate":
        return proposal, None
    assert proposal.ribbing.layout is not None
    if method.buttonhole_chains >= proposal.ribbing.layout.width_stitches:
        return ButtonBandProposal(
            "unsupported", target, proposal.ribbing, (), (), (),
            ("门襟宽度不足：扣眼须留出至少一个普通肋纹针位，未生成扣眼工序。",)), None
    recipe = RibbingRecipe(**(method.model_dump() | {"buttonhole_rows": list(proposal.hole_rows)}),
                           layout=proposal.ribbing.layout)
    generated = append_attached_ribbing(plan, recipe)
    assert target.gauge_basis is not None
    gauge = next(g for g in generated.gauges if g.id == f"{method.prefix}_gauge")
    gauge.basis = target.gauge_basis
    gauge.stitches_per_10cm = target.rib_stitches_per_10cm
    gauge.rows_per_10cm = target.rib_rows_per_10cm
    generated.review_notes.append(
        f"目标扣眼位置{target.buttonhole_positions_cm}cm；量化行号{proposal.hole_rows}；"
        f"行中心线性估计{proposal.estimated_hole_positions_cm}cm；"
        f"另一侧纽扣候选行号{proposal.opposing_button_rows}，须实物核对。")
    generated.review_notes.extend(proposal.reasons)
    return proposal, WorkingPath.model_validate(generated.model_dump())
