"""Explicit, checked references to reserved loops on another component."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.models.instruction_checks import round_expression
from app.models.parts import _ONE_PIECE_NAME
from app.models.profile_shaping import strip_dome
from app.models.stitch_notation import NotationError, format_stitch_expression


class LoopAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_part: str = Field(min_length=1, max_length=80)
    source_row: Literal[1] = 1
    target_part: str = Field(min_length=1, max_length=80)
    target_row: int = Field(ge=1)
    reservation_row: int = Field(ge=2)
    start_stitch: Literal[1] = 1
    end_stitch: int = Field(ge=1)
    loop: Literal["BLO"] = "BLO"

    @field_validator("source_row", "start_stitch", mode="before")
    @classmethod
    def _integer_literal(cls, value):
        if type(value) is not int:
            raise ValueError("针目/圈号须为整数")
        return value


class LoopAttachmentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1"] = "1"
    connections: list[LoopAttachment] = Field(default_factory=list, max_length=40)


def attachment_steps(connection: LoopAttachment) -> str:
    c = connection
    return (
        f"接合准备：钩{c.target_part}第 {c.reservation_row} 圈时，按该圈 FLO 操作式"
        f"只挑第 {c.target_row} 圈的前半针，保留其第 1–{c.end_stitch} 针的后半针。"
        f"身体余下圈按图解完成，再接入裙线，将{c.source_part}第 1 圈钩入这些后半针，每个针目钩 1 短针，"
        f"共 {c.end_stitch} 针；从基底圈记号扣对应的第 1 针开始，按原圈序一一对应。"
        "多份部件按第 1 件接第 1 件依次配对。接合位置为模板腰位，需试钩确认；无需缝合。"
    )


def _all_loops(expression, loop: str) -> bool:
    if expression.stitch is not None:
        return expression.stitch.endswith("-" + loop)
    return bool(expression.children) and all(_all_loops(child, loop) for child in expression.children)


def attachment_issues(params: dict, *, check_notes: bool = True) -> tuple[list[str], list[str]]:
    """Legacy patterns remain readable; declared references are never guessed."""
    parts = {p.get("name"): p for p in params.get("parts", []) if isinstance(p, dict)}
    attached = params.get("skirt_style") == "attached" and "裙子" in parts
    if "stitch_attachments" not in params:
        return [], (["旧接裙图解未记录精确基底圈及预留圈；请重新生成或人工核对后再钩织"] if attached else [])
    try:
        plan = LoopAttachmentPlan.model_validate(params["stitch_attachments"])
    except ValidationError:
        return ["接合记录格式无效：请核对版本、圈号与针目范围"], []
    issues: list[str] = []
    sources: set[str] = set()
    targets: set[tuple[str, int]] = set()
    dependencies = {c.source_part: c.target_part for c in plan.connections}
    for source_name in dependencies:
        visited: set[str] = set()
        current = source_name
        while current in dependencies:
            if current in visited:
                issues.append("接合记录存在循环依赖，无法先建立基底部件")
                break
            visited.add(current)
            current = dependencies[current]
    for c in plan.connections:
        label = f"{c.source_part}接合"
        if c.source_part in sources or (c.target_part, c.target_row) in targets:
            issues.append(f"{label}：源部件或预留针目被重复使用")
        sources.add(c.source_part)
        targets.add((c.target_part, c.target_row))
        source, target = parts.get(c.source_part), parts.get(c.target_part)
        if not source or not target or source is target:
            issues.append(f"{label}：引用的源/目标部件不存在或相同")
            continue
        if source.get("quantity", 1) != target.get("quantity", 1):
            issues.append(f"{label}：源部件与目标部件数量须一一对应")
        if c.source_part == "裙子" and params.get("skirt_style") != "attached":
            issues.append(f"{label}：做法与挑针接合记录不一致")
        graph = params.get("assembly_plan")
        if graph is not None:
            links = graph.get("connections") if isinstance(graph, dict) else None
            if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
                issues.append(f"{label}：结构连接图格式无效")
            else:
                related = [link for link in links if link.get("source_part_name") == c.source_part]
                expected_target = "身体" if c.target_part == _ONE_PIECE_NAME else c.target_part
                if (len(related) != source.get("quantity", 1)
                        or any(link.get("target_part_name") != expected_target
                               or link.get("method") != "crocheted_or_sewn"
                               or link.get("self_anchor") != "opening" for link in related)
                        or (c.source_part == "裙子"
                            and any(link.get("target_anchor") != "waist" for link in related))):
                    issues.append(f"{label}：针目接合记录与结构连接位置或做法不一致")
        source_rounds, target_rounds = source.get("rounds", []), target.get("rounds", [])
        if not isinstance(source_rounds, list) or not isinstance(target_rounds, list):
            issues.append(f"{label}：缺少有效圈序")
            continue
        lookup = {r.get("row"): (i, r) for i, r in enumerate(target_rounds) if isinstance(r, dict)}
        base = lookup.get(c.target_row)
        reserve = lookup.get(c.reservation_row)
        if not source_rounds or not base or not reserve or reserve[0] != base[0] + 1:
            issues.append(f"{label}：预留操作必须位于基底圈的下一圈")
            continue
        first = source_rounds[0]
        if (not isinstance(first, dict) or first.get("row") != c.source_row
                or source.get("magic_ring") is not False):
            issues.append(f"{label}：接入圈必须是非魔法环的第 1 圈")
            continue
        n = base[1].get("stitches")
        if (n != c.end_stitch or first.get("stitches") != n
                or first.get("increase", 0) or first.get("decrease", 0)):
            issues.append(f"{label}：接入针数、基底针数及第 1–{c.end_stitch} 针范围不匹配")
        if check_notes:
            try:
                prepared = round_expression(reserve[1].get("notes"))
                joined = round_expression(first.get("notes"))
                if prepared is None or not _all_loops(prepared, "FLO") or prepared.counts.consumed != n:
                    issues.append(f"{label}：身体预留圈须明确全圈 FLO，消耗基底圈全部针目")
                if joined is None or not _all_loops(joined, "BLO") or joined.counts.consumed != n:
                    issues.append(f"{label}：接入圈须明确全圈 BLO，使用已预留的全部针目")
            except NotationError:
                issues.append(f"{label}：挑针操作式不明确或相互冲突")
    if attached and "裙子" not in sources:
        issues.append("挑针接裙做法缺少裙子的接合记录")
    return issues, []


def prepare_attached_skirt(parts: list[dict], *, body_rows: tuple[int, int] | None = None,
                           assembly_plan: dict | None = None) -> dict:
    """Compile the generated skirt against actual body rounds, before validation."""
    from app.models.crochet_params import _change_note, bridge_rounds

    skirt = next((p for p in parts if p["name"] == "裙子"), None)
    if skirt is None:
        return LoopAttachmentPlan().model_dump()
    body = next((p for p in parts if p["name"] in ("身体", _ONE_PIECE_NAME)), None)
    if body is None:
        raise ValueError("挑针接裙需要身体部件；请添加身体或选择独立裙筒")
    if skirt.get("quantity", 1) != body.get("quantity", 1):
        raise ValueError("挑针接裙需要裙子与身体数量相同")
    if assembly_plan is not None:
        links = [c for c in assembly_plan["connections"] if c["source_part_name"] == "裙子"]
        if (len(links) != skirt.get("quantity", 1)
                or any(c["target_part_name"] != "身体" or c["target_anchor"] != "waist"
                       or c["method"] != "crocheted_or_sewn" or c["self_anchor"] != "opening"
                       for c in links)):
            raise ValueError("挑针接裙需要每件裙子连接身体腰部；请修正结构连接或选择独立裙筒")
    rounds = body["rounds"]
    if body_rows is None:
        wall = strip_dome([r["stitches"] for r in rounds])
        start, end = len(rounds) - len(wall), len(rounds)
    else:
        start, end = body_rows[0] - 1, body_rows[1]
    if end - start < 2:
        raise ValueError("身体筒壁不足两圈，无法明确预留接裙针目；请增加高度或选择独立裙筒")
    desired = start + (end - start - 2) * (0.4 if body_rows else 0.6)
    waist = skirt["rounds"][0]["stitches"]
    candidates = list(range(start, end - 1))
    matching = [i for i in candidates if rounds[i]["stitches"] == waist]
    index = min(matching or candidates, key=lambda i: abs(i - desired))
    base, reserve = rounds[index:index + 2]
    expression = round_expression(reserve["notes"])
    if expression is None:
        raise ValueError("身体预留圈缺少可识别的针法操作式")
    _, _, suffix = reserve["notes"].partition("；")
    reserve["notes"] = "FLO(" + format_stitch_expression(expression) + ")；为裙子保留接合位，见装配说明"
    if suffix:
        reserve["notes"] += "；" + suffix
    old = skirt["rounds"]
    ruffle = bool(old[-1].get("allow_wide_jump"))
    hem = old[-2 if ruffle else -1]["stitches"]
    waist = base["stitches"]
    counts = [waist] + bridge_rounds(waist, hem)
    counts += [hem] * max(1, len(old) - int(ruffle) - len(counts))
    if ruffle:
        counts.append(hem * 2)
    rebuilt = []
    old_main = len(old) - int(ruffle)
    new_main = len(counts) - int(ruffle)
    for i, n in enumerate(counts):
        # Preserve photo colors at normalized heights and the ruffle's own color.
        source_index = (len(old) - 1 if ruffle and i == len(counts) - 1
                        else round(i * (old_main - 1) / max(1, new_main - 1)))
        row = dict(old[source_index])
        row.update(row=i + 1, stitches=n, increase=max(0, n - counts[i - 1]) if i else 0,
                   decrease=max(0, counts[i - 1] - n) if i else 0,
                   allow_wide_jump=bool(ruffle and i == len(counts) - 1),
                   notes=(f"BLO({n}X)；接入预留针目，具体圈号见装配说明"
                          if i == 0 else _change_note(counts[i - 1], n)))
        if row["allow_wide_jump"]:
            row["notes"] = f"V×{hem}；波浪裙摆"
        rebuilt.append(row)
    skirt["rounds"] = rebuilt
    skirt["magic_ring"] = False
    connection = LoopAttachment(source_part="裙子", target_part=body["name"],
                                target_row=base["row"], reservation_row=reserve["row"], end_stitch=waist)
    return LoopAttachmentPlan(connections=[connection]).model_dump()
