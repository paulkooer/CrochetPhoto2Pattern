"""Finite numeric decoding for physical inputs; booleans are not measurements."""
import math
from typing import Any


def finite_float(value: Any) -> float:
    message = "尺寸或密度必须是有限数值，不能是布尔值"
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(message)
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(message) from exc
    if not math.isfinite(number):
        raise ValueError(message)
    return number
