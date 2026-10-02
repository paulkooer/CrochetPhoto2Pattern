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
