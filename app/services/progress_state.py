"""Physical-round progress keyed by semantic identity, independent of widget keys.

Each tab keeps one record ``{"result_id", "completed"}`` in its session state.
The record is the single source of truth: checkboxes are initialized from it and
write back through callbacks, and edits replace it with the retained identities
instead of migrating widget keys between result IDs.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator, Mapping, MutableMapping, Sequence
from typing import Any

from app.schemas import PartData, ResultData, StructureData, StructureInstanceData

MAX_INLINE_ROUNDS = 500
PROGRESS_PAGE_SIZE = 50

# Colour-bearing fields plus the totals derived from them. A change confined to
# these cannot invalidate work already crocheted (见 docs/part-color-selection.md §7).
_COLOR_FIELDS = ("color", "auto_color_summary", "color_origin", "color_section_mode",
                 "instance_colors", "instance_color_ids")
_DERIVED_TOTALS = ("materials", "material_summary", "total_stitches",
                   "estimated_time_minutes", "time_estimate_basis")


def _without_recorded_fragment(note: object, fragment: object) -> object:
    """Remove one previously verified generated fragment, retaining manual text."""
    if not isinstance(note, str):
        return note
    if not note:
        return None
    if not isinstance(fragment, str) or not fragment:
        return note
    before, found, after = note.rpartition(fragment)
    if not found:
        return note
    if before.endswith("；") and not fragment.startswith(" "):
        before = before[:-1]
    return before + after or None


def _part_note_without_color_summary(part: Mapping[str, Any]) -> object:
    """Ignore a summary only when it matches this part's actual round colors."""
    from app.models.color_design import blocks_summary_text

    rounds = part.get("rounds") or []
    colors = [row.get("color") or part.get("color") or "未指定" for row in rounds]
    direction = "自下而上" if part.get("name") in {"身体", "手臂", "腿部"} else "自上而下"
    expected = (f" 配色（按钩织圈序，{direction}）："
                f"{blocks_summary_text(colors, [row['row'] for row in rounds])}。")
    summary = part.get("auto_color_summary")
    if not any(row.get("color") for row in rounds) or len(set(colors)) <= 1:
        summary = None
    return _without_recorded_fragment(part.get("notes"), summary if summary == expected else None)


def _strip_color_state(part: Mapping[str, Any]) -> dict[str, Any]:
    """``part`` with colour evidence replaced; every real instruction survives."""
    from app.models.onepiece import ONE_PIECE_MONO_NOTE

    stripped = {k: v for k, v in part.items() if k not in _COLOR_FIELDS}
    rounds = part.get("rounds") or []
    colors = [row.get("color") or part.get("color") or "未指定" for row in rounds]
    note = _part_note_without_color_summary(part)
    if part.get("name") == "头身（一体）" and isinstance(note, str):
        note = note.replace(ONE_PIECE_MONO_NOTE, "")
    stripped["notes"] = note
    normalized_rounds = []
    for index, rd in enumerate(rounds):
        expected = (f"换线：{colors[index]}（前一针最后一次挂线改用新色；螺旋圈仍可能出现台阶）"
                    if index and colors[index] != colors[index - 1] else None)
        fragment = rd.get("auto_color_note")
        normalized_rounds.append({
            **{k: v for k, v in rd.items() if k not in ("color", "auto_color_note")},
            "notes": _without_recorded_fragment(rd.get("notes"), fragment if fragment == expected else None),
        })
    stripped["rounds"] = normalized_rounds
    return stripped


def _identity_fingerprint(result: ResultData) -> dict[str, list[str]]:
    """Per-part physical copy identity, so a reorder is not a colour-only change.

    Reversing a part's instances leaves every round's stitches identical yet moves
    which physical copy a completed record belongs to. That is a construction
    change and must never be mistaken for recolouring.
    """
    structure: StructureData = result.get("structure") or {}
    graph = {p["name"]: p for p in structure.get("parts", []) if isinstance(p, dict)}
    fingerprint: dict[str, list[str]] = {}
    for part in (result.get("params") or {}).get("parts") or []:
        if not isinstance(part, Mapping):
            continue
        entry = graph.get(part.get("name"))
        instances = (entry.get("instances") or []
                     if entry is not None and structure.get("schema_version") == "2.0" else [])
        fingerprint[str(part.get("name"))] = _copy_instance_ids(instances, part.get("quantity", 1))
    return fingerprint


