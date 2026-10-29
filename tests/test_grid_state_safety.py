"""Failed grid preparation must preserve the current view, inputs and both histories."""
from copy import deepcopy
from io import BytesIO

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from app.models.grid_pattern import (
    export_grid_markdown,
    export_grid_project,
    generate_grid_pattern,
    grid_pattern_from_payload,
    grid_pattern_to_payload,
    import_grid_project,
    render_svg,
)
from app.ui import tab_grid
from tests.test_grid_pattern import _editable_pattern

_UI = '''
from app.ui.tab_grid import render_tab_grid
render_tab_grid()
'''
_ACTIONS = {"restore": "grid_restore_project", "generate": "btn_grid", "edit": "grid_apply_cell",
            "undo": "grid_undo", "redo": "grid_redo"}


class _Upload(BytesIO):
    @property
    def size(self):
        return len(self.getvalue())


def _seed(at):
    view = tab_grid._rendered_grid_view(_editable_pattern())
    past = deepcopy(view["pattern_payload"])
    past["cells"][0][0] = 1
    future = deepcopy(view["pattern_payload"])
    future["cells"][0][1] = 1
    at.session_state["grid_view"] = view
    at.session_state["grid_undo_stack"] = [past]
    at.session_state["grid_redo_stack"] = [future]
    return deepcopy((view, [past], [future]))


def _snapshot(at):
    return deepcopy(tuple(at.session_state[key] for key in
                          ("grid_view", "grid_undo_stack", "grid_redo_stack")))


def _uploads(monkeypatch, action):
    import streamlit as st

    project = _Upload(export_grid_project(_editable_pattern()))
    image = _Upload(b"synthetic image upload")
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs:
                        project if action == "restore" and kwargs.get("key") == "grid_project_uploader"
                        else image if action == "generate" and kwargs.get("key") == "grid_uploader"
                        else None)
    if action == "generate":
        monkeypatch.setattr(tab_grid, "load_uploaded_image_cached",
                            lambda uploaded: Image.new("RGB", (12, 12), "red"))
    return project


@pytest.mark.parametrize("action", ["restore", "generate", "edit", "undo", "redo"])
@pytest.mark.parametrize("stage", ["render_svg", "export_grid_project", "export_grid_markdown"])
def test_failed_render_preserves_current_grid_and_both_histories(monkeypatch, action, stage):
    _uploads(monkeypatch, action)
    at = AppTest.from_string(_UI, default_timeout=30)
    original = _seed(at)
    at.run()
    at.number_input(key="grid_edit_row").set_value(2).run()
    at.selectbox(key="grid_edit_color_2_1").set_value("蓝色").run()

    def fail(*args, **kwargs):
        error = RuntimeError if stage == "export_grid_markdown" else ValueError
        raise error(f"synthetic {stage} preparation failure")

    monkeypatch.setattr(tab_grid, stage, fail)
    at.button(key=_ACTIONS[action]).click().run()

    assert not at.exception
    assert any("失败" in message.value for message in at.error)
    assert _snapshot(at) == original
    assert at.number_input(key="grid_edit_row").value == 2
    assert at.selectbox(key="grid_edit_color_2_1").value == "蓝色"


@pytest.mark.parametrize("dither", [False, True])
@pytest.mark.parametrize("resample", ["lanczos", "nearest"])
def test_generated_grid_uses_native_indices_and_roundtrips_as_an_editable_project(dither, resample):
    image = Image.new("RGB", (12, 12), "red")
    image.paste("blue", (6, 0, 12, 12))
    pattern = generate_grid_pattern(image, grid_width=6, n_colors=2, aspect_ratio=1,
                                    resample=resample, dither=dither)
    assert all(type(cell.col_index) is int for row in pattern.cells for cell in row)
    restored = import_grid_project(export_grid_project(pattern))
    assert grid_pattern_to_payload(restored) == grid_pattern_to_payload(pattern)


@pytest.mark.parametrize("action", ["edit", "undo", "redo"])
def test_history_preparation_failure_does_not_mutate_live_stacks(monkeypatch, action):
    at = AppTest.from_string(_UI, default_timeout=30)
    original = _seed(at)
    at.run()
    at.selectbox(key="grid_edit_color_1_1").set_value("蓝色").run()
    append = tab_grid._bounded_history_append

    def fail_after_append(history, payload):
        append(history, payload)
        raise ValueError("synthetic history preparation failure")

    monkeypatch.setattr(tab_grid, "_bounded_history_append", fail_after_append)
    at.button(key=_ACTIONS[action]).click().run()
    assert not at.exception
    assert any("失败" in message.value for message in at.error)
    assert _snapshot(at) == original


@pytest.mark.parametrize("direction", ["undo", "redo"])
def test_invalid_history_snapshot_is_not_popped_or_replaced(direction):
    at = AppTest.from_string(_UI, default_timeout=30)
    _seed(at)
    at.session_state[f"grid_{direction}_stack"][-1]["cells"][0][0] = 99
    original = _snapshot(at)
    at.run()
    at.button(key=_ACTIONS[direction]).click().run()
    assert not at.exception
    assert any("失败" in message.value for message in at.error)
    assert _snapshot(at) == original


