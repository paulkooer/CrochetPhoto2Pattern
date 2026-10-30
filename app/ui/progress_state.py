"""Progress snapshots independent of ephemeral result/widget IDs."""
from __future__ import annotations

import json
from collections import Counter

MAX_INLINE_ROUNDS = 500
PROGRESS_PAGE_SIZE = 50


def progress_store_key(result: dict, slot: str) -> str:
    return f"progress_{result.get('result_id') or slot}"


def physical_rounds(result: dict) -> int:
    return sum(len(p["rounds"]) * p.get("quantity", 1) for p in result["params"]["parts"])


def progress_copy_prefixes(result: dict, slot: str) -> list[list[str]]:
    """Keep legacy widget keys unless a part name aliases another copy's prefix."""
    rid = result.get("result_id") or slot
    prefixes = [
        [f"chk_{rid}_{part['name']}_" + (f"copy{copy + 1}_" if copy else "")
         for copy in range(max(1, int(part.get("quantity", 1))))]
        for part in result["params"]["parts"]
    ]
    counts = Counter(prefix for copies in prefixes for prefix in copies)
    reserved = set(counts)
    for part_index, copies in enumerate(prefixes):
        for copy, prefix in enumerate(copies):
            if counts[prefix] > 1:
                candidate = f"{prefix}part{part_index + 1}_copy{copy + 1}_"
                # A custom name may also look exactly like our disambiguation.
                while candidate in reserved:
                    candidate += "_"
                copies[copy] = candidate
                reserved.add(candidate)
    return prefixes


def progress_entries(result: dict, slot: str, *, part_index: int | None = None):
    """Yield semantic identity, widget key and part for each physical round.

    Graph instances have stable IDs; legacy patterns use copy ordinals. Part
    names and row numbers are unique at the validated edit/import boundary.
    """
    parts = result["params"]["parts"]
    if (part_index is not None
            and (type(part_index) is not int or not 0 <= part_index < len(parts))):
        raise ValueError("进度部件索引无效")
    prefixes = progress_copy_prefixes(result, slot)
    structure = result.get("structure") or {}
    graph = {p["name"]: p for p in structure.get("parts", [])}
    for selected_index, part in enumerate(parts):
        if part_index is not None and selected_index != part_index:
            continue
        name = part["name"]
        instances = (
            graph.get(name, {}).get("instances", []) if structure.get("schema_version") == "2.0" else []
        )
        for copy, prefix in enumerate(prefixes[selected_index]):
            instance = instances[copy]["instance_id"] if copy < len(instances) else f"copy{copy + 1}"
            for index, rd in enumerate(part["rounds"]):
                identity = json.dumps([name, instance, rd["row"]], ensure_ascii=False)
                yield identity, f"{prefix}{index}", part


def capture_progress(result: dict, slot: str, state) -> dict[str, bool]:
    durable = state.get(progress_store_key(result, slot), {})
    return {identity: True for identity, key, _ in progress_entries(result, slot)
            if state.get(key, durable.get(key, False))}


