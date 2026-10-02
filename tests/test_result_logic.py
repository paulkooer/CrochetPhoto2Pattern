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


def test_import_backup_rejects_future_version():
    data = json.loads(_backup(_result()))
    data["schema_version"] = "999"
    with pytest.raises(ValueError, match="schema_version"):
        result_logic.import_backup(data, "future")


def test_rebuild_params_drops_stale_rows_and_keeps_dicts():
    r = _result()
    edited = {**r["params"],
              "parts": [{**p, "rows": 999} for p in r["params"]["parts"]]}
    out = result_logic.rebuild_params(edited)
    for p in out["parts"]:
        assert "rows" not in p  # 过期 rows 不得复活（由 len(rounds) 派生）
        assert isinstance(p, dict)
    assert out["estimated_time_minutes"] >= 30


def test_edited_gauge_survives_import_resize_and_preview():
    from app.models.gauge import PRESETS
    from app.ui.preview3d import build_payload

    result = _result()
    result["params"]["gauge"] = {"stitches_per_10cm": "20", "rows_per_10cm": "16"}
    imported = result_logic.import_backup(result, "gauge-edit")
    assert imported["gauge"] == {"stitches_per_10cm": 20.0, "rows_per_10cm": 16.0}
    resized = result_logic.regenerate_with_size(imported, 9.0, 18.0)
    assert resized["params"]["gauge"] == imported["gauge"]
    # Legacy result-level metadata may be absent or stale: the pattern is authoritative.
    result["structure"]["parts"][1]["shape"] = "profile"
    payload = build_payload(result)
    body = next(p for p in payload["items"] if p["name"] == "身体")
    first_count = result["params"]["parts"][1]["rounds"][0]["stitches"]
    assert body["lathe"]["radii"][0] == pytest.approx(
        first_count * PRESETS["fine"].stitch_w_cm / (2 * 3.14159265))


def test_rebuild_normalizes_gauge_before_export():
    from app.utils.exporters import export_markdown

    result = _result()
    result["params"]["gauge"] = {"stitches_per_10cm": "20", "rows_per_10cm": "16"}
    rebuilt = result_logic.rebuild_params(result["params"])
    assert rebuilt["gauge"] == {"stitches_per_10cm": 20.0, "rows_per_10cm": 16.0}
    assert "20 针 × 16 行" in export_markdown(rebuilt)


def test_resize_preserves_edited_structure_graph_and_dimension_ratios():
    result = _result()
    structure = result["structure"]
    arm = next(p for p in structure["parts"] if p["name"] == "手臂")
    arm["length_cm"] = 7.0
    arm["count"] = 1
    arm["instances"] = arm["instances"][:1]
    arm["instances"][0]["rotation_deg"]["x"] = 40.0
    arm["instances"][0]["position"]["y"] = 0.7
    arm["instances"][0]["attachments"][0]["target_anchor"] = "back"
    arm["color"] = "红色"
    snapshot = json.loads(json.dumps(result))
    resized = result_logic.regenerate_with_size(result, 18.0, 36.0)
    new_arm = next(p for p in resized["structure"]["parts"] if p["name"] == "手臂")
    assert new_arm["length_cm"] == 14.0
    for key in ("instances", "count", "color", "part_id"):
        assert new_arm[key] == arm[key]
    assert next(p for p in resized["params"]["parts"] if p["name"] == "手臂")["quantity"] == 1
    assert result == snapshot
    # The proportions line is regenerated from the new head/body ratio via the
    # shared prefix constant, not left stale from the previous structure.
    assert resized["structure"]["proportions"].startswith("头部直径约为身体高度的 ")
    _head = next(p for p in resized["structure"]["parts"]
                 if p["name"] == "头部")["diameter_cm"]
    _body = next(p for p in resized["structure"]["parts"]
                 if p["name"] == "身体")["height_cm"]
    assert f"{_head / _body:.1f} 倍" in resized["structure"]["proportions"]


