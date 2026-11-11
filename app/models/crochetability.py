"""可钩性检查：拦截“针数代数自洽，但部件小到钩不成形”的生成结果。

代数自检只证明前后圈针数一致。照片头身比直接套进 Q 版模板时，默认密度下
可能生成只有 6–12 针的头部（两圈的“球”上还要装安全眼）。下限依据本仓库的
真实参考图解（tests/test_reference_patterns.py）：完整头部最小 24 针（小袋鼠
头身一体件 21 针），身体最小 30 针；四肢和尾巴确有 6 针细管的真实做法。阈值
取在这些观测值之下，只拦截明显退化的结果，不代表成品尺寸已经实物验证。

照片确认、手动输入和 CLI 首次生成时，阻断项会拒绝生成；已有图解的编辑、导入
和重算只做提示，不改写用户已确认或手写的内容。
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from .crochet_params import PatternGenerationError
from .gauge import PRESETS, Gauge
from .parts import _ONE_PIECE_NAME, one_piece_neck_index

MIN_CORE_STITCHES = 18
RECOMMENDED_CORE_STITCHES = 24

_HEAD_REASON = "钩不出球形，也装不下安全眼"
# 头部、身体与一体件的头部段承担填充、安全眼和连接，适用针数下限
_CORE_REASONS = {"头部": _HEAD_REASON, "身体": "无法形成可填充的筒身", _ONE_PIECE_NAME: _HEAD_REASON}
_LABELS = {_ONE_PIECE_NAME: "头身一体件的头部段"}
_SLIM_PARTS = frozenset({"手臂", "腿部", "尾巴"})

Level = Literal["block", "warn", "note"]
_RANK: dict[str, int] = {"note": 0, "warn": 1, "block": 2}


@dataclass(frozen=True)
class CrochetabilityFinding:
    part: str
    level: Level
    peak_stitches: int
    message: str


class PatternCrochetabilityError(PatternGenerationError):
    """首次生成遇到阻断项：针数代数自洽，但部件太小，钩不成形。"""

    def __init__(self, findings: Sequence[CrochetabilityFinding]):
        self.findings = tuple(findings)
        super().__init__("可钩性检查未通过：" + "；".join(f.message for f in self.findings))


def _stitch_counts(rounds: Sequence[Any]) -> list[int]:
    return [rd["stitches"] for rd in rounds
            if isinstance(rd, Mapping) and type(rd.get("stitches")) is int]


def _core_peak(part: Mapping[str, Any]) -> int | None:
    rounds = list(part.get("rounds") or [])
    if part.get("name") == _ONE_PIECE_NAME:
        # 一体件只看颈部及以上：身体段可以比头宽，不能替头部凑够针数
        neck = one_piece_neck_index(part)
        if neck is not None:
            rounds = rounds[:neck + 1]
    counts = _stitch_counts(rounds)
    return max(counts) if counts else None


def widest_rounds(params: Mapping[str, Any]) -> list[tuple[str, int]]:
    """各部件最宽一圈的针数，按图解部件顺序（生成前预览用）。"""
    peaks = []
    for part in params.get("parts") or []:
        if isinstance(part, Mapping) and (counts := _stitch_counts(part.get("rounds") or [])):
            peaks.append((str(part.get("name") or "?"), max(counts)))
    return peaks


def crochetability_findings(params: Mapping[str, Any]) -> list[CrochetabilityFinding]:
    """逐部件检查最宽一圈；自定义或未知部件不作推断。"""
    findings: list[CrochetabilityFinding] = []
    for part in params.get("parts") or []:
        if not isinstance(part, Mapping):
            continue
        name = str(part.get("name") or "")
        peak = _core_peak(part)
        if peak is None:
            continue
        label = _LABELS.get(name, name)
        if name in _CORE_REASONS:
            if peak < MIN_CORE_STITCHES:
                findings.append(CrochetabilityFinding(
                    name, "block", peak,
                    f"{label}最宽一圈只有 {peak} 针，低于 {MIN_CORE_STITCHES} 针下限，{_CORE_REASONS[name]}"))
            elif peak < RECOMMENDED_CORE_STITCHES:
                findings.append(CrochetabilityFinding(
                    name, "warn", peak,
                    f"{label}最宽一圈只有 {peak} 针，少于真实图解常见的 {RECOMMENDED_CORE_STITCHES} 针，"
                    "成品会很小，建议先钩小样核对"))
        elif name in _SLIM_PARTS and peak <= 6:
            findings.append(CrochetabilityFinding(
                name, "note", peak, f"{name}是 {peak} 针细管，起针后基本不加针直钩，适合细长部件"))
        elif name == "耳朵" and peak <= 6:
            findings.append(CrochetabilityFinding(
                name, "note", peak, f"耳朵只有 {peak} 针，是约两圈的小凸起"))
    return findings


def at_or_above(findings: Sequence[CrochetabilityFinding], level: Level) -> list[CrochetabilityFinding]:
    return [f for f in findings if _RANK[f.level] >= _RANK[level]]


def require_crochetable(params: Mapping[str, Any]) -> list[CrochetabilityFinding]:
    """首次生成的门禁：有阻断项时抛错，否则返回提示项。"""
    findings = crochetability_findings(params)
    if blocking := at_or_above(findings, "block"):
        raise PatternCrochetabilityError(blocking)
    return findings


T = TypeVar("T")


def first_passing(candidates: Sequence[T], passes: Callable[[T], bool]) -> T | None:
    """升序候选中第一个通过的值（检查随尺寸单调，二分查找）；返回值都实际检查过。"""
    if not candidates or not passes(candidates[-1]):
        return None
    lo, hi = 0, len(candidates) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if passes(candidates[mid]):
            hi = mid
        else:
            lo = mid + 1
    return candidates[lo]


@dataclass(frozen=True)
class CrochetabilityAdvice:
    """单独调整一项即可通过检查的最小值；None 表示在可调范围内找不到。"""

    size: float | None = None
    ratio: float | None = None
    presets: tuple[str, ...] = ()


def _grid_above(start: float, stop: float, step: float) -> list[float]:
    first = math.floor(start / step + 1e-9) + 1
    last = math.floor(stop / step + 1e-9)
    return [round(i * step, 2) for i in range(first, last + 1)]


def crochetability_advice(
    build: Callable[[float, float | None, Gauge], Mapping[str, Any]],
    *,
    gauge: Gauge,
    level: Level,
    size: float,
    size_max: float,
    ratio: float | None = None,
    ratio_max: float | None = None,
) -> CrochetabilityAdvice:
    """搜索让 ``level`` 及以上提示全部消失的最小调整。

    ``build(size, ratio, gauge)`` 必须走与真实生成相同的路径；size 是照片目标
    高度或手动头径（步长 0.5），ratio 是照片头径／主体高度（步长 0.01）。
    """
    def passes(*args: Any) -> bool:
        try:
            params = build(*args)
        except (ValueError, PatternGenerationError):
            return False
        return not at_or_above(crochetability_findings(params), level)

    denser = sorted((name for name, preset in PRESETS.items()
                     if preset.stitches_per_10cm > gauge.stitches_per_10cm),
                    key=lambda name: PRESETS[name].stitches_per_10cm)
    return CrochetabilityAdvice(
        size=first_passing(_grid_above(size, size_max, 0.5), lambda value: passes(value, ratio, gauge)),
        ratio=(first_passing(_grid_above(ratio, ratio_max, 0.01), lambda value: passes(size, value, gauge))
               if ratio is not None and ratio_max is not None else None),
        presets=tuple(name for name in denser if passes(size, ratio, PRESETS[name])),
    )
