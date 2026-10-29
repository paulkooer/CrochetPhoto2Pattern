"""Compare exported and drawn stitch ORDER with independent synthetic sequences."""
from __future__ import annotations

import re
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.models.ring_chart import _round_operation_sequence, render_symbol_strip
from app.models.stitch_notation import StitchExpression
from app.models.validator import validate_pattern
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report, lint_parade_dsl

_IO = {"X": (1, 1), "V": (1, 2), "A": (2, 1), "W": (1, 3), "M": (3, 1)}


def _result(note: str | None, operations: str, quantity: int = 1) -> dict:
    before = sum(_IO[op][0] for op in operations)
    after = sum(_IO[op][1] for op in operations)
    inc = sum(max(0, _IO[op][1] - _IO[op][0]) for op in operations)
    dec = sum(max(0, _IO[op][0] - _IO[op][1]) for op in operations)
    return {"params": {"parts": [{"name": "自制练习件", "quantity": quantity, "magic_ring": True,
                                  "rounds": [{"row": 1, "stitches": before},
                                             {"row": 2, "stitches": after, "increase": inc,
                                              "decrease": dec, "notes": note}]}]}}


def _code_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith(("#", "COLOR:"))]


def _expand_dsl(line: str) -> str:
    """Independent stack-based oracle for small test examples, no app parser."""
    tokens = re.findall(r"sc[23](?:inc|tog)|sc|[0-9]+|[\[\],]", line)
    stack: list[tuple[str, int]] = []
    value = ""
    repeat = 1
    for token in tokens:
        if token.isdigit():
            repeat = int(token)
        elif token == "[":
            stack.append((value, repeat))
            value, repeat = "", 1
        elif token == "]":
            previous, count = stack.pop()
            value = previous + value * count
        elif token != ",":
            value += {"sc": "X", "sc2inc": "V", "sc2tog": "A",
                      "sc3inc": "W", "sc3tog": "M"}[token] * repeat
            repeat = 1
    assert not stack
    return value


@pytest.mark.parametrize("note,operations,dsl", [
    ("X,(V,2X)×5,V,X", "X" + "VXX" * 5 + "VX", "sc,5[sc2inc,2sc],sc2inc,sc"),
    ("(X,V,V)×6", "XVV" * 6, "6[sc,sc2inc,sc2inc]"),
    ("3X,V,A", "XXXVA", "3sc,sc2inc,sc2tog"),
    ("2X,W,M", "XXWM", "2sc,sc3inc,sc3tog"),
    ("4V,2X", "VVVVXX", "4sc2inc,2sc"),
    ("2((X,V)×3,A)", ("XV" * 3 + "A") * 2, "2[3[sc,sc2inc],sc2tog]"),
    ("*1 sc,1 sc-inc,1 sc* crochet 5 times", "XVX" * 5, "5[sc,sc2inc,sc]"),
    ("准备填充；2X,W,M；留线缝合", "XXWM", "2sc,sc3inc,sc3tog"),
])
def test_export_and_chart_preserve_every_operation_position(note, operations, dsl):
    result = _result(note, operations)
    part = result["params"]["parts"][0]
    assert validate_pattern(result["params"])["ok"]
    report = export_parade_report(result)
    assert report.complete and report.inferred_rounds == 0
    # Multiple top-level operations still form exactly one exported round.
    assert _code_lines(report.text) == ["ring", f"sc{part['rounds'][0]['stitches']}inc", dsl]
    assert report.exported_rounds == report.requested_rounds == 2
    assert lint_parade_dsl(report.text) == []
    assert _expand_dsl(dsl) == operations
    assert "".join(_round_operation_sequence(part["rounds"], 1)) == operations
    svg = ET.fromstring(render_symbol_strip(part, max_marks=100))
    drawn = "".join(node.attrib["data-kind"] for node in svg.iter() if "data-kind" in node.attrib)
    assert drawn == "X" * part["rounds"][0]["stitches"] + operations


def test_markdown_stitch_column_retains_placement_instead_of_uniform_rewrite():
    note = "X,(V,2X)×5,V,X"
    result = _result(note, "X" + "VXX" * 5 + "VX")
    row = next(line for line in export_markdown(result["params"]).splitlines() if line.startswith("| 2 |"))
    assert row.split("|")[5].strip() == note
    assert "(2X,V)×6" not in row
    result["params"]["parts"][0]["rounds"][1]["notes"] = "按自定位置加针"
    row = next(line for line in export_markdown(result["params"]).splitlines() if line.startswith("| 2 |"))
    assert row.split("|")[5].strip() == "—"


@given(st.lists(st.sampled_from("XVAWM"), min_size=1, max_size=20), st.integers(1, 5))
def test_random_repeat_exports_match_independently_expanded_sequence(ops, repeat):
    note = f"({','.join(ops)})×{repeat}"
    expected = "".join(ops) * repeat
    result = _result(note, expected)
    report = export_parade_report(result)
    assert report.complete
    assert lint_parade_dsl(report.text) == []
    assert _expand_dsl(_code_lines(report.text)[-1]) == expected


def test_same_counts_different_order_produce_different_exports_and_charts():
    first = _result("(2X,V)×6", "XXV" * 6)
    second = _result("(X,V,X)×6", "XVX" * 6)
    a, b = [r["params"]["parts"][0] for r in (first, second)]
    assert {k: v for k, v in a["rounds"][1].items() if k != "notes"} == {
        k: v for k, v in b["rounds"][1].items() if k != "notes"
    }
    assert export_parade_report(first).text != export_parade_report(second).text
    assert render_symbol_strip(a) != render_symbol_strip(b)


