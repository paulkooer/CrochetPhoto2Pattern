"""Synthetic loop-placement cases, not copies of any published pattern."""
import importlib.util
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.models.instruction_checks import instruction_issues, round_expression
from app.models.ring_chart import _round_operation_sequence, render_symbol_strip
from app.models.stitch_notation import (
    NotationError,
    StitchCounts,
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
from app.utils.pdf_export import export_pdf
from tests.test_app_smoke import _mock_result


def _result(note, before=15, after=20, inc=5, dec=0):
    return {"params": {"parts": [{"name": "挑针练习", "magic_ring": True, "quantity": 1,
                                  "rounds": [{"row": 1, "stitches": before},
                                             {"row": 2, "stitches": after, "increase": inc,
                                              "decrease": dec, "notes": note}]}]}}


@pytest.mark.parametrize("note,expected,operations", [
    ("BLO((X,V,X)×5)", (15, 20, 5, 0), ["X-BLO", "V-BLO", "X-BLO"] * 5),
    ("flo: (2sc,inc)×5", (15, 20, 5, 0), ["X-FLO", "X-FLO", "V-FLO"] * 5),
    ("2X,4 sc-FLO,2X", (8, 8, 0, 0), ["X"] * 2 + ["X-FLO"] * 4 + ["X"] * 2),
    ("(sc-BLO,sc2tog-BLO)×5", (15, 10, 0, 5), ["X-BLO", "A-BLO"] * 5),
    ("BLO(2X,W,M)×3", (18, 18, 6, 6), ["X-BLO", "X-BLO", "W-BLO", "M-BLO"] * 3),
    ("2(FLO(X,V),BLO(X,A))", (10, 10, 2, 2), ["X-FLO", "V-FLO", "X-BLO", "A-BLO"] * 2),
    ("5sc-inc-FLO", (5, 10, 5, 0), ["V-FLO"] * 5),
    ("BLO(BLO(3X))", (3, 3, 0, 0), ["X-BLO"] * 3),
    ("BLO（2X，A）×5", (20, 15, 0, 5), ["X-BLO", "X-BLO", "A-BLO"] * 5),
])
def test_scoped_and_local_loops_keep_counts_order_and_format(note, expected, operations):
    expr = parse_stitch_expression(note)
    assert expr is not None and expr.has_loop_technique
    assert expr.counts == StitchCounts(*expected)
    assert list(expr.iter_stitches()) == operations
    restored = parse_stitch_expression(format_stitch_expression(expr))
    assert restored is not None and restored.counts == expr.counts
    assert list(restored.iter_stitches()) == operations


@pytest.mark.parametrize("note", [
    "BLO(0X)", "FLO(100001X)", "BLO(" * 15 + "X" + ")" * 15,
    "FLO(X", "BLO(X,,V)", "BLO(X-FLO)", "FLO(BLO(X))", "BLO X",
    "BLO((V)×100000)", "BLO(" + ",".join(["X"] * 1100) + ")",
])
def test_bad_or_conflicting_scopes_are_bounded(note):
    with pytest.raises(NotationError):
        parse_stitch_expression(note)


@pytest.mark.parametrize("note", ["BLO(12X),2ch", "FLO(4dc)", "BLO(6X) in next round",
                                      "4sc-FLO,join legs", "6X-back-loop"])
def test_unsupported_suffix_is_never_partly_counted(note):
    assert parse_stitch_notation(note) is None


@pytest.mark.parametrize("directive", ["BLO", "blo.", "本圈只挑后半针", "只挑后半针",
                                           "back loop only", "back loops only"])
def test_separate_whole_round_directive_applies_before_or_after_formula(directive):
    for note in (f"{directive}；(X,V,X)×5；留线缝合", f"(X,V,X)×5;{directive}"):
        result = _result(note)
        assert validate_pattern(result["params"])["ok"]
        report = export_parade_report(result)
        assert report.complete and report.inferred_rounds == 0
        assert "\n5[scbl,scbl2inc,scbl]\n" in report.text
        assert lint_parade_dsl(report.text) == []


@pytest.mark.parametrize("note", ["FLO；BLO；15X", "FLO；15X-BLO", "BLO(FLO(15X))"])
def test_conflicting_scopes_are_rejected_by_validation_and_exports(note):
    result = _result(note, 15, 15, 0)
    assert not validate_pattern(result["params"])["ok"]
    report = export_parade_report(result)
    assert not report.complete and report.exported_rounds == 1
    assert "针位待核对" in render_symbol_strip(result["params"]["parts"][0])


@pytest.mark.parametrize("note", ["下一圈可用 BLO；(X,V,X)×5", "BLO；按自选位置加针",
                                      "(X,V,X)×5 in back loops", "先挑前半针再连接；(X,V,X)×5",
                                      "前半针（BLO）；(X,V,X)×5", "本圈BLO钩织；(X,V,X)×5"])
def test_unresolved_loop_prose_stops_export_without_invalidating_manual_notes(note):
    result = _result(note)
    result["params"]["parts"][0]["rounds"].append({"row": 3, "stitches": 20, "notes": "20X"})
    assert validate_pattern(result["params"])["ok"]
    report = export_parade_report(result)
    assert not report.complete and report.exported_rounds == 1
    assert report.inferred_rounds == 0 and "挑针说明" in report.text
    assert "\n20sc\n" not in report.text
    assert "请核对说明中的操作式" in export_markdown(result["params"])
    assert _round_operation_sequence(result["params"]["parts"][0]["rounds"], 1) == []


def test_local_loop_positions_match_markdown_chart_and_dsl_without_scope_leaking():
    result = _result("2X,4sc-FLO,2sc-BLO", 8, 8, 0)
    part = result["params"]["parts"][0]
    part["quantity"] = 2
    part["rounds"].append({"row": 3, "stitches": 8, "notes": "8X"})
    report = export_parade_report(result)
    assert report.complete and report.exported_rounds == 6
    assert report.text.count("\n2sc,4scfl,2scbl\n8sc\n") == 2
    assert lint_parade_dsl(report.text) == []
    expected = ["X"] * 2 + ["X-FLO"] * 4 + ["X-BLO"] * 2
    assert _round_operation_sequence(part["rounds"], 1) == expected
    svg = ET.fromstring(render_symbol_strip(part))
    assert [node.attrib["data-kind"] for node in svg.iter() if "data-kind" in node.attrib] == (
        ["X"] * 8 + expected + ["X"] * 8
    )
    assert "F=前半针，B=后半针" in "".join(svg.itertext())
    assert "2X,4X-FLO,2X-BLO" in export_markdown(result["params"])


@pytest.mark.parametrize("note,expected", [
    ("FLO(2X,W,M)", "2scfl,scfl3inc,scfl3tog"),
    ("BLO(2X,W,M)", "2scbl,scbl3inc,scbl3tog"),
])
def test_loop_shaping_uses_qualified_stitch_name_before_inc_or_tog(note, expected):
    report = export_parade_report(_result(note, 6, 6, 2, 2))
    assert report.complete and f"\n{expected}\n" in report.text
    assert lint_parade_dsl(report.text) == []


@pytest.mark.parametrize("line", ["5[scfl,scbl2tog]", "2[3scbl,scfl3inc]", "100000scfl"])
def test_linter_accepts_verified_loop_tokens(line):
    assert lint_parade_dsl(line) == []


@pytest.mark.parametrize("line", ["scflbl", "sc2togbl", "0scbl", "scbl0inc", "scfl100001tog",
                                     "100001scbl", "2[scfl,]", "__import__(scbl)"])
def test_linter_rejects_invalid_or_unverified_loop_tokens(line):
    assert lint_parade_dsl(line)


def test_first_round_loop_foundation_is_not_replaced_with_magic_ring():
    result = _result("(X,V,X)×5")
    bad = deepcopy(result["params"]["parts"][0])
    bad["rounds"][0]["notes"] = "BLO(15X)"
    result["params"]["parts"].insert(0, bad)
    report = export_parade_report(result)
    assert not report.complete and report.exported_parts == 1
    assert "首圈挑针缺少可译的基底" in report.text
    assert _round_operation_sequence(bad["rounds"], 0) == []


@pytest.mark.parametrize("note", ["BLO(inv-sc2tog×5)", "5BLO(inv-sc2tog)", "BLO；inv-sc2tog×5",
                                      "FLO；inv-sc2tog×5"])
def test_unverified_invisible_decrease_combination_is_not_replaced_with_loop_tog(note):
    report = export_parade_report(_result(note, 10, 5, 0, 5))
    assert not report.complete and report.exported_rounds == 1
    assert "隐形减针" in report.text


def test_large_loop_scope_stays_compact_and_draws_only_visible_prefix():
    result = _result("BLO(100000X)", 100000, 100000, 0)
    report = export_parade_report(result)
    assert report.complete and "\n100000scbl\n" in report.text
    assert len(report.text) < 1000
    part = result["params"]["parts"][0]
    assert _round_operation_sequence(part["rounds"], 1, 18) == ["X-BLO"] * 18
    svg = render_symbol_strip(part)
    assert svg.count('data-kind="X-BLO"') == 18 and "+99982" in svg


@pytest.mark.parametrize("ending", [
    "拉紧（无痕收口）藏线头", "拉紧藏线头",
    "拉紧藏线头（无痕收口，社区/PlanetJune fastening off 通行技法）",
    "拉紧（无痕收口）藏线头（勿再减针收成6针，底部会过尖）",
])
def test_generated_tail_closure_does_not_requalify_last_crocheted_round(ending):
    note = f"5X；断线留10cm，穿末圈每针前半针后{ending}"
    expr = round_expression(note)
    assert expr is not None and list(expr.iter_stitches()) == ["X"] * 5
    report = export_parade_report(_result(note, 5, 5, 0))
    assert report.complete and "\n5sc\n" in report.text


def test_loop_note_mismatch_is_checked_and_preserved_across_edit_backup_and_print():
    result = _mock_result("loop-backup")
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[2]["notes"] = "FLO((X,V)×6)；继续填充"
    updated = edit_rounds(result, 0, rounds)
    restored = import_backup(PatternResult.from_result(updated).to_backup(), "loops-restored")
    assert rounds[2]["notes"] in export_markdown(restored["params"], result=restored)
    if importlib.util.find_spec("reportlab") is None:
        with pytest.raises(ImportError, match="reportlab"):
            export_pdf(restored["params"], result=restored)
    else:
        assert export_pdf(restored["params"], result=restored).startswith(b"%PDF")
    report = export_parade_report(restored)
    assert report.complete and "\n6[scfl,scfl2inc]\n" in report.text
    rounds[2]["notes"] = "FLO((2X,V)×6)"
    with pytest.raises(ValueError, match="针法说明"):
        edit_rounds(result, 0, rounds)
    restored["params"]["parts"][0]["rounds"][2]["notes"] = rounds[2]["notes"]
    with pytest.raises(ValueError, match="针法说明"):
        import_backup(PatternResult.from_result(restored).to_backup(), "bad-loops")
    for exporter in (export_markdown, export_pdf):
        with pytest.raises(ValueError, match="针法说明"):
            exporter(restored["params"], result=restored)


@given(st.lists(st.sampled_from(["X", "V", "A", "W", "M"]), min_size=1, max_size=20),
       st.sampled_from(["FLO", "BLO"]), st.integers(1, 10))
def test_loop_scope_never_changes_independent_counts_or_order(operations, loop, repeat):
    io = {"X": (1, 1), "V": (1, 2), "A": (2, 1), "W": (1, 3), "M": (3, 1)}
    before = sum(io[op][0] for op in operations) * repeat
    after = sum(io[op][1] for op in operations) * repeat
    inc = sum(max(0, io[op][1] - io[op][0]) for op in operations) * repeat
    dec = sum(max(0, io[op][0] - io[op][1]) for op in operations) * repeat
    note = f"{loop}({','.join(operations)})×{repeat}"
    expr = parse_stitch_expression(note)
    assert expr is not None and expr.counts == StitchCounts(before, after, inc, dec)
    assert list(expr.iter_stitches()) == [f"{op}-{loop}" for op in operations] * repeat
    assert instruction_issues(note, after, inc, dec, previous_stitches=before) == []
    report = export_parade_report(_result(note, before, after, inc, dec))
    assert report.complete and lint_parade_dsl(report.text) == []
