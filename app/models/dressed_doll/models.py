"""Bounded construction IR with distinct foundations, rows, rounds and joins."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.stitch_notation import non_sc_symbols, parse_stitch_expression

Count = Annotated[int, Field(strict=True, ge=1, le=1000)]
Dimension = Annotated[float, Field(gt=0, le=100)]
Label = Annotated[str, Field(min_length=1, max_length=120)]


class DesignModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class DollDesign(DesignModel):
    schema_version: Literal["dressed-doll-design-v1"] = "dressed-doll-design-v1"
    height_cm: Annotated[float, Field(ge=16, le=60)] = 24
    head_diameter_cm: Dimension = 6
    leg_length_cm: Dimension = 6
    body_diameter_cm: Dimension = 3.6
    neck_diameter_cm: Dimension = 1.2
    arm_length_cm: Dimension = 6
    palm_diameter_cm: Dimension = 1.5
    wrist_diameter_cm: Dimension = 0.9
    foot_length_cm: Dimension = 3
    foot_width_cm: Dimension = 1.6
    hat: Literal["wide_brim", "folded_band"] = "wide_brim"
    brim_width_cm: Dimension = 1.8
    hair: Literal["curls", "straight"] = "curls"
    hair_strands: Annotated[int, Field(strict=True, ge=4, le=20)] = 12
    hair_chain_count: Annotated[int, Field(strict=True, ge=6, le=120)] = 16
    outfit: Literal["dress", "jacket_skirt"] = "dress"
    bodice_length_cm: Dimension = 5.4
    skirt_length_cm: Dimension = 7
    skirt_layers: Literal[1, 2] = 2
    garment_ease_cm: Annotated[float, Field(ge=0.5, le=4)] = 1
    bag_width_cm: Dimension = 4
    bag_height_cm: Dimension = 4.5
    strap_length_cm: Dimension = 20
    flowers: bool = True
    stitches_per_10cm: Annotated[float, Field(ge=6, le=40)] = 22
    rows_per_10cm: Annotated[float, Field(ge=8, le=50)] = 28

    @field_validator("skirt_layers", mode="before")
    @classmethod
    def integer_layer_count(cls, value):
        if isinstance(value, bool):
            raise ValueError("裙层数量必须是整数 1 或 2")
        return value

    @model_validator(mode="after")
    def coherent_dimensions(self) -> DollDesign:
        if self.height_cm - self.head_diameter_cm - self.leg_length_cm < 3:
            raise ValueError("总高须为头部、腿部以外留下至少 3cm 的身体与颈部设计空间")
        if self.neck_diameter_cm >= self.body_diameter_cm:
            raise ValueError("颈部直径须小于身体直径")
        if self.wrist_diameter_cm >= self.palm_diameter_cm:
            raise ValueError("掌腕分段要求手掌直径大于手腕直径")
        if self.foot_length_cm < self.foot_width_cm:
            raise ValueError("鞋底长度须不小于宽度")
        if self.skirt_length_cm > self.height_cm - self.head_diameter_cm:
            raise ValueError("裙长不能超过头部以外的目标长度")
        if self.bodice_length_cm > self.height_cm - self.head_diameter_cm:
            raise ValueError("上衣长度不能超过头部以外的目标长度")
        return self


class Foundation(DesignModel):
    kind: Literal["magic_ring", "chain_ring", "flat_chain", "oval_chain"]
    chains: Annotated[int, Field(strict=True, ge=0, le=1000)] = 0

    @model_validator(mode="after")
    def valid_chain_count(self) -> Foundation:
        if self.kind == "magic_ring" and self.chains != 0:
            raise ValueError("魔法环不额外声明锁针起针")
        minimum = {"chain_ring": 3, "flat_chain": 2, "oval_chain": 3}.get(self.kind, 0)
        if self.chains < minimum:
            raise ValueError(f"{self.kind} 起针至少需要 {minimum} 个锁针")
        return self


class WorkStep(DesignModel):
    number: Count
    section: Label
    expression: Annotated[str, Field(min_length=1, max_length=2000)]
    stitches: Count
    turning_chain: Annotated[int, Field(strict=True, ge=0, le=1)] = 0
    loops: Literal["both", "front", "back"] = "both"
    note: str = Field(default="", max_length=1500)


class Component(DesignModel):
    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    name: Label
    role: Label
    quantity: Annotated[int, Field(strict=True, ge=1, le=20)] = 1
    work: Literal["rounds", "rows"]
    foundation: Foundation
    steps: list[WorkStep] = Field(min_length=1, max_length=600)
    finish: str = Field(min_length=1, max_length=2000)
    fitting: list[str] = Field(default_factory=list, max_length=12)
    color: Label = "待选色"

    @model_validator(mode="after")
    def executable_stitch_inventory(self) -> Component:
        if (self.work == "rows") != (self.foundation.kind == "flat_chain"):
            raise ValueError("片钩须用 flat_chain；圈钩须用环形或椭圆起针")
        previous = None
        for index, step in enumerate(self.steps, 1):
            if step.number != index:
                raise ValueError(f"{self.id} 的步骤编号须连续")
            expression = parse_stitch_expression(step.expression)
            if expression is None:
                raise ValueError(f"{self.id} 含不可解析的针法操作式")
            if non_sc_symbols(expression):
                raise ValueError("本版结构方案只支持短针、加针与减针；其他针高须另做密度模型")
            counts = expression.counts
            if counts.produced != step.stitches:
                raise ValueError(f"{self.id} 第 {index} 步产出针数与操作式不符")
            expected_turn = int(self.work == "rows" and index > 1)
            if step.turning_chain != expected_turn:
                raise ValueError("短针片钩每后续行须锁 1 针翻转，该锁针不计入行针数")
            if previous is None:
                chain_count = self.foundation.chains
                expected = {"flat_chain": chain_count - 1, "chain_ring": chain_count,
                            "oval_chain": 2 * chain_count - 4}.get(self.foundation.kind)
                if expected is not None and counts.consumed != expected:
                    raise ValueError(f"{self.id} 首步消耗与起针工作边不符")
                if self.foundation.kind == "oval_chain":
                    # Two end anchors receive W; each middle chain is worked on both sides.
                    straight = chain_count - 3
                    middle = f",{straight}X" if straight else ""
                    if step.expression != f"W{middle},W{middle}":
                        raise ValueError("椭圆首圈须明确两端各 3 短针及锁针两侧的直边")
                if self.foundation.kind == "magic_ring" and counts.increase + counts.decrease:
                    raise ValueError("魔法环首圈须直接声明短针数")
            elif counts.consumed != previous:
                raise ValueError(f"{self.id} 第 {index} 步未完整消耗上一行/圈针目")
            previous = step.stitches
        return self

    @property
    def operations_per_copy(self) -> int:
        return self.foundation.chains + sum(s.stitches + s.turning_chain for s in self.steps)


class Join(DesignModel):
    source: Label
    target: Label
    placement: str = Field(min_length=1, max_length=1200)


class DollPlan(DesignModel):
    schema_version: Literal["dressed-doll-plan-v1"] = "dressed-doll-plan-v1"
    status: Literal["unverified_prototype"] = "unverified_prototype"
    input_origin: Literal["manual_design"] = "manual_design"
    design: DollDesign
    components: list[Component] = Field(min_length=1, max_length=64)
    joins: list[Join] = Field(min_length=1, max_length=100)
    assembly: list[str] = Field(min_length=1, max_length=40)
    limitations: list[str] = Field(min_length=1, max_length=20)
    trial_checkpoints: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def complete_graph(self) -> DollPlan:
        ids = {p.id for p in self.components}
        if len(ids) != len(self.components):
            raise ValueError("部件 ID 不能重复")
        if sum(len(p.steps) for p in self.components) > 6000:
            raise ValueError("结构方案合计步骤超过 6000 步")
        if self.total_operations > 500_000:
            raise ValueError("结构方案针目操作数超过上限")
        seen = set()
        graph: dict[str, list[str]] = {key: [] for key in ids}
        for join in self.joins:
            if join.source not in ids or join.target not in ids or join.source == join.target:
                raise ValueError("装配关系引用了不存在或相同的部件")
            key = (join.source, join.target)
            if key in seen:
                raise ValueError("装配关系不能重复")
            seen.add(key)
            graph[join.source].append(join.target)
        for start in ids:
            pending = list(graph[start])
            visited = set()
            while pending:
                node = pending.pop()
                if node == start:
                    raise ValueError("装配关系不能成环")
                if node not in visited:
                    visited.add(node)
                    pending.extend(graph[node])
        unconnected = ids - {j.source for j in self.joins}
        if unconnected != {"body"}:
            raise ValueError("除身体根部件外，每个部件都须声明装配去向")
        return self

    @property
    def total_operations(self) -> int:
        return sum(p.quantity * p.operations_per_copy for p in self.components)
