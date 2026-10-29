"""Explicit placement must stay executable through generation and numeric edits."""
from copy import deepcopy

import pytest

from app.models.crochet_params import (
    CrochetParamsGenerator,
    _mark_staggered,
    _positioned_change_note,
    _sphere_rounds,
)
from app.models.gauge import PRESETS, ShapingStyle
from app.models.instruction_checks import round_expression
from app.models.ring_chart import _round_operation_sequence
from app.models.structure_designer import StructureDesigner
from app.models.validator import validate_pattern
from app.schemas import ImageAnalysis, PatternResult
from app.ui.pattern_editor import edit_rounds
from app.ui.result_logic import import_backup
from app.utils.parade_export import export_parade_report, lint_parade_dsl
from tests.test_app_smoke import _mock_result


def test_generated_increases_alternate_explicit_end_and_center_positions():
    rounds = _sphere_rounds(48)
    expected = ["V" * 6, "XV" * 6, "XVX" * 6, "XXXV" * 6,
                "XXVXX" * 6, "XXXXXV" * 6, "XXXVXXX" * 6]
    for index, operations in enumerate(expected, 1):
        expression = round_expression(rounds[index]["notes"])
        assert expression is not None
        assert "".join(expression.iter_stitches()) == operations
        assert "".join(_round_operation_sequence(rounds, index)) == operations
        assert expression.counts.consumed == rounds[index - 1]["stitches"]
        assert expression.counts.produced == rounds[index]["stitches"]
    assert [rd["stitches"] for rd in rounds[:8]] == list(range(6, 49, 6))
    assert all("错开半组" not in rd["notes"] for rd in rounds)


@pytest.mark.parametrize("before,after,enabled,expected", [
    (18, 24, True, "(X,V,X)×6"),
    (30, 36, True, "(2X,V,2X)×6"),
    (18, 24, False, "(2X,V)×6，隔2针加1针"),
    (24, 30, True, "(3X,V)×6，隔3针加1针"),
    (18, 30, True, "(X,V,V)×6，均匀加12针"),
    (24, 18, True, "(2X,A)×6，隔2针减1针"),
])
def test_centered_variant_has_a_narrow_stable_scope(before, after, enabled, expected):
    assert _positioned_change_note(before, after, staggered=enabled) == expected


def test_placement_pass_is_idempotent_and_preserves_finishing_and_custom_notes():
    rounds = _sphere_rounds(36)
    rounds[3]["notes"] = "(2X,V)×6，隔2针加1针；加针位置与上一圈错开半组；填充后留线15cm"
    rounds[5]["notes"] = "X,(V,4X)×5,V,3X；自己的记号位置"
    original_custom = rounds[5]["notes"]
    once = _mark_staggered(deepcopy(rounds))
    assert once[3]["notes"] == "(X,V,X)×6；填充后留线15cm"
    assert once[5]["notes"] == original_custom
    assert _mark_staggered(deepcopy(once)) == once
    assert [r["stitches"] for r in once] == [r["stitches"] for r in rounds]


def test_legacy_hint_backup_survives_and_numeric_edit_updates_only_generated_placement():
    result = _mock_result("legacy-stagger")
    old_note = "(2X,V)×6，隔2针加1针；加针位置与上一圈错开半组；留线20cm用于缝合"
    result["params"]["parts"][0]["rounds"][3]["notes"] = old_note
    restored = import_backup(PatternResult.from_result(result).to_backup(), "legacy-stagger")
    assert restored["params"]["parts"][0]["rounds"][3]["notes"] == old_note
    rounds = deepcopy(restored["params"]["parts"][0]["rounds"])
    rounds[0]["stitches"] = 12
    rounds[1]["stitches"] = 18
    rounds[2]["increase"] = 0
    updated = edit_rounds(restored, 0, rounds)
    assert updated["params"]["parts"][0]["rounds"][3]["notes"] == (
        "(2X,V)×6，隔2针加1针；留线20cm用于缝合"
    )
    # Restoring the preceding increase now writes an executable center position.
    rounds = deepcopy(updated["params"]["parts"][0]["rounds"])
    rounds[0]["stitches"] = 6
    rounds[1]["stitches"] = 12
    rounds[2]["increase"] = 6
    final = edit_rounds(updated, 0, rounds)
    assert final["params"]["parts"][0]["rounds"][3]["notes"] == "(X,V,X)×6；留线20cm用于缝合"
    assert "\n6[sc,sc2inc,sc]\n" in export_parade_report(final).text


@pytest.mark.parametrize("gauge", list(PRESETS.values()), ids=list(PRESETS))
@pytest.mark.parametrize("mode", ["ladder", "ideal", "egg"])
@pytest.mark.parametrize("one_piece", [False, True])
def test_all_gauges_and_head_modes_export_complete_explicit_placement(gauge, mode, one_piece):
    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=9, height_cm=18,
                             main_features=[], pose="站立", difficulty="easy", parts=["头部", "身体"])
    params = CrochetParamsGenerator.generate_params(
        analysis, StructureDesigner.design_3d_structure(analysis), gauge=gauge,
        style=ShapingStyle(sphere_mode=mode, one_piece=one_piece),
    )
    assert validate_pattern(params)["ok"]
    report = export_parade_report({"params": params})
    assert report.complete
    assert report.exported_rounds == report.requested_rounds
    assert lint_parade_dsl(report.text) == []
    assert all("错开半组" not in (rd.get("notes") or "") for part in params["parts"] for rd in part["rounds"])
