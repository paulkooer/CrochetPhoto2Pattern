"""Compose parametric cardigan stages, retaining unresolved borders and seams."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.models.attached_ribbing import RibbingMethod, RibbingTarget, design_attached_ribbing
from app.models.button_band import ButtonBandTarget, design_button_band
from app.models.raglan_yoke import YokeMethod, YokeTarget, generate_yoke, propose_yoke
from app.models.working_path import (
    EdgePath,
    FastenOff,
    FoundationChain,
    NewYarn,
    Operation,
    ParkYarn,
    PathModel,
    Route,
    RowEdges,
    RowEnd,
    Seam,
    Span,
    WeaveEnds,
    Work,
    WorkingPath,
    compile_working_path,
)

CARDIGAN_ENGINE_VERSION = "cardigan-parametric-3"


class RibGauge(PathModel):
    stitches_per_10cm: Annotated[float, Field(gt=0, le=100)] | None = None
    rows_per_10cm: Annotated[float, Field(gt=0, le=100)] | None = None
    basis: Literal["hypothetical", "user_entered_swatch"] | None = None

    @model_validator(mode="after")
    def provenance(self) -> RibGauge:
        if (self.stitches_per_10cm is not None or self.rows_per_10cm is not None) and self.basis is None:
            raise ValueError("各类肋纹须分别注明密度来源，不能自动套用普通短针数值")
        return self


class CardiganRequest(PathModel):
    schema_version: Literal["cardigan-design-v1"] = "cardigan-design-v1"
    dimension_basis: Literal["hypothetical", "user_dimensions"]
    yoke: YokeTarget
    method: YokeMethod
    body_length_cm: Annotated[float, Field(gt=0, le=50)]
    sleeve_length_cm: Annotated[float, Field(gt=0, le=50)]
    hem_width_cm: Annotated[float, Field(gt=0, le=10)]
    band_width_cm: Annotated[float, Field(gt=0, le=10)]
    cuff_width_cm: Annotated[float, Field(gt=0, le=10)]
    hem_gauge: RibGauge = Field(default_factory=RibGauge)
    band_gauge: RibGauge = Field(default_factory=RibGauge)
    cuff_gauge: RibGauge = Field(default_factory=RibGauge)
    buttonhole_positions_cm: list[Annotated[float, Field(gt=0, le=100)]] = Field(min_length=1, max_length=20)
    buttonhole_chains: Annotated[int, Field(strict=True, ge=1, le=10)] = 2
    cuff_seam: Literal["open_review", "blo_to_reserved_flo"] = "open_review"
    finishing_tail_cm: Annotated[float, Field(ge=5, le=50)] = 15.0


@dataclass(frozen=True)
class CardiganResult:
    request: CardiganRequest
    stage: str
    plan: WorkingPath | None
    stages: dict
    unresolved: tuple[str, ...]

    def to_dict(self) -> dict:
        compiled = None if self.plan is None else compile_working_path(self.plan)
        return {"schema_version": "cardigan-design-result-v1", "request": self.request.model_dump(),
                "engine_version": CARDIGAN_ENGINE_VERSION,
                "stage": self.stage, "stages": self.stages, "unresolved": self.unresolved,
                "physical_execution_verified": False, "fit_verified": False,
                "photo_method_selection": False, "independent_review": False,
                "ready_for_whole_garment_trial": False,
                "final_edges": {} if compiled is None else {
                    name: len(sites) for name, sites in compiled.final_edges.items()},
                "yarn_accounting": {} if compiled is None else compiled.yarn_accounting,
                }


def _opposite(side: Literal["RS", "WS"]) -> Literal["RS", "WS"]:
    return "WS" if side == "RS" else "RS"


def _row(plan: WorkingPath, identifier: str) -> Route:
    return next(step for step in plan.steps if isinstance(step, Route) and step.id == identifier)


def _extend_body(plan: WorkingPath, prefix: str, count: int) -> str:
    first = _row(plan, f"{prefix}_body_001")
    if count == 1:
        first.turn, first.turning_chains = "none", 0
    for n in range(2, count + 1):
        previous = _row(plan, f"{prefix}_body_{n-1:03d}")
        assert previous.side is not None
        side = _opposite(previous.side)
        plan.steps.append(Route(
            id=f"{prefix}_body_{n:03d}", label=f"衣身 第 {n} 行", section=f"{prefix}_body", row_number=n,
            mode="flat", side=side, row_direction="forward" if side == "RS" else "reverse",
            operations=[Work(source=Span(edge=previous.id, first=1, last=previous.expected_sites,
                                         direction="reverse"))], expected_sites=previous.expected_sites,
            gauge=first.gauge, turn="none" if n == count else "counterclockwise",
            turning_chains=0 if n == count else 1,
        ))
    last = f"{prefix}_body_{count:03d}"
    plan.final_edges = [last if name == first.id else name for name in plan.final_edges]
    return last


def _facing(side: Literal["RS", "WS"]) -> str:
    return "正面" if side == "RS" else "反面"


def _note_ribbing_start(plan: WorkingPath, chain: str, text: str) -> None:
    """State in plain words which face is toward the maker on attaching rows."""
    step = next(s for s in plan.steps if isinstance(s, FoundationChain) and s.id == chain)
    step.note = f"{step.note}{text}"


def _rib_target(sites: int, length: float, width: float, gauge: RibGauge) -> RibbingTarget:
    return RibbingTarget(base_sites=sites, edge_length_cm=length, width_cm=width,
                         rib_rows_per_10cm=gauge.rows_per_10cm,
                         rib_stitches_per_10cm=gauge.stitches_per_10cm, gauge_basis=gauge.basis)


def assemble_cardigan(request: CardiganRequest) -> CardiganResult:
    request = CardiganRequest.model_validate(request.model_dump())
    yoke = propose_yoke(request.yoke, request.method)
    stages = {"yoke": yoke.to_dict()}
    plan = None

    def stop(stage, reason):
        if plan is not None:
            plan.title = f"开衫阶段设计草稿：{stage}（未实钩）"
        return CardiganResult(request, stage, plan, stages, (reason,))

    if yoke.layout is None:
        return stop("yoke_blocked", "；".join(yoke.reasons))
    prefix, hook = request.method.prefix, request.method.hook_mm
    gs, gr = request.yoke.stitches_per_10cm, request.yoke.rows_per_10cm
    assert gs is not None and gr is not None
    body_rows = math.floor(request.body_length_cm * gr / 10 + .5)
    sleeve_rows = math.floor(request.sleeve_length_cm * gr / 10 + .5)
    if not 1 <= body_rows <= 80 or not 1 <= sleeve_rows <= 80:
        return stop("length_blocked", "衣身或袖长量化后的行数超出1–80行范围。")
    plan = generate_yoke(yoke)
    body_last = _extend_body(plan, prefix, body_rows)
    stages["body"] = {"rows": body_rows, "linear_length_cm": body_rows*10/gr,
                      "sleeve_rows": sleeve_rows, "linear_sleeve_length_cm": sleeve_rows*10/gr}
    plan.review_notes.append(f"尺寸来源{request.dimension_basis}；衣身长度从分袖后的首行起计，袖长不含袖口。"
                             "领肩、衣身、下摆和门襟连续用一段线；门襟收线后，两袖分别另接线。")
    body_route = _row(plan, body_last)
    body_count = body_route.expected_sites
    hem_base, body_corner = f"{prefix}_hem_base", f"{prefix}_body_corner"
    plan.steps += [
        EdgePath(id=hem_base, label="下摆基底：从工作环相邻针反向前进", spans=[
            Span(edge=body_last, first=1, last=body_count-1, direction="reverse")]),
        EdgePath(id=body_corner, label="衣身起链根部：用记号扣标出，保留作边缘检查", spans=[
            Span(edge=body_last, first=body_count, last=body_count)]),
    ]
    plan.final_edges.remove(body_last)
    plan.final_edges += [hem_base, body_corner]
    assert body_route.side is not None
    hem_method = RibbingMethod(
        prefix=f"{prefix}_hem", title="下摆短针肋纹设计候选", base_edge=hem_base,
        current_loop=Span(edge=body_corner, first=1, last=1), stitch="sc", foundation_face="underside",
        foundation_turn="counterclockwise", hook_mm=hook, start_side=_opposite(body_route.side),
        outer_edge_both=True, design_basis="下摆根部针明确保留；其余基底按目标长度与独立SC-BLO密度分配。",
    )
    hem, generated = design_attached_ribbing(
        plan, hem_method, _rib_target(body_count-1, (body_count-1)*10/gs,
                                     request.hem_width_cm, request.hem_gauge))
    stages["hem"] = hem.to_dict()
    if generated is None:
        return stop("hem_blocked", "；".join(hem.reasons))
    plan = generated
    assert hem.layout is not None
    _note_ribbing_start(plan, f"{prefix}_hem_chain",
                        f"本段每逢奇数行回到衣身末行作接合，此时衣身{_facing(hem_method.start_side)}朝向自己。")
    hem_last = f"{prefix}_hem_{hem.layout.rows:03d}"
    hem_width = hem.layout.width_stitches
    # Each front-side pickup is declared once per preceding row, excluding the
    # terminal body row already occupied by hem attachment. This is a pickup
    # policy, not a proof of smooth corner geometry.
    garment_rows = [step for step in plan.steps if isinstance(step, Route)
                    and step.section in (f"{prefix}_yoke", f"{prefix}_body")]
    side: Literal["left", "right"] = "left" if body_route.row_direction == "forward" else "right"
    other_side: Literal["left", "right"] = "right" if side == "left" else "left"
    # The front worked first is fixed by the last body row; an even number of
    # body rows therefore mirrors the band (owner decision 2026-11-19). Name the
    # edge without left/right, which depend on the maker's hand.
    begins = (side == "left") == (garment_rows[0].row_direction == "forward")
    first_front = "正面行起头的一侧" if begins == (garment_rows[0].side == "RS") else "正面行收尾的一侧"
    second_front = "正面行收尾的一侧" if first_front == "正面行起头的一侧" else "正面行起头的一侧"
    worn = "左" if first_front == "正面行起头的一侧" else "右"
    up, down = f"{prefix}_front_up", f"{prefix}_front_down"
    band_base, band_corner = f"{prefix}_band_base", f"{prefix}_band_corner"
    plan.steps += [
        RowEdges(id=up, label=f"第一侧前襟（{first_front}）行端，由下往上", rows=[
            RowEnd(row=row.id, side=side) for row in reversed(garment_rows[:-1])]),
        RowEdges(id=down, label=f"另一侧前襟（{second_front}）行端，由上往下", rows=[
            RowEnd(row=row.id, side=other_side) for row in garment_rows[:-1]]),
        EdgePath(id=band_corner, label="门襟起链根部：用记号扣标出，保留作边缘检查", spans=[
            Span(edge=hem_last, first=hem_width, last=hem_width)]),
        EdgePath(id=band_base, label="下摆端、第一侧、领口、另一侧、另一端下摆", spans=[
            *([Span(edge=hem_last, first=1, last=hem_width-1, direction="reverse")]
              if hem_width > 1 else []),
            Span(edge=up, first=1, last=len(garment_rows)-1),
            # Enter the neckline at the end the first front reaches.
            Span(edge=f"{prefix}_neck_edge", first=1, last=yoke.layout.neck_stitches,
                 direction="reverse" if side == "right" else "forward"),
            Span(edge=down, first=1, last=len(garment_rows)-1),
            Span(edge=f"{prefix}_hem_outside", first=1, last=hem_width, direction="reverse"),
        ]),
    ]
    plan.final_edges = [name for name in plan.final_edges
                        if name not in (hem_last, f"{prefix}_neck_edge", f"{prefix}_hem_outside")]
    plan.final_edges += [band_corner, band_base]
    perimeter_sites = 2*hem_width-1 + 2*(len(garment_rows)-1) + yoke.layout.neck_stitches
    hem_gs = request.hem_gauge.stitches_per_10cm
    assert hem_gs is not None
    perimeter_cm = (2*hem_width-1)*10/hem_gs + (
        2*(len(garment_rows)-1)*10/gr + yoke.layout.neck_stitches*10/gs)
    band_target = ButtonBandTarget(
        **_rib_target(perimeter_sites, perimeter_cm, request.band_width_cm, request.band_gauge).model_dump(),
        first_front_sites=hem_width-1+len(garment_rows)-1,
        buttonhole_positions_cm=request.buttonhole_positions_cm,
    )
    hem_route = _row(plan, hem_last)
    assert hem_route.side is not None  # ribbing rows are flat rows and always declare a side
    band_side = _opposite(hem_route.side)
    band_method = RibbingMethod(
        prefix=f"{prefix}_band", title="连续门襟与扣眼设计候选", base_edge=band_base,
        current_loop=Span(edge=band_corner, first=1, last=1), stitch="slst", foundation_face="underside",
        # The band returns along the last hem row, so it always turns first.
        foundation_turn="counterclockwise", hook_mm=hook, start_side=band_side,
        outer_turning_chain=1, buttonhole_chains=request.buttonhole_chains,
        design_basis="门襟行端按每行一位挑针；跨领口顺序及根部保留公开记录，转角平整度未验证。",
    )
    band, generated = design_button_band(plan, band_method, band_target)
    stages["band"] = band.to_dict()
    if generated is None:
        return stop("band_blocked", "；".join(band.reasons))
    plan = generated
    assert band.ribbing.layout is not None
    band_facing = _facing(band_method.start_side)
    _note_ribbing_start(plan, f"{prefix}_band_chain",
                        f"本段每逢奇数行回到衣物边缘作接合，此时衣物{band_facing}朝向自己；"
                        f"扣眼开在第一侧前襟，即{first_front}。")
    plan.review_notes.append(
        f"朝向与前襟：衣身共{body_rows}行，门襟接合行以衣物{band_facing}朝向自己，扣眼在{first_front}的前襟；"
        "衣身行数的奇偶改变时，这两项一起镜像。"
        f"按右手钩织推算，该前襟是穿着者的{worn}前襟，左手钩织相反；此推算未经实物确认。")
    body_yarn = f"{prefix}_body_yarn"
    plan.steps += [
        FastenOff(id=f"{prefix}_finish_body_yarn", label="门襟完成后断线收紧", yarn=body_yarn,
                  source=Span(edge=f"{prefix}_band_{band.ribbing.layout.rows:03d}",
                              first=band.ribbing.layout.width_stitches,
                              last=band.ribbing.layout.width_stitches),
                  tail_cm=request.finishing_tail_cm),
        WeaveEnds(id=f"{prefix}_weave_body_yarn", label="藏好领口起线端与门襟结束端",
                  yarn=body_yarn, ends="both"),
    ]
    for name in ("a", "b"):
        opening = f"{prefix}_opening_{name}"
        previous = opening
        sleeve_prefix = f"{prefix}_sleeve_{name}"
        sleeve_yarn = f"{sleeve_prefix}_yarn"
        plan.steps.append(NewYarn(id=f"{sleeve_prefix}_start_yarn", label=f"袖{name.upper()}另接线起针",
                                  yarn=sleeve_yarn, method="standing_sc", side="RS",
                                  anchor=Span(edge=opening, first=1, last=1)))
        for n in range(1, sleeve_rows + 1):
            operations: list[Operation] = [Work(source=Span(
                edge=previous, first=1, last=yoke.layout.sleeve_stitches, direction="reverse"))]
            if n == 1:
                operations = [Work(source=Span(edge=opening, first=1, last=1), stitch="standing_sc"),
                              Work(source=Span(edge=opening, first=2, last=yoke.layout.sleeve_stitches))]
            identifier = f"{sleeve_prefix}_{n:03d}"
            plan.steps.append(Route(
                id=identifier, label=f"袖{name.upper()} 第 {n} 行", section=sleeve_prefix, row_number=n,
                mode="joined_rows", side="RS" if n % 2 else "WS",
                row_direction="forward" if n % 2 else "reverse", operations=operations,
                expected_sites=yoke.layout.sleeve_stitches, turn="counterclockwise",
                closure="before_turn" if n % 2 else "after_turn", turning_chains=1 if n < sleeve_rows else 0,
                gauge=f"{prefix}_sc",
            ))
            previous = identifier
        plan.final_edges.remove(opening)
        cuff_base = f"{prefix}_cuff_{name}_base"
        # The last sleeve round ends with a turn, so the cuff travels back over it.
        plan.steps.append(EdgePath(id=cuff_base, label="袖口从闭合环相邻针开始，沿末圈反向一周", spans=[
            Span(edge=previous, first=2, last=yoke.layout.sleeve_stitches, direction="reverse"),
            Span(edge=previous, first=1, last=1),
        ]))
        plan.final_edges.append(cuff_base)
        cuff_method = RibbingMethod(
            prefix=f"{prefix}_cuff_{name}", title=f"袖口{name.upper()}引拔肋纹候选", base_edge=cuff_base,
            current_loop=Span(edge=cuff_base, first=yoke.layout.sleeve_stitches,
                              last=yoke.layout.sleeve_stitches), stitch="slst", foundation_face="back_loop",
            foundation_turn="none", hook_mm=hook, start_side="WS" if sleeve_rows % 2 else "RS",
            outer_turning_chain=1, keep_start_loops=True,
            design_basis="袖口首行前半针和末行明确保留；折叠与接缝的半针方向未自动决定。",
        )
        cuff, generated = design_attached_ribbing(
            plan, cuff_method, _rib_target(yoke.layout.sleeve_stitches,
                                          yoke.layout.sleeve_stitches*10/gs,
                                          request.cuff_width_cm, request.cuff_gauge))
        stages[f"cuff_{name}"] = cuff.to_dict()
        if generated is None:
            return stop(f"cuff_{name}_blocked", "；".join(cuff.reasons))
        plan = generated
        _note_ribbing_start(plan, f"{prefix}_cuff_{name}_chain",
                            f"本段每逢奇数行回到袖子末圈作接合，此时袖子{_facing(cuff_method.start_side)}朝向自己。")
        if request.cuff_seam == "blo_to_reserved_flo":
            assert cuff.layout is not None
            cuff_last = f"{prefix}_cuff_{name}_{cuff.layout.rows:03d}"
            cuff_start = f"{prefix}_cuff_{name}_start_loops"
            # The seam travels back over the last cuff row, so that row ends with
            # a turn and the seam is worked with the other face toward the maker.
            last_row = next(s for s in plan.steps if isinstance(s, Route) and s.id == cuff_last)
            assert last_row.side is not None  # ribbing rows are flat rows and always declare a side
            last_row.turn = "counterclockwise"
            seam_side = _opposite(last_row.side)
            plan.steps.append(Seam(
                id=f"{prefix}_cuff_{name}_seam", label=f"袖口{name.upper()}指定半针接合候选",
                left=Span(edge=cuff_last, first=1, last=cuff.layout.width_stitches, direction="reverse"),
                right=Span(edge=cuff_start, first=1, last=cuff.layout.width_stitches),
                left_loop="back", side=seam_side,
                note=f"末行钩完翻面后，以袖口{_facing(seam_side)}朝向自己，沿末行往回接合；"
                "末行的后半针指此时离自己较远的那一根。"
                "从当前环所在的末行末针开始，与首行第一针配对；"
                "这是新设计的BLO/FLO接合选择，不声称对应原教程inner/outer或已验证折向。"))
            plan.final_edges = [edge for edge in plan.final_edges if edge not in (cuff_last, cuff_start)]
            plan.steps += [
                FastenOff(id=f"{prefix}_cuff_{name}_fasten_off", label=f"袖口{name.upper()}接合后断线收紧",
                          yarn=sleeve_yarn, source=Span(edge=f"{prefix}_cuff_{name}_seam",
                              first=cuff.layout.width_stitches,
                              last=cuff.layout.width_stitches, face="binding"),
                          tail_cm=request.finishing_tail_cm),
                WeaveEnds(id=f"{prefix}_cuff_{name}_weave", label=f"藏好袖{name.upper()}起线端与袖口结束端",
                          yarn=sleeve_yarn, ends="both"),
            ]
        else:
            assert cuff.layout is not None
            plan.steps += [
                ParkYarn(id=f"{prefix}_cuff_{name}_park", label=f"袖口{name.upper()}暂停，保留工作环待接合",
                         yarn=sleeve_yarn, source=Span(edge=f"{prefix}_cuff_{name}_{cuff.layout.rows:03d}",
                             first=cuff.layout.width_stitches, last=cuff.layout.width_stitches)),
                WeaveEnds(id=f"{prefix}_cuff_{name}_weave_start", label=f"仅藏好袖{name.upper()}起线端",
                          yarn=sleeve_yarn, ends="starting"),
            ]
    if request.cuff_seam == "blo_to_reserved_flo":
        plan.title = "参数生成开衫接合候选（未实钩）"
        compile_working_path(plan)
        return CardiganResult(request, "integrated_cuff_seam_candidate", plan, stages, (
            "袖口使用末行BLO与首行预留FLO的指定接合；配对从末行末针到首行首针，折叠朝向未实物验证。",
            "衣身、门襟根部针与起链保留侧的边缘处理、转角、肩部及袖窿形变待实物核对。",
            "尺寸来自线性估算；没有原作复原、合身、独立审核或照片自动设计证据。",
        ))
    plan.title = "参数生成开衫工序组合稿（袖口未接合，未实钩）"
    compile_working_path(plan)
    return CardiganResult(request, "integrated_open_cuffs", plan, stages, (
        "两只袖口的首末行接合与折叠方向未确认；当前保留相应针位，不假装已经闭合。",
        "衣身和门襟各保留一处起链根部针目；其边缘处理、前襟转角挑针与袖窿朝向待实物审查。",
        "尺寸仅按输入密度线性估算；未验证弹性、穿着余量、纽扣直径或照片相似度。",
    ))
