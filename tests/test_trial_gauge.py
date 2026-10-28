"""Measured density can inform a reversible pattern edit without rebinding evidence."""
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.crochet_params import refresh_derived
from app.models.skirt_edit import move_skirt_join, waist_rows
from app.models.stitch_attachments import WAIST_POSITION_KEY
from app.models.validator import require_valid_pattern
from app.ui.result_logic import import_backup, regenerate_with_gauge
from app.utils.backup import decode_backup_json
from app.utils.trial_bundle import (
    create_trial_bundle,
    trial_comparison_rows,
    trial_gauge_candidate,
    update_trial_bundle,
)
from tests.test_app_smoke import _mock_result
from tests.test_project_backup import RENDER
from tests.test_stitch_attachments import _check
from tests.test_trial_editor import _app, _click, _completed, _draft, _start
from tests.test_waist_persistence import _source


def _measured(bundle=None, *, stitches=18.0, rows=24.0):
    bundle = bundle or _draft()
    return update_trial_bundle(bundle, swatch={**bundle.record.swatch.model_dump(), "measured": True,
                                              "stitches_per_10cm": stitches, "rows_per_10cm": rows},
                               observation=None)


def test_gauge_regeneration_retains_dimensions_and_recomputes_real_rounds():
    source = _mock_result("density")
    source["params"]["yarn_spec"] = {"ball_weight_g": 50, "ball_length_m": 120, "waste_percent": 8}
    refresh_derived(source["params"])
    snapshot = deepcopy(source)
    updated = regenerate_with_gauge(source, 18, 24)
    assert source == snapshot
    assert updated["structure"] == source["structure"]
    assert updated["analysis"] == source["analysis"]
    assert updated["style"] == source["style"] and updated["sizing"] == source["sizing"]
    assert updated["params"]["yarn_spec"] == source["params"]["yarn_spec"]
    assert updated["gauge"] == updated["params"]["gauge"] == {
        "stitches_per_10cm": 18.0, "rows_per_10cm": 24.0}
    # 9 cm diameter at 18 stitches/10 cm needs about 51 circumference
    # stitches, rounded to the generator's nearest six-stitch group (48).
    head = next(p for p in updated["params"]["parts"] if p["name"] == "头部")
    assert max(r["stitches"] for r in head["rounds"]) == 48
    assert updated["params"]["total_stitches"] > source["params"]["total_stitches"]
    assert updated["params"]["total_stitches"] == sum(
        r["stitches"] * p["quantity"] for p in updated["params"]["parts"] for r in p["rounds"])
    require_valid_pattern(updated["params"])


def test_identical_gauge_preserves_manual_rounds_and_does_not_alias_source():
    source = _mock_result("same")
    source["params"]["parts"][0]["rounds"][2]["notes"] += "；此处放记号扣"
    updated = regenerate_with_gauge(source, 13, 16)
    assert updated == source
    updated["params"]["parts"][0]["rounds"][2]["notes"] = "other"
    assert updated != source


@pytest.mark.parametrize("stitches,rows", [(True, 16), (13, False), (float("nan"), 16),
                                          (13, float("inf")), (5, 16), (41, 16), (13, 7), (13, 51)])
def test_invalid_gauge_refuses_regeneration_without_changing_source(stitches, rows):
    source = _mock_result("invalid")
    before = deepcopy(source)
    with pytest.raises(ValueError):
        regenerate_with_gauge(source, stitches, rows)
    assert source == before


@pytest.mark.parametrize("one_piece", [False, True])
def test_density_change_keeps_pinned_waist_and_matching_actual_reservations(one_piece):
    source = _source(one_piece)
    fixed = move_skirt_join(source, waist_rows(source["params"])[1]["row"])
    position = fixed["params"][WAIST_POSITION_KEY]
    updated = regenerate_with_gauge(fixed, 18, 24)
    actual = _check(updated)
    rows = waist_rows(updated["params"])
    assert updated["params"][WAIST_POSITION_KEY] == position
    assert actual["target_row"] == rows[round(position * (len(rows) - 1))]["row"]
    assert updated["structure"] == fixed["structure"]
    assert updated["vision_meta"] == fixed["vision_meta"]
    assert updated["color_bands"] == fixed["color_bands"]


def test_trial_candidate_uses_saved_swatch_without_changing_source_or_record():
    bundle = _measured()
    before = deepcopy(bundle)
    source = import_backup(decode_backup_json(bundle.source), "new-session")
    snapshot = deepcopy(source)
    candidate = trial_gauge_candidate(bundle, source)
    assert bundle == before and source == snapshot
    assert candidate["gauge"]["stitches_per_10cm"] == 18
    assert candidate["analysis"]["height_cm"] == source["analysis"]["height_cm"]


@pytest.mark.parametrize("damage", ["not_measured", "different_pattern", "tampered_source"])
def test_trial_density_requires_measured_swatch_and_exact_source(damage):
    bundle = _measured()
    source = import_backup(decode_backup_json(bundle.source), "source")
    if damage == "not_measured":
        bundle = _draft()
    elif damage == "different_pattern":
        source["params"]["parts"][0]["rounds"][0]["color"] = "红色"
    else:
        bundle.record.pattern.total_stitches += 1
    with pytest.raises(ValueError):
        trial_gauge_candidate(bundle, source)