@pytest.mark.parametrize("note", ["(X,V)×6", "不加不减", "共 999 针", "(V×6"])
def test_export_stops_on_note_contradiction_without_breaking_other_parts(note):
    result = _result("V×6", "V" * 6, quantity=2)
    good = deepcopy(result["params"]["parts"][0])
    good.update(name="完整件", quantity=1)
    bad = result["params"]["parts"][0]
    bad["rounds"][1]["notes"] = note
    bad["rounds"].append({"row": 3, "stitches": 12, "notes": "12X", "color": "#ff0000"})
    result["params"]["parts"].append(good)
    report = export_parade_report(result)
    assert not report.complete
    assert (report.exported_rounds, report.requested_rounds) == (4, 8)
    assert (report.exported_parts, report.requested_parts) == (1, 3)
    assert "该圈及后续圈已跳过" in report.text
    assert "12sc" not in _code_lines(report.text)
    assert "COLOR: #ff0000" not in report.text
    assert lint_parade_dsl(report.text) == []


def test_first_round_instruction_error_skips_only_that_part():
    result = _result("V×6", "V" * 6)
    bad = deepcopy(result["params"]["parts"][0])
    bad["rounds"][0]["notes"] = "魔法环起999针"
    result["params"]["parts"].insert(0, bad)
    report = export_parade_report(result)
    assert not report.complete
    assert (report.exported_parts, report.requested_parts) == (1, 2)
    assert "首圈说明矛盾" in report.text


def test_multiple_whole_round_formulas_are_not_arbitrarily_chosen():
    result = _result("(2X,V)×6；(X,V,X)×6", "XXV" * 6)
    report = export_parade_report(result)
    assert not report.complete and "多个独立操作式" in report.text
    assert "针位待核对" in render_symbol_strip(result["params"]["parts"][0])
    assert "请核对说明中的操作式" in export_markdown(result["params"])


def test_aggregate_fallback_is_counted_per_physical_copy():
    result = _result(None, "XXV" * 6, quantity=3)
    report = export_parade_report(result)
    assert report.complete and report.inferred_rounds == 3
    assert "按数值均匀安排针位" in report.text
    result["params"]["parts"][0]["rounds"][1]["notes"] = "(2X,V)×6"
    assert export_parade_report(result).inferred_rounds == 0


def test_mixed_shaping_without_explicit_order_is_not_drawn_as_plain_stitches():
    result = _result(None, "XXXVA")
    part = result["params"]["parts"][0]
    assert _round_operation_sequence(part["rounds"], 1) == []
    assert "针位待核对" in render_symbol_strip(part)
    assert not export_parade_report(result).complete


def test_large_repeat_stays_compact_and_chart_only_reads_visible_prefix(monkeypatch):
    result = _result("(X,V)×30000", "XV" * 30000)
    original = StitchExpression.iter_stitches

    def bounded(self):
        for index, stitch in enumerate(original(self)):
            assert index < 18, "chart expanded operations beyond its visible prefix"
            yield stitch

    monkeypatch.setattr(StitchExpression, "iter_stitches", bounded)
    report = export_parade_report(result)
    assert report.complete
    assert _code_lines(report.text)[-1] == "30000[sc,sc2inc]"
    assert lint_parade_dsl(report.text) == []
    svg = render_symbol_strip(result["params"]["parts"][0])
    assert svg.count('data-kind=') == 36  # 18 visible operations for each round.
    assert "+59982" in svg


@pytest.mark.parametrize("line", [
    "2[3[sc,sc2inc],sc2tog]", "sc,5[sc2inc,2sc],sc2inc,sc", "2sc,sc3inc,sc3tog",
])
def test_emitter_lint_accepts_nested_and_mixed_operations(line):
    assert lint_parade_dsl(line) == []


@pytest.mark.parametrize("line", [
    "2[sc,3[sc2inc]", "2[sc,]", "2[]", "sc,,sc", "0sc", "2[sc,unknown]",
    "sc3inc extra", "2sc2tog,", "2[sc]]", "COLOR: #ffffff; start_anew",
    "9" * 5000 + "sc", "2[" * 20 + "sc" + "]" * 20,
])
def test_emitter_lint_rejects_invalid_or_excessive_syntax(line):
    assert lint_parade_dsl(line)


def test_metadata_cannot_inject_instruction_lines():
    result = _result(None, "XXV" * 6)
    part = result["params"]["parts"][0]
    part["name"] = "name\nstart_anew\nsc999inc"
    part["color"] = "#ffffff\nstart_anew\nsc999inc"
    report = export_parade_report(result)
    assert "sc999inc" not in _code_lines(report.text)
    assert "start_anew" not in _code_lines(report.text)
    assert lint_parade_dsl(report.text) == []


@pytest.mark.parametrize("color,expected", [("#aBc", "#aaBBcc"), ("#a1B2c3", "#a1B2c3")])
def test_valid_custom_hex_colors_survive_export(color, expected):
    result = _result("(2X,V)×6", "XXV" * 6)
    result["params"]["parts"][0]["color"] = color
    report = export_parade_report(result)
    assert f"COLOR: {expected}" in report.text
    assert lint_parade_dsl(report.text) == []
