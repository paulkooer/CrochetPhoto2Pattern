"""Per-operation timings and a cooperative active-work budget; no input data."""

from __future__ import annotations

import math
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class RunTrace:
    budget_seconds: float = 180.0
    stages: list[dict] = field(default_factory=list)
    fallbacks: list[str] = field(default_factory=list)
    _started: float | None = field(default=None, repr=False)

    def __post_init__(self):
        if not math.isfinite(self.budget_seconds) or not 0 < self.budget_seconds <= 600:
            raise ValueError("运行预算必须在 0–600 秒之间")

    @property
    def elapsed(self) -> float:
        return sum(s["seconds"] for s in self.stages) + (
            time.monotonic() - self._started if self._started is not None else 0
        )

    def remaining(self) -> float:
        remaining = self.budget_seconds - self.elapsed
        if remaining <= 0:
            raise TimeoutError("任务已达到运行预算；保留当前结果，请缩小图片或切换本地模式后重试")
        return remaining

    @contextmanager
    def stage(self, name: str):
        self.remaining()
        started = time.monotonic()
        self._started = started
        status = "success"
        try:
            yield
            self.remaining()
        except Exception:
            status = "failed"
            raise
        finally:
            elapsed = time.monotonic() - started
            self._started = None
            self.stages.append({"stage": name, "seconds": elapsed, "status": status})

    def payload(self) -> dict:
        return {
            "budget_seconds": self.budget_seconds,
            "active_seconds": round(self.elapsed, 4),
            "budget_mode": "cooperative_active_work",
            "stages": [{**s, "seconds": round(s["seconds"], 4)} for s in self.stages],
            "fallbacks": list(self.fallbacks),
        }


def timed_export(result: dict, name: str, operation):
    """A fresh cooperative budget for each export; only its latest timing is kept."""
    trace = RunTrace(60)
    try:
        with trace.stage(name):
            return operation()
    finally:
        diagnostics = result.setdefault("diagnostics", {})
        diagnostics.setdefault("exports", {})[name] = trace.payload()
