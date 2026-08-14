"""Smoke tests for the Streamlit UI layer (app/main.py) via AppTest.

app.models 的单元测试永远不会执行 main.py——这类冒烟测试专门捕获
启动级故障：NameError（如 tab_grid 未定义）、DuplicateWidgetID、
注解语法兼容问题等。无需浏览器，直接进 pytest 套件。
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.image_parser import ImageParser
from app.models.structure_designer import StructureDesigner

_APP = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


def _mock_result(result_id: str) -> dict:
    analysis = ImageParser._mock_analysis()
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(analysis, structure)
    return {
        "analysis": analysis.model_dump(),
        "structure": structure,
        "params": params,
        "result_id": result_id,
    }


def test_app_boots_without_exception():
    """The script must run top-to-bottom with no uncaught exception."""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.run()
    assert not at.exception


def test_both_tabs_with_results_render_together():
    """照片 Tab 与手动 Tab 的结果同屏渲染时不得发生 widget key 冲突。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("smoke-photo-1")
    at.session_state["manual_result"] = _mock_result("smoke-manual-1")
    at.run()
    assert not at.exception


def test_mark_all_done_button_checks_every_round():
    """「全部完成」必须真正勾上所有圈（回归：旧实现被 checkbox 状态覆盖而静默失效）。"""
    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("smoke-photo-2")
    at.run()
    assert not at.exception

    at.button(key="all_smoke-photo-2_头部").click().run()
    assert not at.exception
    head_checks = [
        c for c in at.checkbox
        if c.key and c.key.startswith("chk_smoke-photo-2_头部_")
    ]
    assert head_checks, "未找到头部的逐圈 checkbox"
    assert all(c.value for c in head_checks)
