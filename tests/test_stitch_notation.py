"""Synthetic notation examples; no third-party pattern is reproduced here."""
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import _change_note
from app.models.instruction_checks import instruction_issues
from app.models.ring_chart import render_symbol_strip
from app.models.stitch_notation import (
    NotationError,
    StitchCounts,
    format_stitch_expression,
    non_sc_symbols,
    parse_stitch_expression,
    parse_stitch_notation,
)
from app.models.validator import validate_pattern
from app.schemas import MAX_ROUND_STITCHES, PatternResult
from app.services.result_logic import import_backup
from app.ui.pattern_editor import edit_rounds
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report
from app.utils.pdf_export import export_pdf
from tests.test_app_smoke import _mock_result


@pytest.mark.parametrize("expression,expected", [
    ("(2X,V)×5", (15, 20, 5, 0)),
    ("[sc, sc-inc, sc] x 5", (15, 20, 5, 0)),
    ("5（X，V，X）", (15, 20, 5, 0)),
    ("X,(V,2X)×4,V,X", (15, 20, 5, 0)),
    ("*1 sc,1 sc-inc,1 sc* crochet 5 times", (15, 20, 5, 0)),
    ("*2 sc,inv-sc2tog,1 sc* repeat twice", (10, 8, 0, 2)),
    ("(sc, sc2tog, sc)*5", (20, 15, 0, 5)),
    ("(X,A)×5", (15, 10, 0, 5)),
    ("(DEC,sc)×5", (15, 10, 0, 5)),
    ("2X+V+A", (5, 5, 1, 1)),
    ("(2X,W,M)×3", (18, 18, 6, 6)),
    ("2((X,V)×3,A)", (16, 20, 6, 2)),
    ("6 SC.", (6, 6, 0, 0)),
    ("12F", (12, 12, 0, 0)),
    ("(X,T)×6", (12, 12, 0, 0)),
    ("4E", (4, 4, 0, 0)),
    ("5B", (5, 5, 0, 0)),
    ("8SL", (8, 8, 0, 0)),
    ("2F-FLO", (2, 2, 0, 0)),
    ("T-BLO", (1, 1, 0, 0)),
    ("12FV", (12, 24, 12, 0)),
    ("FA", (2, 1, 0, 1)),
    ("(FV,F)×2", (4, 6, 2, 0)),
    ("4*FV", (4, 8, 4, 0)),
    ("K1", (1, 0, 0, 0)),
    ("K2", (2, 0, 0, 0)),
    ("2K", (2, 0, 0, 0)),
    ("K1,3X,K1", (5, 3, 0, 0)),
    ("3NX", (3, 3, 0, 0)),
    ("S-SC", (1, 1, 0, 0)),
    ("4x", (4, 4, 0, 0)),
    ("BLO(2FV)", (2, 4, 2, 0)),
    ("X×000006", (6, 6, 0, 0)),
    (f"{MAX_ROUND_STITCHES}X", (MAX_ROUND_STITCHES, MAX_ROUND_STITCHES, 0, 0)),
])
def test_complete_expression_counts(expression, expected):
    assert parse_stitch_notation(expression) == StitchCounts(*expected)


@pytest.mark.parametrize("expression", [
    "", "下一圈 (2X,V)×5", "如果需要，(2X,V)×5", "示例：(2X,V)×5",
    "2X,4 dc-FLO,2X", "(2X,V)×5，最后与另一条腿并钩", "6X,2ch,6X",
    "6CH", "6X,2CH,6X", "空8针", "空3针目", "枣形针", "钩一颗枣形针",
    "同针(X+V)", "SFO", "KCH", "跳过1针", "(反向&BLO)2X", "全部BLO:2X",
    "(2X,V)×5 in back loops", "1 sc in each st around", "6X,sc4tog",
    "(2X,V)×5（局部）", "sc in red,sc in blue", "6X,-1X", "6X,1.5V",
    "(" * 100 + "free prose", "9" * 5000 + " cm 留线",
])
def test_unsupported_or_partial_instructions_are_not_guessed(expression):
    assert parse_stitch_notation(expression) is None


@pytest.mark.parametrize("expression", [
    "(X,V", "(X,V))×5", "X,,V", "(X,V)×", "X V", "X+", "()×5",
    "0X", "V×0", "X×1×", "6", "M1.", "12K1", "K0",
    "9" * 5000 + "X", "(V×100000)×100000", "(" * 100 + "X" + ")" * 100,
    ",".join(["X"] * 2000), "50001W",
])
def test_malformed_or_excessive_supported_notation_is_bounded(expression):
    with pytest.raises(NotationError, match="针法说明"):
        parse_stitch_notation(expression)


@given(st.lists(st.sampled_from("XVAWM"), min_size=1, max_size=30),
       st.integers(1, 20))
