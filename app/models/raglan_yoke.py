"""A bounded symmetric SC raglan candidate, not recovered source instructions.

Four panel boundaries receive one increase on each adjacent side (+8).
Shaping rounds are spread over the requested depth. Counts and linear gauge
estimates are explicit; neither drape nor neck/armhole fit is simulated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.models.working_path import (
    MAX_SITES,
    ChainBridge,
    ConstructionGauge,
    FoundationChain,
    Hold,
    NewYarn,
    Operation,
    PathModel,
    Route,
    Span,
    Step,
    Work,
    WorkingPath,
    compile_working_path,
)

Dimension = Annotated[float, Field(gt=0, le=100)]
Gauge = Annotated[float, Field(gt=0, le=100)]


class YokeTarget(PathModel):
    neck_edge_cm: Dimension
    body_span_cm: Dimension
    sleeve_circumference_cm: Dimension
    yoke_depth_cm: Dimension
    stitches_per_10cm: Gauge | None = None
    rows_per_10cm: Gauge | None = None
    gauge_basis: Literal["hypothetical", "reference_declared", "user_entered_swatch"] | None = None

    @model_validator(mode="after")
    def identify_measurements(self) -> YokeTarget:
        if ((self.stitches_per_10cm is not None or self.rows_per_10cm is not None)
                and self.gauge_basis is None):
            raise ValueError("短针密度须注明来源；目标衣身宽度不含门襟，不等于成衣胸围")
        return self


class YokeMethod(PathModel):
    prefix: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,19}$")]
    hook_mm: Annotated[float, Field(gt=0, le=20)]
    underarm_chains: Annotated[int, Field(strict=True, ge=3, le=15)] = 5
    stitch_adjustment: Annotated[int, Field(strict=True, ge=0, le=3)] = 1
    split_side: Literal["RS"] = "RS"

    @model_validator(mode="after")
    def centered_bridge(self) -> YokeMethod:
        if self.underarm_chains % 2 == 0:
            raise ValueError("本做法从桥的正中针开始挑袖，当前只支持奇数根腋下锁针")
        return self


class YokeLayout(PathModel):
    neck_stitches: Annotated[int, Field(strict=True, ge=8, le=300)]
    rows_to_split: Annotated[int, Field(strict=True, ge=3, le=80)]
    increase_rows: list[Annotated[int, Field(strict=True, ge=2, le=79)]]
    front_start: Annotated[int, Field(strict=True, ge=1, le=100)]
    sleeve_start: Annotated[int, Field(strict=True, ge=2, le=100)]
    back_start: Annotated[int, Field(strict=True, ge=2, le=100)]
    underarm_chains: Annotated[int, Field(strict=True, ge=3, le=15)]

    @model_validator(mode="after")
    def coherent_panels(self) -> YokeLayout:
        if not self.rows_to_split % 2:
            raise ValueError("此版本从正面分袖，含分袖行的领肩须为奇数行")
        if 2 * (self.front_start + self.sleeve_start) + self.back_start != self.neck_stitches:
            raise ValueError("领口五段之和不等于起针数")
        if self.increase_rows != sorted(set(self.increase_rows)) or not self.increase_rows:
            raise ValueError("加针行须递增、不重复，且至少有一行")
        if self.increase_rows[-1] >= self.rows_to_split:
            raise ValueError("分袖行不作本模块的插肩加针")
        if self.underarm_chains % 2 == 0:
            raise ValueError("腋下桥须有明确的中央针位")
        return self

    def panels_after(self, increases: int) -> tuple[int, int, int, int, int]:
        return (self.front_start + increases, self.sleeve_start + 2 * increases,
                self.back_start + 2 * increases, self.sleeve_start + 2 * increases,
                self.front_start + increases)

    @property
    def body_stitches(self) -> int:
        front, _, back, _, _ = self.panels_after(len(self.increase_rows))
        return 2 * front + back + 2 * self.underarm_chains

    @property
    def sleeve_stitches(self) -> int:
        return self.sleeve_start + 2 * len(self.increase_rows) + self.underarm_chains + 2


@dataclass(frozen=True)
class YokeProposal:
    status: Literal["needs_gauge", "unsupported", "design_candidate"]
    target: YokeTarget
    method: YokeMethod
    layout: YokeLayout | None
    reasons: tuple[str, ...]
    estimated_cm: dict[str, float]
    adjustment_stitches: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "status": self.status, "target": self.target.model_dump(), "method": self.method.model_dump(),
            "layout": None if self.layout is None else self.layout.model_dump(),
            "reasons": self.reasons, "estimated_cm": self.estimated_cm,
            "adjustment_stitches": self.adjustment_stitches,
            "physical_execution_verified": False, "fit_verified": False,
            "source_pattern_reconstruction": False,
            "depth_policy": "nearest_supported_odd_row_for_RS_split",
        }


def propose_yoke(target: YokeTarget, method: YokeMethod) -> YokeProposal:
    target = YokeTarget.model_validate(target.model_dump())
    method = YokeMethod.model_validate(method.model_dump())

    def blocked(status, reason):
        return YokeProposal(status, target, method, None, (reason,), {}, {})

    gs, gr = target.stitches_per_10cm, target.rows_per_10cm
    if gs is None or gr is None:
        return blocked("needs_gauge", "缺少短针针/行密度，不能从目标尺寸生成领肩。")
    neck = math.floor(target.neck_edge_cm * gs / 10 + .5)
    desired_rows = target.yoke_depth_cm * gr / 10
    possible_depths = [r for r in range(3, 80, 2) if abs(r-desired_rows) <= 1 + 1e-9]
    if not 8 <= neck <= 300 or not possible_depths:
        return blocked("unsupported", f"量化后领口{neck}针、肩深约{desired_rows:g}行，超出本做法范围。")
    depth = min(possible_depths, key=lambda r: (abs(r-desired_rows), -r))
    body_float = target.body_span_cm * gs / 10
    sleeve_float = target.sleeve_circumference_cm * gs / 10
    body_target, sleeve_target = math.floor(body_float + .5), math.floor(sleeve_float + .5)
    bridge, tolerance = method.underarm_chains, method.stitch_adjustment
    candidates = []
    for n in range(1, depth - 1):
        for db in range(-tolerance, tolerance + 1):
            for ds in range(-tolerance, tolerance + 1):
                body, sleeve = body_target + db, sleeve_target + ds
                held = sleeve - bridge - 2
                body_core = body - 2 * bridge
                sleeve_start, body_start = held - 2 * n, body_core - 4 * n
                if neck + 8 * n != body_core + 2 * held or sleeve_start < 2 or body_start < 4:
                    continue
                front = min((body_start + 2) // 4, (body_start - 2) // 2)
                back = body_start - 2 * front
                if front < 1 or back < 2:
                    continue
                score = (abs(body - body_float) + 2 * abs(sleeve - sleeve_float),
                         max(abs(db), abs(ds)), n)
                candidates.append((score, n, front, sleeve_start, back, db, ds))
    if not candidates:
        return blocked("unsupported", "固定领口与肩深下，四分界每次共加8针，无法同时满足衣身和袖围的"
                       f"±{tolerance}针调整范围。请修改设计约束或选用另一构造，不会自动改成直筒。")
    _, n, front, sleeve_start, back, db, ds = min(candidates)
    slots = depth - 2
    increase_rows = [index + 1 for index in range(1, slots + 1)
                     if math.ceil(index * n / slots) > math.ceil((index - 1) * n / slots)]
    layout = YokeLayout(neck_stitches=neck, rows_to_split=depth, increase_rows=increase_rows,
                        front_start=front, sleeve_start=sleeve_start, back_start=back,
                        underarm_chains=bridge)
    totals = [neck + 8 * sum(r <= row for r in increase_rows) for row in range(1, depth)]
    # Foundations, shaping rows, two two-sided bridges, four corner witnesses,
    # split-row SC outputs and the first complete body row.
    site_estimate = 2 * neck + sum(totals) + 4 * bridge + 4 + layout.body_stitches * 2 - 2 * bridge
    if site_estimate > MAX_SITES:
        return blocked("unsupported", "领肩预计针位数量超过编译预算，须缩小输入或分段设计。")
    return YokeProposal(
        "design_candidate", target, method, layout,
        ("五段为前片A、袖A、后片、袖B、前片B；前片相同、两袖相同；四分界两侧各加1针。",
         "本版本固定正面RS分袖，再从正面挑袖；肩深量化为最近的可用奇数行，估算深度另列。"
         "衣身展开宽度不含门襟。袖围估算包含桥与两转角，未验证转角形变。",
         "首行采用短针，不复用参考教程的松引拔首行；腋下锁针数量由做法指定，未推算其实际长度。"),
        {"neck_edge": neck * 10 / gs, "body_span": layout.body_stitches * 10 / gs,
         "sleeve_circumference": layout.sleeve_stitches * 10 / gs, "yoke_depth": depth * 10 / gr},
        {"body": db, "sleeve": ds},
    )


def _panel_operations(edge: str, counts: tuple[int, ...], *, reverse: bool,
                      increase: bool) -> list[Operation]:
    count = sum(counts)
    cursor = count if reverse else 1
    operations: list[Operation] = []
    for panel, length in enumerate(counts):
        for index in range(length):
            inc = increase and ((panel > 0 and index == 0) or (panel < 4 and index == length - 1))
            stitch: Literal["inc", "sc"] = "inc" if inc else "sc"
            previous = operations[-1] if operations else None
            if isinstance(previous, Work) and previous.stitch == stitch:
                previous.source.first = min(previous.source.first, cursor)
                previous.source.last = max(previous.source.last, cursor)
            else:
                operations.append(Work(stitch=stitch, source=Span(
                    edge=edge, first=cursor, last=cursor, direction="reverse" if reverse else "forward")))
            cursor += -1 if reverse else 1
    return operations


def generate_yoke(proposal: YokeProposal) -> WorkingPath:
    # Recompute rather than trusting a caller-supplied proposal's layout or status.
    proposal = propose_yoke(proposal.target, proposal.method)
    layout = proposal.layout
    if layout is None:
        raise ValueError("领肩约束未满足，不能生成工序")
    prefix, hook = proposal.method.prefix, proposal.method.hook_mm
    chain, gauge_id = f"{prefix}_neck_chain", f"{prefix}_sc"
    steps: list[Step] = [NewYarn(id=f"{prefix}_start_body_yarn", label="领口另取线起针",
                                yarn=f"{prefix}_body_yarn", method="foundation_chain", side="RS"),
                        FoundationChain(id=chain, label="领口短针起链", chains=layout.neck_stitches + 1,
                                        work_face="underside", other_face="top")]
    assert proposal.target.gauge_basis is not None
    plan = WorkingPath(title="参数设计的领肩与分袖候选（未实钩）", input_origin="parametric_design",
                       yarn_tracking=True,
                       steps=steps, gauges=[ConstructionGauge(id=gauge_id, method="短针片钩及袖子闭合行",
                            hook_mm=hook, basis=proposal.target.gauge_basis,
                            stitches_per_10cm=proposal.target.stitches_per_10cm,
                            rows_per_10cm=proposal.target.rows_per_10cm)])
    increases = 0
    operations: list[Operation]
    for row in range(1, layout.rows_to_split):
        previous = chain if row == 1 else f"{prefix}_yoke_{row-1:03d}"
        counts = layout.panels_after(increases)
        inc = row in layout.increase_rows
        if row == 1:
            operations = [Work(source=Span(edge=chain, first=1, last=layout.neck_stitches, face="underside"))]
        else:
            operations = _panel_operations(previous, counts, reverse=True, increase=inc)
        increases += int(inc)
        plan.steps.append(Route(
            id=f"{prefix}_yoke_{row:03d}", label=f"领肩 第 {row} 行",
            section=f"{prefix}_yoke", row_number=row,
            mode="flat", side="RS" if row % 2 else "WS", row_direction="forward" if row % 2 else "reverse",
            operations=operations, expected_sites=sum(layout.panels_after(increases)),
            turn="counterclockwise", turning_chains=1, gauge=gauge_id,
        ))
    front, sleeve, back, _, _ = layout.panels_after(increases)
    total = 2 * (front + sleeve) + back
    previous = f"{prefix}_yoke_{layout.rows_to_split-1:03d}"
    first_bridge, second_bridge = f"{prefix}_bridge_a", f"{prefix}_bridge_b"
    split = f"{prefix}_yoke_{layout.rows_to_split:03d}"
    operations = [
        Work(source=Span(edge=previous, first=total-front+1, last=total, direction="reverse")),
        ChainBridge(id=first_bridge, count=layout.underarm_chains, route_face="underside", corner_sites=True),
        Work(source=Span(edge=previous, first=front+sleeve+1, last=front+sleeve+back, direction="reverse")),
        ChainBridge(id=second_bridge, count=layout.underarm_chains,
                    route_face="underside", corner_sites=True),
        Work(source=Span(edge=previous, first=1, last=front, direction="reverse")),
    ]
    row = layout.rows_to_split
    plan.steps.append(Route(id=split, label=f"领肩 第 {row} 行（分袖）", section=f"{prefix}_yoke",
                            row_number=row, mode="flat", side="RS" if row % 2 else "WS",
                            row_direction="forward" if row % 2 else "reverse", operations=operations,
                            expected_sites=layout.body_stitches, turn="counterclockwise",
                            turning_chains=1, gauge=gauge_id))
    for name, bridge, first, last in (
        ("a", first_bridge, front+sleeve+back+1, total-front),
        ("b", second_bridge, front+1, front+sleeve),
    ):
        middle = (layout.underarm_chains + 1) // 2
        plan.steps.append(Hold(id=f"{prefix}_opening_{name}", label=f"袖窿{name.upper()}，按工作顺序编号",
                               spans=[
            Span(edge=bridge, first=1, last=middle, direction="reverse"),
            Span(edge=bridge, first=1, last=1, face="corner_start"),
            Span(edge=previous, first=first, last=last, direction="reverse"),
            Span(edge=bridge, first=1, last=1, face="corner_end"),
            Span(edge=bridge, first=middle+1, last=layout.underarm_chains, direction="reverse"),
        ]))
    plan.steps.append(Route(
        id=f"{prefix}_body_001", label="衣身 第 1 行（钩过腋下桥里山）",
        section=f"{prefix}_body", row_number=1,
        mode="flat", side="RS" if (row+1) % 2 else "WS",
        row_direction="forward" if (row+1) % 2 else "reverse",
        operations=[Work(source=Span(edge=split, first=1, last=layout.body_stitches, direction="reverse"))],
        expected_sites=layout.body_stitches, turn="counterclockwise", turning_chains=1, gauge=gauge_id,
    ))
    plan.steps.append(Hold(id=f"{prefix}_neck_edge", label="领口另一侧保留，用于后续门襟",
                           spans=[Span(edge=chain, first=1, last=layout.neck_stitches)]))
    plan.final_edges = [f"{prefix}_body_001", f"{prefix}_opening_a",
                        f"{prefix}_opening_b", f"{prefix}_neck_edge"]
    plan.review_notes = [*proposal.reasons,
                         f"输入密度来源{proposal.target.gauge_basis}，非本次实测。尺寸仅为线性估算："
                         + "；".join(f"{name}={v:.3f}cm" for name, v in proposal.estimated_cm.items()),
                         f"相对目标四舍五入针数的调整：{proposal.adjustment_stitches}；"
                         "此调整不代表合身。未使用固定照片模板，也没有实体或照片相似度证据。"]
    compile_working_path(plan)
    return plan
