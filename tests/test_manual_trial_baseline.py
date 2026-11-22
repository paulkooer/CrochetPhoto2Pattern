"""A result fresh from the manual page must be the trial's own baseline.

Regression for the false "pattern changed" warning: the manual page omitted the
top-level gauge that import normalisation later fills in. These tests start
from the real manual page, never from a result stub that already has a gauge.
"""
from dataclasses import asdict

import pytest
from streamlit.testing.v1 import AppTest

from app.models.gauge import gauge_from_ui
from app.utils.project import pattern_revision
from tests.test_app_smoke import _APP

MANUAL = """
from app.ui.tab_manual import render_tab_manual
render_tab_manual()
"""
CUSTOM = {"gauge_preset": "custom", "gauge_st_input": 18.0, "gauge_rw_input": 22.0}


@pytest.mark.parametrize("session", [{}, CUSTOM])
def test_manual_result_records_the_gauge_actually_used(session):
    at = AppTest.from_string(MANUAL, default_timeout=60)
    for key, value in session.items():
        at.session_state[key] = value
    at.run()
    at.button(key="btn_manual").click().run()
    assert not at.exception
    result = at.session_state["manual_result"]
    expected = asdict(gauge_from_ui(session.get("gauge_preset", "classic"),
                                    session.get("gauge_st_input"), session.get("gauge_rw_input")))
    assert result["gauge"] == expected == result["params"]["gauge"]
    if session:
        assert result["gauge"] == {"stitches_per_10cm": 18.0, "rows_per_10cm": 22.0}


@pytest.mark.parametrize("session", [{}, CUSTOM])
def test_new_trial_from_a_fresh_manual_result_has_no_change_warning(session):
    at = AppTest.from_file(_APP, default_timeout=120)
    for key, value in session.items():
        at.session_state[key] = value
    at.run()
    at.button(key="btn_manual").click().run()
    assert not at.exception
    at.text_input(key="trial_maker_manual_result").input("maker-a")
    next(b for b in at.button if b.label == "以当前图解新建试钩").click().run()
    assert not at.exception
    workspace = at.session_state["trial_workspace_manual_result"]
    assert workspace["bundle"].source_revision == pattern_revision(at.session_state["manual_result"])
    assert not any("试钩原图解不同" in str(w.value) for w in at.warning)


@pytest.mark.parametrize("session", [{}, CUSTOM])
def test_saved_measured_gauge_can_be_previewed_from_a_fresh_manual_result(session):
    """The whole reported path: generate, new trial, save a measured swatch, preview the recalculation."""
    at = AppTest.from_file(_APP, default_timeout=120)
    for key, value in session.items():
        at.session_state[key] = value
    at.run()
    at.button(key="btn_manual").click().run()
    at.text_input(key="trial_maker_manual_result").input("maker-a")
    next(b for b in at.button if b.label == "以当前图解新建试钩").click().run()
    token = at.session_state["trial_workspace_manual_result"]["token"]
    prefix = f"trial_fields_manual_result_{token}_"
    before = dict(at.session_state["manual_result"]["gauge"])
    measured = {"stitches_per_10cm": before["stitches_per_10cm"] + 2.0,
                "rows_per_10cm": before["rows_per_10cm"] + 3.0}
    at.checkbox(key=prefix + "measured").check()
    for field, value in measured.items():
        at.number_input(key=prefix + field).set_value(value)
    next(b for b in at.button if b.label == "保存记录并更新下载").click().run()
    assert not at.exception and not at.error
    preview = at.button(key="trial_gauge_preview_manual_result")
    assert not preview.disabled
    preview.click().run()
    assert not at.exception
    assert not any("无法生成密度调整方案" in str(e.value) for e in at.error)
    pending = at.session_state["workspace_manual_result"]["pending_preview"]
    assert pending["candidate"]["gauge"] == measured
    assert pending["source"]["gauge"] == before
    assert not any("试钩原图解不同" in str(w.value) for w in at.warning)


def test_a_real_edit_after_creating_the_trial_is_still_reported():
    at = AppTest.from_file(_APP, default_timeout=120).run()
    at.button(key="btn_manual").click().run()
    at.text_input(key="trial_maker_manual_result").input("maker-a")
    next(b for b in at.button if b.label == "以当前图解新建试钩").click().run()
    changed = dict(at.session_state["manual_result"])
    changed["params"] = dict(changed["params"], total_stitches=changed["params"]["total_stitches"] + 1)
    at.session_state["manual_result"] = changed
    at.run()
    assert any("试钩原图解不同" in str(w.value) for w in at.warning)
