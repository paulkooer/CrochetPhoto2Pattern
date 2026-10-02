"""PatternValidator（T4）——生成后图解自检，借鉴 CrochetPARADE 的
correctness checking 理念：把"代数自洽"从测试层暴露给用户。

检查项：
1. 针数代数：每圈针数 = 上圈针数 + 加针 − 减针（首圈为起针，不检查）；
2. 可执行性：针数 ≥ 1（组合减针——M/sc4tog——不受纯 A 配对
   限制，见第 5 处先验降级）；
3. 生成器先验（notes 提示，非硬错误——印证校准）：非 6 倍数圈与
   超平滑节奏圈只提示、正常导出；加减速混用圈、加针超源针圈、减针
   超纯 A 配对圈超出均匀分组表达，由 Parade 导出器跳过并留 warning。
   混用圈在真实图解的面部/异形塑形中常见（如垂耳兔眼窝圈
   7X,7V,A,7V,7X）；加针超源在空间加针工艺中常见（如 granny 四角
   往锁针空间加针）——均完全可钩；
4. 圈数非空（schema 层已拦，这里兜底 JSON 直改路径）。

输出的 issues 是"部件名 + 圈号 + 具体矛盾"的可读列表——用户据此用
局部修正修复，而不是拿到一份默默错误的图解。
"""
from __future__ import annotations

from typing import Any

from ..schemas import MAX_PART_ROUNDS, MAX_PATTERN_PARTS, MAX_ROUND_STITCHES
from ..utils.counts import integer_count as _integer_count
from .gauge import gauge_from_mapping


def shaping_policy_for_pattern(params: dict[str, Any]) -> dict[str, Any]:
    """Derive trusted shaping policy from gauge, never editable metadata."""
    gauge = gauge_from_mapping(params.get("gauge"))
    return {
        "continuous_delta": round(gauge.shaping_continuous_delta, 2),
        "max_stitch_change": gauge.max_shaping_change,
        "quantization": "ceil_to_six_stitch_sectors",
    }


def shaping_limit_for_pattern(params: dict[str, Any]) -> int:
    """Compatibility helper returning the trusted per-round stitch cap."""
    return int(shaping_policy_for_pattern(params)["max_stitch_change"])


