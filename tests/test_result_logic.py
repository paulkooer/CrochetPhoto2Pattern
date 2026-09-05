"""结果页业务逻辑纯函数层（app/ui/result_logic.py）的单测。

这三条流程（快速调尺寸 / 结构修正 / 备份导入）此前埋在按钮回调里，
照片 Tab 的生成按钮路径覆盖率为零；抽离后可离线构造结果并断言行为。
"""
import json

import pytest
from PIL import Image

from app.models.orchestrator import PipelineOrchestrator
from app.ui import result_logic


def _result() -> dict:
    return PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 80)), local_vision=True)


def _backup(result: dict) -> str:
    from app.schemas import PatternResult

    return json.dumps(PatternResult.from_result(result).to_backup(),
                      ensure_ascii=False)


def test_regenerate_with_size_updates_analysis_and_sizing_only():
    r = _result()
    old_head = r["analysis"]["head_diameter_cm"]
    new = result_logic.regenerate_with_size(r, old_head + 3.0,
                                            r["analysis"]["height_cm"])
    assert new["analysis"]["head_diameter_cm"] == old_head + 3.0
    assert new["sizing"]["source"] == "user_resize"
    # 未变化的维度原样透传：usage/vision_meta/gauge/style/色带/几何
    for key in ("usage", "vision_meta", "gauge", "style", "color_bands",
                "spans", "spans_measured", "preview", "geometry"):
        assert new[key] == r.get(key)
    # 键集与 orchestrator 产物一致（PatternResult 契约），不丢不增
    assert set(new) == set(r)


def test_regenerate_with_size_changes_stitch_counts():
    r = _result()
    new = result_logic.regenerate_with_size(
        r, r["analysis"]["head_diameter_cm"] * 2,
        r["analysis"]["height_cm"])
    old_head = next(p for p in r["params"]["parts"] if p["name"] == "头部")
    new_head = next(p for p in new["params"]["parts"] if p["name"] == "头部")
    assert max(s["stitches"] for s in new_head["rounds"]) > max(
        s["stitches"] for s in old_head["rounds"])


def test_regenerate_with_structure_updates_params_and_validates_graph():
    r = _result()
    edited = json.loads(json.dumps(r["structure"], ensure_ascii=False))
    arm = next(p for p in edited["parts"] if p.get("name") == "手臂")
    arm["length_cm"] = (arm.get("length_cm") or 0) + 2.0
    new = result_logic.regenerate_with_structure(r, edited)
    assert new["structure"] == edited
    assert set(new) == set(r)
    # v2 图契约仍然生效：count 与 instances 数量不一致必须拒绝
    bad = json.loads(json.dumps(edited, ensure_ascii=False))
    bad["parts"][0]["count"] = 99
    with pytest.raises(ValueError):
        result_logic.regenerate_with_structure(r, bad)


def test_import_backup_roundtrip_preserves_keys():
    r = _result()
    imported = result_logic.import_backup(json.loads(_backup(r)), "imp-1")
    assert imported["result_id"] == "imp-1"
    # 备份键集 ⊆ 导入产物（result_id 为导入新加的会话字段）
    from app.utils.share import _BACKUP_KEYS

    assert set(_BACKUP_KEYS) <= set(imported)
    for key in _BACKUP_KEYS:
        if key == "params":
            continue  # params 经重建（dict 化 + 派生量重算），逐键语义不同
        assert imported[key] == r.get(key), key


def test_import_backup_tolerates_legacy_minimal_backup():
    """旧格式备份（缺 style/gauge/preview 等）→ 缺键以 None 兜底。"""
    from app.schemas import ImageAnalysis

    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部"])
    legacy = {"analysis": a.model_dump(),
              "structure": {"parts": [{"name": "头部", "shape": "sphere",
                                       "diameter_cm": 9.0}]},
              # 旧备份必带 params（生成器产物）；仅缺 V4+ 的新键
              "params": {"parts": [{"name": "头部", "type": "sphere",
                                    "rounds": [{"row": 1, "stitches": 6}],
                                    "color": "肤色"}]}}
    imported = result_logic.import_backup(legacy, "legacy-1")
    assert imported["style"] is None
    assert imported["gauge"] is None
    assert imported["result_id"] == "legacy-1"
    assert imported["params"]["parts"]


def test_import_backup_rejects_malformed():
    # pydantic ValidationError 包装为 ValueError（与历史库 save 同出口）
    with pytest.raises(ValueError):
        result_logic.import_backup({"analysis": {"body_type": "标准"}}, "bad-1")


def test_rebuild_params_drops_stale_rows_and_keeps_dicts():
    r = _result()
    edited = {**r["params"],
              "parts": [{**p, "rows": 999} for p in r["params"]["parts"]]}
    out = result_logic.rebuild_params(edited)
    for p in out["parts"]:
        assert "rows" not in p  # 过期 rows 不得复活（由 len(rounds) 派生）
        assert isinstance(p, dict)
    assert out["estimated_time_minutes"] >= 30
