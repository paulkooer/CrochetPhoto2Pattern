"""Technique identity and row labels must survive counting and presentation."""
import html
from copy import deepcopy
from itertools import islice
from xml.etree import ElementTree as ET

import pytest

from app.models.instruction_checks import round_expression
from app.models.ring_chart import _round_operation_sequence, render_ring_svg, render_symbol_strip
from app.models.stitch_connections import round_connections
from app.models.stitch_notation import (
    StitchCounts,
    UnsupportedLoopError,
    format_stitch_expression,
    parse_stitch_expression,
    parse_stitch_notation,
)
from app.models.validator import validate_pattern
from app.schemas import PatternResult
from app.ui.pattern_editor import edit_rounds
from app.ui.result_logic import import_backup
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report, lint_parade_dsl
from tests.test_app_smoke import _mock_result


def _part(note="2X,inv-sc2tog", *, quantity=1):
    return {"name": "自制减针练习", "type": "cylinder", "color": "红色",
            "quantity": quantity, "magic_ring": True, "rounds": [
                {"row": 7, "stitches": 4, "notes": "4X"},
                {"row": 19, "stitches": 3, "decrease": 1, "notes": note},
                {"row": 23, "stitches": 3, "notes": "3X"},
            ]}


@pytest.mark.parametrize("note,counts,prefix", [
    ("2X,inv-sc2tog", StitchCounts(4, 3, 0, 1), ["X", "X", "inv-sc2tog"]),
    ("2((X,inv-sc2tog)×2,A)", StitchCounts(16, 10, 0, 6),
     ["X", "inv-sc2tog", "X", "inv-sc2tog", "A"] * 2),
    ("INV-SC2TOG×50000", StitchCounts(100000, 50000, 0, 50000), ["inv-sc2tog"] * 10),
])
def test_invisible_decrease_retains_technique_in_order_and_compact_roundtrip(note, counts, prefix):
    expression = parse_stitch_expression(note)
    assert expression is not None
    assert expression.counts == counts == parse_stitch_notation(note)
    assert expression.has_invisible_decrease and not expression.has_loop_technique
    assert list(islice(expression.iter_stitches(), len(prefix))) == prefix
    formatted = format_stitch_expression(expression)
    assert "inv-sc2tog" in formatted and len(formatted) < 100
    restored = parse_stitch_expression(formatted)
    assert restored is not None and restored.has_invisible_decrease
    assert restored.counts == counts
    assert list(islice(restored.iter_stitches(), len(prefix))) == prefix


def test_invisible_decrease_is_not_aliased_to_ordinary_or_front_loop_decrease():
    expressions = [parse_stitch_expression(text) for text in ("A", "sc2tog", "A-FLO", "inv-sc2tog")]
    assert all(expression.counts == StitchCounts(2, 1, 0, 1) for expression in expressions)
    assert [list(expression.iter_stitches()) for expression in expressions] == [
        ["A"], ["A"], ["A-FLO"], ["inv-sc2tog"],
    ]


def test_partial_dsl_stops_at_invisible_decrease_but_keeps_other_parts_and_copies():
    part = _part(quantity=2)
    good = {"name": "普通件", "magic_ring": True, "rounds": [
        {"row": 1, "stitches": 4}, {"row": 2, "stitches": 8, "increase": 4, "notes": "4V"},
    ]}
    result = {"params": {"parts": [part, good]}}
    original = deepcopy(result)
    assert validate_pattern(result["params"])["ok"]
    report = export_parade_report(result)
    assert not report.complete
    assert (report.exported_parts, report.requested_parts) == (1, 3)
    assert (report.exported_rounds, report.requested_rounds) == (4, 8)
    assert report.inferred_rounds == 0
    assert any("第 19 圈" in warning and "隐形减针" in warning for warning in report.warnings)
    code = [line for line in report.text.splitlines() if line and not line.startswith(("#", "COLOR:"))]
    assert "2sc,sc2tog" not in code and "3sc" not in code
    assert "4sc2inc" in code and lint_parade_dsl(report.text) == []
    assert result == original


@pytest.mark.parametrize("technique", ["隐形减针", "invisible decrease", "Invisible Decreases", "invdec"])
def test_prose_technique_is_not_silently_exported_or_drawn_as_ordinary_decrease(technique):
    part = _part(f"{technique}；2X,A")
    assert validate_pattern({"parts": [part]})["ok"]
    report = export_parade_report({"params": {"parts": [part]}})
    assert not report.complete and report.exported_rounds == 1
    assert _round_operation_sequence(part["rounds"], 1) == []
    assert "隐形减针工艺待核对" in render_symbol_strip(part)
    with pytest.raises(ValueError, match="隐形减针"):
        round_connections(part, 1)
    row = next(line for line in export_markdown({"parts": [part]}).splitlines() if line.startswith("| 19 |"))
    assert "隐形减针" in row.split("|")[5]


def test_markdown_preserves_explicit_invisible_formula_and_notes():
    part = _part()
    row = next(line for line in export_markdown({"parts": [part]}).splitlines() if line.startswith("| 19 |"))
    assert row.split("|")[5].strip() == "2X,inv-sc2tog"
    assert row.split("|")[7].strip() == part["rounds"][1]["notes"]
    assert _round_operation_sequence(part["rounds"], 1) == []