def validate_pattern(params: dict[str, Any]) -> dict[str, Any]:
    """校验图解代数自洽 + 物理边界。返回 {"ok", "issues", "checked"}。

    两类检查解耦（V2）：
    - 代数自洽（一直有）：每圈针数 = 上圈 + 加 − 减；
    - 物理边界：相邻圈变化不超过 gauge 的
      ``ceil_to_6(2π·行高/针宽)``；旧图解无 gauge 时回退经典 ±6。
      宽跳变默认只降级为 note；CrochetStitch.allow_wide_jump
      置位可抑制该 note（如波浪裙摆"每针放2针"）。
    """
    issues: list[str] = []
    notes: list[str] = []
    checked = 0
    shaping_policy = shaping_policy_for_pattern(params)
    max_change = int(shaping_policy["max_stitch_change"])
    parts = params.get("parts")
    seen_names: set[str] = set()
    if not isinstance(parts, list) or not parts:
        issues.append("图解缺少有效的部件列表")
        parts = []
    elif len(parts) > MAX_PATTERN_PARTS:
        issues.append(
            f"部件数量 {len(parts)} 超过上限 {MAX_PATTERN_PARTS}，仅检查前 "
            f"{MAX_PATTERN_PARTS} 个")
        parts = parts[:MAX_PATTERN_PARTS]
    for index, part in enumerate(parts, 1):
        if not isinstance(part, dict):
            issues.append(f"第 {index} 个部件：必须是对象")
            continue
        name = part.get("name", "?")
        if isinstance(name, str) and name != "?":
            if name in seen_names:
                issues.append(f"{name}: 部件名称不能重复")
            seen_names.add(name)
        try:
            quantity = _integer_count(part.get("quantity", 1))
            if not 1 <= quantity <= 20:
                raise ValueError("部件数量超出范围")
        except ValueError:
            issues.append(f"{name}: 部件数量必须是 1–20 的整数（不能是布尔值）")
        rounds = part.get("rounds")
        if not isinstance(rounds, list) or not rounds:
            issues.append(f"{name}: 没有任何圈或圈列表格式无效")
            continue
        if len(rounds) > MAX_PART_ROUNDS:
            issues.append(
                f"{name}: 圈数 {len(rounds)} 超过上限 {MAX_PART_ROUNDS}，"
                "跳过逐圈代数检查")
            continue
        checked += len(rounds)
        prev_stitches = None
        seen_rows: set[int] = set()
        for i, rd in enumerate(rounds, 1):
            if not isinstance(rd, dict):
                issues.append(f"{name} 第 {i} 圈：必须是对象")
                prev_stitches = None
                continue
            # Legacy dict patterns may omit row labels; explicit labels must
            # be positive and unique to keep progress-widget identities valid.
            if "row" in rd:
                try:
                    row = _integer_count(rd["row"])
                    if row < 1 or row in seen_rows:
                        raise ValueError("圈号无效或重复")
                    seen_rows.add(row)
                except ValueError:
                    issues.append(f"{name} 第 {i} 圈：圈号必须是正整数且不能重复")
            try:
                st = _integer_count(rd.get("stitches", 0))
                inc = _integer_count(0 if rd.get("increase") is None else rd["increase"])
                dec = _integer_count(0 if rd.get("decrease") is None else rd["decrease"])
            except (TypeError, ValueError, OverflowError):
                issues.append(f"{name} 第 {i} 圈：针数/加减针必须是有限整数（不能是布尔值）")
                prev_stitches = None
                continue
            if inc < 0 or dec < 0:
                issues.append(f"{name} 第 {i} 圈：加减针不能为负数")
                prev_stitches = None
                continue
            if st > MAX_ROUND_STITCHES:
                # 病态输入（如手改 JSON 写入 1e99）会污染后续所有代数消息；
                # 报上限并重置相邻链，让之后的圈恢复可读诊断。
                issues.append(f"{name} 第 {i} 圈：针数 {st} 超出上限 {MAX_ROUND_STITCHES}")
                prev_stitches = None
                continue
            if inc > 0 and dec > 0:
                # 印证修正：真实图解的面部/异形塑形常在同圈混用加减速
                # （垂耳兔眼窝圈 7X,7V,A,7V,7X：30→43），代数与可执行性
                # 均成立——只是超出本生成器的均匀分组表达，降级为提示；
                # parade 导出器会诚实跳过该圈
                notes.append(
                    f"{name} 第 {i} 圈：同圈混用加针 {inc} 与减针 {dec}——"
                    "面部/异形塑形的常见写法，可钩；超出均匀分组表达，"
                    "CrochetPARADE 导出将跳过此圈")
            if st < 1:
                issues.append(f"{name} 第 {i} 圈：针数 {st} 无效")
            elif st < 6 or st % 6:
                # 印证修正（真实图解校准）：六等分是本生成器的先验约定，
                # 不是可钩性要求——社区公开图解常见 22 针腿、16 针臂、
                # 9 针尾（Clover AKIHIRO）。降级为提示而非错误。
                notes.append(
                    f"{name} 第 {i} 圈：针数 {st} 非 6 的倍数——偏离本生成器"
                    "的六等分先验，但仍可正常钩织")
            if prev_stitches is not None:
                expect = prev_stitches + inc - dec
                if st != expect:
                    issues.append(
                        f"{name} 第 {i} 圈：针数 {st} ≠ 上圈 {prev_stitches}"
                        f" + {inc} − {dec} = {expect}")
                if inc > prev_stitches:
                    # 印证修正（第 4 处先验降级）：V 不多于源针是均匀分组
                    # 表达的限制而非可钩性边界——granny 四角往锁针空间
                    # 加针（12→28，每边每圈 +4，Lion Brand/Marching North
                    # 逐字源）、贝壳花与 W（1 针目 3 短针）往单针塞多针，
                    # 均完全可钩。降级为 notes，导出器跳过该圈。
                    notes.append(
                        f"{name} 第 {i} 圈：加针 {inc} 超过上圈 "
                        f"{prev_stitches} 个源针——若为往锁针空间或单针内"
                        "多针的工艺（granny 四角、贝壳花、W 泡芙）则完全"
                        "可钩；超出均匀分组 (aX,V)×n 表达，导出将跳过此圈")
                if dec > prev_stitches // 2:
                    # 印证修正（第 5 处先验降级，外部 AI 审核发现）：
                    # "A 不多于源针一半"只对纯 A（2并1）成立；词表中的
                    # M（3→1）、sc4tog（4→1）、圈圈减针（挂4环）都是真实
                    # 可钩的组合减针——机械反例：上一圈 4 针用一次
                    # sc4tog 收到 1 针（1 = 4 + 0 − 3，而 3 > 4//2）。
                    # decrease 字段语义是"净减少针数"，不能同时当作
                    # "A 的数量"。降级为 notes，导出器跳过该圈。
                    notes.append(
                        f"{name} 第 {i} 圈：减针 {dec} 超过上圈 "
                        f"{prev_stitches} 针的纯 A（2并1）配对上限——若含"
                        " M 三并一/sc4tog/跳针等组合减针则完全可钩；超出"
                        "均匀分组 (aX,A)×n 表达，导出将跳过此圈")
                # V2 → 印证修正：|Δ| 上限是本生成器的平滑度先验而非
                # 可钩性边界（真实图解的 8→16 倍增圈常见且完全可钩）。
                # 超限降级为 notes；allow_wide_jump 只是抑制这条 note 的
                # 标志（置位与否 ok 均为真）——生成器仍对波浪裙摆等
                # 装饰工艺显式置位以保持 notes 干净。
                if abs(st - prev_stitches) > max_change and not rd.get(
                        "allow_wide_jump", False):
                    notes.append(
                        f"{name} 第 {i} 圈：相邻圈跳变 {prev_stitches}→{st} "
                        f"超过本生成器的平滑塑形节奏 ±{max_change}——"
                        "确认为有意工艺（如倍增圈）即可照钩")
            prev_stitches = st if st > 0 else None

    return {"ok": not issues, "issues": issues, "notes": notes,
            "checked": checked,
            "max_stitch_change": max_change,
            "shaping_continuous_delta": shaping_policy["continuous_delta"]}
