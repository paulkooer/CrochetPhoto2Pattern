"""PatternValidator（T4）——生成后图解自检，借鉴 CrochetPARADE 的
correctness checking 理念：把"代数自洽"从测试层暴露给用户。

检查项：
1. 针数代数：每圈针数 = 上圈针数 + 加针 − 减针（首圈为起针，不检查）；
2. 加减针不共存：同一圈不得同时加针与减针；
3. 六等分拓扑与可执行性：针数为正的 6 倍数；V 不多于源针数，A 不多于
   源针数的一半；
4. 圈数非空（schema 层已拦，这里兜底 JSON 直改路径）。

输出的 issues 是"部件名 + 圈号 + 具体矛盾"的可读列表——用户据此用
局部修正修复，而不是拿到一份默默错误的图解。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .gauge import gauge_from_mapping


def _rounds_of(part: Any) -> List[Dict[str, Any]]:
    rounds = part.get("rounds", []) if isinstance(part, dict) else getattr(
        part, "rounds", [])
    out = []
    for r in rounds:
        out.append(r if isinstance(r, dict) else (
            r.model_dump() if hasattr(r, "model_dump") else {}))
    return out


def shaping_policy_for_pattern(params: Dict[str, Any]) -> Dict[str, Any]:
    """Derive trusted shaping policy from gauge, never editable metadata."""
    gauge = gauge_from_mapping(params.get("gauge"))
    return {
        "continuous_delta": round(gauge.shaping_continuous_delta, 2),
        "max_stitch_change": gauge.max_shaping_change,
        "quantization": "ceil_to_six_stitch_sectors",
    }


def shaping_limit_for_pattern(params: Dict[str, Any]) -> int:
    """Compatibility helper returning the trusted per-round stitch cap."""
    return int(shaping_policy_for_pattern(params)["max_stitch_change"])


def validate_pattern(params: Dict[str, Any]) -> Dict[str, Any]:
    """校验图解代数自洽 + 物理边界。返回 {"ok", "issues", "checked"}。

    两类检查解耦（V2）：
    - 代数自洽（一直有）：每圈针数 = 上圈 + 加 − 减；加减不共存；
    - 物理边界：相邻圈变化不超过 gauge 的
      ``ceil_to_6(2π·行高/针宽)``；旧图解无 gauge 时回退经典 ±6。
      装饰性宽跳变须由
      CrochetStitch.allow_wide_jump 显式置位豁免（如波浪裙摆
      "每针放2针"），否则视为生成器缺陷。
    """
    issues: List[str] = []
    checked = 0
    shaping_policy = shaping_policy_for_pattern(params)
    max_change = int(shaping_policy["max_stitch_change"])
    for part in params.get("parts", []):
        name = (part.get("name") if isinstance(part, dict)
                else getattr(part, "name", "?"))
        rounds = _rounds_of(part)
        if not rounds:
            issues.append(f"{name}: 没有任何圈")
            continue
        checked += len(rounds)
        prev_stitches = None
        for i, rd in enumerate(rounds, 1):
            try:
                st = int(rd.get("stitches", 0))
                inc = int(rd.get("increase") or 0)
                dec = int(rd.get("decrease") or 0)
            except (TypeError, ValueError):
                issues.append(f"{name} 第 {i} 圈：针数/加减针不是数字")
                continue
            if inc > 0 and dec > 0:
                issues.append(f"{name} 第 {i} 圈：同时加针 {inc} 与减针 {dec}")
            if st < 6 or st % 6:
                issues.append(
                    f"{name} 第 {i} 圈：针数 {st} 不是正的 6 的倍数")
            if prev_stitches is not None:
                expect = prev_stitches + inc - dec
                if st != expect:
                    issues.append(
                        f"{name} 第 {i} 圈：针数 {st} ≠ 上圈 {prev_stitches}"
                        f" + {inc} − {dec} = {expect}")
                if inc > prev_stitches:
                    issues.append(
                        f"{name} 第 {i} 圈：加针 {inc} 超过上圈 "
                        f"{prev_stitches} 个源针，无法用每源针至多一个 V 执行")
                if dec > prev_stitches // 2:
                    issues.append(
                        f"{name} 第 {i} 圈：减针 {dec} 超过上圈 "
                        f"{prev_stitches} 针可组成的 A 数量")
                # V2：物理边界（显式白名单豁免——波浪裙摆等装饰工艺）
                if abs(st - prev_stitches) > max_change and not rd.get(
                        "allow_wide_jump", False):
                    issues.append(
                        f"{name} 第 {i} 圈：相邻圈跳变 {prev_stitches}→{st} "
                        f"超过当前密度塑形上限 ±{max_change} "
                        "且未声明 allow_wide_jump")
            prev_stitches = st

    return {"ok": not issues, "issues": issues, "checked": checked,
            "max_stitch_change": max_change,
            "shaping_continuous_delta": shaping_policy["continuous_delta"]}
