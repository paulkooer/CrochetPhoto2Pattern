"""Bind per-copy color overrides to stable physical-copy identities."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.models.parts import _part_quantity
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


def color_copy_ids(result: ResultData, part: Mapping[str, Any]) -> list[str]:
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
        raise ValueError("调整会移除带独立颜色的实体，请先清除该实体的单独配色：" + "、".join(removed))
    result["instance_colors"] = [by_id.get(identity) for identity in identities]
    result["instance_color_ids"] = list(identities)
    return result
