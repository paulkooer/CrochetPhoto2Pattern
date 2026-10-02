"""Malformed JSON must produce diagnostics without inventing valid stitch counts."""
import pytest

from app.models.validator import validate_pattern


@pytest.mark.parametrize("field,value", [
    ("stitches", 6.9), ("stitches", True), ("stitches", float("inf")),
    ("stitches", float("nan")), ("increase", 0.5), ("decrease", -6),
    ("increase", -6), ("increase", []), ("decrease", False),
])
def test_invalid_counts_are_not_coerced_to_valid_rounds(field, value):
    rd = {"stitches": 6, "increase": 0, "decrease": 0, field: value}
    result = validate_pattern({"parts": [{"name": "probe", "rounds": [rd]}]})
    assert not result["ok"]
    assert any("probe 第 1 圈" in issue for issue in result["issues"])


@pytest.mark.parametrize("params", [
    {}, {"parts": []}, {"parts": None}, {"parts": {}},
    {"parts": [None]}, {"parts": [{"rounds": None}]},
    {"parts": [{"rounds": "bad"}]}, {"parts": [{"rounds": [None]}]},
])
def test_malformed_pattern_shape_returns_failure(params):
    result = validate_pattern(params)
    assert not result["ok"]
    assert result["issues"]


def test_invalid_round_breaks_adjacency_without_hiding_later_checks():
    result = validate_pattern({"parts": [{"name": "probe", "rounds": [
        {"stitches": 6}, {"stitches": "bad"},
        {"stitches": 12}, {"stitches": 18},
    ]}]})
    assert len(result["issues"]) == 2
    assert any("第 2 圈" in issue for issue in result["issues"])
    assert any("第 4 圈" in issue for issue in result["issues"])


def test_integral_legacy_counts_still_work():
    assert validate_pattern({"parts": [{"rounds": [
        {"stitches": "6"}, {"stitches": 12.0, "increase": "6"},
    ]}]})["ok"]


def test_oversized_stitch_count_is_reported_without_cascading():
    result = validate_pattern({"parts": [{"name": "probe", "rounds": [
        {"stitches": 6}, {"stitches": 10**9}, {"stitches": 12},
    ]}]})
    assert not result["ok"]
    assert len(result["issues"]) == 1
    assert "上限" in result["issues"][0]
