"""The design UI must expose gaps and bind downloads to the current inputs."""
import pytest
from streamlit.testing.v1 import AppTest

UI = "from app.ui.cardigan_design import render_cardigan_designer\nrender_cardigan_designer()"


def test_no_automatic_generation_and_missing_ribbing_is_explicit():
    app = AppTest.from_string(UI, default_timeout=30).run()
    assert not app.exception and not app.get("download_button")
    app.button(key="cardigan_generate").click().run()
    assert not app.exception
    report = app.session_state["cardigan_design_result"]["report"]
    assert report["stage"] == "hem_blocked"
    assert any("密度" in item.value for item in app.warning)


def test_example_is_generated_and_changed_dimensions_disable_old_downloads():
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.radio(key="cardigan_gauge_mode").set_value("用假设密度查看工程示例").run()
    app.button(key="cardigan_generate").click().run()
    assert not app.exception and not app.error
    stored = app.session_state["cardigan_design_result"]
    assert stored["report"]["stage"] == "integrated_open_cuffs"
    assert stored["plan"]["input_origin"] == "parametric_design"
    assert any(node.label == "查看接线、暂停与收尾" for node in app.expander)
    app.number_input(key="cardigan_neck").set_value(9.0).run()
    assert all(node.proto.disabled for node in app.get("download_button"))
    assert app.session_state["cardigan_design_result"] == stored


def test_pdf_failure_keeps_the_generated_plan(monkeypatch):
    pytest.importorskip("reportlab")

    def fail(_):
        raise ValueError("layout")

    monkeypatch.setattr("app.ui.cardigan_design.export_working_recipe_pdf", fail)
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.radio(key="cardigan_gauge_mode").set_value("用假设密度查看工程示例").run()
    app.button(key="cardigan_generate").click().run()
    plan = app.session_state["cardigan_design_result"]["plan"]
    app.button(key="cardigan_prepare_pdf").click().run()
    assert app.error and not app.exception
    assert app.session_state["cardigan_design_result"]["plan"] == plan


def test_selecting_own_swatch_does_not_relabel_the_example_numbers_as_measurements():
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.radio(key="cardigan_gauge_mode").set_value("填入自己的小样密度").run()
    assert app.number_input(key="cardigan_sc_own_gs").value is None
    assert app.number_input(key="cardigan_hem_own_gr").value is None
    app.button(key="cardigan_generate").click().run()
    assert not app.exception
    stored = app.session_state["cardigan_design_result"]
    assert stored["report"]["stage"] == "yoke_blocked" and stored["plan"] is None


def test_changed_generator_version_keeps_old_view_but_disables_its_downloads(monkeypatch):
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.radio(key="cardigan_gauge_mode").set_value("用假设密度查看工程示例").run()
    app.button(key="cardigan_generate").click().run()
    original = app.session_state["cardigan_design_result"]
    monkeypatch.setattr("app.ui.cardigan_design.CARDIGAN_ENGINE_VERSION", "future-version")
    app.run()
    assert all(node.proto.disabled for node in app.get("download_button"))
    assert app.session_state["cardigan_design_result"] == original
