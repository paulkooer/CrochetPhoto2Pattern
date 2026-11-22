"""Dressed-doll fixes from the 2026-11 audit: skirt flare, body height, cap placement, UI scaling."""
import collections
import math
import re

import pytest
from streamlit.testing.v1 import AppTest

from app.models.dressed_doll import build_doll_plan, starter_design
from app.models.dressed_doll.recipes import expression_for_change, oval_boot, staggered_increase
from app.models.gauge import Gauge


def _expand(expression: str) -> list[str]:
    """Flatten e.g. '(2X,V)×6,3X' into single operations, independently of the generator."""
    text, out, position = expression.replace(" ", ""), [], 0
    while position < len(text):
        if text[position] == ",":
            position += 1
        elif text[position] == "(":
            end = text.index(")", position)
            inner = _expand(text[position + 1:end])
            match = re.match(r"×(\d+)", text[end + 1:])
            out.extend(inner * (int(match.group(1)) if match else 1))
            position = end + 1 + (len(match.group(0)) if match else 0)
        else:
            match = re.match(r"(\d+)X|([VA])(?:×(\d+))?", text[position:])
            assert match, (expression, position)
            out.extend(["X"] * int(match.group(1)) if match.group(1)
                       else [match.group(2)] * int(match.group(3) or 1))
            position += len(match.group(0))
    return out


def _foundation_columns(component) -> tuple[list[int], int]:
    """For each stitch of the last round, the foundation stitch it descends from."""
    current = list(range(component.steps[0].stitches))
    for step in component.steps[1:]:
        following, cursor = [], 0
        for op in _expand(step.expression):
            following.extend([current[cursor]] * (2 if op == "V" else 1))
            cursor += 2 if op == "A" else 1
        assert cursor == len(current) and len(following) == step.stitches
        current = following
    return current, component.steps[0].stitches


