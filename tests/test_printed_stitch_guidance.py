"""Printed guidance must not contradict the operations in a round."""
import html

import pytest
from streamlit.testing.v1 import AppTest

from app.models.stitches import PLACEMENT_GUIDANCE, ROUND_WORKING_GUIDANCE, STITCH_LEGEND_ZH
from app.utils.exporters import export_markdown
from tests.test_app_smoke import _mock_result


def _result():
    result = _mock_result("printed-guidance")
    result["params"]["parts"][0]["rounds"][2]["notes"] = "BLO((X,V)×6)"
    return result


def test_markdown_defines_loop_and_decrease_terms_without_overriding_placement():
    result = _result()
    md = export_markdown(result["params"], result=result)
    assert "A = sc2tog (single crochet 2 stitches together)" in md
    assert "sc2tog 与隐形减针（invdec）操作不同" in md
    assert "FLO=只挑前半针，BLO=只挑后半针" in md
    assert "BLO((X,V)×6)" in md
    for obsolete in ("sc2tog (invisible decrease)", "自动漂移 1 针", "按习惯任选即可"):
        assert obsolete not in md
    assert "不再额外错位" in md and "重新核对起立针计数" in md


def test_pdf_uses_same_legends_and_retains_actual_loop_instruction(monkeypatch):
    pytest.importorskip("reportlab")
    import reportlab.platypus as platypus

    from app.utils.pdf_export import export_pdf

    texts = []
    paragraph = platypus.Paragraph

    def capture(text, *args, **kwargs):
        texts.append(html.unescape(text))
        return paragraph(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    result = _result()
    assert export_pdf(result["params"], result=result).startswith(b"%PDF-")
    md = export_markdown(result["params"], result=result)
    for prefix in ("记号：", "Stitch Key:", "钩法：", "加针点提示："):
        instructions = [text for text in texts if text.startswith(prefix)]
        assert len(instructions) == 1 and instructions[0] in md
    assert "FLO=只挑前半针，BLO=只挑后半针" in "\n".join(texts)
    assert "BLO((X,V)×6)" in "\n".join(texts)
    assert "sc2tog (invisible decrease)" not in "\n".join(texts)


def test_result_page_shares_printed_stitch_guidance():
    at = AppTest.from_string('''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
''', default_timeout=30)
    at.session_state["result"] = _result()
    at.run()
    assert not at.exception
    captions = [caption.value for caption in at.caption]
    for instruction in (STITCH_LEGEND_ZH, ROUND_WORKING_GUIDANCE, PLACEMENT_GUIDANCE):
        assert instruction in captions


@pytest.mark.parametrize("old_version", [None, 3, 5, 6])
def test_pdf_from_previous_guidance_is_removed_and_regenerated(old_version, monkeypatch):
    from app.ui.export_cache import EXPORT_CACHE_VERSION
    from app.ui.result_renderer import purge_result_state

    built = []

    def fake_pdf(*args, **kwargs):
        built.append(True)
        return b"%PDF-updated-guidance"

    monkeypatch.setattr("app.utils.pdf_export.export_pdf", fake_pdf)
    at = AppTest.from_string('''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state.result, "result")
''', default_timeout=30)
    at.session_state["result"] = _result()
    at.session_state["pdf_printed-guidance"] = b"%PDF-old-guidance"
    if old_version is not None:
        at.session_state["pdf_format_printed-guidance"] = old_version
    at.run()
    assert not at.exception
    assert "pdf_printed-guidance" not in at.session_state
    assert not any(button.label == "📄 下载 PDF" for button in at.get("download_button"))
    assert not built
    at.button(key="pdf_gen_printed-guidance").click().run()
    assert not at.exception and len(built) == 1
    assert at.session_state["pdf_format_printed-guidance"] == EXPORT_CACHE_VERSION
    assert at.session_state["pdf_printed-guidance"] == b"%PDF-updated-guidance"
    at.run()
    assert len(built) == 1
    assert any(button.label == "📄 下载 PDF" for button in at.get("download_button"))
    # Edits/imports clean up both PDF bytes and their format marker.
    state = dict(at.session_state.to_dict())
    monkeypatch.setattr("app.ui.result_renderer.st.session_state", state)
    purge_result_state(_result())
    assert "pdf_printed-guidance" not in state
    assert "pdf_format_printed-guidance" not in state
