"""S4：图解历史持久化（SQLite）+ PDF 导出。"""

from pathlib import Path

import pytest

_APP = str(Path(__file__).resolve().parents[1] / "app" / "main.py")


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "h.db"))
    return tmp_path / "h.db"


def _result(rid="r1", head=9.0):
    from app.models.structure_designer import StructureDesigner
    from app.schemas import ImageAnalysis

    a = ImageAnalysis(body_type="标准", head_diameter_cm=head, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体"])
    return {
        "analysis": a.model_dump(),
        "structure": StructureDesigner.design_3d_structure(a),
        "params": {},
        "result_id": rid,
    }


def test_history_save_list_load_delete(tmp_db):
    from app.utils import history

    r = _result("r1")
    r["params"] = {"parts": [], "materials": [], "total_stitches": 0,
                   "estimated_time_minutes": 30,
                   "assembly_instructions": "1. x"}
    assert history.save_result(r) == "r1"
    items = history.list_results()
    assert len(items) == 1 and items[0]["summary"].startswith("标准")
    loaded = history.load_result("r1")
    assert loaded["result_id"] == "r1"
    assert loaded["analysis"]["head_diameter_cm"] == 9.0
    history.delete_result("r1")
    assert history.load_result("r1") is None
    assert history.list_results() == []


def test_history_missing_id_rejected(tmp_db):
    from app.utils import history
    with pytest.raises(ValueError):
        history.save_result({"analysis": {}})


def test_pdf_export_renders_chinese(tmp_db):
    """PDF 生成成功且包含中文图解内容（reportlab CID 字体路径）。"""
    pytest.importorskip("reportlab")
    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.structure_designer import StructureDesigner
    from app.schemas import ImageAnalysis
    from app.utils.pdf_export import export_pdf

    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体"])
    params = CrochetParamsGenerator.generate_params(
        a, StructureDesigner.design_3d_structure(a))
    data = export_pdf(params, a.model_dump())
    assert data[:5] == b"%PDF-" and len(data) > 3000


def test_app_history_save_and_sidebar_load(tmp_db):
    """端到端：结果页「存入历史」→ 侧栏历史出现 → 「载入」恢复结果。"""
    from streamlit.testing.v1 import AppTest

    from app.utils import history
    from tests.test_app_smoke import _mock_result

    at = AppTest.from_file(_APP, default_timeout=30)
    at.session_state["result"] = _mock_result("hist-e2e")
    at.run()
    assert not at.exception
    at.button(key="hist_save_hist-e2e").click().run()
    assert not at.exception
    assert [i for i in history.list_results() if i["rid"] == "hist-e2e"]

    # 全新会话：侧栏载入
    at2 = AppTest.from_file(_APP, default_timeout=30)
    at2.run()
    at2.button(key="hist_load_hist-e2e").click().run()
    assert not at2.exception
    assert "result" in at2.session_state
    assert at2.session_state["result"]["result_id"] == "hist-e2e"