def _pattern_shape(result: ResultData) -> dict[str, Any]:
    params: dict[str, Any] = {k: v for k, v in (result.get("params") or {}).items()
                              if k not in _DERIVED_TOTALS}
    parts = params.get("parts") or []
    params["parts"] = [_strip_color_state(p) for p in parts if isinstance(p, Mapping)]
    params["_copy_identity"] = _identity_fingerprint(result)
    return params


def color_only_change(current: ResultData, updated: ResultData) -> bool:
    """True when two patterns differ only in colour-bearing fields.

    A verified pure recolouring keeps every completed round: stitches, techniques,
    joins and hand-written instructions are identical, so nothing already worked
    needs re-checking. Any other difference keeps the conservative rule.
    """
    stable_keys = ("analysis", "structure", "style", "gauge", "color_bands", "spans",
                   "spans_measured", "geometry")
    if any(current.get(key) != updated.get(key) for key in stable_keys):
        return False
    before = (current.get("params") or {}).get("parts") or []
    after = (updated.get("params") or {}).get("parts") or []
    def colors(parts):
        return [({key: part.get(key) for key in _COLOR_FIELDS},
                 [(row.get("color"), row.get("auto_color_note")) for row in part.get("rounds", [])])
                for part in parts]
    return colors(before) != colors(after) and _pattern_shape(current) == _pattern_shape(updated)


def progress_record_key(slot: str) -> str:
    return f"project_progress_{slot}"


def completed_rounds(result: ResultData, slot: str, state: Mapping) -> dict[str, bool]:
    """The live record for ``result``; a record left by another result reads as empty."""
    record = state.get(progress_record_key(slot))
    if not isinstance(record, dict) or record.get("result_id") != (result.get("result_id") or slot):
        return {}
    return record["completed"]


def store_completed_rounds(result: ResultData, slot: str, progress: Mapping[str, bool],
                           state: MutableMapping) -> dict[str, bool]:
    """Replace the tab's record with ``progress`` for ``result`` and return the stored dict."""
    completed = {identity: True for identity, done in progress.items() if done}
    state[progress_record_key(slot)] = {"result_id": result.get("result_id") or slot, "completed": completed}
    return completed


def physical_rounds(result: ResultData) -> int:
    return sum(len(p["rounds"]) * p.get("quantity", 1) for p in result["params"]["parts"])


def progress_copy_prefixes(result: ResultData, slot: str) -> list[list[str]]:
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


def _copy_instance_ids(instances: Sequence[StructureInstanceData], quantity: int) -> list[str]:
    """Reserve graph IDs before assigning deterministic IDs to extra copies."""
    reserved = {instance["instance_id"] for instance in instances}
    identities = []
    for index in range(quantity):
        if index < len(instances):
            identity = instances[index]["instance_id"]
        else:
            identity = f"copy{index + 1}"
            while identity in reserved:
                identity += "_"
            reserved.add(identity)
        identities.append(identity)
    return identities


def _legacy_identity_collisions(result: ResultData) -> dict[str, set[str]]:
    """Find copy IDs that the old graph/fallback mapping assigned twice."""
    structure: StructureData = result.get("structure") or {"parts": []}
    graph = {p["name"]: p for p in structure.get("parts", [])}
    collisions = {}
    for part in result["params"]["parts"]:
        entry = graph.get(part["name"])
        instances = (entry.get("instances", [])
                     if entry is not None and structure.get("schema_version") == "2.0" else [])
        ids = [instances[i]["instance_id"] if i < len(instances) else f"copy{i + 1}"
               for i in range(part.get("quantity", 1))]
        duplicated = {identity for identity, count in Counter(ids).items() if count > 1}
        if duplicated:
            collisions[part["name"]] = duplicated
    return collisions


def has_legacy_identity_collision(result: ResultData) -> bool:
    return bool(_legacy_identity_collisions(result))


def ambiguous_legacy_progress(result: ResultData, progress: dict[str, bool]) -> set[str]:
    """Old duplicate IDs cannot establish which physical copy was completed."""
    collisions = _legacy_identity_collisions(result)
    return {identity for part in result["params"]["parts"]
            for copy_id in collisions.get(part["name"], ()) for rd in part["rounds"]
            if (identity := json.dumps([part["name"], copy_id, rd["row"]], ensure_ascii=False)) in progress}


