"""Lossless count decoding shared by models, validation, and export."""
from typing import Any


def integer_count(value: Any) -> int:
    """Keep legacy integer strings/integral floats; reject booleans and truncation."""
    message = "计数必须是有限整数，不能是布尔值"
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(message)
    try:
        count = int(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(message) from exc
    if isinstance(value, float) and value != count:
        raise ValueError(message)
    return count
