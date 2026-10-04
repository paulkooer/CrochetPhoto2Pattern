"""装配说明：按 v2 连接图逐实例生成缝合步骤，旧格式回退名称模板。

从 crochet_params 拆出；_CLOSING_RE 的闭合语义与开口统计一并随迁。
"""
from __future__ import annotations

import re
from typing import Any

from .parts import _ONE_PIECE_NAME, _part_name, _part_rounds, _round_stitches

# 末圈注记里的闭合语义："收口/勒紧收口/无痕收口"=已闭合；"不收口/勿收口"
# 是开口声明——负向断言排除后者（中文社区头套"开口保留…不收口"）
_CLOSING_RE = re.compile(r"(?<![不勿])收口")


def _openings_by_part(parts: list[dict[str, Any]]) -> dict[str, int]:
    """各部件的开口针数（末圈针数）——完全收口的部件不计入。

    专业图解装配段的通行惯例：缝合前先报开口针数（"sew the remaining
    12 sts to the body"）。球体头部以"无痕收口"完全闭合，无开口；
    圆柱四肢以"断线留15cm用于缝合"收尾留口；帽/裙明确不收口。
    """
    openings: dict[str, int] = {}
    for p in parts:
        rounds = _part_rounds(p)
        if not rounds:
            continue
        last = rounds[-1]
        # "收口"=闭合无开口；但"不收口/勿收口"是明确的开口声明
        #（真实图解如中文社区头套"开口保留…不收口"），不得误判
        if _CLOSING_RE.search(str(last.get("notes") or "")):
            continue
        openings[_part_name(p)] = _round_stitches(last)
    return openings