def _copy_roles(result: ResultData) -> dict[str, dict[str, tuple[str, str | int]]]:
    """Distinguish real graph IDs from ordinal IDs assigned to extra copies."""
    structure: StructureData = result.get("structure") or {"parts": []}
    graph = {p["name"]: p for p in structure.get("parts", [])}
    roles: dict[str, dict[str, tuple[str, str | int]]] = {}
    for part in result["params"]["parts"]:
        entry = graph.get(part["name"])
        instances = (entry.get("instances", [])
                     if entry is not None and structure.get("schema_version") == "2.0" else [])
        identities = _copy_instance_ids(instances, part.get("quantity", 1))
        roles[part["name"]] = {
            identity: ("graph", instances[index]["instance_id"]) if index < len(instances)
            else ("fallback", index + 1)
            for index, identity in enumerate(identities)
        }
    return roles


def progress_entries(result: ResultData, slot: str, *,
                     part_index: int | None = None) -> Iterator[tuple[str, str, PartData]]:
    """Yield semantic identity, widget key and part for each physical round.

    Graph instances have stable IDs; legacy patterns use copy ordinals. Part
    names and row numbers are unique at the validated edit/import boundary.
    """
    parts = result["params"]["parts"]
    if (part_index is not None
            and (type(part_index) is not int or not 0 <= part_index < len(parts))):
        raise ValueError("进度部件索引无效")
    prefixes = progress_copy_prefixes(result, slot)
    structure: StructureData = result.get("structure") or {"parts": []}
    graph = {p["name"]: p for p in structure.get("parts", [])}
    for selected_index, part in enumerate(parts):
        if part_index is not None and selected_index != part_index:
            continue
        name = part["name"]
        entry = graph.get(name)
        instances = (entry.get("instances", [])
                     if entry is not None and structure.get("schema_version") == "2.0" else [])
        for instance, prefix in zip(_copy_instance_ids(instances, len(prefixes[selected_index])),
                                    prefixes[selected_index], strict=True):
            for index, rd in enumerate(part["rounds"]):
                identity = json.dumps([name, instance, rd["row"]], ensure_ascii=False)
                yield identity, f"{prefix}{index}", part


def capture_progress(result: ResultData, slot: str, state: Mapping) -> dict[str, bool]:
    """A copy of the live progress, limited to the result's current physical rounds."""
    completed = completed_rounds(result, slot, state)
    return {identity: True for identity, _, _ in progress_entries(result, slot) if completed.get(identity)}


def progress_limits(current: ResultData, updated: ResultData) -> dict[str, int]:
    """Count the unchanged leading rounds, before propagating join dependencies.

    Compare full instructions (including colors and finishing notes), not just
    counts. Unknown part-wide changes conservatively invalidate the whole part.
    """
    from app.models.gauge import gauge_for_part, gauge_from_result

    old = {p["name"]: p for p in current["params"]["parts"]}
    new = {p["name"]: p for p in updated["params"]["parts"]}
    limits = dict.fromkeys(new, 0)
    old_links = (current["params"].get("stitch_attachments") or {}).get("connections", [])
    new_links = (updated["params"].get("stitch_attachments") or {}).get("connections", [])
    # 跨部件预留半针接合下，一个部件的针目身份取决于「被接」的一方。这类部件即使
    # 只改颜色也沿用下面的保守规则：这是既有测试钉住的契约，不随纯颜色修改放松。
    joined = {name for connection in [*old_links, *new_links]
              for name in (connection.get("source_part"), connection.get("target_part"))}
    # 已验证的纯颜色修改：逐圈针法、人工文字、密度与接合都未变，只有颜色及由颜色
    # 重新推导的自动片段不同。此时未涉及接合的部件整段保留完成圈次；界面另须提示
    # 「已钩出的旧颜色不会因为图解改色而改变」。任何施工变化都会让 pure_colour 为假。
    pure_colour = color_only_change(current, updated)

    def part_instructions(part):
        metadata = {k: v for k, v in part.items()
                    if k not in ("quantity", "rounds", "color", "auto_color_summary", "gauge",
                                 "color_origin", "color_section_mode", "instance_colors",
                                 "instance_color_ids")}
        metadata["notes"] = _part_note_without_color_summary(part) or ""
        return metadata

    def round_instructions(rd, part):
        instruction = {k: v for k, v in rd.items() if k != "auto_color_note"}
        instruction["color"] = rd.get("color") or part.get("color")
        return instruction

    for name, part in new.items():
        before = old.get(name)
        if before is None or part_instructions(before) != part_instructions(part):
            continue
        if (gauge_for_part(before, gauge_from_result(current))
                != gauge_for_part(part, gauge_from_result(updated))):
            continue
        if name in joined and before.get("instance_colors") != part.get("instance_colors"):
            continue
        if pure_colour and name not in joined:
            limits[name] = len(part["rounds"])
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

    def copies(result: ResultData, name: str) -> list[str]:
        part = next((p for p in result["params"]["parts"] if p["name"] == name), None)
        if part is None:
            return []
        structure: StructureData = result.get("structure") or {"parts": []}
        entry = next((p for p in structure.get("parts", []) if p["name"] == name), None)
        instances = (entry.get("instances", [])
                     if entry is not None and structure.get("schema_version") == "2.0" else [])
        return _copy_instance_ids(instances, part.get("quantity", 1))

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
            before, after = old.get(target), new.get(target)
            if (before is None or after is None or limits.get(target, 0) < len(before["rounds"])
                    or limits.get(target, 0) < len(after["rounds"])):
                cut(connection["source_part"])
        if limits == previous:
            return limits


