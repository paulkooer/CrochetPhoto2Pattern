"""Bounded JSON export values in the caller's session, never a shared cache."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from typing import TypeVar

T = TypeVar("T", str, dict)
MAX_EXPORT_CACHE_BYTES = 2 << 20
# Increment when export semantics or cached report fields change, including
# source-tree hot reloads where the installed package version stays unchanged.
EXPORT_CACHE_VERSION = 3


def cached_export(cache: dict, name: str, source: dict, build: Callable[[], T]) -> T:
    """Reuse only matching content; cache successful exports within a byte cap.

    The cap counts serialized UTF-8 values, not total Python heap usage. An
    oversized output is still downloadable, but is not retained here.
    """
    fingerprint = hashlib.sha256(json.dumps(
        {"cache_version": EXPORT_CACHE_VERSION, "source": source},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    entry = cache.get(name)
    if entry is not None and entry["fingerprint"] == fingerprint:
        return deepcopy(entry["value"])
    # Failed generation must not leave an older value eligible for reuse.
    cache.pop(name, None)
    value = build()
    size = len(json.dumps(value, ensure_ascii=False).encode())
    if size <= MAX_EXPORT_CACHE_BYTES:
        while cache and size + sum(item["bytes"] for item in cache.values()) > MAX_EXPORT_CACHE_BYTES:
            cache.pop(next(iter(cache)))
        cache[name] = {"fingerprint": fingerprint, "value": deepcopy(value), "bytes": size}
    return value


def parade_payload(result: dict) -> dict:
    from dataclasses import asdict

    from app.utils.parade_export import export_parade_report, lint_parade_dsl

    report = export_parade_report(result)
    return {**asdict(report), "issues": lint_parade_dsl(report.text)}
