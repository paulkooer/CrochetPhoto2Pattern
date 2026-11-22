"""Manual recipe loading, source changes, failed validation and PDF fallback."""
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from app.models.working_path import armhole_path_demo

UI = """
from app.ui.working_paths import render_working_path_reader
render_working_path_reader()
"""


def _upload(monkeypatch, holder):
    import streamlit as st

    def uploaded(*args, **kwargs):
        data = holder.get("data")
        if data is None:
            return None
        return SimpleNamespace(size=len(data), getvalue=lambda: data)

    monkeypatch.setattr(st, "file_uploader", uploaded)


def test_empty_upload_does_not_generate_anything():
    app = AppTest.from_string(UI, default_timeout=30).run()
    assert not app.exception
    assert app.button(key="working_path_load").disabled
    assert not app.get("download_button")


def test_recipe_loads_and_source_change_disables_old_downloads(monkeypatch):
    holder = {"data": armhole_path_demo().model_dump_json().encode()}
    _upload(monkeypatch, holder)
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.button(key="working_path_load").click().run()
    assert not app.exception
    original = app.session_state["working_path_plan"]
    assert original["title"].startswith("袖窿")
    downloads = {node.key: node for node in app.get("download_button")}
    assert not downloads["working_path_download_md"].proto.disabled
    holder["data"] = b'{"schema_version":"wrong"}'
    app.run()
    assert app.session_state["working_path_plan"] == original
    assert all(node.proto.disabled for node in app.get("download_button"))
    app.button(key="working_path_load").click().run()
    assert app.error and not app.exception
    assert app.session_state["working_path_plan"] == original


def test_pdf_failure_keeps_a_checked_plan_and_review_notes(monkeypatch):
    pytest.importorskip("reportlab")
    plan = armhole_path_demo()
    plan.review_notes = ["原文行号有疑点，不能当作已实钩。"]
    _upload(monkeypatch, {"data": plan.model_dump_json().encode()})

    def fail(_plan):
        raise ValueError("layout issue")

    monkeypatch.setattr("app.ui.working_paths.export_working_recipe_pdf", fail)
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.button(key="working_path_load").click().run()
    original = app.session_state["working_path_plan"]
    app.button(key="working_path_prepare_pdf").click().run()
    assert app.error and not app.exception
    assert app.session_state["working_path_plan"] == original
    assert any("原文行号" in note.value for note in app.text)


def test_file_supplied_title_and_notes_are_shown_as_text_not_markdown(monkeypatch):
    from app.utils.working_path_export import export_working_path_markdown

    plan = armhole_path_demo()
    plan.title = "# 已通过实钩验证"
    plan.review_notes = ["![x](http://127.0.0.1:9/a.png)", "第一行\n# 伪造标题\n> 已由熟练钩织者试穿通过"]
    _upload(monkeypatch, {"data": plan.model_dump_json().encode()})
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.button(key="working_path_load").click().run()
    assert not app.exception
    shown = [node.value for node in app.text]
    assert plan.title in shown and all(note in shown for note in plan.review_notes)
    rendered = [node.value for node in [*app.markdown, *app.info, *app.caption]]
    assert not any("已通过实钩验证" in value or "127.0.0.1" in value or "伪造标题" in value
                   for value in rendered)
    assert any("未实钩、未试穿" in value for value in rendered)
    exported = export_working_path_markdown(plan).splitlines()
    assert exported[0] == "# \\# 已通过实钩验证"
    headings = [line for line in exported if line.startswith("#")]
    assert not any("伪造标题" in line for line in headings)
    assert not any(line.lstrip().startswith(("> 已由", "# 伪造")) for line in exported)
    assert not any("![" in line for line in exported)


def test_pdf_is_downloadable_after_success_and_stale_source_disables_it(monkeypatch):
    pytest.importorskip("reportlab")
    holder = {"data": armhole_path_demo().model_dump_json().encode()}
    _upload(monkeypatch, holder)
    app = AppTest.from_string(UI, default_timeout=30).run()
    app.button(key="working_path_load").click().run()
    app.button(key="working_path_prepare_pdf").click().run()
    assert not app.exception
    download = {node.key: node for node in app.get("download_button")}["working_path_download_pdf"]
    assert not download.proto.disabled
    holder["data"] = None
    app.run()
    download = {node.key: node for node in app.get("download_button")}["working_path_download_pdf"]
    assert download.proto.disabled