def _edited_result():
    result = _mock_result("technique-roundtrip")
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    index = next(i for i, rd in enumerate(rounds) if rd.get("decrease"))
    rounds[index]["notes"] = rounds[index]["notes"].replace("A", "inv-sc2tog")
    return result, rounds, index


def test_edit_and_backup_preserve_invisible_technique_without_changing_counts():
    result, rounds, index = _edited_result()
    original = deepcopy(result)
    updated = edit_rounds(result, 0, rounds)
    restored = import_backup(PatternResult.from_result(updated).to_backup(), "restored-technique")
    row = restored["params"]["parts"][0]["rounds"][index]
    assert row["notes"] == rounds[index]["notes"]
    expression = round_expression(row["notes"])
    assert expression is not None and expression.has_invisible_decrease
    assert "inv-sc2tog" in format_stitch_expression(expression)
    assert result == original and validate_pattern(restored["params"])["ok"]


def test_pdf_retains_invisible_technique_in_original_notes(monkeypatch):
    pytest.importorskip("reportlab")
    from reportlab import platypus

    from app.utils.pdf_export import export_pdf

    texts = []
    original = platypus.Paragraph

    def capture(text, *args, **kwargs):
        texts.append(html.unescape(text))
        return original(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    result, rounds, index = _edited_result()
    updated = edit_rounds(result, 0, rounds)
    assert export_pdf(updated["params"], result=updated).startswith(b"%PDF-")
    assert rounds[index]["notes"] in texts


def test_symbol_and_ring_charts_use_actual_nonconsecutive_row_labels():
    part = _part("2X,A")
    for svg in (render_ring_svg(part), render_symbol_strip(part)):
        texts = list(ET.fromstring(svg).itertext())
        assert any(text.startswith("R7") for text in texts)
        assert any(text.startswith("R19") for text in texts)
        assert any(text.startswith("R23") for text in texts)
        assert not any(text == "R1" or text.startswith("R1 成圈") for text in texts)


def test_truncated_strip_titles_and_legacy_missing_labels_stay_consistent():
    part = {"name": "自制长圈序", "rounds": [
        {"row": row, "stitches": 4, "notes": "4X"} for row in (7, 10, 13, 16, 19, 23)
    ]}
    texts = " ".join(ET.fromstring(render_symbol_strip(part, max_rounds=2)).itertext())
    assert "自第 19 圈起" in texts and "R19 成圈" in texts and "R23 成圈" in texts
    for rd in part["rounds"]:
        rd.pop("row")
    texts = " ".join(ET.fromstring(render_symbol_strip(part, max_rounds=2)).itertext())
    assert "自第 5 圈起" in texts and "R5 成圈" in texts and "R6 成圈" in texts


@pytest.mark.parametrize("max_rounds", [0, -1])
def test_empty_strip_window_does_not_attempt_to_read_a_first_label(max_rounds):
    assert render_symbol_strip(_part(), max_rounds=max_rounds) == ""


@pytest.mark.parametrize("loop", ["FLO", "BLO"])
def test_invisible_decrease_cannot_be_rewritten_by_a_loop_modifier(loop):
    expression = parse_stitch_expression("2X,inv-sc2tog")
    with pytest.raises(UnsupportedLoopError, match="隐形减针"):
        expression.with_loop(loop)


@pytest.mark.parametrize("note", ["FLO(2X,A)；隐形减针", "invisible decrease；BLO(2X,A)"])
def test_invisible_prose_and_scoped_loop_combination_remain_manual_review(note):
    part = _part(note)
    assert validate_pattern({"parts": [part]})["ok"]
    with pytest.raises(UnsupportedLoopError, match="隐形减针"):
        round_expression(note)
    assert not export_parade_report({"params": {"parts": [part]}}).complete


@pytest.mark.parametrize("note", ["2X,inv-sc2tog", "隐形减针；2X,A"])
def test_skirt_preparation_does_not_rewrite_invisible_decreases(note):
    from app.models.stitch_attachments import prepare_attached_skirt

    body = _part(note)
    body["name"] = "身体"
    skirt = {"name": "裙子", "rounds": [{"row": 1, "stitches": 4}, {"row": 2, "stitches": 4}]}
    parts = [body, skirt]
    original = deepcopy(parts)
    with pytest.raises(ValueError, match="隐形减针"):
        prepare_attached_skirt(parts, target_row=7)
    assert parts == original


def test_waist_move_rejects_invisible_new_reservation_and_preserves_current_pattern():
    from app.models.skirt_edit import move_skirt_join, skirt_connection, waist_rows
    from tests.test_skirt_editor import _shaped

    result = _shaped()
    connection = skirt_connection(result["params"])
    choices = {row["row"] for row in waist_rows(result["params"])}
    body = next(part for part in result["params"]["parts"] if part["name"] == connection["target_part"])
    rounds = body["rounds"]
    index = next(i for i in range(1, len(rounds))
                 if rounds[i - 1]["row"] in choices
                 and rounds[i - 1]["row"] != connection["target_row"]
                 and rounds[i].get("decrease") and not rounds[i].get("increase"))
    decrease = rounds[index]["decrease"]
    plain = rounds[index - 1]["stitches"] - 2 * decrease
    rounds[index]["notes"] = (f"{plain}X," if plain else "") + f"inv-sc2tog×{decrease}"
    assert validate_pattern(result["params"])["ok"]
    original = deepcopy(result)
    with pytest.raises(ValueError, match="特殊工艺"):
        move_skirt_join(result, rounds[index - 1]["row"])
    assert result == original
