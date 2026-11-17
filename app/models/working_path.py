"""Experimental explicit working paths, including held sites and chain bridges.

This checks a declared stitch-site inventory. It does not infer garment shape,
measure gauge, or establish that a physical piece can be made or fits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Count = Annotated[int, Field(strict=True, ge=1, le=1000)]
ChainFace = Literal["top", "underside", "front_loop", "back_loop"]
Face = Literal["top", "underside", "front_loop", "back_loop", "corner_start", "corner_end",
               "row_left", "row_right", "binding"]
Loop = Literal["both", "front", "back"]
MAX_SITES = 20_000


class PathModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExistingEdge(PathModel):
    """A manually declared piece of fabric, rather than a simulated foundation."""

    id: Identifier
    count: Count


class Span(PathModel):
    edge: Identifier
    first: Count
    last: Count
    face: Face = "top"
    direction: Literal["forward", "reverse"] = "forward"

    @model_validator(mode="after")
    def ordered_bounds(self) -> Span:
        if self.first > self.last:
            raise ValueError("针位范围须 first <= last；反向工作请声明 direction=reverse")
        return self


class Work(PathModel):
    kind: Literal["work"] = "work"
    source: Span
    stitch: Literal["sc", "standing_sc", "inc", "dec", "slst"] = "sc"
    loop: Loop = "both"
    disposition: Literal["working", "binding"] = "working"

    @model_validator(mode="after")
    def binding_is_explicit(self) -> Work:
        if self.disposition == "binding" and self.stitch != "slst":
            raise ValueError("不进入下一行工作边的接合操作须明确为引拔针")
        return self


class ChainBridge(PathModel):
    kind: Literal["chain"] = "chain"
    id: Identifier
    count: Count
    route_face: Literal["top", "underside"]
    corner_sites: bool = False
    placement: Literal["bridge", "buttonhole"] = "bridge"
    skipped: Span | None = None

    @model_validator(mode="after")
    def explicit_hole(self) -> ChainBridge:
        if self.placement == "buttonhole" and (self.skipped is None or self.corner_sites):
            raise ValueError("扣眼须明确跳过的旧针位，不自动增加袖窿转角")
        if self.placement == "bridge" and self.skipped is not None:
            raise ValueError("普通锁针桥的保留位置须单独声明，不能当作扣眼边退休")
        return self


class ConstructionGauge(PathModel):
    id: Identifier
    method: str = Field(min_length=1, max_length=120)
    hook_mm: Annotated[float, Field(gt=0, le=20)]
    basis: Literal["reference_declared", "unmeasured", "hypothetical", "user_entered_swatch"]
    stitches_per_10cm: Annotated[float, Field(gt=0, le=100)] | None = None
    rows_per_10cm: Annotated[float, Field(gt=0, le=100)] | None = None

    @model_validator(mode="after")
    def no_fabricated_measurement(self) -> ConstructionGauge:
        if self.basis == "unmeasured" and (self.stitches_per_10cm is not None
                                           or self.rows_per_10cm is not None):
            raise ValueError("未测密度不能填写假定的实测数值")
        return self


Operation = Annotated[Work | ChainBridge, Field(discriminator="kind")]


class Route(PathModel):
    kind: Literal["route"] = "route"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    operations: list[Operation] = Field(min_length=1, max_length=100)
    expected_sites: Count
    mode: Literal["segment", "flat", "joined_rows"] = "segment"
    row_direction: Literal["forward", "reverse"] | None = None
    side: Literal["RS", "WS"] | None = None
    turning_chains: Annotated[int, Field(strict=True, ge=0, le=6)] = 0
    turn: Literal["none", "clockwise", "counterclockwise"] = "none"
    closure: Literal["none", "before_turn", "after_turn"] = "none"
    gauge: Identifier | None = None
    source_ref: str = Field(default="", max_length=240)
    note: str = Field(default="", max_length=1200)
    section: str = Field(default="", max_length=120)
    row_number: Count | None = None

    @model_validator(mode="after")
    def bridges_have_both_ends(self) -> Route:
        if bool(self.section) != (self.row_number is not None):
            raise ValueError("工序分段与段内行号须一起声明")
        for index, operation in enumerate(self.operations):
            if not isinstance(operation, ChainBridge):
                continue
            if index == 0 or index == len(self.operations) - 1:
                raise ValueError("本版锁针桥须位于两段已声明的钩织之间，不作起链或翻转链")
            previous, following = self.operations[index - 1], self.operations[index + 1]
            if not isinstance(previous, Work) or not isinstance(following, Work):
                raise ValueError("本版锁针桥须位于两段已声明的钩织之间，不作起链或翻转链")
            expected_after = "working" if operation.placement == "bridge" else "binding"
            if previous.disposition != "working" or following.disposition != expected_after:
                raise ValueError("本版锁针桥须位于两段已声明的钩织之间，不作起链或翻转链")
        if self.mode != "segment" and (self.row_direction is None or self.side is None):
            raise ValueError("行钩须明确正反面及行方向，不能猜测行侧边")
        if self.mode == "joined_rows":
            expected = "before_turn" if self.side == "RS" else "after_turn"
            if self.closure != expected or self.turn == "none":
                raise ValueError("闭合行：正面先隐形引拔后翻面；反面先翻面后隐形引拔")
        elif self.closure != "none":
            raise ValueError("隐形闭合接头须使用 joined_rows 模式")
        if self.turning_chains and self.turn == "none":
            raise ValueError("翻转链须与明确的翻面操作同时声明")
        return self


class Hold(PathModel):
    kind: Literal["hold"] = "hold"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    spans: list[Span] = Field(min_length=1, max_length=40)


class EdgePath(PathModel):
    """Explicitly transfer available sites from their current named edges.

    This names an ordered work path, not a physical seam or a new stitch.
    Old aliases lose access to transferred sites.
    """
    kind: Literal["edge_path"] = "edge_path"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    spans: list[Span] = Field(min_length=1, max_length=40)


class FoundationChain(PathModel):
    kind: Literal["foundation_chain"] = "foundation_chain"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    chains: Annotated[int, Field(strict=True, ge=2, le=1000)]
    skip_from_hook: Annotated[int, Field(strict=True, ge=1, le=6)] = 1
    work_face: ChainFace
    other_face: ChainFace
    anchor: Span | None = None
    anchor_mode: Literal["takes_site", "continues_loop"] = "takes_site"
    turn_after_chain: Literal["none", "clockwise", "counterclockwise"] = "none"
    source_ref: str = Field(default="", max_length=240)
    note: str = Field(default="", max_length=1200)

    @model_validator(mode="after")
    def valid_foundation(self) -> FoundationChain:
        if self.skip_from_hook >= self.chains:
            raise ValueError("起链须留下至少一个工作位置")
        if {self.work_face, self.other_face} not in ({"top", "underside"}, {"front_loop", "back_loop"}):
            raise ValueError("须明确起链互不重复的两面：顶部/里山，或前/后半针")
        if self.anchor is not None and self.anchor.first != self.anchor.last:
            raise ValueError("继续起链的根部须为一个明确针位")
        if self.anchor_mode == "continues_loop" and self.anchor is None:
            raise ValueError("继续起链须明确当前工作环的来源")
        return self


class RowEnd(PathModel):
    row: Identifier
    side: Literal["left", "right"]


class RowEdges(PathModel):
    kind: Literal["row_edges"] = "row_edges"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    rows: list[RowEnd] = Field(min_length=1, max_length=600)


class FreeLoops(PathModel):
    kind: Literal["free_loops"] = "free_loops"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    source: Span
    loop: Literal["front", "back"]


class Seam(PathModel):
    kind: Literal["seam"] = "seam"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    left: Span
    right: Span
    left_loop: Loop = "both"
    right_loop: Loop = "both"
    source_ref: str = Field(default="", max_length=240)
    note: str = Field(default="", max_length=1200)


class FinishEdge(PathModel):
    kind: Literal["finish_edge"] = "finish_edge"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    source: Span
    reason: Literal["finished_border", "unused_chain_face"]


class NewYarn(PathModel):
    kind: Literal["new_yarn"] = "new_yarn"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    yarn: Identifier
    method: Literal["foundation_chain", "standing_sc"]
    side: Literal["RS", "WS"]
    anchor: Span | None = None

    @model_validator(mode="after")
    def explicit_start(self) -> NewYarn:
        if self.method == "foundation_chain" and self.anchor is not None:
            raise ValueError("独立起链的新线段不引用旧针目")
        if self.method == "standing_sc" and (self.anchor is None or self.anchor.first != self.anchor.last):
            raise ValueError("另接线起立短针须指定单个落针位置")
        return self


class FastenOff(PathModel):
    kind: Literal["fasten_off"] = "fasten_off"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    yarn: Identifier
    source: Span
    tail_cm: Annotated[float, Field(ge=5, le=50)]


class ParkYarn(PathModel):
    kind: Literal["park_yarn"] = "park_yarn"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    yarn: Identifier
    source: Span


class ResumeYarn(PathModel):
    kind: Literal["resume_yarn"] = "resume_yarn"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    yarn: Identifier


class WeaveEnds(PathModel):
    kind: Literal["weave_ends"] = "weave_ends"
    id: Identifier
    label: str = Field(min_length=1, max_length=120)
    yarn: Identifier
    ends: Literal["starting", "finishing", "both"]


YarnControl = NewYarn | FastenOff | ParkYarn | ResumeYarn | WeaveEnds
Step = Annotated[Route | Hold | EdgePath | FoundationChain | RowEdges | FreeLoops | Seam | FinishEdge
                 | YarnControl,
                 Field(discriminator="kind")]


class WorkingPath(PathModel):
    schema_version: Literal["working-path-v1", "working-path-v2"] = "working-path-v2"
    input_origin: Literal["manual_existing_edges", "manual_instructions", "parametric_design"] = (
        "manual_existing_edges")
    title: str = Field(min_length=1, max_length=120)
    yarn_tracking: bool = False
    existing_edges: list[ExistingEdge] = Field(default_factory=list, max_length=20)
    steps: list[Step] = Field(min_length=1, max_length=600)
    final_edges: list[Identifier] = Field(default_factory=list, max_length=40)
    gauges: list[ConstructionGauge] = Field(default_factory=list, max_length=20)
    review_notes: list[Annotated[str, Field(min_length=1, max_length=1200)]] = Field(
        default_factory=list, max_length=20)


@dataclass(frozen=True)
class Site:
    edge: str
    position: int
    face: Face = "top"


@dataclass(frozen=True)
class StitchEvent:
    route: str
    stitch: str
    sources: tuple[Site, ...]
    outputs: tuple[Site, ...]
    role: Literal["working", "binding", "reference", "closure", "retired", "yarn_control"] = "working"
    source_loops: tuple[str, ...] = ()
    note: str = ""
    yarn_id: str = ""


@dataclass
class _YarnState:
    status: Literal["ready", "working", "parked", "closed"]
    side: Literal["RS", "WS"]
    loop_site: Site | None = None
    has_worked: bool = False
    woven_ends: set[str] = field(default_factory=set)
    tail_cm: float | None = None


@dataclass(frozen=True)
class PathResult:
    plan: WorkingPath
    events: tuple[StitchEvent, ...]
    edges: dict[str, tuple[Site, ...]]
    held_edges: dict[str, tuple[Site, ...]]
    final_edges: dict[str, tuple[Site, ...]]
    created_sites: int
    consumed_sites: int
    yarn_accounting: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        retired = [event for event in self.events if event.role == "retired"]
        return {
            "schema_version": "working-path-result-v2",
            "evidence": "declared_site_inventory_only",
            "physical_execution_verified": False,
            "fit_verified": False,
            "photo_likeness_verified": False,
            "plan": self.plan.model_dump(),
            "events": [asdict(event) for event in self.events],
            "edges": {key: [asdict(s) for s in value] for key, value in self.edges.items()},
            "held_edges": {key: [asdict(s) for s in value] for key, value in self.held_edges.items()},
            "final_edges": {key: [asdict(s) for s in value] for key, value in self.final_edges.items()},
            "created_sites": self.created_sites, "consumed_sites": self.consumed_sites,
            "yarn_accounting": self.yarn_accounting,
            "inventory_accounting": {
                "retired_without_work": len({site for event in retired for site in event.sources}),
                "retirement_declarations": [
                    {"step": event.route, "reason": event.note, "sites": len(event.sources)}
                    for event in retired
                ],
                "unconsumed_sites": self.created_sites - self.consumed_sites,
            },
        }


class _Compiler:
    def __init__(self, *, yarn_tracking: bool = False):
        self.edges: dict[tuple[str, Face], tuple[Site, ...]] = {}
        self.sites: set[Site] = set()
        self.consumed: set[Site] = set()
        self.reserved: dict[Site, str] = {}
        self.holds: dict[str, tuple[Site, ...]] = {}
        self.events: list[StitchEvent] = []
        self.free_lips: set[tuple[Site, str]] = set()
        self.rows: dict[str, Route] = {}
        self.current_loop: Site | None = None
        self.section_rows: dict[str, Route] = {}
        self.chain_sites: set[Site] = set()
        self.yarn_tracking = yarn_tracking
        self.yarns: dict[str, _YarnState] = {}
        self.active_yarn: str | None = None
        self.expected_side: Literal["RS", "WS"] | None = None
        self.pending_start: Literal["foundation_chain", "standing_sc"] | None = None
        self.pending_anchor: Site | None = None
        self.pending_chain_work: Site | None = None

    def yarn_control(self, step: YarnControl) -> None:
        if not self.yarn_tracking:
            raise ValueError("用线动作须启用 yarn_tracking，不能当作已检查的旧工序")
        sources: tuple[Site, ...] = ()
        if isinstance(step, NewYarn):
            if self.active_yarn is not None:
                raise ValueError("另接线前须收掉或暂停当前工作环")
            if step.yarn in self.yarns:
                raise ValueError("新线段名称重复；暂停的线段须恢复，不能当作新线另起")
            if step.anchor is not None:
                sources = self.resolve(step.anchor)
                self.available(sources, via=step.anchor.edge)
            self.yarns[step.yarn] = _YarnState("ready", step.side)
            self.active_yarn, self.expected_side = step.yarn, step.side
            self.pending_start = step.method
            self.pending_anchor = sources[0] if sources else None
            self.current_loop = None
        elif isinstance(step, ResumeYarn):
            state = self.yarns.get(step.yarn)
            if self.active_yarn is not None or state is None or state.status != "parked":
                raise ValueError("恢复工作环须有暂停记录，且当前没有另一条正在工作的线段")
            state.status = "working"
            self.active_yarn, self.current_loop, self.expected_side = step.yarn, state.loop_site, state.side
            assert state.loop_site is not None
            sources = (state.loop_site,)
        elif isinstance(step, WeaveEnds):
            state = self.yarns.get(step.yarn)
            if state is None or not state.has_worked:
                raise ValueError("藏线须引用已经钩入织物的线段")
            ends = {"starting", "finishing"} if step.ends == "both" else {step.ends}
            if "finishing" in ends and state.status != "closed":
                raise ValueError("结束端尚未断线收紧，不能提前声明已藏线")
            if state.woven_ends.intersection(ends):
                raise ValueError("同一个线端不能重复登记藏线")
            state.woven_ends.update(ends)
            sources = (state.loop_site,) if state.loop_site is not None else ()
        else:
            if (step.yarn != self.active_yarn or self.current_loop is None
                    or self.pending_start is not None or self.pending_chain_work is not None):
                raise ValueError("收线或暂停须引用当前已有的工作环，不能跳到另一条线")
            sources = self.resolve(step.source)
            if sources != (self.current_loop,):
                raise ValueError("收线或暂停的位置不等于当前工作环")
            state = self.yarns[step.yarn]
            state.loop_site = self.current_loop
            assert self.expected_side is not None
            state.side = self.expected_side
            if isinstance(step, FastenOff):
                state.status, state.tail_cm = "closed", step.tail_cm
            else:
                state.status = "parked"
            self.active_yarn, self.current_loop, self.expected_side = None, None, None
        self.events.append(StitchEvent(step.id, step.kind, sources, (),
                                       role="yarn_control", yarn_id=step.yarn))

    def before_work(self, step: Route | FoundationChain | Seam) -> None:
        if not self.yarn_tracking:
            return
        if self.active_yarn is None:
            raise ValueError("钩织前须另接新线或恢复已暂停的工作环")
        if isinstance(step, FoundationChain):
            if self.pending_chain_work is not None or self.pending_start == "standing_sc":
                raise ValueError("须先按新线起针或起链的已声明来源完成下一步")
            if self.pending_start == "foundation_chain":
                if step.anchor is not None:
                    raise ValueError("新线独立起链不能借用旧工作环")
            elif step.anchor is None or step.anchor_mode != "continues_loop":
                raise ValueError("当前线段继续起链须明确接续工作环；另起链须声明新线段")
            return
        if isinstance(step, Seam):
            if (self.pending_start is not None or self.pending_chain_work is not None
                    or self.resolve(step.left)[0] != self.current_loop):
                raise ValueError("接合须从当前工作环一端开始，不能无说明跳到另一端")
            return
        first = step.operations[0]
        if self.pending_start == "foundation_chain":
            raise ValueError("新线声明为独立起链，须先执行起链")
        if self.pending_start == "standing_sc":
            if (not isinstance(first, Work) or first.stitch != "standing_sc"
                    or first.disposition != "working"
                    or self.resolve(first.source) != (self.pending_anchor,)):
                raise ValueError("另接线首针须在声明位置作单个起立短针")
        elif any(isinstance(op, Work) and op.stitch == "standing_sc" for op in step.operations):
            raise ValueError("起立短针须有另接新线记录，不能静默替换当前线段")
        if self.pending_start == "standing_sc" and any(
                isinstance(op, Work) and op.stitch == "standing_sc" for op in step.operations[1:]):
            raise ValueError("新线起立短针只用于首个落针位置")
        if self.pending_chain_work is not None and (
                not isinstance(first, Work) or self.resolve(first.source)[0] != self.pending_chain_work):
            raise ValueError("起链后的首针没有回到已声明的工作面起点")
        if step.side is not None and self.expected_side != step.side:
            raise ValueError("当前织物朝向与下一行正反面不一致，须明确翻面或另接线")

    def after_work(self, step: Route | FoundationChain | Seam, event_start: int) -> None:
        if not self.yarn_tracking:
            return
        assert self.active_yarn is not None
        for index in range(event_start, len(self.events)):
            event = self.events[index]
            if event.role in ("working", "binding", "closure"):
                self.events[index] = replace(event, yarn_id=self.active_yarn)
        self.pending_start, self.pending_anchor = None, None
        state = self.yarns[self.active_yarn]
        if isinstance(step, FoundationChain):
            self.pending_chain_work = self.edges[step.id, step.work_face][0]
            if step.turn_after_chain != "none":
                self.expected_side = "WS" if self.expected_side == "RS" else "RS"
        else:
            self.pending_chain_work = None
            state.has_worked, state.status = True, "working"
            if isinstance(step, Route) and step.side is not None:
                self.expected_side = (("WS" if step.side == "RS" else "RS")
                                      if step.turn != "none" else step.side)
        state.loop_site = self.current_loop
        assert self.expected_side is not None
        state.side = self.expected_side

    def yarn_report(self) -> dict:
        return {
            "mode": "explicit" if self.yarn_tracking else "legacy_untracked",
            "evidence": "instruction_declarations_only",
            "segments": {key: {"declared_status": value.status,
                               "declared_woven_ends": sorted(value.woven_ends),
                               "tail_cm": value.tail_cm,
                               "loop_reference": None if value.loop_site is None else asdict(value.loop_site),
                               "next_side": value.side} for key, value in self.yarns.items()},
            "all_fasten_off_steps_present": bool(self.yarns) and all(
                state.status == "closed" for state in self.yarns.values()),
            "all_weave_steps_present": bool(self.yarns) and all(
                state.status == "closed" and state.woven_ends == {"starting", "finishing"}
                for state in self.yarns.values()),
        }

    def create(self, site: Site) -> Site:
        if site in self.sites:
            raise ValueError("重复创建针位")
        if len(self.sites) >= MAX_SITES:
            raise ValueError("工作路径的针位数量超过上限")
        self.sites.add(site)
        return site

    def resolve(self, span: Span) -> tuple[Site, ...]:
        edge = self.edges.get((span.edge, span.face))
        if edge is None:
            raise ValueError(f"工作边或表面尚未建立：{span.edge}/{span.face}")
        if span.last > len(edge):
            raise ValueError(f"针位越界：{span.edge} 只有 {len(edge)} 个工作位置")
        sites = edge[span.first - 1:span.last]
        return tuple(reversed(sites)) if span.direction == "reverse" else sites

    def available(self, sites: tuple[Site, ...], *, via: str) -> None:
        if len(set(sites)) != len(sites):
            raise ValueError("同一路径重复引用针位")
        for site in sites:
            if site in self.consumed:
                raise ValueError(f"针位已使用，不能通过其他别名再次使用：{site}")
            if site in self.reserved and self.reserved[site] != via:
                raise ValueError(f"针位已保留给 {self.reserved[site]}，须通过该保留边继续")

    def consume(self, sites: tuple[Site, ...], loop: Loop) -> None:
        for site in sites:
            if loop != "both":
                if site.face != "top":
                    raise ValueError("半针或特殊落针位不能再次拆分为半针")
                self.free_lips.add((site, "back" if loop == "front" else "front"))
            self.consumed.add(site)

    def foundation(self, step: FoundationChain) -> None:
        parents = () if step.anchor is None else self.resolve(step.anchor)
        if step.anchor is not None:
            if step.anchor_mode == "continues_loop":
                if parents != (self.current_loop,):
                    raise ValueError("继续起链须从当前工作环出发，不能任意引用旧针目")
            else:
                self.available(parents, via=step.anchor.edge)
                self.consume(parents, "both")
        positions = range(step.skip_from_hook + 1, step.chains + 1)
        first = tuple(self.create(Site(step.id, i, step.work_face)) for i in positions)
        second = tuple(self.create(Site(step.id, i, step.other_face)) for i in positions)
        self.edges[step.id, step.work_face] = first
        self.edges[step.id, step.other_face] = second
        self.chain_sites.update(first + second)
        self.events.append(StitchEvent(step.id, "foundation_chain", parents, first + second,
                                       note="跳过的起立链不作后续工作针位；根部连接另有明确来源"))
        self.current_loop = None

    def row_edges(self, step: RowEdges) -> None:
        sites = []
        for ref in step.rows:
            row = self.rows.get(ref.row)
            if row is None or row.mode != "flat":
                raise ValueError("行侧挑针须引用已建立并明确方向的片钩行")
            edge = self.edges[ref.row, "top"]
            first = (ref.side == "left") == (row.row_direction == "forward")
            anchor = edge[0] if first else edge[-1]
            face: Face = "row_left" if ref.side == "left" else "row_right"
            site = Site(ref.row, 1, face)
            if site not in self.sites:
                self.create(site)
                self.events.append(StitchEvent(step.id, "row_end_site", (anchor,), (site,),
                                               role="reference", note=f"{ref.side} 行端；不是新钩一针"))
            sites.append(site)
        self.available(tuple(sites), via=step.id)
        self.edges[step.id, "top"] = tuple(sites)

    def loops(self, step: FreeLoops) -> None:
        sites = []
        for parent in self.resolve(step.source):
            if (parent, step.loop) not in self.free_lips:
                raise ValueError("该半针没有被先前的挑针操作保留，不能凭空补出")
            face: Face = "front_loop" if step.loop == "front" else "back_loop"
            site = Site(parent.edge, parent.position, face)
            if site not in self.sites:
                self.create(site)
                self.events.append(StitchEvent(step.id, "reserved_loop_site", (parent,), (site,),
                                               role="reference", note=f"明确预留的 {step.loop} 半针"))
            sites.append(site)
        self.available(tuple(sites), via=step.id)
        self.edges[step.id, "top"] = tuple(sites)

    def seam(self, step: Seam) -> None:
        left, right = self.resolve(step.left), self.resolve(step.right)
        if len(left) != len(right):
            raise ValueError("接缝两侧针位数不一致，不能静默拉伸或补针")
        self.available(left, via=step.left.edge)
        self.available(right, via=step.right.edge)
        if set(left).intersection(right):
            raise ValueError("接缝不能通过别名将同一针位接到自身")
        bindings = []
        for i, (a, b) in enumerate(zip(left, right, strict=True), 1):
            self.consume((a,), step.left_loop)
            self.consume((b,), step.right_loop)
            output = self.create(Site(step.id, i, "binding"))
            self.consumed.add(output)
            bindings.append(output)
            self.events.append(StitchEvent(step.id, "slst", (a, b), (output,), role="binding",
                                           source_loops=(step.left_loop, step.right_loop)))
        self.edges[step.id, "binding"] = tuple(bindings)
        self.current_loop = bindings[-1]

    def finish(self, step: FinishEdge) -> None:
        sites = self.resolve(step.source)
        self.available(sites, via=step.source.edge)
        if step.reason == "unused_chain_face" and not set(sites).issubset(self.chain_sites):
            raise ValueError("未用锁针侧须引用实际起链或锁针桥，不能用来注销普通针目")
        self.consume(sites, "both")
        self.events.append(StitchEvent(step.id, "finish_edge", sites, (), role="retired", note=step.reason))
        if self.current_loop in sites and not self.yarn_tracking:
            self.current_loop = None

    def hold(self, step: Hold) -> None:
        sites = tuple(site for span in step.spans for site in self.resolve(span))
        # A reserved path is deliberately not re-reservable under a second name.
        self.available(sites, via=step.id)
        for site in sites:
            self.reserved[site] = step.id
        self.edges[step.id, "top"] = sites
        self.holds[step.id] = sites

    def edge_path(self, step: EdgePath) -> None:
        sites: list[Site] = []
        for span in step.spans:
            chunk = self.resolve(span)
            self.available(chunk, via=span.edge)
            sites.extend(chunk)
        if len(set(sites)) != len(sites):
            raise ValueError("工作边重排重复引用同一针位")
        for site in sites:
            self.reserved[site] = step.id
        ordered = tuple(sites)
        self.edges[step.id, "top"] = ordered
        self.holds[step.id] = ordered
        self.events.append(StitchEvent(step.id, "edge_path", ordered, (), role="reference",
                                       note="仅转移已有针位的工作边归属，不钩织、不缝合、不新增针位"))

    def route(self, step: Route) -> None:
        if step.section:
            previous_row = self.section_rows.get(step.section)
            if previous_row is None:
                expected = 1
            else:
                assert previous_row.row_number is not None
                expected = previous_row.row_number + 1
            if step.row_number != expected:
                raise ValueError(f"{step.section} 段内行号应为 {expected}，不能漏行或重复编号")
            if previous_row is not None:
                self.check_turned_continuation(previous_row, step)
            self.section_rows[step.section] = step
        output: list[Site] = []
        bindings = 0
        binding_sites: list[Site] = []
        for op_index, op in enumerate(step.operations):
            if isinstance(op, ChainBridge):
                top = tuple(self.create(Site(op.id, i)) for i in range(1, op.count + 1))
                bottom = tuple(self.create(Site(op.id, i, "underside")) for i in range(1, op.count + 1))
                self.edges[op.id, "top"], self.edges[op.id, "underside"] = top, bottom
                self.chain_sites.update(top + bottom)
                output.extend(top if op.route_face == "top" else bottom)
                self.events.append(StitchEvent(step.id, "chain", (), top + bottom))
                if op.placement == "buttonhole":
                    assert op.skipped is not None
                    skipped = self.resolve(op.skipped)
                    self.available(skipped, via=op.skipped.edge)
                    self.consume(skipped, "both")
                    other = bottom if op.route_face == "top" else top
                    self.consumed.update(other)
                    self.events.append(StitchEvent(step.id, "buttonhole_boundary", skipped + other, (),
                                                   role="retired", note="未工作旧针位和链的另一面保留为孔边"))
                if op.corner_sites:
                    previous = step.operations[op_index - 1]
                    following = step.operations[op_index + 1]
                    assert isinstance(previous, Work) and isinstance(following, Work)
                    ends = (self.resolve(previous.source)[-1], self.resolve(following.source)[0])
                    remaining = bottom if op.route_face == "top" else top
                    for endpoint, anchor, chain_end in zip(
                        ("corner_start", "corner_end"), ends, (remaining[0], remaining[-1]), strict=True,
                    ):
                        face: Face = "corner_start" if endpoint == "corner_start" else "corner_end"
                        corner = self.create(Site(op.id, 1, face))
                        self.edges[op.id, face] = (corner,)
                        self.events.append(StitchEvent(step.id, "corner_site", (anchor, chain_end), (corner,),
                                                       role="reference",
                                                       note="锁针桥与基底连接处的转角入针位"))
                continue
            sites = self.resolve(op.source)
            self.available(sites, via=op.source.edge)
            inputs = 2 if op.stitch == "dec" else 1
            outputs = 2 if op.stitch == "inc" else 1
            if len(sites) % inputs:
                raise ValueError("减针来源须完整两两配对，不能遗留一针")
            for index in range(0, len(sites), inputs):
                parents = sites[index:index + inputs]
                children: tuple[Site, ...]
                if op.disposition == "binding":
                    bindings += 1
                    children = (self.create(Site(step.id, bindings, "binding")),)
                    binding_sites.extend(children)
                    self.consumed.update(children)
                else:
                    children = tuple(self.create(Site(step.id, len(output) + offset + 1))
                                     for offset in range(outputs))
                    output.extend(children)
                self.consume(parents, op.loop)
                self.events.append(StitchEvent(step.id, op.stitch, parents, children,
                                               role=op.disposition, source_loops=(op.loop,) * len(parents)))
        if len(output) != step.expected_sites:
            raise ValueError(f"{step.id} 工作边应有 {step.expected_sites} 个位置，实际 {len(output)} 个")
        self.edges[step.id, "top"] = tuple(output)
        if binding_sites:
            self.edges[step.id, "binding"] = tuple(binding_sites)
        self.rows[step.id] = step
        self.current_loop = binding_sites[-1] if binding_sites else output[-1]
        if step.closure != "none":
            self.events.append(StitchEvent(step.id, "invisible_slip", (output[-1], output[0]), (),
                                           role="closure", note=step.closure))
            self.current_loop = output[0]

    def check_turned_continuation(self, previous: Route, step: Route) -> None:
        """Check the declared section's ordinary turned rows, resolving aliases.

        This verifies order on the preceding row only. It does not infer the
        geometry of an arbitrary pickup path or continuity between sections.
        """
        if step.mode == "segment":
            return
        previous_order = {site: index for index, site in enumerate(self.edges[previous.id, "top"])}
        sources: list[Site] = []
        for op in step.operations:
            if isinstance(op, Work) and op.disposition == "working":
                sources.extend(self.resolve(op.source))
            elif isinstance(op, ChainBridge) and op.skipped is not None:
                sources.extend(self.resolve(op.skipped))
        indices = [previous_order[site] for site in sources if site in previous_order]
        if not indices:
            return
        if previous.turn == "none" or previous.row_direction == step.row_direction:
            raise ValueError(f"{step.id} 连续翻面行须从上一行反向工作，并明确交替行方向")
        if previous.side is None or previous.side == step.side:
            raise ValueError(f"{step.id} 连续翻面行须交替声明正反面")
        if any(a <= b for a, b in zip(indices, indices[1:], strict=False)):
            raise ValueError(f"{step.id} 翻面后的来源顺序须沿上一行反向工作，不能分段跳回")


def compile_working_path(plan: WorkingPath) -> PathResult:
    """Resolve explicit sites, reject reuse/leaks, and retain all source indices."""
    plan = WorkingPath.model_validate(plan.model_dump())
    if plan.schema_version == "working-path-v1":
        for step in plan.steps:
            if (not isinstance(step, (Route, Hold))
                or isinstance(step, Route) and (
                    step.mode != "segment" or step.gauge is not None
                    or any(isinstance(op, Work) and (op.stitch not in ("sc", "inc", "dec")
                                                    or op.loop != "both" or op.disposition != "working")
                           or isinstance(op, ChainBridge) and (op.corner_sites or op.placement != "bridge")
                           for op in step.operations)
                )):
                raise ValueError("这些工序需要 working-path-v2 格式，不能冒充旧版能力")
    gauge_ids = {gauge.id for gauge in plan.gauges}
    if len(gauge_ids) != len(plan.gauges):
        raise ValueError("密度 ID 不可重复")
    if any(isinstance(step, Route) and step.gauge is not None and step.gauge not in gauge_ids
           for step in plan.steps):
        raise ValueError("工序引用的密度不存在")
    ids = [edge.id for edge in plan.existing_edges] + [step.id for step in plan.steps]
    ids += [op.id for step in plan.steps if isinstance(step, Route)
            for op in step.operations if isinstance(op, ChainBridge)]
    if len(ids) != len(set(ids)):
        raise ValueError("已有边、工序、保留边和锁针桥的 ID 不可重复")
    if len(plan.final_edges) != len(set(plan.final_edges)):
        raise ValueError("最终工作边不可重复")
    compiler = _Compiler(yarn_tracking=plan.yarn_tracking)
    for edge in plan.existing_edges:
        compiler.edges[edge.id, "top"] = tuple(compiler.create(Site(edge.id, i))
                                               for i in range(1, edge.count + 1))
    for step in plan.steps:
        start = len(compiler.events)
        if isinstance(step, (Route, FoundationChain, Seam)):
            compiler.before_work(step)
        if isinstance(step, Hold):
            compiler.hold(step)
        elif isinstance(step, EdgePath):
            compiler.edge_path(step)
        elif isinstance(step, Route):
            compiler.route(step)
        elif isinstance(step, FoundationChain):
            compiler.foundation(step)
        elif isinstance(step, RowEdges):
            compiler.row_edges(step)
        elif isinstance(step, FreeLoops):
            compiler.loops(step)
        elif isinstance(step, Seam):
            compiler.seam(step)
        elif isinstance(step, (NewYarn, FastenOff, ParkYarn, ResumeYarn, WeaveEnds)):
            compiler.yarn_control(step)
        else:
            compiler.finish(step)
        if isinstance(step, (Route, FoundationChain, Seam)):
            compiler.after_work(step, start)
    final: dict[str, tuple[Site, ...]] = {}
    exposed: set[Site] = set()
    for name in plan.final_edges:
        sites = compiler.edges.get((name, "top"))
        if sites is None:
            raise ValueError(f"最终工作边不存在：{name}")
        compiler.available(sites, via=name)
        if exposed.intersection(sites):
            raise ValueError("最终工作边通过别名重复列出同一针位")
        exposed.update(sites)
        final[name] = sites
    unused = compiler.sites - compiler.consumed
    if exposed != unused:
        raise ValueError(f"有 {len(unused - exposed)} 个未使用针位未声明去向；须保留或继续钩织")
    return PathResult(plan, tuple(compiler.events),
                      {name: sites for (name, face), sites in compiler.edges.items() if face == "top"},
                      compiler.holds, final, len(compiler.sites), len(compiler.consumed),
                      compiler.yarn_report())


def armhole_path_demo() -> WorkingPath:
    """An original synthetic inventory exercise, not a recovered doll pattern.

    Its counts are chosen for inspecting routes, not for a wearable garment.
    Corner pickups, fit, turns, shaping and neckline/hem construction are absent.
    """
    def span(edge, first, last, *, face="top", direction="forward"):
        return Span(edge=edge, first=first, last=last, face=face, direction=direction)

    return WorkingPath(
        title="袖窿工作路径演示小样（不是完整衣物图解）",
        existing_edges=[ExistingEdge(id="yoke", count=28)],
        steps=[
            Route(id="body_edge", label="分出衣身与两侧开口", expected_sites=22, operations=[
                Work(source=span("yoke", 1, 4)), ChainBridge(id="left_bridge", count=3, route_face="top"),
                Work(source=span("yoke", 11, 18)), ChainBridge(id="right_bridge", count=3, route_face="top"),
                Work(source=span("yoke", 25, 28)),
            ]),
            Hold(id="left_opening", label="保留左袖窿工作边", spans=[
                span("yoke", 5, 10), span("left_bridge", 1, 3, face="underside", direction="reverse"),
            ]),
            Hold(id="right_opening", label="保留右袖窿工作边", spans=[
                span("yoke", 19, 24), span("right_bridge", 1, 3, face="underside", direction="reverse"),
            ]),
            Route(id="left_sleeve", label="沿左袖窿继续一段", expected_sites=9,
                  operations=[Work(source=span("left_opening", 1, 9))]),
            Route(id="right_sleeve", label="沿右袖窿继续一段", expected_sites=9,
                  operations=[Work(source=span("right_opening", 1, 9))]),
        ], final_edges=["body_edge", "left_sleeve", "right_sleeve"],
    )
