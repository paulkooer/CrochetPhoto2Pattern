"""Preview orientation follows all three editable Euler rotation components."""
from copy import deepcopy

import pytest

from app.ui.preview3d import _render_static_svg, _rot_instance


@pytest.mark.parametrize("vertex,rz,rx,ry,expected", [
    ((1, 0, 0), 0, 0, 90, (0, 0, -1)),
    ((0, 0, 1), 0, 0, 90, (1, 0, 0)),
    ((0, 1, 0), 0, 90, 90, (1, 0, 0)),
    ((1, 0, 0), 90, 90, 90, (1, 0, 0)),
])
def test_rotation_applies_z_then_x_then_y(vertex, rz, rx, ry, expected):
    assert _rot_instance(vertex, rz, rx, ry) == pytest.approx(expected, abs=1e-12)


def test_rendered_tilted_limb_changes_when_y_rotation_changes():
    payload = {"height": 18, "items": [{"shape": "cylinder", "color": "#ff0000",
                "dims": {"r": 1, "h": 6}, "instances": [{"p": [0, 0, 0], "r": [45, 0, 0]}]}]}
    turned = deepcopy(payload)
    turned["items"][0]["instances"][0]["r"][1] = 90
    before, after = _render_static_svg(payload), _render_static_svg(turned)
    assert "<polygon" in before and "<polygon" in after
    assert before != after


def test_old_two_axis_rotation_call_keeps_its_orientation():
    assert _rot_instance((0, 1, 0), 0, 90) == pytest.approx((0, 0, 1), abs=1e-12)


def _arms(colors, ids, rounds=None):
    from app.ui.preview3d import build_payload

    return build_payload({
        "analysis": {"height_cm": 18},
        "structure": {"schema_version": "2.0", "parts": [{
            "name": "手臂", "shape": "sphere", "diameter_cm": 4,
            "instances": [
                {"instance_id": "arm-r", "position": {"x": 1, "y": 0.4, "z": 0},
                 "rotation_deg": {}},
                {"instance_id": "arm-l", "position": {"x": -1, "y": 0.4, "z": 0},
                 "rotation_deg": {}},
            ],
        }]},
        "params": {"parts": [{
            "name": "手臂", "color": "黄色",
            "instance_colors": colors, "instance_color_ids": ids,
            "rounds": rounds or [{"row": 1, "stitches": 6, "color": "黄色"}],
        }]},
    })


def test_copy_colours_follow_ids_and_blank_slots_keep_the_part_colour():
    payload = _arms(["红色", None], ["arm-l", "arm-r"])
    arms = next(item for item in payload["items"] if item["name"] == "手臂")
    by_x = {round(inst["p"][0]): inst["color"] for inst in arms["instances"]}
    assert by_x[18] == "#ffff00"   # arm-r has no override; part colour is yellow
    assert by_x[-18] == "#ff0000"  # arm-l is red even though red is listed first
    assert arms["color"] == "#ffff00"


def test_ordinal_colours_follow_instance_order_without_ids():
    payload = _arms(["红色", "蓝色"], None)
    colors = [inst["color"] for inst in payload["items"][0]["instances"]]
    assert colors == ["#ff0000", "#0078d7"]


def test_unknown_copy_colour_does_not_keep_the_part_colour():
    from app.models.colors import UNRESOLVED_DISPLAY_HEX

    payload = _arms(["不是色表里的名字"], ["arm-r"])
    arms = payload["items"][0]
    assert arms["instances"][0]["color"] == UNRESOLVED_DISPLAY_HEX
    assert arms["instances"][0]["color"] != "#ffff00"
    assert arms["instances"][1]["color"] == "#ffff00"


def test_reordered_ids_do_not_paint_the_other_copy():
    payload = _arms(["红色", "蓝色"], ["arm-l", "arm-r"])
    arms = payload["items"][0]
    by_x = {round(inst["p"][0]): inst["color"] for inst in arms["instances"]}
    assert by_x[18] == "#0078d7"
    assert by_x[-18] == "#ff0000"


def test_round_stripes_do_not_change_the_copy_colour():
    payload = _arms(
        None, None,
        [{"row": 1, "stitches": 6, "color": "红色"},
         {"row": 2, "stitches": 6, "color": "蓝色"}])
    arms = payload["items"][0]
    assert {inst["color"] for inst in arms["instances"]} == {"#ffff00"}


def test_svg_uses_each_copy_colour():
    import re

    payload = _arms(["红色", "蓝色"], ["arm-r", "arm-l"])
    svg = _render_static_svg(payload)
    fills = [(int(r), int(g), int(b))
             for r, g, b in re.findall(r'fill="rgb\((\d+),(\d+),(\d+)\)"', svg)]
    assert any(g == 0 and b == 0 and r > 0 for r, g, b in fills)
    assert any(b > r and b > 0 for r, g, b in fills)