def test_resize_does_not_restore_removed_parts():
    result = _result()
    result["structure"]["parts"] = [p for p in result["structure"]["parts"] if p["name"] != "手臂"]
    resized = result_logic.regenerate_with_size(result, 10.0, 20.0)
    assert "手臂" not in {p["name"] for p in resized["structure"]["parts"]}
    assert "手臂" not in {p["name"] for p in resized["params"]["parts"]}


def test_explicit_new_head_size_overrides_previous_structure_head_edit():
    result = _result()
    next(p for p in result["structure"]["parts"] if p["name"] == "头部")["diameter_cm"] = 12.0
    old_arm = next(p for p in result["structure"]["parts"] if p["name"] == "手臂")
    old_arm["diameter_cm"] = 3.0
    resized = result_logic.regenerate_with_size(result, 10.0, 20.0)
    head = next(p for p in resized["params"]["parts"] if p["name"] == "头部")
    assert head["diameter_cm"] == resized["analysis"]["head_diameter_cm"] == 10.0
    new_arm = next(p for p in resized["structure"]["parts"] if p["name"] == "手臂")
    assert new_arm["diameter_cm"] == pytest.approx(old_arm["diameter_cm"] * 10 / 12)
    assert new_arm["length_cm"] == pytest.approx(old_arm["length_cm"] * (20 - 10) / (18 - 12))


@pytest.mark.parametrize("name", ["身体", "手臂", "腿部"])
def test_structure_diameter_edit_changes_cylinder_stitch_counts(name):
    result = _result()
    edited = json.loads(json.dumps(result["structure"]))
    part = next(p for p in edited["parts"] if p["name"] == name)
    part["diameter_cm"] = 12.0
    updated = result_logic.regenerate_with_structure(result, edited)
    old = next(p for p in result["params"]["parts"] if p["name"] == name)
    new = next(p for p in updated["params"]["parts"] if p["name"] == name)
    assert max(r["stitches"] for r in new["rounds"]) > max(r["stitches"] for r in old["rounds"])


def test_structure_color_edit_overrides_saved_photo_colors():
    result = _result()
    result["analysis"]["top_color"] = "蓝色"
    result["color_bands"] = [{"start": 0.0, "end": 1.0, "color": "黑色"}]
    edited = json.loads(json.dumps(result["structure"]))
    next(p for p in edited["parts"] if p["name"] == "身体")["color"] = "红色"
    updated = result_logic.regenerate_with_structure(result, edited)
    body = next(p for p in updated["params"]["parts"] if p["name"] == "身体")
    assert body["color"] == "红色"
    assert {r["color"] for r in body["rounds"]} == {"红色"}


def test_cup_height_edit_changes_wall_depth():
    result = _result()
    edited = json.loads(json.dumps(result["structure"]))
    arm = next(p for p in edited["parts"] if p["name"] == "手臂")
    arm.update(shape="cup", diameter_cm=5.0, height_cm=10.0)
    updated = result_logic.regenerate_with_structure(result, edited)
    part = next(p for p in updated["params"]["parts"] if p["name"] == "手臂")
    assert part["height_cm"] == 10.0


def test_empty_structure_edit_fails_instead_of_restoring_analysis_parts():
    from app.models.crochet_params import PatternGenerationError

    result = _result()
    edited = {**result["structure"], "parts": []}
    with pytest.raises(PatternGenerationError, match="部件列表"):
        result_logic.regenerate_with_structure(result, edited)


def test_skirt_diameter_edit_supports_taper_without_algebra_break():
    from app.models.gauge import DEFAULT
    from app.models.validator import validate_pattern

    result = _result()
    edited = json.loads(json.dumps(result["structure"]))
    skirt = next(p for p in edited["parts"] if p["name"] == "手臂")
    skirt.update(name="裙子", shape="cup", diameter_cm=4.0, height_cm=5.0)
    updated = result_logic.regenerate_with_structure(result, edited)
    part = next(p for p in updated["params"]["parts"] if p["name"] == "裙子")
    assert part["rounds"][-1]["stitches"] == DEFAULT.stitches_for_diameter(4.0)
    assert part["rounds"][-1]["stitches"] < part["rounds"][0]["stitches"]
    assert validate_pattern(updated["params"])["ok"]