def build_assembly(part_names, skirt_style: str = "ring",
                   quantities: dict[str, int] | None = None,
                   assembly_plan: dict[str, Any] | None = None,
                   openings: dict[str, int] | None = None) -> str:
    """Build assembly text from the v2 graph, with a legacy name fallback."""
    quantities = quantities or {}
    openings = openings or {}

    def opening_note(name: str) -> str:
        n = openings.get(name)
        if not n:
            return ""
        # 垂耳兔等社区图解惯例：极小开口捏扁缝合（可免填充）
        flat = "，小开口可捏扁缝合" if n <= 6 else ""
        return f"（开口 {n} 针{flat}）"

    def placement(name: str, paired: str, single: str, many: str) -> str:
        quantity = max(1, int(quantities.get(name, 1)))
        if quantity == 1:
            return single
        if quantity == 2:
            return paired
        return f"{name}共 {quantity} 个，{many}"

    one_piece = _ONE_PIECE_NAME in part_names
    steps: list[str] = ["按各部件标注数量分别完成并填充棉花"]
    if "身体" in part_names or one_piece:
        steps.append(
            "可选：坐/站姿增稳——配重珠约 3/4 杯装入丝袜打结，于身体开始"
            "减针、开口尚能伸手时置入底部，再正常填充（Grace and Yarn；"
            "3 岁以下儿童玩偶勿用）")
    if one_piece:
        steps.append("一体件钩完头部后先填充头部再继续钩身体（分阶段填充）")
    if "头部" in part_names or one_piece:
        steps.append("头部安装安全眼（第2/3高度处）")
        steps.append("用黑色毛线绣鼻子和嘴巴")
        steps.append(
            "可选：针塑形（needle sculpting）——长针带同色线自一侧眼位"
            "入针、横穿头内至对侧眼位再穿回，两端自同一针孔拉紧打结藏线，"
            "形成眼窝凹陷（PlanetJune needlesculpting；本图解塑形已内建，"
            "此步仅在想要更立体五官时使用）")

    # Old backups have no graph.  Keep their established name-based behavior
    # rather than pretending to infer missing connection nodes during import.
    if assembly_plan is None:
        if "头部" in part_names and "身体" in part_names and not one_piece:
            steps.append("用隐形缝合法将头部接合到身体顶部；"
                         "头颈缝合处塞棉紧实，防止头部前倾"
                         "（AmiguRoom 俄语熊评论区试钩共识）")
        if "手臂" in part_names:
            steps.append(placement(
                "手臂", f"手臂对称缝合到身体两侧上方{opening_note('手臂')}",
                f"手臂缝合到身体一侧上方{opening_note('手臂')}",
                f"均匀缝合到身体上部{opening_note('手臂')}"))
        if "腿部" in part_names:
            steps.append(placement(
                "腿部", f"腿部对称缝合到身体底部{opening_note('腿部')}",
                f"腿部缝合到身体底部{opening_note('腿部')}",
                f"均匀缝合到身体底部{opening_note('腿部')}"))
        if "耳朵" in part_names:
            steps.append(placement(
                "耳朵", "耳朵对称缝合在头部两侧",
                "耳朵缝合在头部一侧", "均匀缝合在头部周围"))
        if "帽子" in part_names:
            hat_n = openings.get("帽子")
            hat_open = f"帽口 {hat_n} 针" if hat_n else "帽口"
            steps.append(f"{hat_open}不收口，直接戴在头部（试戴后可缝合固定）")
        if "裙子" in part_names:
            if skirt_style == "attached":
                steps.append("裙子已挑后半针钩在身体腰部，无需缝合")
            else:
                skirt_n = openings.get("裙子")
                skirt_open = f"（{skirt_n} 针开口）" if skirt_n else ""
                steps.append(f"裙筒腰部{skirt_open}套入身体后缝合固定"
                             "（腰部为开口起针）")
        if "尾巴" in part_names:
            steps.append("尾巴缝合在身体后方")
        return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))

    def effective_name(name: str) -> str:
        if one_piece and name in ("头部", "身体"):
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
        "头部": ("身体", "sewn", "bottom", {"top"}),
        "手臂": ("身体", "sewn", "inner_end", {"upper_left", "upper_right"}),
        "腿部": ("身体", "sewn", "top", {"bottom_left", "bottom_right"}),
        "耳朵": ("头部", "sewn", "base", {"side_left", "side_right"}),
        "帽子": ("头部", "worn", "opening", {"top"}),
        "裙子": ("身体", "crocheted_or_sewn", "opening", {"waist"}),
        "尾巴": ("身体", "sewn", "base", {"back"}),
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
        default = defaults.get(source)
        anchors = {str(item.get("target_anchor") or "") for item in connections}
        quantity = max(1, int(quantities.get(source, 1)))
        distinct_instances = {item.get("source_instance_id") for item in connections}
        same_sides = all(
            not str(item.get("source_instance_id") or "").endswith(suffix)
            or str(item.get("target_anchor") or "").endswith(suffix)
            for item in connections for suffix in ("_left", "_right"))
        canonical = (default is not None and original_target == default[0]
                     and method == default[1] and anchors == default[3]
                     and len(anchors) == len(connections) == quantity
                     and len(distinct_instances) == quantity and same_sides
                     and len(instances_by_source[source]) == quantity
                     and all(item.get("self_anchor") == default[2] for item in connections))
        if canonical and source == "头部" and target == "身体":
            steps.append("用隐形缝合法将头部接合到身体顶部；"
                         "头颈缝合处塞棉紧实，防止头部前倾"
                         "（AmiguRoom 俄语熊评论区试钩共识）")
        elif canonical and source == "手臂" and target in ("身体", _ONE_PIECE_NAME):
            steps.append(placement(
                "手臂", f"手臂对称缝合到{target_label}两侧上方{opening_note('手臂')}",
                f"手臂缝合到{target_label}一侧上方{opening_note('手臂')}",
                f"均匀缝合到{target_label}上部{opening_note('手臂')}"))
        elif canonical and source == "腿部" and target in ("身体", _ONE_PIECE_NAME):
            steps.append(placement(
                "腿部", f"腿部对称缝合到{target_label}底部{opening_note('腿部')}",
                f"腿部缝合到{target_label}底部{opening_note('腿部')}",
                f"均匀缝合到{target_label}底部{opening_note('腿部')}"))
        elif canonical and source == "耳朵" and target in ("头部", _ONE_PIECE_NAME):
            steps.append(placement(
                "耳朵", "耳朵对称缝合在头部两侧",
                "耳朵缝合在头部一侧", "均匀缝合在头部周围"))
        elif canonical and source == "帽子" and target in ("头部", _ONE_PIECE_NAME):
            hat_n = openings.get("帽子")
            hat_open = f"帽口 {hat_n} 针" if hat_n else "帽口"
            steps.append(f"{hat_open}不收口，直接戴在头部（试戴后可缝合固定）")
        elif canonical and source == "裙子" and target in ("身体", _ONE_PIECE_NAME):
            if skirt_style == "attached":
                steps.append(f"裙子已挑后半针钩在{target_label}腰部，无需缝合")
            else:
                skirt_n = openings.get("裙子")
                skirt_open = f"（{skirt_n} 针开口）" if skirt_n else ""
                steps.append(f"裙筒腰部{skirt_open}套入{target_label}后缝合固定"
                             "（腰部为开口起针）")
        elif canonical and source == "尾巴" and target in ("身体", _ONE_PIECE_NAME):
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

    roots = {_ONE_PIECE_NAME, "身体"}
    if "身体" not in part_names and not one_piece:
        roots.add("头部")
    for name in sorted(part_names - roots - connected_sources):
        steps.append(f"{name}未设置连接关系，暂按独立部件保留")
    return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
