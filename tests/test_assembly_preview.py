"""装配预览（app/ui/preview3d.assembly_payload / assembly_preview_html）单测。

要点：预览不看结构层的粗形状（耳朵在那里可能只记成球），而是把每个部件
的**真实圈数**做成旋转体，再用 app.utils.parade_assembly 的同一套布局摆成
成品——所以它与 `--assemble` 导出的 CrochetPARADE 装配块同源。
"""
import math

import pytest
from PIL import Image

from app.models.gauge import gauge_from_result
from app.models.orchestrator import PipelineOrchestrator
from app.ui.preview3d import assembly_payload, assembly_preview_html, build_payload
from app.utils.parade_assembly import layout_positions

_STITCH_W = 10.0 / 13.0   # classic 10cm/13针
_ROW_H = 10.0 / 16.0      # 10cm/16行


def _rounds(counts):
    rounds, prev = [], counts[0]
    for i, n in enumerate(counts):
        rd = {"row": i + 1, "stitches": n}
        if i:
            diff = n - prev
            if diff > 0:
                rd["increase"] = diff
            elif diff < 0:
                rd["decrease"] = -diff
        rounds.append(rd)
        prev = n
    return rounds


def _sphere(peak: int, rows: int):
    up = list(range(6, peak + 1, 6))
    down = list(reversed(up))[1:]
    counts = up + [peak] * max(1, rows - len(up) - len(down)) + down
    return _rounds(counts)


def _tube(stitches: int, rows: int):
    return _rounds([6, 6] + [stitches] * rows)


def _result() -> dict:
    return {
        "params": {
            "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
            "parts": [
                {"name": "头部", "quantity": 1, "color": "skin",
                 "rounds": _sphere(36, 18)},
                {"name": "身体", "quantity": 1, "color": "body",
                 "rounds": _sphere(42, 17)},
                {"name": "手臂", "quantity": 2, "color": "skin",
                 "rounds": _tube(12, 10)},
                {"name": "腿部", "quantity": 2, "color": "skin",
                 "rounds": _tube(12, 11)},
                {"name": "耳朵", "quantity": 2, "color": "skin",
                 "rounds": _tube(12, 15)},
            ],
        },
        "analysis": {"height_cm": 18.0},
    }


def test_payload_is_none_without_rounds():
    assert assembly_payload({}) is None
    assert assembly_payload({"params": {"parts": []}}) is None
    assert assembly_payload(
        {"params": {"parts": [{"name": "头部", "rounds": []}]}}) is None
    assert assembly_preview_html({}) is None


def test_every_part_becomes_a_lathe_from_its_real_rounds():
    payload = assembly_payload(_result())
    assert payload is not None
    items = {item["name"]: item for item in payload["items"]}
    assert set(items) == {"头部", "身体", "手臂", "腿部", "耳朵"}
    assert all(item["shape"] == "lathe" for item in payload["items"])
    # 长耳：15 圈 12 针的管，而不是结构层记的"球"
    assert len(items["耳朵"]["lathe"]["radii"]) == 17
    assert items["耳朵"]["lathe"]["row_h"] == pytest.approx(_ROW_H)
    # r = N_max·针宽/2π（厘米）
    for name, peak in (("头部", 36), ("身体", 42)):
        assert max(items[name]["lathe"]["radii"]) == pytest.approx(
            peak * _STITCH_W / (2 * math.pi))


def test_positions_are_anatomically_stacked_and_mirrored():
    payload = assembly_payload(_result())
    y = {item["name"]: item["instances"][0]["p"][1]
         for item in payload["items"]}
    xs = {item["name"]: [inst["p"][0] for inst in item["instances"]]
          for item in payload["items"]}
    assert y["身体"] == pytest.approx(0.0)
    assert y["耳朵"] > y["头部"] > y["身体"] > y["腿部"]
    assert y["手臂"] > y["腿部"]                      # 手在腿上方
    assert xs["头部"] == [0.0] and xs["身体"] == [0.0]
    assert xs["手臂"][0] < 0 < xs["手臂"][1]          # 左右镜像，第 1 份在左
    assert xs["手臂"] == pytest.approx([-abs(xs["手臂"][0]), abs(xs["手臂"][0])])
    assert xs["腿部"][0] < 0 < xs["腿部"][1]
    assert xs["耳朵"][0] < 0 < xs["耳朵"][1]


def test_positions_have_no_rotation_baked_in():
    # 与 --assemble 一致：只给平移，朝向留给 CP 手工摆正
    payload = assembly_payload(_result())
    assert all(inst["r"] == [0.0, 0.0, 0.0]
               for item in payload["items"] for inst in item["instances"])


def test_payload_is_deterministic():
    assert assembly_payload(_result()) == assembly_payload(_result())


def test_preview_renders_static_svg():
    html = assembly_preview_html(_result())
    assert html
    assert html.startswith("<svg")
    assert "<polygon" in html


def test_preview_shares_one_layout_with_the_parade_export():
    """预览用厘米、CP 用"针"：x 方向应恰好差一个针宽系数（同一套布局）。"""
    result = _result()
    payload = assembly_payload(result)
    stitch_positions = layout_positions(result["params"]["parts"])

    cm_arm = next(i for i in payload["items"] if i["name"] == "手臂")
    stitch_arm = stitch_positions[2]           # 头部/身体之后的第 1 只手
    assert cm_arm["instances"][0]["p"][0] == pytest.approx(
        stitch_arm[0] * _STITCH_W)
    assert cm_arm["instances"][0]["p"][0] < 0


def test_old_structure_preview_still_available():
    """旧的粗形状预览保留（可回退对比），两者互不干扰。"""
    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 80)), local_vision=True)
    assert build_payload(result) is not None
    assert assembly_payload(result) is not None


def test_full_pipeline_preview_uses_pattern_gauge():
    result = PipelineOrchestrator().run_full_pipeline(
        Image.new("RGB", (40, 80)), local_vision=True)
    payload = assembly_payload(result)
    assert payload is not None
    assert len(payload["items"]) == len(result["params"]["parts"])
    row_h = gauge_from_result(result).row_h_cm
    for item in payload["items"]:
        assert item["lathe"]["row_h"] == pytest.approx(row_h)
        assert item["instances"]
