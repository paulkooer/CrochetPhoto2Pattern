import pytest
from streamlit.testing.v1 import AppTest

RENDER = """
from app.ui.dressed_doll import render_dressed_doll_designer
render_dressed_doll_designer()
"""


def test_designer_generates_distinct_components_and_disables_stale_downloads():
    app = AppTest.from_string(RENDER, default_timeout=30).run()
    assert not app.exception
    app.button(key="doll_design_generate").click().run()
    assert not app.exception
    original = app.session_state["doll_design_plan"]
    assert original["status"] == "unverified_prototype"
    assert any(p["id"] == "hair" for p in original["components"])
    assert any(p["id"] == "shoes" for p in original["components"])
    downloads = {d.key: d for d in app.get("download_button")}
    assert not downloads["doll_design_download_md"].proto.disabled
    app.number_input(key="doll_design_hair_chains_wide_brim_curls").set_value(20).run()
    downloads = {d.key: d for d in app.get("download_button")}
    assert downloads["doll_design_download_md"].proto.disabled
    assert app.session_state["doll_design_plan"] == original
    app.button(key="doll_design_generate").click().run()
    assert not app.exception
    assert app.session_state["doll_design_plan"]["design"]["hair_chain_count"] == 20


def test_alternative_starter_and_invalid_palm_wrist_fail_without_losing_plan():
    app = AppTest.from_string(RENDER, default_timeout=30).run()
    app.selectbox(key="doll_design_starter").select("folded_cap_layers").run()
    app.button(key="doll_design_generate").click().run()
    assert not app.exception
    original = app.session_state["doll_design_plan"]
    assert any(p["id"] == "hat_band" for p in original["components"])
    assert not any(p["id"] == "flower_centres" for p in original["components"])
    app.number_input(key="doll_design_wrist_folded_cap_layers").set_value(2.0).run()
    assert app.button(key="doll_design_generate").disabled
    assert app.error and not app.exception
    assert app.session_state["doll_design_plan"] == original


def test_pdf_failure_retains_the_plan_and_does_not_crash_ui(monkeypatch):
    pytest.importorskip("reportlab")

    def failed(_plan):
        raise ValueError("layout failure")

    monkeypatch.setattr("app.ui.dressed_doll.export_doll_pdf", failed)
    app = AppTest.from_string(RENDER, default_timeout=30).run()
    app.button(key="doll_design_generate").click().run()
    original = app.session_state["doll_design_plan"]
    app.button(key="doll_design_prepare_pdf").click().run()
    assert app.error and not app.exception
    assert app.session_state["doll_design_plan"] == original
