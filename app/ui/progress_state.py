"""Progress snapshots independent of ephemeral result/widget IDs."""
from __future__ import annotations

import json

MAX_INLINE_ROUNDS = 500
PROGRESS_PAGE_SIZE = 50


def progress_store_key(result: dict, slot: str) -> str:
    return f"progress_{result.get('result_id') or slot}"


def physical_rounds(result: dict) -> int:
    return sum(len(p["rounds"]) * p.get("quantity", 1) for p in result["params"]["parts"])


def progress_entries(result: dict, slot: str):
    """Yield semantic identity, widget key and part for each physical round.

    Graph instances have stable IDs; legacy patterns use copy ordinals. Part
    names and row numbers are unique at the validated edit/import boundary.
    """
    rid = result.get("result_id") or slot
    structure = result.get("structure") or {}
    graph = {p["name"]: p for p in structure.get("parts", [])}
    for part in result["params"]["parts"]:
        name = part["name"]
        instances = (
            graph.get(name, {}).get("instances", []) if structure.get("schema_version") == "2.0" else []
        )
        for copy in range(part.get("quantity", 1)):
            instance = instances[copy]["instance_id"] if copy < len(instances) else f"copy{copy + 1}"
            prefix = f"chk_{rid}_{name}_" + (f"copy{copy + 1}_" if copy else "")
            for index, rd in enumerate(part["rounds"]):
                identity = json.dumps([name, instance, rd["row"]], ensure_ascii=False)
                yield identity, f"{prefix}{index}", part


def capture_progress(result: dict, slot: str, state) -> dict[str, bool]:
    durable = state.get(progress_store_key(result, slot), {})
    return {identity: True for identity, key, _ in progress_entries(result, slot)
            if state.get(key, durable.get(key, False))}


def retained_progress(current: dict, updated: dict, slot: str, progress: dict) -> dict[str, bool]:
    """Keep unchanged physical parts; changed gauge invalidates all progress."""
    from app.models.gauge import gauge_from_result

    if gauge_from_result(current) != gauge_from_result(updated):
        return {}
    old_parts = {p["name"]: {k: v for k, v in p.items() if k != "quantity"}
                 for p in current["params"]["parts"]}
    unchanged = {
        p["name"] for p in updated["params"]["parts"]
        if old_parts.get(p["name"]) == {k: v for k, v in p.items() if k != "quantity"}
    }
    # Changing a reserved base or moving an attachment invalidates the work
    # which depends on it, even if the skirt's own stitch counts are unchanged.
    old_connections = (current["params"].get("stitch_attachments") or {}).get("connections", [])
    new_connections = (updated["params"].get("stitch_attachments") or {}).get("connections", [])
    for connection in old_connections + new_connections:
        source, target = connection["source_part"], connection["target_part"]
        if connection not in old_connections or connection not in new_connections:
            unchanged.difference_update((source, target))
    old_plan = (current["params"].get("assembly_plan") or {}).get("connections", [])
    new_plan = (updated["params"].get("assembly_plan") or {}).get("connections", [])
    for connection in old_plan + new_plan:
        if connection not in old_plan or connection not in new_plan:
            unchanged.discard(connection["source_part_name"])
    # Propagate after every direct invalidation. A single pass (or two passes
    # over old/new records) depends on list order and misses deeper join chains.
    while True:
        dependent = {c["source_part"] for c in old_connections + new_connections
                     if c["target_part"] not in unchanged and c["source_part"] in unchanged}
        if not dependent:
            break
        unchanged.difference_update(dependent)
    return {
        identity: True
        for identity, _, part in progress_entries(updated, slot)
        if progress.get(identity) and part["name"] in unchanged
    }


def install_progress(result: dict, slot: str, progress: dict, state) -> None:
    destination = {} if physical_rounds(result) > MAX_INLINE_ROUNDS else state
    for identity, key, _ in progress_entries(result, slot):
        if progress.get(identity):
            destination[key] = True
    if destination is not state:
        state[progress_store_key(result, slot)] = destination
