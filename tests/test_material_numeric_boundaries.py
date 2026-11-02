"""Reject unusable physical inputs consistently before any derived output."""
import json
import math
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.materials import YarnSpec
from app.models.validator import require_valid_pattern
from app.ui.pattern_editor import edit_yarn
from app.ui.result_logic import import_backup
from app.utils.exporters import export_markdown
from app.utils.pdf_export import export_pdf
from tests.test_project_backup import RENDER
from tests.test_swatch_provenance import SPEC, source


@pytest.mark.parametrize("field,value", [
    ("ball_weight_g", 1e-320), ("ball_length_m", 1e-320),
    ("swatch_weight_g", 1e-320), ("ball_weight_g", 1e-7),
    ("ball_length_m", 1e-7), ("swatch_weight_g", 1e-7), ("ball_weight_g", True),
    ("ball_length_m", True), ("swatch_weight_g", True), ("waste_percent", True),
])
def test_invalid_measurements_rejected_on_edit_import_and_export(field, value):
    spec = {**SPEC, field: value}
    current = source()
    original = deepcopy(current)
    with pytest.raises(ValueError):
        YarnSpec.model_validate(spec)
    with pytest.raises(ValueError):
        edit_yarn(current, spec)
    assert current == original

    invalid = deepcopy(current)
    invalid["params"]["yarn_spec"] = spec
    for operation in (
        lambda: require_valid_pattern(invalid["params"]),
        lambda: import_backup(invalid, "invalid"),
        lambda: export_markdown(invalid["params"], result=invalid),
        lambda: export_pdf(invalid["params"], result=invalid),
    ):
        with pytest.raises(ValueError):
            operation()


def test_small_positive_legacy_values_and_numeric_strings_remain_usable():
    current = source()
    updated = edit_yarn(current, {**SPEC, "ball_weight_g": "0.1", "ball_length_m": "0.2",
                                  "swatch_weight_g": "0.01"})
    assert updated["params"]["yarn_spec"]["ball_weight_g"] == 0.1
    restored = import_backup(updated, "restored")
    assert restored["params"]["material_summary"] == updated["params"]["material_summary"]


def test_minimum_measurements_produce_finite_derived_values():
    spec = {**SPEC, "ball_weight_g": 1e-6, "ball_length_m": 10000,
            "swatch_weight_g": 1e-6, "swatch_stitches": 1000, "swatch_rows": 1000}
    updated = edit_yarn(source(), spec)
    summary = updated["params"]["material_summary"]
    assert math.isfinite(summary["grams"]) and math.isfinite(summary["meters"])
    json.dumps(updated, ensure_ascii=False, allow_nan=False)


def test_invalid_json_edit_preserves_live_pattern_progress_and_notes_then_allows_retry():
    current = source()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = current
    at.run()
    at.checkbox(key="chk_swatch_头部_0").check().run()
    at.text_area(key="project_notes_swatch").input("先核对线标").run()
    params = deepcopy(current["params"])
    params["yarn_spec"] = {**SPEC, "ball_weight_g": 1e-320}
    at.text_area(key="json_edit_swatch").input(json.dumps(params, ensure_ascii=False)).run()
    at.button(key="regen_swatch").click().run()
    assert not at.exception
    assert any("失败" in error.value for error in at.error)
    assert at.session_state["result"] == current
    assert at.checkbox(key="chk_swatch_头部_0").value
    assert at.text_area(key="project_notes_swatch").value == "先核对线标"

    params["yarn_spec"]["ball_weight_g"] = 50
    at.text_area(key="json_edit_swatch").input(json.dumps(params, ensure_ascii=False)).run()
    at.button(key="regen_swatch").click().run()
    assert not at.exception
    rid = at.session_state["result"]["result_id"]
    assert at.session_state["result"]["params"]["yarn_spec"]["ball_weight_g"] == 50
    assert at.checkbox(key=f"chk_{rid}_头部_0").value
    assert at.text_area(key=f"project_notes_{rid}").value == "先核对线标"
