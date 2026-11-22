"""装配说明：按 v2 连接图逐实例生成缝合步骤，旧格式回退名称模板。

从 crochet_params 拆出；_CLOSING_RE 的闭合语义与开口统计一并随迁。
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from ..schemas import PART_LABELS_ZH, PartKind, part_kind_from_name
from .parts import _ONE_PIECE_NAME, _part_name, _part_rounds, _round_stitches, same_round

# 末圈注记里的闭合语义："收口/勒紧收口/无痕收口"=已闭合；"不收口/勿收口/
# 未收口/没收口"是开口声明——负向断言排除这些前导字（中文社区头套
# "开口保留…不收口"；"未收口"变体此前会被误判为已闭合而丢失开口）
_CLOSING_RE = re.compile(r"(?<![不勿未没别])收口")


def joining_round(part: Mapping[str, Any]) -> dict | None:
    """Resolve one actual joining row, sharing the legacy fallback rules."""
    rounds = _part_rounds(part)
    if not rounds:
        return None
    selected = part.get("opening_row")
    if part.get("connection_state") == "closed":
        return None
    if part.get("connection_state") == "open":
        return next((rd for rd in rounds if same_round(rd.get("row"), selected)), None)
    row = (next(rd for rd in rounds if rd["row"] == selected) if selected is not None
           else rounds[0] if part_kind_from_name(_part_name(part)) is PartKind.SKIRT else rounds[-1])
    return None if _CLOSING_RE.search(str(row.get("notes") or "")) else row


def opening_rows_by_part(parts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {_part_name(p): row["row"] for p in parts
            if (row := joining_round(p)) is not None and "row" in row
            and (part_kind_from_name(_part_name(p)) is not PartKind.HEAD or p.get("opening_row") is not None)}


def _openings_by_part(parts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Resolve the declared joining round; legacy skirts join at their first row.

    专业图解装配段的通行惯例：缝合前先报开口针数（"sew the remaining
    12 sts to the body"）。球体头部以"无痕收口"完全闭合，无开口；
    圆柱四肢以"断线留15cm用于缝合"收尾留口；帽/裙明确不收口。
    """
    openings: dict[str, int] = {}
    for p in parts:
        if (row := joining_round(p)) is not None:
            openings[_part_name(p)] = _round_stitches(row)
    return openings


def hat_fit_note(parts: Sequence[Mapping[str, Any]], gauge: Mapping[str, Any] | None) -> str:
    """Estimated hat rim against the widest head round, each by its own gauge.

    Stitch counts times stitch width: an estimate from the input gauge, not a
    measurement and not a fit guarantee. A hat may carry a gauge of its own, so
    raw stitch counts are never compared. Returns "" when the pattern has no
    hat, no head to compare with, or no recorded gauge. This belongs to the
    assembly text, not to the hat part: a hat with a fixed gauge must stay
    unchanged when the rest of the pattern is regenerated.
    """
    def width(part: Mapping[str, Any]) -> float | None:
        own = part.get("gauge") or gauge
        try:
            stitches = float(own["stitches_per_10cm"]) if own else 0.0
        except (KeyError, TypeError, ValueError):
            return None
        return 10.0 / stitches if stitches > 0 else None

    hat = next((p for p in parts if part_kind_from_name(_part_name(p)) is PartKind.HAT
                and p.get("type") == "cup" and _part_rounds(p)), None)
    head_rounds: list[dict[str, Any]] = []
    head = None
    for part in parts:
        rounds = _part_rounds(part)
        if part_kind_from_name(_part_name(part)) is PartKind.HEAD:
            head, head_rounds = part, list(rounds)
        elif _part_name(part) == _ONE_PIECE_NAME and isinstance(part.get("neck_row"), int):
            head, head_rounds = part, [rd for rd in rounds if rd.get("row", 0) <= part["neck_row"]]
        if head_rounds:
            break
    if hat is None or head is None or not head_rounds:
        return ""
    hat_width, head_width = width(hat), width(head)
    if hat_width is None or head_width is None:
        return ""
    widest = max(_round_stitches(rd) for rd in head_rounds)
    rim_cm, head_cm = _round_stitches(_part_rounds(hat)[-1]) * hat_width, widest * head_width
    difference = round(rim_cm, 1) - round(head_cm, 1)
    measured = f"按密度估算，帽口周长约 {rim_cm:.1f}cm，头部最宽圈（{widest} 针）约 {head_cm:.1f}cm"
    if difference > 0.05:
        return (f"{measured}，帽口多约 {difference:.1f}cm；这是估算不是实测，头发或发帽还要占余量。"
                "先试戴，合适后再缝合固定")
    if difference > -0.05:
        return (f"{measured}，两者相同，没有余量，可能偏紧；这是估算不是实测。"
                "先试戴，偏紧就把帽子直径改大后重新生成")
    return (f"{measured}，帽口少约 {-difference:.1f}cm，可能戴不过头部最宽处；这是估算不是实测。"
            "先试戴，戴不上就把帽子直径改大后重新生成")


