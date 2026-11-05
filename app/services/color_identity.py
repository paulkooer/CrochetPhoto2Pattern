"""Bind per-copy color overrides to stable physical-copy identities."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.models.parts import _part_instance_colors, _part_quantity
from app.schemas import ResultData


def has_stable_copy_ids(result: ResultData, part: Mapping[str, Any]) -> bool:
    """Only graph instances with one durable ID per copy can receive overrides."""
    structure = result.get("structure") or {}
    if structure.get("schema_version") != "2.0":
        return False
    entry = next((item for item in structure.get("parts", [])
                  if isinstance(item, dict) and item.get("name") == part.get("name")), None)
    instances = entry.get("instances", []) if entry is not None else []
    identities = [item.get("instance_id") for item in instances if isinstance(item, dict)]
    return (len(identities) == _part_quantity(part) and all(isinstance(i, str) and i for i in identities)
            and len(set(identities)) == len(identities))


def color_copy_ids(result: Mapping[str, Any], part: Mapping[str, Any]) -> list[str]:
    """Use exactly the same graph/fallback IDs as physical progress."""
    from app.services.progress_state import _copy_instance_ids

    structure = result.get("structure") or {}
    entry = next((item for item in structure.get("parts", [])
                  if isinstance(item, dict) and item.get("name") == part.get("name")), None)
    instances = (entry.get("instances", [])
                 if entry is not None and structure.get("schema_version") == "2.0" else [])
    return _copy_instance_ids(instances, _part_quantity(part))


def align_copy_colors(part: Mapping[str, Any], identities: list[str]) -> dict[str, Any]:
    """Remap by ID; reject removing a colored copy rather than losing its choice."""
    result = deepcopy(dict(part))
    colors = result.get("instance_colors")
    if not colors or not any(colors):
        result.pop("instance_colors", None)
        result.pop("instance_color_ids", None)
        return result
    saved_ids = result.get("instance_color_ids")
    if saved_ids is None:
        # Pre-release local records used ordinals only. Their original graph
        # order cannot be reconstructed; retain their recorded order as-is.
        if len(colors) != len(identities):
            raise ValueError("旧逐份颜色缺少实体身份，数量改变前请先核对并重新选择颜色")
        saved_ids = identities
    if len(saved_ids) != len(colors) or len(set(saved_ids)) != len(saved_ids):
        raise ValueError("逐份颜色的实体身份无效，请先修正图解")
    by_id = dict(zip(saved_ids, colors, strict=True))
    removed = [identity for identity, color in by_id.items() if color and identity not in identities]
    if removed:
        raise ValueError(f"「{part.get('name', '未命名部件')}」调整会移除带独立颜色的实体，"
                         "请先修正实体身份或清除对应配色：" + "、".join(removed))
    result["instance_colors"] = [by_id.get(identity) for identity in identities]
    result["instance_color_ids"] = list(identities)
    return result


def require_aligned_copy_colors(result: Mapping[str, Any]) -> None:
    """Reject snapshots whose displayed copy colors would change on restore."""
    params = result.get("params") or {}
    for part in params.get("parts") or []:
        if not isinstance(part, Mapping):
            continue
        colors = _part_instance_colors(part)
        if colors is None:
            continue
        aligned = align_copy_colors(part, color_copy_ids(result, part))
        if _part_instance_colors(aligned) != colors:
            raise ValueError(f"「{part.get('name', '未命名部件')}」逐份颜色与实体身份顺序不一致；"
                             "请在高级 JSON 中预览并应用当前内容以重新对齐")


def copy_color_alignment_rows(original: Mapping[str, Any],
                              aligned: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Describe copy colors whose displayed order changed during ID alignment."""
    before = {part["name"]: part for part in original.get("parts", []) if isinstance(part, Mapping)}
    rows: list[dict[str, Any]] = []
    for part in aligned.get("parts", []):
        if not isinstance(part, Mapping):
            continue
        source = before.get(part.get("name"))
        if source is None or source.get("instance_colors") == part.get("instance_colors"):
            continue
        colors = _part_instance_colors(part)
        identities = part.get("instance_color_ids") or []
        if colors is None or len(colors) != len(identities):
            continue
        for index, (identity, color) in enumerate(zip(identities, colors, strict=True), 1):
            rows.append({"部件": part["name"], "份序": index, "实体 ID": identity,
                         "对齐后颜色": color or "沿用逐圈配色"})
    return rows