@pytest.mark.parametrize("starter", ["wide_brim_curls", "folded_cap_layers"])
@pytest.mark.parametrize("height", [16, 24, 48])
def test_skirt_increases_are_spread_round_the_piece(starter, height):
    plan = build_doll_plan(starter_design(starter, height_cm=height))
    for part in (p for p in plan.components if p.id.startswith("skirt_")):
        columns, foundation = _foundation_columns(part)
        increases = part.steps[-1].stitches - foundation
        share = collections.Counter(columns)
        widened = sum(1 for count in share.values() if count > 1)
        assert widened >= min(foundation, increases) * 0.6, (part.id, widened, increases)
        # No single waist stitch carries more than a small part of the flare.
        assert max(share.values()) - 1 <= max(2, increases // 4), (part.id, share.most_common(2))


@pytest.mark.parametrize(("before", "after"), [(28, 29), (28, 31), (30, 45), (12, 24), (40, 41)])
@pytest.mark.parametrize("turn", range(1, 9))
def test_staggered_increase_uses_every_stitch_once(before, after, turn):
    ops = _expand(staggered_increase(before, after, turn))
    assert "A" not in ops and len(ops) == before          # one operation per stitch of the round below
    assert sum(2 if op == "V" else 1 for op in ops) == after
    assert ops.count("V") == after - before


def test_single_increase_position_moves_between_rounds():
    places = {_expand(staggered_increase(28, 29, turn)).index("V") for turn in range(1, 9)}
    assert len(places) >= 5


def test_shaped_parts_keep_their_targeted_decreases():
    assert expression_for_change(28, 29) == "27X,V"
    boot = oval_boot(3, 1.6, 7, Gauge(22, 28))
    toe = [s.expression for s in boot.steps if s.section == "鞋头收窄"]
    assert toe and all(expression.count("A") >= 1 for expression in toe)
    assert not any(step.section == "裙身展开" for step in boot.steps)


def _body_estimates(body, gauge) -> tuple[float, float]:
    """Recomputed here, independently of the planner: (every round a full row, axial part only)."""
    counts = [step.stitches for step in body.steps]
    low = sum(math.sqrt(max(0.0, gauge.row_h_cm ** 2 - ((b - a) * gauge.stitch_w_cm / (2 * math.pi)) ** 2))
              for a, b in zip(counts, counts[1:], strict=False))
    return len(counts) * gauge.row_h_cm, low


@pytest.mark.parametrize("starter", ["wide_brim_curls", "folded_cap_layers"])
@pytest.mark.parametrize("height", [16, 24, 40, 60])
@pytest.mark.parametrize("gauge", [Gauge(22, 28), Gauge(30, 36), Gauge(14, 16)])
def test_body_rounds_follow_the_allocated_height(starter, height, gauge):
    design = starter_design(starter, height_cm=height, gauge=gauge)
    body = next(p for p in build_doll_plan(design).components if p.id == "body")
    target = design.height_cm - design.head_diameter_cm - design.leg_length_cm
    high, low = _body_estimates(body, gauge)
    middle = (high + low) / 2
    # The target lies between the two estimates, at their midpoint to within half a round.
    assert middle >= target - gauge.row_h_cm / 2 - 1e-9
    plain = {section: sum(1 for a, b in zip(body.steps, body.steps[1:], strict=False)
                          if b.section == section and a.stitches == b.stitches)
             for section in ("下身", "胸肩")}
    if middle > target + gauge.row_h_cm / 2 + 1e-9:
        # Only when no plain round is left to remove: both sections are at their floor of two.
        assert plain == {"下身": 2, "胸肩": 2}
    else:
        assert low <= target <= high
    note = next(text for text in body.fitting if "目标高度" in text)
    assert f"{target:.1f} cm" in note and f"共 {len(body.steps)} 圈" in note
    assert f"约 {high:.1f} cm" in note and f"约 {low:.1f} cm" in note and "不是实测" in note


def test_body_shortfall_no_longer_grows_with_the_doll():
    """At 6c88b7d the same share was 95% at 24 cm and 82% at 60 cm (by rounds), 68% and 57% (axial)."""
    gauge = Gauge(22, 28)
    shares = []
    for height in (24, 40, 60):
        design = starter_design("wide_brim_curls", height_cm=height, gauge=gauge)
        body = next(p for p in build_doll_plan(design).components if p.id == "body")
        target = design.height_cm - design.head_diameter_cm - design.leg_length_cm
        high, low = _body_estimates(body, gauge)
        shares.append(((high + low) / 2) / target)
    assert all(abs(share - 1) < 0.02 for share in shares), shares


@pytest.mark.parametrize("height", [16, 24, 40, 60])
def test_cap_placement_text_follows_the_generated_rounds(height):
    plan = build_doll_plan(starter_design("wide_brim_curls", height_cm=height))
    parts = {p.id: p for p in plan.components}
    eye = int(re.search(r"第 (\d+) 圈为眼位候选", parts["head"].finish).group(1))
    cap_rounds = len(parts["hair_cap"].steps)
    text = next(j.placement for j in plan.joins if j.source == "hair_cap")
    assert f"发帽共 {cap_rounds} 圈" in text and f"头部第 {eye} 圈" in text
    if cap_rounds >= eye:
        assert "向后倾斜" in text and "发帽边缘放在眼位上方" not in text
    assert "珠针" in text


UI = """
from app.ui.dressed_doll import render_dressed_doll_designer
render_dressed_doll_designer()
"""


def _sizes(at) -> dict[str, float]:
    return {node.key.removeprefix("doll_design_").removesuffix("_wide_brim_curls"): node.value
            for node in at.number_input if node.key.endswith("_wide_brim_curls")}


def test_changing_the_height_rescales_the_proportional_inputs():
    at = AppTest.from_string(UI, default_timeout=60).run()
    at.number_input(key="doll_design_height").set_value(48.0).run()
    assert not at.exception
    expected = starter_design("wide_brim_curls", height_cm=48.0)
    sizes = _sizes(at)
    assert sizes["head"] == pytest.approx(expected.head_diameter_cm) == pytest.approx(12.0)
    assert sizes["palm"] == pytest.approx(expected.palm_diameter_cm)
    assert sizes["wrist"] == pytest.approx(expected.wrist_diameter_cm)
    assert sizes["foot_length"] == pytest.approx(expected.foot_length_cm)
    assert sizes["foot_width"] == pytest.approx(expected.foot_width_cm)
    assert sizes["bodice"] == pytest.approx(expected.bodice_length_cm)
    at.button(key="doll_design_generate").click().run()
    assert not at.exception
    # The page and the command line now give the same design for the same height.
    assert at.session_state["doll_design_plan"]["design"] == expected.model_dump()
    assert not any("已手改" in caption.value for caption in at.caption)


def test_a_hand_edited_size_is_kept_and_named_until_reset():
    at = AppTest.from_string(UI, default_timeout=60).run()
    at.number_input(key="doll_design_head_wide_brim_curls").set_value(7.0).run()
    at.number_input(key="doll_design_height").set_value(48.0).run()
    assert not at.exception
    sizes = _sizes(at)
    assert sizes["head"] == 7.0                       # typed by the user: stays
    assert sizes["palm"] == pytest.approx(3.0)        # untouched: follows the height
    note = next(caption.value for caption in at.caption if "已手改" in caption.value)
    assert "原型头径" in note and "手掌直径" not in note
    at.button(key="doll_design_generate").click().run()
    design = at.session_state["doll_design_plan"]["design"]
    assert design["head_diameter_cm"] == 7.0 and design["height_cm"] == 48.0
    at.button(key="doll_design_reset_wide_brim_curls").click().run()
    assert not at.exception
    assert _sizes(at)["head"] == pytest.approx(12.0)
    assert not any("已手改" in caption.value for caption in at.caption)
    # A later height change moves it again.
    at.number_input(key="doll_design_height").set_value(24.0).run()
    assert _sizes(at)["head"] == pytest.approx(6.0)


def test_reset_right_after_a_height_change_uses_the_new_height():
    """Found in a real browser: the button once restored the proportions of the previous height."""
    at = AppTest.from_string(UI, default_timeout=60).run()
    at.number_input(key="doll_design_height").set_value(31.0).run()
    at.number_input(key="doll_design_head_wide_brim_curls").set_value(7.0).run()
    at.number_input(key="doll_design_height").set_value(36.0).run()
    at.button(key="doll_design_reset_wide_brim_curls").click().run()
    assert not at.exception
    expected = starter_design("wide_brim_curls", height_cm=36.0)
    sizes = _sizes(at)
    assert sizes["head"] == pytest.approx(expected.head_diameter_cm) == pytest.approx(9.0)
    assert sizes["palm"] == pytest.approx(expected.palm_diameter_cm)
    assert sizes["bodice"] == pytest.approx(expected.bodice_length_cm)
    assert not any("已手改" in caption.value for caption in at.caption)
    at.number_input(key="doll_design_height").set_value(24.0).run()
    assert _sizes(at)["head"] == pytest.approx(6.0) and _sizes(at)["palm"] == pytest.approx(1.5)


def test_gauge_change_keeps_sizes_and_the_other_starter_is_independent():
    at = AppTest.from_string(UI, default_timeout=60).run()
    at.number_input(key="doll_design_head_wide_brim_curls").set_value(7.0).run()
    at.number_input(key="doll_design_stitches").set_value(26.0).run()
    assert _sizes(at)["head"] == 7.0 and _sizes(at)["palm"] == pytest.approx(1.5)
    at.selectbox(key="doll_design_starter").select("folded_cap_layers").run()
    assert not at.exception
    other = {node.key: node.value for node in at.number_input}
    assert other["doll_design_head_folded_cap_layers"] == pytest.approx(6.0)
    at.selectbox(key="doll_design_starter").select("wide_brim_curls").run()
    assert not at.exception