def _retained_progress(current: ResultData, updated: ResultData, progress: dict,
                       limits: dict[str, int]) -> tuple[dict[str, bool], dict[str, int]]:
    eligible = {p["name"]: {r["row"] for r in p["rounds"][:limits[p["name"]]]}
                for p in updated["params"]["parts"]}
    old_roles = _copy_roles(current)
    new_roles = _copy_roles(updated)
    next_ids = {}
    for name, copies in old_roles.items():
        new_by_role = {role: identity for identity, role in new_roles.get(name, {}).items()}
        next_ids[name] = {identity: new_by_role[role] for identity, role in copies.items()
                          if role in new_by_role}
    retained: dict[str, bool] = {}
    kept: dict[str, int] = {}
    # Work from completed rounds: a large pattern can have hundreds of
    # thousands of physical rounds but only a few checked entries.
    for identity, completed in progress.items():
        if not completed:
            continue
        try:
            parsed = json.loads(identity)
        except (TypeError, ValueError, RecursionError):
            continue
        if (not isinstance(parsed, list) or len(parsed) != 3
                or not isinstance(parsed[0], str) or not isinstance(parsed[1], str)
                or type(parsed[2]) is not int or json.dumps(parsed, ensure_ascii=False) != identity):
            continue
        name, copy_id, row = parsed
        next_copy = next_ids.get(name, {}).get(copy_id)
        if next_copy is not None and row in eligible.get(name, set()):
            next_identity = identity if next_copy == copy_id else json.dumps([name, next_copy, row],
                                                                            ensure_ascii=False)
            retained[next_identity] = True
            kept[name] = kept.get(name, 0) + 1
    return retained, kept


def retained_progress(current: ResultData, updated: ResultData, slot: str, progress: dict) -> dict[str, bool]:
    """Retain only existing physical rounds before the first affected round."""
    return _retained_progress(current, updated, progress, progress_limits(current, updated))[0]


def progress_impact(current: ResultData, updated: ResultData, slot: str, progress: dict) -> list[dict]:
    """Human-readable changes, with counts per logical part across its copies."""
    limits = progress_limits(current, updated)
    _, kept = _retained_progress(current, updated, progress, limits)
    old_parts = {p["name"]: p for p in current["params"]["parts"]}
    new_parts = {p["name"]: p for p in updated["params"]["parts"]}
    done: dict[str, int] = {}
    for identity, value in progress.items():
        if value:
            name = json.loads(identity)[0]
            done[name] = done.get(name, 0) + 1
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


def install_progress(result: ResultData, slot: str, progress: Mapping[str, bool],
                     state: MutableMapping) -> None:
    """Record ``progress`` for ``result``; checkboxes initialize from it when rendered."""
    known = {identity for identity, _, _ in progress_entries(result, slot)}
    store_completed_rounds(result, slot, {k: v for k, v in progress.items() if k in known}, state)
