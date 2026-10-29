"""Recognized whole-round prose must agree with its explicit stitch formula."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.instruction_checks import instruction_issues
from app.models.validator import validate_pattern
from app.schemas import PatternResult
from app.ui.pattern_editor import edit_rounds
from app.ui.result_logic import import_backup
from app.utils.exporters import export_markdown
from app.utils.parade_export import export_parade_report
from tests.test_app_smoke import _mock_result


@pytest.mark.parametrize("formula,stitches,increase,decrease,previous", [
    ("6V，均匀减6针", 12, 6, 0, 6),
    ("6A，均匀加6针", 6, 0, 6, 12),
    ("6X，均匀加6针", 6, 0, 0, 6),
    ("6X，均匀减6针", 6, 0, 0, 6),
    ("6X，隔2针加1针", 6, 0, 0, 6),
    ("6X，隔2针减1针", 6, 0, 0, 6),
    ("6V，隔2针减1针", 12, 6, 0, 6),
    ("6A，隔2针加1针", 6, 0, 6, 12),
    ("加针×5（V×6，每针都加）", 12, 6, 0, 6),
    ("减针×5（A×6，每2针并1针）", 6, 0, 6, 12),
    ("减针×6（V×6，每针都加）", 12, 6, 0, 6),
    ("加针×6（A×6，每2针并1针）", 6, 0, 6, 12),
    ("加针×6（V×6，每2针并1针）", 12, 6, 0, 6),
    ("减针×6（A×6，每针都加）", 6, 0, 6, 12),
])
def test_complete_claims_cannot_hide_wrong_direction_or_repetitions(
    formula, stitches, increase, decrease, previous,
):
    # Each formula agrees with all numeric fields, so these failures depend on
    # the contradictory prose rather than the existing arithmetic checks.
    pattern = {"parts": [{"name": "练习", "rounds": [
        {"row": 1, "stitches": previous},
        {"row": 2, "stitches": stitches, "increase": increase, "decrease": decrease, "notes": formula},
    ]}]}
    assert validate_pattern(pattern, check_notes=False)["ok"]
    checked = validate_pattern(pattern)
    assert not checked["ok"]
    assert all("练习 第 2 圈：" in issue for issue in checked["issues"])


@pytest.mark.parametrize("digits", ["9" * 5000, "0" * 5000 + "7"])
@pytest.mark.parametrize("template", ["6V，均匀加{}针", "6V，隔{}针加1针", "加针×{}（V×6，每针都加）"])
def test_excessive_claim_numbers_return_bounded_diagnostics(template, digits):
    issues = instruction_issues(template.format(digits), 12, 6, 0, previous_stitches=6)
    assert issues
    assert all(len(issue) < 200 for issue in issues)


@pytest.mark.parametrize("formula,stitches,increase,decrease,previous", [
    ("6V，均匀加000006针", 12, 6, 0, 6),
    ("6A，均匀减000006针", 6, 0, 6, 12),
    ("(2X,V)×6，隔000002针加1针", 24, 6, 0, 18),
    ("6X，均匀加0针", 6, 0, 0, 6),
    ("6X；下一圈均匀加6针", 6, 0, 0, 6),
    ("6X；如果需要，隔2针减1针", 6, 0, 0, 6),
    ("加针×000006（V×6，每针都加）", 12, 6, 0, 6),
    ("减针×000006（A×6，每2针并1针）", 6, 0, 6, 12),
])
def test_consistent_claims_and_future_round_prose_remain_usable(
    formula, stitches, increase, decrease, previous,
):
    assert not instruction_issues(formula, stitches, increase, decrease, previous_stitches=previous)


def test_zero_padding_does_not_require_converting_an_untrusted_integer():
    zeros = "0" * 5000
    assert not instruction_issues(f"6V，均匀加{zeros}6针", 12, 6, 0, previous_stitches=6)
    assert not instruction_issues(f"6V，隔{zeros}0针加1针", 12, 6, 0, previous_stitches=6)
    assert not instruction_issues(f"加针×{zeros}6（V×6，每针都加）", 12, 6, 0, previous_stitches=6)


def test_contradictory_claim_rejected_at_edit_import_and_exports_without_mutation():
    result = _mock_result("claim-gates")
    original = deepcopy(result)
    rounds = deepcopy(result["params"]["parts"][0]["rounds"])
    rounds[1]["notes"] = "6V，均匀减6针"
    with pytest.raises(ValueError, match="文字"):
        edit_rounds(result, 0, rounds)
    assert result == original
    damaged = deepcopy(result)
    damaged["params"]["parts"][0]["rounds"] = rounds
    with pytest.raises(ValueError, match="文字"):
        import_backup(PatternResult.from_result(damaged).to_backup(), "bad-claim")
    with pytest.raises(ValueError, match="文字"):
        export_markdown(damaged["params"], result=damaged)
    report = export_parade_report(damaged)
    assert not report.complete
    assert any("文字" in warning for warning in report.warnings)


def test_pasted_backup_reports_wrong_claim_then_accepts_correction():
    import json

    from tests.test_app_smoke import _APP

    existing = _mock_result("keep-claim-progress")
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = existing
    at.session_state["chk_keep-claim-progress_头部_0"] = True
    at.session_state["project_notes_keep-claim-progress"] = "保留现有工程"
    at.run()
    damaged = PatternResult.from_result(existing).to_backup()
    damaged["params"]["parts"][0]["rounds"][1]["notes"] = "6V，均匀减6针"
    at.radio(key="open_backup_source").set_value("粘贴 JSON").run()
    at.text_area(key="open_backup_text").input(json.dumps(damaged, ensure_ascii=False)).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception and any("文字" in error.value for error in at.error)
    assert at.session_state["result"] == existing
    assert at.checkbox(key="chk_keep-claim-progress_头部_0").value
    assert at.text_area(key="project_notes_keep-claim-progress").value == "保留现有工程"
    damaged["params"]["parts"][0]["rounds"][1]["notes"] = "6V，均匀加6针"
    at.text_area(key="open_backup_text").input(json.dumps(damaged, ensure_ascii=False)).run()
    at.button(key="open_backup_apply").click().run()
    assert not at.exception and not at.error
    assert at.session_state["result"]["params"]["parts"][0]["rounds"][1]["notes"] == "6V，均匀加6针"
