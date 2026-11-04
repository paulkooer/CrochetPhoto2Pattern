"""Placeholder yarn colors stay editable data while their meaning is visible."""

from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from app.models.color_design import refresh_color_instructions
from app.models.materials import yarn_requirements
from app.utils.color_labels import display_color_name, display_generated_color_note
from app.utils.exporters import export_markdown
from tests.test_app_smoke import _mock_result
from tests.test_project_backup import RENDER


def _result():
    result = _mock_result("placeholder-color")
    rounds = result["params"]["parts"][0]["rounds"]
    rounds[0]["color"] = "skin"
    rounds[1]["color"] = "body"
    rounds[2]["color"] = "蓝色"
    result["params"]["parts"][0]["notes"] = "手写 skin 不应改写。"
    refresh_color_instructions(result["params"]["parts"][0])
    return result


@pytest.mark.parametrize(("raw", "shown"), [
    ("skin", "肤色（待选色）"),
    ("body", "主体色（待选色）"),
    ("蓝色", "蓝色"),
    ("skin tone", "skin tone"),
    ("Skin", "Skin"),
    (None, None),
    (42, 42),
    ({"legacy": "skin"}, {"legacy": "skin"}),
])
def test_only_reserved_color_values_are_translated(raw, shown):
    assert display_color_name(raw) == shown


def test_generated_color_notes_change_only_the_recorded_generated_fragment():
    auto = "换线：body（前一针最后一次挂线改用新色；螺旋圈仍可能出现台阶）"
    note = f"手写 skin；{auto}"
    assert display_generated_color_note(note, auto) == note.replace(
        "换线：body", "换线：主体色（待选色）")
    duplicated = f"手写 {auto}；{auto}"
    assert display_generated_color_note(duplicated, auto) == (
        f"手写 {auto}；{auto.replace('换线：body', '换线：主体色（待选色）')}")
    summary = " 配色（按钩织圈序，自上而下）：R1 skin tone；R2 body；R3 Skin。"
    assert display_generated_color_note(summary, summary) == summary.replace(
        "R2 body；", "R2 主体色（待选色）；")
    assert display_generated_color_note(note, None) == note
    assert display_generated_color_note(note, "unrelated") == note
    assert display_generated_color_note("手写 skin", auto) == "手写 skin"


def test_result_and_paged_progress_show_labels_without_mutating_the_pattern():
    result = _result()
    original = deepcopy(result)
    materials_before = yarn_requirements(result["params"]["parts"])
    assert {"肤色（待选色）", "主体色（待选色）"} <= {row["color"] for row in materials_before[0]}

    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    assert not at.exception
    assert any("**颜色**: 肤色（待选色）" in item.value for item in at.markdown)
    assert any("**颜色**: 主体色（待选色）" in item.value for item in at.markdown)
    assert any("肤色（待选色）" in item.label for item in at.checkbox)
    assert any("主体色（待选色）" in item.label for item in at.checkbox)
    assert any("蓝色" in item.label for item in at.checkbox)
    assert any("换线：主体色（待选色）" in item.label for item in at.checkbox)
    assert any("手写 skin" in item.value and "R1 肤色（待选色）" in item.value for item in at.info)
    structure = next(item.value for item in at.dataframe if "基准色" in item.value.columns)
    assert set(structure["基准色"]) >= {"肤色（待选色）", "主体色（待选色）"}
    assert any("待选色使用示意颜色" in item.value for item in at.caption)

    paged = AppTest.from_string('''
import streamlit as st
from app.ui.result_renderer import _render_paged_progress
_render_paged_progress(st.session_state.result, "result")
''', default_timeout=30)
    paged.session_state["result"] = deepcopy(original)
    paged.run()
    assert not paged.exception
    assert any("肤色（待选色）" in item.label for item in paged.checkbox)
    assert any("主体色（待选色）" in item.label for item in paged.checkbox)
    assert any("换线：主体色（待选色）" in item.label for item in paged.checkbox)

    assert result == original == at.session_state["result"] == paged.session_state["result"]
    assert yarn_requirements(result["params"]["parts"]) == materials_before


def test_markdown_labels_placeholders_and_preserves_custom_color_escaping():
    result = _result()
    result["params"]["parts"][0]["rounds"][3]["color"] = "蓝|<b>绿</b>"
    refresh_color_instructions(result["params"]["parts"][0])
    original = deepcopy(result)
    markdown = export_markdown(result["params"], result=result)

    assert "**颜色**：肤色（待选色）" in markdown
    assert "**颜色**：主体色（待选色）" in markdown
    assert "| 肤色（待选色） |" in markdown
    assert "| 主体色（待选色） |" in markdown
    assert "| 蓝色 |" in markdown
    assert "手写 skin" in markdown and "R1 肤色（待选色）" in markdown
    assert "换线：主体色（待选色）" in markdown
    assert r"蓝\|&lt;b&gt;绿&lt;/b&gt;" in markdown
    assert result == original


def test_pdf_reports_part_and_round_colors_without_mutating_the_pattern(monkeypatch):
    platypus = pytest.importorskip("reportlab.platypus")
    from app.utils.pdf_export import export_pdf

    result = _result()
    result["params"]["parts"][0]["rounds"][3]["color"] = "蓝<b>绿</b>"
    refresh_color_instructions(result["params"]["parts"][0])
    original = deepcopy(result)
    texts = []
    paragraph = platypus.Paragraph

    def capture(text, *args, **kwargs):
        texts.append(text)
        return paragraph(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    assert export_pdf(result["params"], result=result).startswith(b"%PDF-")
    assert "部件颜色：肤色（待选色）" in texts
    assert "部件颜色：主体色（待选色）" in texts
    assert "肤色（待选色）" in texts
    assert "主体色（待选色）" in texts
    assert "蓝色" in texts
    assert any("手写 skin" in text and "R1 肤色（待选色）" in text for text in texts)
    assert any("换线：主体色（待选色）" in text for text in texts)
    assert "蓝&lt;b&gt;绿&lt;/b&gt;" in texts
    assert result == original