def progress_limits(current: dict, updated: dict) -> dict[str, int]:
    """Count the unchanged leading rounds, before propagating join dependencies.

    Compare full instructions (including colors and finishing notes), not just
    counts. Unknown part-wide changes conservatively invalidate the whole part.
    """
    from app.models.gauge import gauge_from_result

    old = {p["name"]: p for p in current["params"]["parts"]}
    new = {p["name"]: p for p in updated["params"]["parts"]}
    limits = dict.fromkeys(new, 0)
    if gauge_from_result(current) != gauge_from_result(updated):
        return limits

    def part_instructions(part):
        metadata = {k: v for k, v in part.items()
                    if k not in ("quantity", "rounds", "color", "auto_color_summary")}
        summary = part.get("auto_color_summary") or ""
        metadata["notes"] = (part.get("notes") or "").replace(summary, "")
        return metadata

    def round_instructions(rd, part):
        instruction = {k: v for k, v in rd.items() if k != "auto_color_note"}
        instruction["color"] = rd.get("color") or part.get("color")
        return instruction

    for name, part in new.items():
        before = old.get(name)
        if before is None or part_instructions(before) != part_instructions(part):
            continue
        for left, right in zip(before["rounds"], part["rounds"], strict=False):
            if round_instructions(left, before) != round_instructions(right, part):
                break
            limits[name] += 1

    def cut(name: str, index: int = 0) -> None:
        if name in limits:
            limits[name] = min(limits[name], index)

    def reservation_index(parts: dict, connection: dict) -> int:
        rows = parts.get(connection["target_part"], {}).get("rounds", [])
        return next((i for i, row in enumerate(rows)
                     if row["row"] == connection["reservation_row"]), 0)

    old_links = (current["params"].get("stitch_attachments") or {}).get("connections", [])
    new_links = (updated["params"].get("stitch_attachments") or {}).get("connections", [])
    def copies(result: dict, name: str) -> list[str]:
        part = next((p for p in result["params"]["parts"] if p["name"] == name), None)
        if part is None:
            return []
        structure = result.get("structure") or {}
        entry: dict = next((p for p in structure.get("parts", []) if p["name"] == name), {})
        instances = entry.get("instances", []) if structure.get("schema_version") == "2.0" else []
        return [instances[i]["instance_id"] if i < len(instances) else f"copy{i + 1}"
                for i in range(part.get("quantity", 1))]

    for connection in old_links + new_links:
        if any(copies(current, connection[field]) != copies(updated, connection[field])
               for field in ("source_part", "target_part")):
            cut(connection["source_part"])
        if connection not in old_links or connection not in new_links:
            cut(connection["source_part"])
            cut(connection["target_part"], min(reservation_index(old, connection),
                                               reservation_index(new, connection)))
    old_plan = (current["params"].get("assembly_plan") or {}).get("connections", [])
    new_plan = (updated["params"].get("assembly_plan") or {}).get("connections", [])
    for connection in old_plan + new_plan:
        if connection not in old_plan or connection not in new_plan:
            cut(connection["source_part_name"])
    # Keep dependency invalidation conservative: any changed target work means
    # its attached source must be reviewed, even when the reserved row survived.
    while True:
        previous = limits.copy()
        for connection in old_links + new_links:
            target = connection["target_part"]
            before, after = old.get(target, {}), new.get(target, {})
            if (not before or not after or limits.get(target, 0) < len(before["rounds"])
                    or limits.get(target, 0) < len(after["rounds"])):
                cut(connection["source_part"])
        if limits == previous:
            return limits


def retained_progress(current: dict, updated: dict, slot: str, progress: dict) -> dict[str, bool]:
    """Retain only existing physical rounds before the first affected round."""
    limits = progress_limits(current, updated)
    eligible = {p["name"]: {r["row"] for r in p["rounds"][:limits[p["name"]]]}
                for p in updated["params"]["parts"]}
    return {identity: True for identity, _, part in progress_entries(updated, slot)
            if progress.get(identity) and json.loads(identity)[2] in eligible[part["name"]]}


def progress_impact(current: dict, updated: dict, slot: str, progress: dict) -> list[dict]:
    """Human-readable changes, with counts per logical part across its copies."""
    limits = progress_limits(current, updated)
    retained = retained_progress(current, updated, slot, progress)
    old_parts = {p["name"]: p for p in current["params"]["parts"]}
    new_parts = {p["name"]: p for p in updated["params"]["parts"]}
    done: dict[str, int] = {}
    kept: dict[str, int] = {}
    for identity, value in progress.items():
        if value:
            name = json.loads(identity)[0]
            done[name] = done.get(name, 0) + 1
            kept[name] = kept.get(name, 0) + int(identity in retained)
    summary = []
    for name in dict.fromkeys([*old_parts, *new_parts]):
        part = new_parts.get(name)
        before = old_parts.get(name)
        limit = limits.get(name, 0)
        if part is None:
            scope = "部件已删除"
        elif before is None:
            scope = "新增部件"
        elif limit < len(part["rounds"]):
            scope = f"从第 {part['rounds'][limit]['row']} 圈起重新核对"
        elif limit < len(before["rounds"]):
            scope = "末尾圈次已删除；前段保持不变"
        else:
            scope = "原有圈次保持不变"
        summary.append({"部件": name, "变化范围": scope,
                        "保留完成圈次": kept.get(name, 0),
                        "清除完成圈次": done.get(name, 0) - kept.get(name, 0)})
    return summary


def install_progress(result: dict, slot: str, progress: dict, state) -> None:
    destination = {} if physical_rounds(result) > MAX_INLINE_ROUNDS else state
    for identity, key, _ in progress_entries(result, slot):
        if progress.get(identity):
            destination[key] = True
    if destination is not state:
        state[progress_store_key(result, slot)] = destination