def test_noop_recolor_keeps_redo_and_does_not_rebuild_outputs(monkeypatch):
    at = AppTest.from_string(_UI, default_timeout=30)
    original = _seed(at)
    at.run()

    def forbidden(*args, **kwargs):
        pytest.fail("a no-op must preserve history without rebuilding outputs")

    monkeypatch.setattr(tab_grid, "_rendered_grid_view", forbidden)
    at.button(key="grid_apply_cell").click().run()
    assert not at.exception and not at.error
    assert any("没有产生修改" in message.value for message in at.info)
    assert _snapshot(at) == original


def test_edit_undo_redo_keep_downloads_and_preview_in_sync(monkeypatch):
    import streamlit as st

    downloads = {}
    real_download = st.download_button

    def capture(label, data, *args, **kwargs):
        downloads[label] = data
        return real_download(label, data, *args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture)
    at = AppTest.from_string(_UI, default_timeout=30)
    original = _seed(at)
    at.session_state["result"] = {"unrelated": "photo result"}
    at.session_state["trial_workspace_result"] = {"unrelated": "physical trial"}
    at.run()
    at.selectbox(key="grid_edit_color_1_1").set_value("蓝色").run()
    at.button(key="grid_apply_cell").click().run()
    changed = deepcopy(at.session_state["grid_view"])
    assert changed["pattern_payload"]["cells"][1][0] == 1
    assert at.session_state["grid_redo_stack"] == []
    for action in (None, "undo", "redo"):
        if action is not None:
            at.button(key=_ACTIONS[action]).click().run()
        assert not at.exception
        expected = original[0] if action == "undo" else changed
        assert at.session_state["grid_view"] == expected
        pattern = import_grid_project(downloads["💾 下载可编辑工程"])
        assert grid_pattern_to_payload(pattern) == expected["pattern_payload"]
        assert downloads["📥 下载 SVG 网格图"] == expected["svg"] == render_svg(pattern)
        assert downloads["📄 下载完整 Markdown 图解"] == expected["markdown"] == export_grid_markdown(pattern)
    assert at.session_state["result"] == {"unrelated": "photo result"}
    assert at.session_state["trial_workspace_result"] == {"unrelated": "physical trial"}


@pytest.mark.parametrize("action", ["restore", "generate"])
def test_replacement_can_retry_after_failure_then_resets_history_and_editor(monkeypatch, action):
    upload = _uploads(monkeypatch, action)
    if action == "restore":
        payload = grid_pattern_to_payload(_editable_pattern())
        payload.update(width=1, height=1, cells=[[0]])
        upload.seek(0)
        upload.write(export_grid_project(grid_pattern_from_payload(payload)))
        upload.truncate()
    at = AppTest.from_string(_UI, default_timeout=30)
    original = _seed(at)
    at.run()
    at.number_input(key="grid_edit_row").set_value(2).run()
    at.selectbox(key="grid_edit_color_2_1").set_value("蓝色").run()

    def fail(*args, **kwargs):
        raise ValueError("synthetic one-time preparation failure")

    with monkeypatch.context() as temporary:
        temporary.setattr(tab_grid, "render_svg", fail)
        at.button(key=_ACTIONS[action]).click().run()
        assert not at.exception and _snapshot(at) == original
    at.button(key=_ACTIONS[action]).click().run()
    assert not at.exception and not at.error
    assert at.session_state["grid_undo_stack"] == at.session_state["grid_redo_stack"] == []
    assert at.number_input(key="grid_edit_row").value == 1
    assert at.session_state["grid_view"] != original[0]
    if action == "restore":
        assert at.session_state["grid_view"]["width"] == at.session_state["grid_view"]["height"] == 1
    restored = import_grid_project(at.session_state["grid_view"]["project_json"])
    assert grid_pattern_to_payload(restored) == at.session_state["grid_view"]["pattern_payload"]
    installed = _snapshot(at)
    at.run()
    assert not at.exception and _snapshot(at) == installed


def test_invalid_project_keeps_current_work_and_editor_inputs(monkeypatch):
    upload = _uploads(monkeypatch, "restore")
    upload.seek(0)
    upload.write(b"{")
    upload.truncate()
    at = AppTest.from_string(_UI, default_timeout=30)
    original = _seed(at)
    at.run()
    at.number_input(key="grid_edit_row").set_value(2).run()
    at.button(key="grid_restore_project").click().run()
    assert not at.exception and any("失败" in message.value for message in at.error)
    assert _snapshot(at) == original
    assert at.number_input(key="grid_edit_row").value == 2


def test_failed_rectangle_recolor_keeps_region_inputs_and_history(monkeypatch):
    at = AppTest.from_string(_UI, default_timeout=30)
    original = _seed(at)
    at.run()
    at.radio(key="grid_edit_mode").set_value("矩形").run()
    at.number_input(key="grid_region_row_start").set_value(2)
    at.number_input(key="grid_region_row_end").set_value(2)
    at.number_input(key="grid_region_col_end").set_value(2).run()
    at.selectbox(key="grid_region_color_2_2_1_2").set_value("蓝色").run()

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic rectangle export failure")

    monkeypatch.setattr(tab_grid, "export_grid_markdown", fail)
    at.button(key="grid_apply_cell").click().run()
    assert not at.exception and any("失败" in message.value for message in at.error)
    assert _snapshot(at) == original
    assert at.number_input(key="grid_region_row_start").value == 2
    assert at.number_input(key="grid_region_col_end").value == 2
    assert at.selectbox(key="grid_region_color_2_2_1_2").value == "蓝色"