def test_group_counts_match_independently_expanded_operations(operations, repeats):
    # Independent small expansion oracle exercises grouping and mixed shaping.
    consumed = produced = inc = dec = 0
    for op in operations * repeats:
        before, after = {"X": (1, 1), "V": (1, 2), "A": (2, 1), "W": (1, 3), "M": (3, 1)}[op]
        consumed += before
        produced += after
        inc += max(0, after - before)
        dec += max(0, before - after)
    assert parse_stitch_notation(f"({','.join(operations)})×{repeats}") == StitchCounts(
        consumed, produced, inc, dec,
    )


@pytest.mark.parametrize("before,after", [(6, 12), (12, 6), (18, 24), (24, 18),
                                         (18, 30), (30, 18), (24, 24)])
def test_generator_notes_share_the_counting_contract(before, after):
    assert instruction_issues(
        _change_note(before, after), after, max(0, after - before), max(0, before - after),
        previous_stitches=before,
    ) == []


def _pattern(before, after, inc, dec, notation):
    return {"parts": [{"name": "测试件", "rounds": [
        {"row": 1, "stitches": before},
        {"row": 2, "stitches": after, "increase": inc, "decrease": dec, "notes": notation},
    ]}]}


@pytest.mark.parametrize("params", [
    _pattern(18, 24, 6, 0, "(3X,V)×6"),  # wrong source and output, same increases
    _pattern(18, 24, 6, 0, "(2sc,sc)×8"),  # output agrees, source and increases do not
    _pattern(18, 18, 0, 0, "(X,V,A)×4,2X"),  # same output, mixed shaping hidden
    _pattern(18, 24, 6, 0, "(3X,V)×6，隔3针加1针；断线留15cm"),
    _pattern(6, 12, 6, 0, "加针×5（V×5，每针都加）"),
])
def test_numeric_algebra_alone_cannot_detect_instruction_errors(params):
    assert validate_pattern(params, check_notes=False)["ok"]
    validation = validate_pattern(params)
    assert not validation["ok"]
    assert all("测试件 第 2 圈：针法说明" in issue for issue in validation["issues"])


def test_height_slip_and_bobble_keep_their_symbols():
    leaves = [parse_stitch_expression(text) for text in ("X", "SC", "T", "F", "E", "B", "SL")]
    assert [next(item.iter_stitches()) for item in leaves] == ["X", "X", "T", "F", "E", "B", "SL"]
    assert all(item.counts == StitchCounts(1, 1) for item in leaves)
    grouped = parse_stitch_expression("(X,T)×6")
    assert grouped is not None
    assert non_sc_symbols(grouped) == ("T",)
    invisible = parse_stitch_expression("2X,inv-sc2tog")
    assert invisible is not None and non_sc_symbols(invisible) == ()
    flo = parse_stitch_expression("2F-FLO")
    assert flo is not None and non_sc_symbols(flo) == ("F",)
    assert format_stitch_expression(grouped) == "(X,T)×6"
    restored = parse_stitch_expression(format_stitch_expression(parse_stitch_expression("12F")))
    assert restored is not None and list(restored.iter_stitches()) == ["F"] * 12


def test_taller_shaping_and_skips_keep_their_symbols():
    fv = parse_stitch_expression("12FV")
    fa = parse_stitch_expression("FA")
    skip = parse_stitch_expression("K2")
    inner = parse_stitch_expression("3NX")
    standing = parse_stitch_expression("S-SC,2X")
    assert fv is not None and list(fv.iter_stitches()) == ["FV"] * 12
    assert fa is not None and next(fa.iter_stitches()) == "FA"
    assert skip is not None and skip.counts == StitchCounts(2, 0, 0, 0)
    assert list(skip.iter_stitches()) == ["K", "K"]
    assert inner is not None and list(inner.iter_stitches()) == ["NX"] * 3
    assert standing is not None and non_sc_symbols(standing) == ("S-SC",)
    scoped = parse_stitch_expression("BLO(S-SC)")
    assert scoped is not None and next(scoped.iter_stitches()) == "S-SC-BLO"
    assert non_sc_symbols(scoped) == ("S-SC",)


def test_taller_stitch_round_is_counted_but_not_stored_as_short_crochet():
    assert parse_stitch_notation("12F") == StitchCounts(12, 12)
    params = {"parts": [{"name": "衣片", "type": "cylinder", "magic_ring": True, "rounds": [
        {"row": 1, "stitches": 12, "notes": "12X"},
        {"row": 2, "stitches": 12, "notes": "12F"},
    ]}]}
    validation = validate_pattern(params)
    assert not validation["ok"]
    assert any("不能写成短针整圈" in issue for issue in validation["issues"])
    report = export_parade_report({"params": params})
    assert not report.complete
    assert "12sc" not in report.text
    assert any("短针整圈" in warning for warning in report.warnings)
    strip = render_symbol_strip(params["parts"][0])
    assert "短针以外的针不按短针符号绘制" in strip
    assert 'data-kind="F"' not in strip


