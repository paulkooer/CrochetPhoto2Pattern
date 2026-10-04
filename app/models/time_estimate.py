"""U23 时长估算：针数×单针 + 圈数×每圈固定开销（经验模型，未校准）。

从 crochet_params 拆出的单一时长来源；常数经 trials 模块的实体试钩
校准闭环评估，修改前先读 docs/physical-trials.md 的校准流程。
"""
from __future__ import annotations

from typing import Any

from .parts import _part_quantity, _part_rounds, _round_stitches

# U23（升级版，按 Opus 5 校准）：时长 = 针数×单针 + 圈数×每圈固定开销
# （起头/记号扣/换线等固定动作）。物理驱动量是针数（每针一个手部动作）；
# 单针耗时跨密度近似恒定。结构 v2 后，classic 默认玩偶按头/身各一件、
# 手/腿各两件计为 1224 针/66 个实际圈次，约 144 分钟；旧版 121 分钟
# 漏算了第二只手臂和腿。跨密度仍使用同一物理模型。
# 数值为经验估算，不署名任何标准机构（V6 教训）。
SECONDS_PER_STITCH = 6.5
SECONDS_PER_ROUND_OVERHEAD = 10.0


def estimate_minutes(parts: list[Any]) -> int:
    """U23：共用时长估算（refresh_derived 与 _build_result 共用，消除
    两份重复实现的失同步风险）。时长 = 针数×单针 + 圈数×每圈固定开销；
    下限 30 分钟（含备料/收针/藏线头等固定开销——极小样本上线性模型
    必然低估）。经验估算值。"""
    total_stitches = sum(
        _round_stitches(rd) * _part_quantity(p)
        for p in parts for rd in _part_rounds(p))
    total_rounds = sum(
        len(_part_rounds(p)) * _part_quantity(p) for p in parts)
    return max(30, round((total_stitches * SECONDS_PER_STITCH
                          + total_rounds * SECONDS_PER_ROUND_OVERHEAD) / 60.0))


def time_estimate_basis() -> dict[str, Any]:
    """Describe the deliberately narrow, currently uncalibrated time model."""
    return {
        "scope": "round_crochet_baseline",
        "confidence": "low_uncalibrated",
        "included": ["stitch_count", "physical_round_overhead"],
        "excluded": [
            "assembly",
            "stuffing",
            "color_changes",
            "embroidery",
            "rework",
            "breaks",
        ],
        "seconds_per_stitch": SECONDS_PER_STITCH,
        "seconds_per_round_overhead": SECONDS_PER_ROUND_OVERHEAD,
        "minimum_minutes": 30,
    }