def assembly_for_pattern(params: Mapping[str, Any]) -> str:
    """Render declared loop references from current data, not stale saved prose."""
    if "stitch_attachments" not in params and params.get("head_opening_stitches") is None:
        return params.get("assembly_instructions") or ""
    parts = params.get("parts", [])
    quantities = {_part_name(p): int(p.get("quantity", 1)) for p in parts}
    return build_assembly(set(quantities), params.get("skirt_style", "ring"), quantities,
                          params.get("assembly_plan"), _openings_by_part(parts),
                          params.get("stitch_attachments"),
                          opening_rows=opening_rows_by_part(parts),
                          updated_guidance=params.get("construction_guidance_version") == 1,
                          hat_fit=hat_fit_note(parts, params.get("gauge")))


def build_assembly(part_names, skirt_style: str = "ring",
                   quantities: dict[str, int] | None = None,
                   assembly_plan: dict[str, Any] | None = None,
                   openings: dict[str, int] | None = None,
                   stitch_attachments: dict | None = None, *,
                   opening_rows: dict[str, int] | None = None,
                   updated_guidance: bool = True, hat_fit: str = "") -> str:
    """Build assembly text from the v2 graph, with a legacy name fallback."""
    quantities = quantities or {}
    openings = openings or {}
    opening_rows = opening_rows or {}
    part_kinds = {part_kind_from_name(name) for name in part_names}
    openings_by_kind = {kind: value for name, value in openings.items()
                        if (kind := part_kind_from_name(name)) is not None}
    rows_by_kind = {kind: value for name, value in opening_rows.items()
                    if (kind := part_kind_from_name(name)) is not None}

    def saved_name(name: str | PartKind) -> str:
        return PART_LABELS_ZH[name] if isinstance(name, PartKind) else name

    def head_connection() -> str:
        head_n = openings_by_kind.get(PartKind.HEAD)
        if head_n is None or PartKind.HEAD not in rows_by_kind:
            orientation = "头部第 1 圈为头顶，末圈收口一侧为头底；" if updated_guidance else ""
            reference = "" if updated_guidance else "（AmiguRoom 俄语熊评论区试钩共识）"
            return (orientation + "用隐形缝合法将头部接合到身体顶部；"
                    "头颈缝合处塞棉紧实，防止头部前倾" + reference)
        head_row = f"第 {rows_by_kind[PartKind.HEAD]} 圈" if PartKind.HEAD in rows_by_kind else "末圈"
        body_row = f"第 {rows_by_kind[PartKind.BODY]} 圈" if PartKind.BODY in rows_by_kind else "末圈"
        body_n = openings_by_kind.get(PartKind.BODY)
        target = f"身体顶部{body_row}开口（{body_n} 针）" if body_n else "身体顶部（开口待核对）"
        note = f"将头部{head_row}颈口（{head_n} 针）与{target}缝合；"
        if body_n is not None and head_n != body_n:
            note += "两侧针数不同，请人工核对对齐位置与缝合分配；"
        return note + "填充后逐段固定，头颈支撑与成品比例需试钩确认"

    def skirt_connection() -> str:
        from .stitch_attachments import LoopAttachmentPlan, attachment_steps

        if stitch_attachments is not None:
            plan = LoopAttachmentPlan.model_validate(stitch_attachments)
            for connection in plan.connections:
                if part_kind_from_name(connection.source_part) is PartKind.SKIRT:
                    return attachment_steps(connection)
        return "接裙位置待核对：旧图解未记录精确基底圈及预留圈，请先核对或重新生成后再钩织。"

    def hat_step(hat_open: str) -> str:
        # Patterns made under the older guidance keep their original sentence.
        if not (updated_guidance and hat_fit):
            return f"{hat_open}不收口，直接戴在头部（试戴后可缝合固定）"
        return f"{hat_open}不收口，戴在头部。{hat_fit}"

    def opening_note(name: str | PartKind) -> str:
        name = saved_name(name)
        n = openings.get(name)
        if not n:
            return ""
        # 垂耳兔等社区图解惯例：极小开口捏扁缝合（可免填充）
        flat = "，小开口可捏扁缝合" if n <= 6 else ""
        return f"（开口 {n} 针{flat}）"

    def placement(name: str | PartKind, paired: str, single: str, many: str) -> str:
        name = saved_name(name)
        quantity = max(1, int(quantities.get(name, 1)))
        if quantity == 1:
            return single
        if quantity == 2:
            return paired
        return f"{name}共 {quantity} 个，{many}"

    one_piece = _ONE_PIECE_NAME in part_names
    steps: list[str] = [] if updated_guidance else ["按各部件标注数量分别完成并填充棉花"]
    if updated_guidance and PartKind.SKIRT in part_kinds and skirt_style != "attached":
        entry = "一体件在身体底端收口前从底端套入" if one_piece else "从颈口一端套入"
        steps.append(
            "独立裙筒先试套：身体未填棉、相邻部件未缝合时，"
            f"{entry}裙腰暂留腰位；过紧勿强拉，须改图重试并新建试钩记录")
    if updated_guidance and (PartKind.HEAD in part_kinds or one_piece):
        steps.append(
            "头部安全眼按部件说明的具体圈号定位；在填充和封口前安装并扣好内侧垫片")
    if PartKind.BODY in part_kinds or one_piece:
        steps.append(
            "可选配重：配重珠装入丝袜打结，身体减针前置底再填棉（3 岁以下儿童玩偶勿用）"
            if updated_guidance else
            "可选：坐/站姿增稳——配重珠约 3/4 杯装入丝袜打结，于身体开始"
            "减针、开口尚能伸手时置入底部，再正常填充（Grace and Yarn；"
            "3 岁以下儿童玩偶勿用）")
    if updated_guidance:
        steps.append("按部件标注数量制作，在开口缩小或封口前分次填充棉花，再进行下列缝合")
    if one_piece:
        steps.append("一体件钩完头部后先填充头部再继续钩身体（分阶段填充）")
    if PartKind.HEAD in part_kinds or one_piece:
        if not updated_guidance:
            steps.append("头部安装安全眼（第2/3高度处）")
        steps.append("用黑色毛线绣鼻子和嘴巴")
        steps.append(
            "可选：针塑形（needle sculpting）——同色线自一侧眼位入针、横穿至对侧再穿回，"
            "两端自同一针孔拉紧打结藏线，形成眼窝凹陷"
            if updated_guidance else
            "可选：针塑形（needle sculpting）——长针带同色线自一侧眼位"
            "入针、横穿头内至对侧眼位再穿回，两端自同一针孔拉紧打结藏线，"
            "形成眼窝凹陷（PlanetJune needlesculpting；本图解塑形已内建，"
            "此步仅在想要更立体五官时使用）")

    # Old backups have no graph.  Keep their established name-based behavior
    # rather than pretending to infer missing connection nodes during import.
    if assembly_plan is None:
        if PartKind.HEAD in part_kinds and PartKind.BODY in part_kinds and not one_piece:
            steps.append(head_connection())
        if PartKind.ARMS in part_kinds:
            steps.append(placement(
                PartKind.ARMS, f"手臂对称缝合到身体两侧上方{opening_note(PartKind.ARMS)}",
                f"手臂缝合到身体一侧上方{opening_note(PartKind.ARMS)}",
                f"均匀缝合到身体上部{opening_note(PartKind.ARMS)}"))
        if PartKind.LEGS in part_kinds:
            steps.append(placement(
                PartKind.LEGS, f"腿部对称缝合到身体底部{opening_note(PartKind.LEGS)}",
                f"腿部缝合到身体底部{opening_note(PartKind.LEGS)}",
                f"均匀缝合到身体底部{opening_note(PartKind.LEGS)}"))
        if PartKind.EARS in part_kinds:
            steps.append(placement(
                PartKind.EARS, "耳朵对称缝合在头部两侧",
                "耳朵缝合在头部一侧", "均匀缝合在头部周围"))
        if PartKind.HAT in part_kinds:
            hat_n = openings_by_kind.get(PartKind.HAT)
            hat_open = f"帽口 {hat_n} 针" if hat_n else "帽口"
            steps.append(hat_step(hat_open))
        if PartKind.SKIRT in part_kinds:
            if skirt_style == "attached":
                steps.append(skirt_connection())
            else:
                skirt_n = openings_by_kind.get(PartKind.SKIRT)
                skirt_open = f"（{skirt_n} 针开口）" if skirt_n else ""
                steps.append(
                    f"将预先套入身体的裙筒腰部{skirt_open}调整到腰位后缝合固定"
                    if updated_guidance else
                    f"裙筒腰部{skirt_open}套入身体后缝合固定（腰部为开口起针）")
        if PartKind.TAIL in part_kinds:
            steps.append("尾巴缝合在身体后方")
        return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))

    def effective_name(name: str) -> str:
        if one_piece and part_kind_from_name(name) in (PartKind.HEAD, PartKind.BODY):
            return _ONE_PIECE_NAME
        return name

    raw_connections = (assembly_plan.get("connections", [])
                       if isinstance(assembly_plan, dict) else [])
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for connection in raw_connections:
        if not isinstance(connection, dict):
            continue
        source = effective_name(str(connection.get("source_part_name") or ""))
        target = effective_name(str(connection.get("target_part_name") or ""))
        if (not source or not target or source == target
                or source not in part_names or target not in part_names):
            continue
        # Preserve the original target region when head/body become one piece.
        key = (source, target, str(connection.get("method") or "sewn"),
               str(connection.get("target_part_name") or ""))
        grouped.setdefault(key, []).append(connection)

    connected_sources = set()
    anchor_labels = {
        "top": "顶部", "bottom": "底部", "back": "后方", "front": "前方",
        "waist": "腰部", "side_left": "左侧", "side_right": "右侧",
        "upper_left": "左侧上方", "upper_right": "右侧上方",
        "bottom_left": "左侧底部", "bottom_right": "右侧底部",
        "inner_end": "内端", "base": "根部", "opening": "开口", "tip": "末端",
    }
    # Familiar prose is valid only for the actual template edge configuration.
    # An edited anchor/method must reach the generic per-instance instructions.
    defaults = {
        PartKind.HEAD: (PartKind.BODY, "sewn", "bottom", {"top"}),
        PartKind.ARMS: (PartKind.BODY, "sewn", "inner_end", {"upper_left", "upper_right"}),
        PartKind.LEGS: (PartKind.BODY, "sewn", "top", {"bottom_left", "bottom_right"}),
        PartKind.EARS: (PartKind.HEAD, "sewn", "base", {"side_left", "side_right"}),
        PartKind.HAT: (PartKind.HEAD, "worn", "opening", {"top"}),
        PartKind.SKIRT: (PartKind.BODY, "crocheted_or_sewn", "opening", {"waist"}),
        PartKind.TAIL: (PartKind.BODY, "sewn", "base", {"back"}),
    }
    instances_by_source: dict[str, set[str]] = {}
    for (source, *_), connections in grouped.items():
        instances_by_source.setdefault(source, set()).update(
            str(item.get("source_instance_id") or "") for item in connections)
    for source, instance_ids in instances_by_source.items():
        quantity = max(1, int(quantities.get(source, 1)))
        if quantity != len(instance_ids):
            steps.append(f"{source}共 {quantity} 个，连接图记录 {len(instance_ids)} 个实例；"
                         "请在部件结构中核对数量和连接位置")

    for (source, target, method, original_target), connections in grouped.items():
        connected_sources.add(source)
        target_label = (f"一体件{original_target}段" if target == _ONE_PIECE_NAME else target)
        source_kind = part_kind_from_name(source)
        target_kind = part_kind_from_name(target)
        default = defaults.get(source_kind) if source_kind is not None else None
        anchors = {str(item.get("target_anchor") or "") for item in connections}
        quantity = max(1, int(quantities.get(source, 1)))
        distinct_instances = {item.get("source_instance_id") for item in connections}
        same_sides = all(
            not str(item.get("source_instance_id") or "").endswith(suffix)
            or str(item.get("target_anchor") or "").endswith(suffix)
            for item in connections for suffix in ("_left", "_right"))
        canonical = (default is not None and part_kind_from_name(original_target) is default[0]
                     and method == default[1] and anchors == default[3]
                     and len(anchors) == len(connections) == quantity
                     and len(distinct_instances) == quantity and same_sides
                     and len(instances_by_source[source]) == quantity
                     and all(item.get("self_anchor") == default[2] for item in connections))
        if canonical and source_kind is PartKind.HEAD and target_kind is PartKind.BODY:
            steps.append(head_connection())
        elif canonical and source_kind is PartKind.ARMS and (target_kind is PartKind.BODY
                                                            or target == _ONE_PIECE_NAME):
            steps.append(placement(
                PartKind.ARMS, f"手臂对称缝合到{target_label}两侧上方{opening_note(PartKind.ARMS)}",
                f"手臂缝合到{target_label}一侧上方{opening_note(PartKind.ARMS)}",
                f"均匀缝合到{target_label}上部{opening_note(PartKind.ARMS)}"))
        elif canonical and source_kind is PartKind.LEGS and (target_kind is PartKind.BODY
                                                            or target == _ONE_PIECE_NAME):
            steps.append(placement(
                PartKind.LEGS, f"腿部对称缝合到{target_label}底部{opening_note(PartKind.LEGS)}",
                f"腿部缝合到{target_label}底部{opening_note(PartKind.LEGS)}",
                f"均匀缝合到{target_label}底部{opening_note(PartKind.LEGS)}"))
        elif canonical and source_kind is PartKind.EARS and (target_kind is PartKind.HEAD
                                                            or target == _ONE_PIECE_NAME):
            steps.append(placement(
                PartKind.EARS, "耳朵对称缝合在头部两侧",
                "耳朵缝合在头部一侧", "均匀缝合在头部周围"))
        elif canonical and source_kind is PartKind.HAT and (target_kind is PartKind.HEAD
                                                           or target == _ONE_PIECE_NAME):
            hat_n = openings_by_kind.get(PartKind.HAT)
            hat_open = f"帽口 {hat_n} 针" if hat_n else "帽口"
            steps.append(hat_step(hat_open))
        elif canonical and source_kind is PartKind.SKIRT and (target_kind is PartKind.BODY
                                                             or target == _ONE_PIECE_NAME):
            if skirt_style == "attached":
                steps.append(skirt_connection())
            else:
                skirt_n = openings_by_kind.get(PartKind.SKIRT)
                skirt_open = f"（{skirt_n} 针开口）" if skirt_n else ""
                steps.append(
                    f"将预先套入{target_label}的裙筒腰部{skirt_open}调整到腰位后缝合固定"
                    if updated_guidance else
                    f"裙筒腰部{skirt_open}套入{target_label}后缝合固定（腰部为开口起针）")
        elif canonical and source_kind is PartKind.TAIL and (target_kind is PartKind.BODY
                                                           or target == _ONE_PIECE_NAME):
            steps.append(f"尾巴缝合在{target_label}后方")
        else:
            labels = list(dict.fromkeys(
                anchor_labels.get(str(item.get("target_anchor")),
                                  str(item.get("target_anchor") or "指定位置"))
                for item in connections))
            action = {
                "sewn": "缝合到",
                "worn": "佩戴到",
                "crocheted_or_sewn": "挑针钩接或缝合到",
            }.get(method, "连接到")
            opening = opening_note(source)
            details = []
            for connection in connections:
                instance_id = str(connection.get("source_instance_id") or "")
                if instance_id.endswith("_left"):
                    instance_label = f"左{source}"
                elif instance_id.endswith("_right"):
                    instance_label = f"右{source}"
                elif len(connections) > 1 and instance_id not in ("", source):
                    # Edited copies keep their ids so instances stay
                    # distinguishable; a lone instance's template id would
                    # only leak an internal identifier into the prose.
                    instance_label = f"{source}（{instance_id}）"
                else:
                    instance_label = source
                self_anchor = str(connection.get("self_anchor") or "指定连接点")
                target_anchor = str(connection.get("target_anchor") or "指定位置")
                details.append(
                    f"{instance_label}的{anchor_labels.get(self_anchor, self_anchor)}"
                    f"{action}{target_label}的{anchor_labels.get(target_anchor, target_anchor)}")
            if len(details) == 1:
                # One instance: merge the summary into the single detail line
                # instead of emitting near-duplicate prose.
                steps.append(f"{details[0]}{opening}")
            else:
                steps.append(
                    f"{source}{action}{target_label}的{'、'.join(labels)}{opening}")
                steps.extend(details)

    roots = {_ONE_PIECE_NAME, PART_LABELS_ZH[PartKind.BODY]}
    if PartKind.BODY not in part_kinds and not one_piece:
        roots.add(PART_LABELS_ZH[PartKind.HEAD])
    for name in sorted(part_names - roots - connected_sources):
        steps.append(f"{name}未设置连接关系，暂按独立部件保留")
    return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
