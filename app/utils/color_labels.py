"""Display names for yarn placeholders, without changing stored colors."""

from __future__ import annotations

import re

_PLACEHOLDER_LABELS = {
    "skin": "肤色（待选色）",
    "body": "主体色（待选色）",
}
_CHANGE_COLOR = re.compile(
    r"(?<=换线：)(skin|body)(?=（前一针最后一次挂线改用新色；螺旋圈仍可能出现台阶）)"
)
_SUMMARY_COLOR = re.compile(r"(R\d+(?:–R\d+)? )(skin|body)(?=[；。])")


def display_color_name(color: object) -> object:
    """Translate the two reserved values; preserve custom and legacy values."""
    if isinstance(color, str):
        return _PLACEHOLDER_LABELS.get(color, color)
    return color


def is_reserved_placeholder(color: object) -> bool:
    """True for the internal ``skin``/``body`` placeholders.

    They mean "no yarn chosen yet", so a colour picker must offer a real yarn
    instead of pre-filling the internal value as if the user had picked it.
    """
    return isinstance(color, str) and color in _PLACEHOLDER_LABELS


def display_generated_color_note(note: object, generated: object) -> object:
    """Translate known generated fragments only; retain all user-written text."""
    if not isinstance(note, str) or not isinstance(generated, str) or not generated:
        return note
    if generated.startswith("换线："):
        shown = _CHANGE_COLOR.sub(lambda match: _PLACEHOLDER_LABELS[match[1]], generated)
    elif generated.startswith(" 配色（按钩织圈序，"):
        shown = _SUMMARY_COLOR.sub(lambda match: match[1] + _PLACEHOLDER_LABELS[match[2]], generated)
    else:
        return note
    before, found, after = note.rpartition(generated)
    return before + shown + after if found else note
