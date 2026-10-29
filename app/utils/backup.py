"""Bounded JSON decoding for uploaded and pasted result backups."""
from __future__ import annotations

import json
import math
from typing import Any

MAX_BACKUP_BYTES = 20 << 20
MAX_PASTED_BACKUP_BYTES = 2 << 20


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("备份 JSON 不能包含非有限数值")
    return number


def _reject_constant(value: str) -> None:
    raise ValueError("备份 JSON 不能包含 NaN 或 Infinity")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("备份 JSON 含重复字段，请修正后再导入")
        value[key] = item
    return value


def loads_strict(text: str) -> Any:
    """json.loads 的严格变体：拒绝 NaN/Infinity 与重复键。

    与备份导入同口径，供分享 token 解码等其他不可信 JSON 入口复用，避免
    各入口对非有限数值/重复键的处理不一致。"""
    return json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float,
                      object_pairs_hook=_unique_object)


def decode_backup_json(payload: bytes | str, *, max_bytes: int = MAX_BACKUP_BYTES) -> dict[str, Any]:
    """Decode UTF-8 (including BOM), before the existing schema/notation checks.

    Enforce bytes rather than character count; do not accept a valid prefix of
    truncated JSON, duplicate keys or non-finite numbers. No session mutation.
    """
    limit_message = f"备份超过 {max_bytes // (1 << 20)} MiB 上限"
    if len(payload) > max_bytes:
        raise ValueError(limit_message)
    try:
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        if len(raw) > max_bytes:
            raise ValueError(limit_message)
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("备份须使用 UTF-8 编码的 JSON 文件") from exc
    if not text.strip():
        raise ValueError("请上传备份文件或粘贴完整备份 JSON")
    try:
        data = loads_strict(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"备份不是有效 JSON（第 {exc.lineno} 行，第 {exc.colno} 列）") from exc
    except RecursionError as exc:
        raise ValueError("备份 JSON 嵌套过深，请使用系统导出的完整备份") from exc
    if not isinstance(data, dict):
        raise ValueError("备份顶层必须是 JSON 对象")
    if "analysis" not in data or "structure" not in data or "params" not in data:
        raise ValueError("请使用「备份完整结果」文件，需包含 analysis、structure 和 params")
    return data
