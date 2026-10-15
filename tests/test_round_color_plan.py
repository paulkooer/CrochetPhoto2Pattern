"""Resolution-aware yarn allocation, with an independent integer-pixel oracle."""
import numpy as np
import pytest

from app.models.color_design import round_color, round_color_plan
from app.models.crochet_params import CrochetParamsGenerator
from app.models.validator import validate_pattern
from app.schemas import CrochetPart, CrochetStitch, ImageAnalysis
from app.utils.exporters import export_markdown


def test_midpoint_sliver_is_not_magnified_and_loss_is_reported():
    blocks = [(0, 0.049, "白色"), (0.049, 0.051, "黑色"), (0.051, 1, "白色")]
    assert round_color(0.05, blocks) == "黑色"
    colors, omitted = round_color_plan(blocks, (0, 1), 10)
    assert colors == ["白色"] * 10
    assert omitted == 1


def test_multiple_colors_choose_coverage_not_midpoint():
    blocks = [(0, 0.3, "白色"), (0.3, 0.55, "黑色"), (0.55, 1, "红色")]
    assert round_color(0.5, blocks) == "黑色"
    assert round_color_plan(blocks, (0, 1), 1) == (["红色"], 2)


def test_resolvable_stripe_and_bottom_up_plan_are_preserved():
    blocks = [(0.2, 0.35, "白色"), (0.35, 0.4, "黑色"), (0.4, 0.7, "红色")]
    top, loss = round_color_plan(blocks, (0.2, 0.7), 10)
    bottom, reverse_loss = round_color_plan(blocks, (0.2, 0.7), 10, bottom_up=True)
    assert top == ["白色"] * 3 + ["黑色"] + ["红色"] * 6
    assert bottom == top[::-1] and loss == reverse_loss == 0


def test_repeated_color_does_not_hide_loss_of_a_separate_stripe():
    blocks = [(0, 0.2, "黑色"), (0.2, 0.449, "白色"),
              (0.449, 0.451, "黑色"), (0.451, 1, "白色")]
    colors, omitted = round_color_plan(blocks, (0, 1), 10)
    assert "黑色" in colors and omitted == 1


def test_gaps_are_not_filled_from_last_color():
    assert round_color_plan([(0.2, 0.4, "蓝色")], (0, 1), 5) == (
        [None, "蓝色", None, None, None], 0)
    assert round_color_plan([], (0, 1), 2) == ([None, None], 0)


def test_tied_coverage_retains_midpoint_then_image_order():
    assert round_color_plan([(0, 0.5, "白色"), (0.5, 1, "黑色")], (0, 1), 1)[0] == ["黑色"]
    blocks = [(0, 0.45, "白色"), (0.45, 0.55, "蓝色"), (0.55, 1, "黑色")]
    assert round_color_plan(blocks, (0, 1), 1)[0] == ["白色"]


@pytest.mark.parametrize("n", [1, 2, 3, 4, 6, 10, 12])
def test_plan_minimizes_pixel_mismatch_against_independent_oracle(n):
    rng = np.random.default_rng(825)
    for _ in range(40):
        boundaries = [0, *sorted(rng.choice(np.arange(1, 120), size=12, replace=False)), 120]
        labels = rng.choice(["白色", "黑色", "红色"], size=len(boundaries) - 1)
        blocks = [(a / 120, b / 120, str(c))
                  for a, b, c in zip(boundaries, boundaries[1:], labels, strict=False)]
        pixels = np.empty(120, dtype="<U2")
        for a, b, c in zip(boundaries, boundaries[1:], labels, strict=False):
            pixels[a:b] = c
        colors, _lost = round_color_plan(blocks, (0, 1), n)
        for j, chosen in enumerate(colors):
            cell = pixels[j * 120 // n:(j + 1) * 120 // n]
            _, counts = np.unique(cell, return_counts=True)
            assert np.count_nonzero(cell == chosen) == counts.max()
        assert round_color_plan(blocks, (0, 1), n, bottom_up=True)[0] == colors[::-1]


def test_generated_pattern_exports_loss_without_changing_stitch_algebra():
    analysis = ImageAnalysis(body_type="标准", head_diameter_cm=9, height_cm=18,
                             main_features=[], pose="站立", difficulty="easy", parts=["头部"])
    structure = {"parts": [{"name": "头部", "shape": "sphere", "diameter_cm": 9}]}
    baseline = CrochetParamsGenerator.generate_params(analysis, structure)
    n = len(baseline["parts"][0]["rounds"])
    center, half_width = 0.05 + 0.25 * 3.5 / n, 0.25 * 0.01 / n
    bands = [{"start": 0, "end": center - half_width, "color": "白色"},
             {"start": center - half_width, "end": center + half_width, "color": "黑色"},
             {"start": center + half_width, "end": 1, "color": "白色"}]
    result = CrochetParamsGenerator.generate_params(analysis, structure, color_bands=bands)
    head = result["parts"][0]
    assert {r["color"] for r in head["rounds"]} == {"白色"}
    assert "1个照片色段未分配" in head["notes"]
    assert "配色分辨率" in export_markdown(result)
    for before, after in zip(baseline["parts"][0]["rounds"], head["rounds"], strict=True):
        for key in ("stitches", "increase", "decrease"):
            assert after[key] == before[key]
    assert validate_pattern(result)["ok"]


def test_bottom_up_notes_and_main_color_ties_follow_work_order():
    part = CrochetPart(name="身体", type="cylinder", color="body",
                       rounds=[CrochetStitch(row=i, stitches=6) for i in range(1, 5)])
    bands = [{"start": 0, "end": 0.5, "color": "白色"},
             {"start": 0.5, "end": 1, "color": "黑色"}]
    CrochetParamsGenerator._apply_color_plan(part, bands, spans={"身体": (0, 1)})
    assert [r.color for r in part.rounds] == ["黑色", "黑色", "白色", "白色"]
    assert part.color == "黑色"
    assert "按钩织圈序，自下而上" in part.notes
    assert "螺旋圈仍可能出现台阶" in part.rounds[2].notes
    assert "避免螺旋台阶" not in part.rounds[2].notes


@pytest.mark.parametrize("span,n", [((0, 1), 0), ((1, 0), 2), ((0, float("nan")), 2)])
def test_invalid_round_plan_is_rejected(span, n):
    with pytest.raises(ValueError):
        round_color_plan([], span, n)
