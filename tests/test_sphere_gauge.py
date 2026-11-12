"""Classic sphere dimensions use both stitch width and row height."""
from math import pi

import pytest

from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import PRESETS, Gauge, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.models.validator import validate_pattern
from app.schemas import ImageAnalysis


def _head(gauge: Gauge, *, opening: int | None = None):
    analysis = ImageAnalysis(
        body_type="未评估", head_diameter_cm=8.3, height_cm=18,
        main_features=[], pose="站立", difficulty="easy", parts=["头部"],
    )
    structure = {"parts": [{"name": "头部", "shape": "sphere", "diameter_cm": 8.3}]}
    params = CrochetParamsGenerator.generate_params(
        analysis, structure, gauge=gauge, head_opening_stitches=opening)
    return params, params["parts"][0]


@pytest.mark.parametrize("name", ["classic", "dk", "fine"])
def test_classic_sphere_uses_gauge_to_match_model_meridian(name):
    gauge = PRESETS[name]
    params, head = _head(gauge)
    rows = head["rounds"]
    peak = max(row["stitches"] for row in rows)
    # The peak is quantized in stitches, so compare with its equivalent diameter.
    equivalent_diameter = peak * gauge.stitch_w_cm / pi
    ideal_arc = pi * equivalent_diameter / 2
    assert abs(len(rows) * gauge.row_h_cm - ideal_arc) <= gauge.row_h_cm / 2 + 1e-9
    assert rows[0]["stitches"] == rows[-1]["stitches"] == 6
    assert [row["stitches"] for row in rows[:4]] == [6, 12, 18, 24]
    # A long flat belt can match total arc length while producing a barrel.
    quarter_width = rows[len(rows) // 4 - 1]["stitches"] / peak
    assert 0.5 <= quarter_width <= 0.85
    assert all(abs(b["stitches"] - a["stitches"]) <= 6 for a, b in zip(rows, rows[1:], strict=False))
    assert validate_pattern(params)["ok"]


def test_classic_sphere_reports_when_six_stitch_steps_cannot_match_target():
    gauge = Gauge(40, 8)
    params, head = _head(gauge)
    rows = head["rounds"]
    peak = max(row["stitches"] for row in rows)
    assert len(rows) == 2 * (peak // 6) - 1
    assert len(rows) * gauge.row_h_cm > peak * gauge.stitch_w_cm / 2
    assert "无法匹配" in head["notes"]
    assert validate_pattern(params)["ok"]


def test_gauge_corrected_head_keeps_explicit_opening():
    params, head = _head(PRESETS["dk"], opening=16)
    assert head["connection_state"] == "open"
    assert head["opening_row"] == head["rounds"][-1]["row"]
    assert head["rounds"][-1]["stitches"] == 16
    assert validate_pattern(params)["ok"]


@pytest.mark.parametrize("gauge", [Gauge(6, 8), Gauge(6, 50), Gauge(40, 8), Gauge(40, 50)])
def test_classic_sphere_density_boundaries_still_generate_valid_rounds(gauge):
    params, head = _head(gauge)
    assert head["rounds"][0]["stitches"] == 6
    assert head["rounds"][-1]["stitches"] == 6
    assert validate_pattern(params)["ok"]


def test_unreachable_gauge_warning_survives_one_piece_conversion():
    analysis = ImageAnalysis(
        body_type="未评估", head_diameter_cm=8.3, height_cm=18,
        main_features=[], pose="站立", difficulty="easy", parts=["头部", "身体"],
    )
    params = CrochetParamsGenerator.generate_params(
        analysis, StructureDesigner.design_3d_structure(analysis),
        gauge=Gauge(40, 8), style=ShapingStyle(one_piece=True))
    one_piece = next(part for part in params["parts"] if part["type"] == "onepiece")
    assert "无法匹配" in one_piece["notes"]
    assert validate_pattern(params)["ok"]
