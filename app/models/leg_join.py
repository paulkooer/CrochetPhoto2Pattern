"""A manual planning aid for joining two open leg rounds with a chain bridge."""
from __future__ import annotations

import json
import re

from app.schemas import MAX_ROUND_STITCHES

MAX_LEG_JOIN_PLAN_BYTES = 16 * 1024


def leg_join_plan(*, left_row: int, left_stitches: int, left_marker: int,
                  right_row: int, right_stitches: int, right_marker: int,
                  chain: int) -> dict:
    """Count one sc in each leg stitch and on each side of each chain stitch.

    Inputs describe the maker's actual openings; they are not inferred from a pattern.
    The marker indices are references for manual review, not a proven connection path.
    """
    fields = {"左腿圈号": left_row, "左腿开口针数": left_stitches, "左腿记号针": left_marker,
              "右腿圈号": right_row, "右腿开口针数": right_stitches, "右腿记号针": right_marker,
              "连接锁针数": chain}
    for name, value in fields.items():
        if type(value) is not int or not 1 <= value <= MAX_ROUND_STITCHES:
            raise ValueError(f"{name}须为 1–{MAX_ROUND_STITCHES} 的整数")
    if left_marker > left_stitches or right_marker > right_stitches:
        raise ValueError("记号针序号不能超过对应腿部开口针数")
    total = left_stitches + right_stitches + 2 * chain
    if total > MAX_ROUND_STITCHES:
        raise ValueError(f"连接后的总针数超过上限 {MAX_ROUND_STITCHES}")
    return {
        "schema_version": "1",
        "kind": "manual_leg_chain_join_plan",
        "left": {"row": left_row, "stitches": left_stitches, "marker": left_marker},
        "right": {"row": right_row, "stitches": right_stitches, "marker": right_marker},
        "chain_stitches": chain,
        "chain_sides": 2,
        "sc_per_base_stitch": 1,
        "result_stitches": total,
    }


def decode_leg_join_plan(data: bytes) -> dict:
    """Reject ambiguous or altered plans before exposing any values to the UI."""
    if len(data) > MAX_LEG_JOIN_PLAN_BYTES:
        raise ValueError("并腿方案超过 16 KiB 上限")

    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("并腿方案包含重复字段")
            obj[key] = value
        return obj

    def nonfinite(value):
        raise ValueError("并腿方案不能包含非有限数值")

    try:
        payload = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique,
                             parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("并腿方案不是有效的 UTF-8 JSON") from exc
    fields = {"schema_version", "kind", "left", "right", "chain_stitches", "chain_sides",
              "sc_per_base_stitch", "result_stitches"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError("并腿方案字段不完整或包含未知字段")
    if payload["schema_version"] != "1" or payload["kind"] != "manual_leg_chain_join_plan":
        raise ValueError("并腿方案类型或版本不支持")
    for side in ("left", "right"):
        part = payload[side]
        if not isinstance(part, dict) or set(part) != {"row", "stitches", "marker"}:
            raise ValueError("并腿方案开口记录无效")
    for key in ("chain_sides", "sc_per_base_stitch", "result_stitches"):
        if type(payload[key]) is not int:
            raise ValueError("并腿方案针数须为整数")
    left, right = payload["left"], payload["right"]
    checked = leg_join_plan(left_row=left["row"], left_stitches=left["stitches"],
                            left_marker=left["marker"], right_row=right["row"],
                            right_stitches=right["stitches"], right_marker=right["marker"],
                            chain=payload["chain_stitches"])
    if payload != checked:
        raise ValueError("并腿方案的计数或做法不一致，请重新核对")
    return checked


def compare_leg_join(plan: dict, parts: list[dict], left_index: int, right_index: int
                     ) -> tuple[list[dict], list[str]]:
    """Compare explicit references with selected parts without mutating either."""
    if any(type(i) is not int or i < 0 or i >= len(parts) for i in (left_index, right_index)):
        raise ValueError("请选择当前图解中的左右腿部件")
    rows = []
    issues = []
    if left_index == right_index:
        quantity = parts[left_index].get("quantity", 1)
        if type(quantity) is not int or quantity < 2:
            issues.append("左右腿选择了同一部件，但该部件不足两份实体")
    for side, label, index in (("left", "左腿", left_index), ("right", "右腿", right_index)):
        part = parts[index]
        quantity = part.get("quantity", 1)
        if type(quantity) is not int or quantity < 1:
            issues.append(f"{label}：部件实体数量无效")
        reference = plan[side]
        rounds = part.get("rounds")
        matches = ([r for r in rounds if isinstance(r, dict) and type(r.get("row")) is int
                    and r["row"] == reference["row"]]
                   if isinstance(rounds, list) else [])
        actual = matches[0].get("stitches") if len(matches) == 1 else None
        if len(matches) != 1 or type(actual) is not int or actual < 1:
            status = "圈号不存在或不唯一"
            actual = None
        elif actual != reference["stitches"]:
            status = "针数不一致"
        else:
            status = "圈号与针数一致"
        if status != "圈号与针数一致":
            issues.append(f"{label}：{status}")
        rows.append({"侧别": label, "所选部件": str(part.get("name", "未命名")),
                     "方案圈号": reference["row"], "方案针数": reference["stitches"],
                     "图解针数": actual if actual is not None else "—", "核对": status})
    return rows, issues


def leg_join_advisories(plan: dict, parts: list[dict], left_index: int, right_index: int) -> list[str]:
    """Flag later rounds and finish-related wording without inferring a physical opening."""
    if any(type(i) is not int or i < 0 or i >= len(parts) for i in (left_index, right_index)):
        raise ValueError("请选择当前图解中的左右腿部件")
    warnings = []
    for side, label, index in (("left", "左腿", left_index), ("right", "右腿", right_index)):
        rounds = parts[index].get("rounds")
        if not isinstance(rounds, list):
            continue
        row_number = plan[side]["row"]
        matches = [(i, r) for i, r in enumerate(rounds) if isinstance(r, dict)
                   and type(r.get("row")) is int and r["row"] == row_number]
        if len(matches) != 1:
            continue
        position, row = matches[0]
        later = len(rounds) - position - 1
        if later:
            warnings.append(f"{label}：所选第 {row_number} 圈后还有 {later} 圈；"
                            "请确认连接时实际停在此圈，后续圈及收尾是否需要调整。")
        notes = row.get("notes")
        if isinstance(notes, str) and re.search(
                r"断线|收口|封口|缝合|fasten\s+off|\bfinish(?:ed|ing)?\b", notes, re.I):
            warnings.append(f"{label}：所选圈说明提及断线、收口或缝合等收尾；"
                            "请核对其具体要求以及连接前是否仍有开口。")
    return warnings