def test_skip_is_not_stored_as_a_decrease():
    params = _pattern(4, 3, 0, 1, "K1,3X")
    issues = validate_pattern(params)["issues"]
    assert any("不能写成短针整圈" in issue for issue in issues)
    assert any("减 0 针" in issue and "减 1 针" in issue for issue in issues)
    report = export_parade_report({"params": params})
    assert not report.complete
    assert "sc2tog" not in report.text and "3sc" not in report.text
    assert any("短针整圈" in warning for warning in report.warnings)


def test_equal_net_change_still_checks_both_shaping_counts():
    params = _pattern(6, 6, 0, 0, "3X,V,A")
    issues = validate_pattern(params)["issues"]
    assert len(issues) == 1
    assert "加 1 针、减 1 针" in issues[0]
    params["parts"][0]["rounds"][1].update(increase=1, decrease=1)
    assert validate_pattern(params)["ok"]


def test_non_six_sectors_and_combined_stitches_remain_valid():
    for params in (_pattern(15, 20, 5, 0, "(X,V,X)×5"),
                   _pattern(6, 6, 2, 2, "2X,W,M"),
                   _pattern(3, 1, 0, 2, "M")):
        assert validate_pattern(params)["ok"]


def test_formula_mismatch_rejected_at_edit_import_and_printable_exports():
    result = _mock_result("notation")
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    # Keep the correct 6 -> 12 numeric transition, change only its instructions.
    rounds[1]["notes"] = "(X,V)×6"
    with pytest.raises(ValueError, match="第 2 圈：针法说明"):
        edit_rounds(result, 0, rounds)
    assert result["params"]["parts"][0]["rounds"][1]["notes"] != rounds[1]["notes"]
    result["params"]["parts"][0]["rounds"] = rounds
    with pytest.raises(ValueError, match="针法说明"):
        import_backup(PatternResult.from_result(result).to_backup(), "bad-notation")
    for exporter in (export_markdown, export_pdf):
        with pytest.raises(ValueError, match="针法说明"):
            exporter(result["params"], result=result)


def test_valid_split_group_survives_edit_backup_and_export():
    result = _mock_result("split-notation")
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[3]["notes"] = "X,(V,2X)×5,V,X；继续填充"
    updated = edit_rounds(result, 0, rounds)
    restored = import_backup(PatternResult.from_result(updated).to_backup(), "notation-roundtrip")
    assert rounds[3]["notes"] in export_markdown(restored["params"], result=restored)
    assert validate_pattern(restored["params"])["ok"]
    report = export_parade_report(restored)
    assert report.complete
    assert "\nsc,5[sc2inc,2sc],sc2inc,sc\n" in report.text


def test_editor_calculator_counts_and_recovers_without_mutating_pattern():
    result = _mock_result("calculator")
    at = AppTest.from_string('''
import streamlit as st
from app.ui.pattern_editor import render_pattern_editor
render_pattern_editor(st.session_state.result, "result")
''', default_timeout=20)
    at.session_state["result"] = deepcopy(result)
    at.run()
    calculator = "edit_calculator_notation0"
    at.text_input(key=calculator).set_value("(X,V,X)×5").run()
    assert any("消耗上一圈 15 针 → 本圈 20 针；加 5 针，减 0 针" in msg.value for msg in at.info)
    at.text_input(key=calculator).set_value("(X,V").run()
    assert any("右括号" in msg.value for msg in at.error)
    at.text_input(key=calculator).set_value("6X,4 sc-FLO").run()
    assert not at.error
    assert any("本圈 10 针；加 0 针，减 0 针" in msg.value for msg in at.info)
    at.text_input(key=calculator).set_value("6X,4 dc-FLO").run()
    assert any("尚未支持" in msg.value for msg in at.info)
    at.text_input(key=calculator).set_value("12F").run()
    assert any("本圈 12 针" in msg.value and "长针" in msg.value and "只点数" in msg.value
               for msg in at.info)
    at.text_input(key=calculator).set_value("8SL").run()
    assert any("引拔针" in msg.value and "只点数" in msg.value for msg in at.info)
    at.text_input(key=calculator).set_value("12FV").run()
    assert any("本圈 24 针" in msg.value and "长针加针" in msg.value and "只点数" in msg.value
               for msg in at.info)
    at.text_input(key=calculator).set_value("K1,3X").run()
    assert any("减 0 针" in msg.value and "跳针" in msg.value and "不是并针" in msg.value
               for msg in at.info)
    at.text_input(key=calculator).set_value("SFO").run()
    assert any("尚未支持" in msg.value for msg in at.info)
    at.text_input(key=calculator).set_value("枣形针").run()
    assert any("尚未支持" in msg.value for msg in at.info)
    at.text_input(key=calculator).set_value("3X,V,A").run()
    assert any("本圈 6 针；加 1 针，减 1 针" in msg.value for msg in at.info)
    assert not at.exception
    assert at.session_state["result"] == result
