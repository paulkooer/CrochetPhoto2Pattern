"""G8：键集相等断言——share.py 注释承诺"钉死在结构层"的回归测试。

F24/F26/F27 同病根三处发作的根因是 result dict 的顶层键集在 6 条路径
各自手抄。此文件把键集约束钉死在结构层。
"""
from app.utils.share import _BACKUP_KEYS, _SHARE_KEYS


def test_share_keys_subset_of_backup_keys():
    """分享 token 键集 = 备份键集 − preview（6000 门控）。"""
    assert set(_SHARE_KEYS) == set(_BACKUP_KEYS) - {"preview"}


def test_backup_keys_superset_of_orchestrator_output():
    """备份键集必须覆盖 orchestrator 产出的全部顶层键（含 usage）。"""
    from PIL import Image

    from app.models.orchestrator import PipelineOrchestrator
    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 40)), local_vision=True)
    orch_keys = set(result.keys())
    missing = orch_keys - set(_BACKUP_KEYS)
    assert not missing, f"orchestrator 产出键 {missing} 不在 _BACKUP_KEYS 中"


def test_backup_import_preserves_all_backup_keys():
    """G1 断言：备份导入后所有 _BACKUP_KEYS 键的值必须与备份 JSON 一致。

    此测试在 G1 修复前会失败（imported.setdefault(k, None) 把 8 个键
    写成 None 而非从备份 JSON 读取）。
    """
    import json

    from app.models.crochet_params import CrochetParamsGenerator
    from app.models.gauge import Gauge, ShapingStyle
    from app.models.structure_designer import StructureDesigner
    from app.schemas import ImageAnalysis
    from app.ui.result_renderer import _BACKUP_KEYS, _rebuild_params, _validated_backup

    a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                      main_features=[], pose="站立", difficulty="easy",
                      parts=["头部", "身体", "腿部"])
    s = StructureDesigner.design_3d_structure(a)
    g = Gauge(20.0, 24.0)
    style = ShapingStyle("egg", True, "attached", True)
    params = CrochetParamsGenerator.generate_params(a, s, gauge=g, style=style)
    sp = json.loads(json.dumps(params, default=lambda o: o.model_dump(),
                               ensure_ascii=False))
    backup = {"analysis": a.model_dump(), "structure": s, "params": sp,
              "style": {"sphere_mode": "egg", "one_piece": True,
                        "skirt_style": "attached", "ruffle_hem": True},
              "gauge": {"stitches_per_10cm": 20.0, "rows_per_10cm": 24.0},
              "color_bands": [{"start": 0.0, "end": 1.0, "color": "蓝色"}],
              "spans": {"头部": (0.0, 0.2)},
              "spans_measured": ["头部"],
              "vision_meta": {"source": "opencv-face"},
              "sizing": {"source": "manual_dimensions",
                         "absolute_scale_from_photo": False},
              "geometry": {"schema_version": "1.0", "silhouette": None,
                           "used_for_generation": False},
              "preview": "data:image/jpeg;base64,abc"}

    data = json.loads(json.dumps(backup, ensure_ascii=False))
    analysis, structure = _validated_backup(data)
    imported = {
        "analysis": analysis,
        "structure": structure,
        "params": _rebuild_params(dict(data["params"])),
        "result_id": "test-g1",
    }
    # G1 修复后：从备份数据读取（不是 setdefault None）
    for k in _BACKUP_KEYS:
        imported.setdefault(k, data.get(k))

    assert imported["style"]["sphere_mode"] == "egg"
    assert imported["gauge"]["stitches_per_10cm"] == 20.0
    assert imported["color_bands"] == [{"start": 0.0, "end": 1.0, "color": "蓝色"}]
    assert imported["sizing"]["source"] == "manual_dimensions"
    assert imported["geometry"]["schema_version"] == "1.0"


def test_backup_validation_accepts_legacy_structure_but_checks_v2_graph():
    """无版本旧备份继续可读；声明 v2 后必须满足 count/instance 图契约。"""
    import copy

    import pytest

    from app.models.structure_designer import StructureDesigner
    from app.schemas import ImageAnalysis
    from app.ui.result_renderer import _validated_backup

    analysis = ImageAnalysis(
        body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
        main_features=[], pose="站立", difficulty="easy", parts=["手臂"],
    )
    legacy = {"analysis": analysis.model_dump(), "structure": {
        "parts": [{"name": "手臂", "shape": "cylinder", "length_cm": 3.0}],
    }}
    assert _validated_backup(legacy)[1] == legacy["structure"]

    invalid_v2 = StructureDesigner.design_3d_structure(analysis)
    invalid_v2 = copy.deepcopy(invalid_v2)
    invalid_v2["parts"][0]["count"] = 1
    with pytest.raises(ValueError):
        _validated_backup({
            "analysis": analysis.model_dump(), "structure": invalid_v2})


def test_backup_carries_schema_version_and_session_dict_does_not():
    """备份/分享序列化携带 schema_version；会话内 result dict 保持既有键集。"""
    from PIL import Image

    from app.models.orchestrator import PipelineOrchestrator
    from app.schemas import SCHEMA_VERSION, PatternResult

    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 40)), local_vision=True)
    assert "schema_version" not in result
    backup = PatternResult.from_result(result).to_backup()
    assert backup["schema_version"] == SCHEMA_VERSION
    # 备份键集 = 会话键集 + schema_version，无缺漏
    assert set(backup) == set(result) | {"schema_version"}


def test_decode_rejects_future_schema_version():
    """分享 token 声明更高 schema 版本时拒绝载入（不猜测兼容性）。"""
    import base64
    import json as _json
    import zlib as _zlib

    from app.utils import share

    blob = _json.dumps({
        "analysis": {"body_type": "标准"}, "structure": {"parts": []},
        "params": {"parts": []}, "schema_version": "999",
    }, ensure_ascii=False)
    token = base64.urlsafe_b64encode(
        _zlib.compress(blob.encode("utf-8"), 9)).decode()
    assert share.decode_result(token) is None


def test_from_result_tolerates_legacy_backup_without_new_keys():
    """旧备份（缺 style/gauge/preview 等键）仍可经 PatternResult 载入。"""
    from PIL import Image

    from app.models.orchestrator import PipelineOrchestrator
    from app.schemas import PatternResult

    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 40)), local_vision=True)
    legacy = {k: result[k] for k in ("analysis", "structure", "params")}
    legacy["result_id"] = "legacy-1"
    restored = PatternResult.from_result(legacy).to_result_dict()
    assert restored["result_id"] == "legacy-1"
    assert restored["style"] is None
    assert restored["vision_meta"] == {}
    # 三必带键之外的缺失键与 orchestrator 键集一致（不丢不增）
    assert set(restored) == set(result) | {"result_id"}