@pytest.mark.parametrize("scope", ["full_project", "round_crochet_baseline"])
def test_comparisons_use_correct_units_and_only_compatible_time_scopes(scope):
    bundle = _completed(scope=scope)
    bundle.record.swatch.stitches_per_10cm = 19.5
    bundle.record.swatch.rows_per_10cm = 8.0
    rows = {row["项目"]: row for row in trial_comparison_rows(bundle)}
    assert rows["10 cm 针数"]["差异"] == "+50.0%"
    assert rows["10 cm 行数"]["差异"] == "-50.0%"
    assert rows["成品总高（cm）"]["差异"] == "+6.7%"
    assert rows["用线（g）"]["已保存实测"] == "70.5"
    if scope == "full_project":
        assert rows["操作时间（分钟）"]["差异"] == "—"
        assert "口径不同" in rows["操作时间（分钟）"]["说明"]
    else:
        expected = (110 / bundle.record.pattern.estimated_time_minutes - 1) * 100
        assert rows["操作时间（分钟）"]["差异"] == f"{expected:+.1f}%"


def test_unmeasured_defaults_are_not_shown_as_measurements():
    rows = trial_comparison_rows(_draft())
    assert len(rows) == 2
    assert all(row["已保存实测"] == "未确认测量" and row["差异"] == "—" for row in rows)


def test_legacy_missing_material_estimate_is_not_treated_as_zero():
    source = _mock_result("legacy")
    source["params"].pop("material_summary")
    bundle = _completed(create_trial_bundle(source, trial_id="legacy", maker_id="maker-a"))
    row = next(r for r in trial_comparison_rows(bundle) if r["项目"] == "用线（g）")
    assert row["原图解目标 / 估算"] == "未记录" and row["差异"] == "—"


def test_preview_apply_undo_and_redo_preserve_trial_and_restore_progress():
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = _mock_result("trial-source")
    at.run()
    at.checkbox(key="chk_trial-source_头部_0").check().run()
    at.text_area(key="project_notes_trial-source").input("记得保留原试钩").run()
    prefix = _start(at)
    at.checkbox(key=prefix + "measured").check()
    at.number_input(key=prefix + "stitches_per_10cm").set_value(18)
    at.number_input(key=prefix + "rows_per_10cm").set_value(24)
    _click(at, "保存记录并更新下载")
    archive = at.session_state["trial_workspace_result"]["archive"]
    original = deepcopy(at.session_state["result"])
    # Unsaved form input must not silently replace the saved swatch used by preview.
    at.number_input(key=prefix + "stitches_per_10cm").set_value(22).run()
    at.button(key="trial_gauge_preview_result").click().run()
    assert not at.exception
    pending = at.session_state["edit_trial-source_pending_preview"]
    assert pending["candidate"]["gauge"]["stitches_per_10cm"] == 18
    assert at.session_state["result"] == original
    assert at.checkbox(key="chk_trial-source_头部_0").value
    assert any("10 cm 针数" in str(table.value) and "修改后" in str(table.value) for table in at.table)
    at.button(key="edit_trial-source_preview_cancel").click().run()
    assert at.session_state["result"] == original
    at.button(key="trial_gauge_preview_result").click().run()
    at.button(key="edit_trial-source_preview_apply").click().run()
    assert not at.exception
    updated = at.session_state["result"]
    rid = updated["result_id"]
    assert updated["analysis"] == original["analysis"]
    assert updated["gauge"]["stitches_per_10cm"] == 18
    assert not at.checkbox(key=f"chk_{rid}_头部_0").value
    assert at.text_area(key=f"project_notes_{rid}").value == "记得保留原试钩"
    assert at.session_state["trial_workspace_result"]["archive"] == archive
    assert at.button(key="trial_gauge_preview_result").disabled
    at.button(key=f"edit_{rid}_undo").click().run()
    rid = at.session_state["result"]["result_id"]
    assert at.checkbox(key=f"chk_{rid}_头部_0").value
    assert at.session_state["result"]["gauge"] == original["gauge"]
    assert not at.button(key="trial_gauge_preview_result").disabled
    at.button(key=f"edit_{rid}_redo").click().run()
    rid = at.session_state["result"]["result_id"]
    assert not at.checkbox(key=f"chk_{rid}_头部_0").value
    assert at.session_state["trial_workspace_result"]["archive"] == archive


def test_editor_disables_density_action_until_changed_measurement_is_saved():
    at = _app()
    prefix = _start(at)
    assert at.button(key="trial_gauge_preview_result").disabled
    at.checkbox(key=prefix + "measured").check()
    _click(at, "保存记录并更新下载")
    assert at.button(key="trial_gauge_preview_result").disabled
    assert any("无需重算" in c.value for c in at.caption)
    at.number_input(key=prefix + "stitches_per_10cm").set_value(18).run()
    assert at.button(key="trial_gauge_preview_result").disabled
    _click(at, "保存记录并更新下载")
    assert not at.button(key="trial_gauge_preview_result").disabled
    source = deepcopy(at.session_state["result"])
    source["analysis"]["height_cm"] = 25
    at.session_state["result"] = source
    at.run()
    assert at.button(key="trial_gauge_preview_result").disabled
