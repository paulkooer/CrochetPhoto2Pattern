"""Round-7 review: revived silhouette check and crash-proof provenance text."""
from app.ui import result_renderer as rr


def _result(part_type="profile", stitches=(6, 12, 12)):
    return {
        "params": {
            "gauge": {"stitches_per_10cm": 13.0, "rows_per_10cm": 16.0},
            "parts": [{"name": "身体", "type": part_type,
                       "rounds": [{"stitches": s} for s in stitches]}],
        },
        "geometry": {"silhouette": {"profile": [0.5, 1.0, 0.5],
                                    "confidence": 0.9}},
        "spans": {"身体": (0.1, 0.9)},
    }


def test_silhouette_verification_renders_profile_parts():
    pairs = rr._silhouette_verifications(_result())
    assert len(pairs) == 1
    name, svg = pairs[0]
    assert name == "身体"
    assert svg.startswith("<svg")
    assert "polygon" in svg


def test_silhouette_verification_ignores_other_part_types():
    assert rr._silhouette_verifications(_result(part_type="cylinder")) == []
    assert rr._silhouette_verifications({}) == []
    # 病态圈行不产生崩溃（由渲染层 try/except 兜底转为提示）
    assert isinstance(rr._silhouette_verifications(
        _result(stitches=())), list)


def test_silhouette_verification_skips_non_dict_rounds():
    result = _result()
    result["params"]["parts"][0]["rounds"] = [None, {"stitches": 12}]
    pairs = rr._silhouette_verifications(result)
    assert len(pairs) == 1


def test_crafted_confidence_and_ratio_cannot_crash_rendering():
    # geometry/sizing 是备份可控的自由字段；展示层必须容错
    assert rr._confidence_text({"confidence": None}) == "启发式估算（未经校准）"
    assert rr._confidence_text({"confidence": "abc"}) == "启发式估算（未经校准）"
    assert rr._confidence_text({"confidence": 0.86}) == "启发式估算（未经校准）"
    assert rr._ratio_text({"photo_head_to_height_ratio": None}) == "None"
    assert rr._ratio_text({"photo_head_to_height_ratio": "junk"}) == "junk"
    assert rr._ratio_text({"photo_head_to_height_ratio": 0.42857}) == "0.429"
