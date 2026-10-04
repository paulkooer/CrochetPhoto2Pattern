"""部件 dict 访问助手与部件名常量——材料/装配/时长/生成器的共享底层。

params["parts"] 的统一 dict 形态（见 crochet_params._build_result 双态收敛）
是所有派生量的共同输入；微型访问助手集中在无依赖的本模块，派生模块
（materials/assembly/time_estimate）只依赖这里，不反向依赖 crochet_params。
"""
from __future__ import annotations

from typing import Any

# 头身一体件：粗略计入两组用线（实际占比取决于配色，可试钩后修正）
_ONE_PIECE_NAME = "头身（一体）"


# 材料分组：哪些部件用肤色线 / 主体色线
_SKIN_PARTS = frozenset({"头部", "手臂", "腿部", "耳朵"})
_BODY_PARTS = frozenset({"身体", "帽子", "裙子", "尾巴"})


def _part_name(part: dict[str, Any]) -> str:
    return part["name"]


def _part_rounds(part: dict[str, Any]) -> list[dict[str, Any]]:
    return part.get("rounds", [])


def _part_quantity(part: dict[str, Any]) -> int:
    """Physical copies represented by one logical part pattern (legacy = 1)."""
    try:
        return max(1, min(20, int(part.get("quantity", 1))))
    except (TypeError, ValueError):
        return 1


def _round_stitches(rd: dict[str, Any]) -> int:
    return int(rd.get("stitches", 0))
