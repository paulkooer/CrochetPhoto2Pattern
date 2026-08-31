"""第十五轮（Opus 5 第二部分）回归：V6/U23升级/U24升级/U30/V5/U26。"""
import sqlite3

import pytest

from app.models.crochet_params import (
    CrochetParamsGenerator,
    estimate_minutes,
)
from app.models.gauge import PRESETS
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis


def _params(parts=("头部", "身体", "手臂", "腿部"), gauge=None):
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=list(parts))
    st = StructureDesigner.design_3d_structure(a)
    return CrochetParamsGenerator.generate_params(
        a, st, gauge=gauge or PRESETS["classic"])


# ── V6：CYC 署名纠正 ─────────────────────────────────────────────────────

def test_meters_docstring_no_cyc_attribution():
    """V6：meters_per_100g 不得再署名 CYC（CYC 标准不含 m/100g 数据）。"""
    import inspect

    from app.models.gauge import Gauge
    doc = inspect.getdoc(Gauge.meters_per_100g)
    # 断言的是"不再声称数值来自 CYC"，而非"完全不提 CYC"——纠正说明
    # 里如实引用 CYC 标准不含长度数据这一事实是被允许且必要的
    assert "CYC Standard Yarn Weight System 的 m/100g" not in doc
    assert "经验估算" in doc and "以实际线标为准" in doc


def test_materials_estimate_disclaimer_in_exports():
    """导出物材料区带"以实际线标为准"免责提示（V6）。"""
    from app.utils.exporters import export_markdown
    from app.utils.pdf_export import export_pdf
    params = _params()
    md = export_markdown(params, {"body_type": "标准"})
    assert "以实际线标为准" in md
    pytest.importorskip("reportlab")
    data = export_pdf(params, {"body_type": "标准"})
    assert data[:5] == b"%PDF-"


# ── U23 升级：校准模型 ───────────────────────────────────────────────────

def test_time_model_anchor_preserved():
    """校准锚点：classic 默认玩偶含左右手/腿，不能再漏算第二件。"""
    params = _params(gauge=PRESETS["classic"])
    assert params["total_stitches"] == 1224
    assert params["estimated_time_minutes"] == pytest.approx(144, abs=5)
    assert params["time_estimate_basis"]["scope"] == "round_crochet_baseline"
    assert params["time_estimate_basis"]["confidence"] == "low_uncalibrated"
    assert "assembly" in params["time_estimate_basis"]["excluded"]


def test_time_model_cross_gauge_consistent():
    """跨密度隐含单针耗时一致（U23 修正目标：不再 0.117→0.080 漂移）。"""
    implied = {}
    for name in ("classic", "dk", "fine"):
        params = _params(gauge=PRESETS[name])
        implied[name] = (params["estimated_time_minutes"]
                         / params["total_stitches"] * 60)
    assert max(implied.values()) - min(implied.values()) < 1.0


def test_estimate_minutes_shared_by_both_paths():
    """refresh_derived 与 _build_result 共用 _estimate_minutes（防失同步）。"""
    params = _params()
    edited = {**{k: v for k, v in params.items() if k != "parts"},
              "parts": [p.model_dump() for p in params["parts"]]}
    edited["parts"][0]["rounds"] = edited["parts"][0]["rounds"] * 2
    from app.models.crochet_params import refresh_derived
    out = refresh_derived(edited)
    expect = estimate_minutes(out["parts"])
    assert out["estimated_time_minutes"] == expect
    assert out["time_estimate_basis"] == params["time_estimate_basis"]


def test_time_estimate_scope_is_explicit_in_exports():
    from app.utils.exporters import export_markdown

    md = export_markdown(_params(), {"body_type": "标准"})
    assert "基础操作估时" in md
    assert "未校准的低置信度经验值" in md
    assert "不含缝合、填充、换色、刺绣、返工和休息" in md


# ── U24 升级：密度导出兜底 ───────────────────────────────────────────────

def test_density_fallback_when_gauge_missing():
    """无 gauge 键时导出兜底声明（旧备份兼容）。"""
    from app.utils.exporters import export_markdown
    params = _params()
    no_gauge = {k: v for k, v in params.items() if k != "gauge"}
    md = export_markdown(no_gauge, {"body_type": "标准"})
    assert "未记录（按经典图解默认 13 针 × 16 行 / 10cm）" in md


def test_density_line_has_regen_hint():
    from app.utils.exporters import export_markdown
    md = export_markdown(_params(), {"body_type": "标准"})
    assert "改密度后重新生成" in md


def test_export_explains_gauge_dependent_shaping_limit():
    from app.utils.exporters import export_markdown

    classic = export_markdown(_params(gauge=PRESETS["classic"]))
    fine = export_markdown(_params(gauge=PRESETS["fine"]))
    assert "连续几何变化率约 5.11 针/圈" in classic
    assert "每圈 ±6 针" in classic
    assert "连续几何变化率约 7.85 针/圈" in fine
    assert "每圈 ±12 针" in fine


# ── U30 双语记号对照 ─────────────────────────────────────────────────────

def test_bilingual_stitch_key_in_exports():
    from app.utils.exporters import export_markdown
    from app.utils.pdf_export import export_pdf
    md = export_markdown(_params(), {"body_type": "标准"})
    assert "Stitch Key" in md and "sc2tog" in md and "2 sc in same st" in md
    pytest.importorskip("reportlab")
    data = export_pdf(_params(), {"body_type": "标准"})
    assert data[:5] == b"%PDF-"


# ── V5 历史载入校验对等 ──────────────────────────────────────────────────

def test_validated_backup_rejects_corrupt_history_record(tmp_path):
    """坏历史记录经 _validated_backup 必须报错（与备份导入对等）。"""
    from app.ui.result_renderer import _validated_backup
    with pytest.raises((ValueError, TypeError, KeyError)):
        _validated_backup({"analysis": {"body_type": "标准"},
                           "structure": ["坏结构"],
                           "params": {}})


def test_history_save_rejects_malformed(tmp_path, monkeypatch):
    """V5 入口校验：缺 params.parts 的数据拒绝入库。"""
    from app.utils import history
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "h.db"))
    with pytest.raises(ValueError):
        history.save_result({"result_id": "bad", "analysis": {"x": 1}})


def test_history_title_and_migration(tmp_path, monkeypatch):
    """U26：旧 schema 幂等迁移 + title 命名 + 搜索命中 title。"""
    from app.utils import history
    db = tmp_path / "h.db"
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(db))
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE patterns (rid TEXT PRIMARY KEY, created_at REAL,"
                 " summary TEXT, blob TEXT)")
    conn.execute("INSERT INTO patterns VALUES ('old1', 0, '旧记录', '{}')")
    conn.commit()
    conn.close()
    assert len(history.list_results()) == 1      # 迁移后可读
    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部"])
    p = _params()
    history.save_result({"result_id": "t1", "analysis": a.model_dump(),
                         "params": p}, title="蓝色小兔")
    hits = history.list_results(query="蓝色小兔")
    assert len(hits) == 1 and hits[0]["title"] == "蓝色小兔"
