"""Independent parent/child expectations for explicit round-connection windows."""
import json
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given
from hypothesis import strategies as hs
from streamlit.testing.v1 import AppTest

from app.models.stitch_connection_diagram import connection_svg
from app.models.stitch_connections import MAX_CONNECTION_WINDOW, round_connections
from app.models.stitch_notation import StitchExpression
from app.schemas import MAX_ROUND_STITCHES
from app.utils.project import pattern_revision
from tests.test_app_smoke import _mock_result

_IO = {"X": (1, 1), "V": (1, 2), "A": (2, 1), "W": (1, 3), "M": (3, 1)}
_UI = '''
import streamlit as st
from app.ui.stitch_connections import render_stitch_connections
render_stitch_connections(st.session_state.result, "result")
'''


def _part(note="FLO(X,V),BLO(A)", operations="XVA"):
    before = sum(_IO[s][0] for s in operations)
    after = sum(_IO[s][1] for s in operations)
    return {"name": "自制连接练习", "quantity": 2, "rounds": [
        {"row": 7, "stitches": before},
        {"row": 19, "stitches": after,
         "increase": sum(max(0, _IO[s][1] - _IO[s][0]) for s in operations),
         "decrease": sum(max(0, _IO[s][0] - _IO[s][1]) for s in operations), "notes": note},
    ]}


def test_connections_keep_exact_parent_and_child_indices_and_scoped_loops():
    part = _part()
    original = deepcopy(part)
    view = round_connections(part, 1)
    assert [(op.index, op.symbol, op.loop, op.sources, op.targets) for op in view.operations] == [
        (1, "X", "FLO", (1,), (1,)),
        (2, "V", "FLO", (2,), (2, 3)),
        (3, "A", "BLO", (3, 4), (4,)),
    ]
    assert (view.source_row, view.target_row) == (7, 19)
    assert view.source_stitches == view.target_stitches == 4
    assert view.operation_count == 3 and view.to_dict()["complete"]
    assert part == original


def test_triple_increase_and_decrease_are_not_split_into_binary_shaping():
    view = round_connections(_part("W,M", "WM"), 1)
    assert [(op.sources, op.targets) for op in view.operations] == [((1,), (1, 2, 3)), ((2, 3, 4), (4,))]
    assert [op.symbol for op in view.operations] == ["W", "M"]


def test_nested_repeats_keep_offsets_when_a_page_starts_inside_a_group():
    view = round_connections(_part("2((X,V)×3,A)", ("XV" * 3 + "A") * 2), 1, start=5, limit=4)
    assert [(op.index, op.sources, op.targets) for op in view.operations] == [
        (6, (6,), (8, 9)), (7, (7, 8), (10,)), (8, (9,), (11,)), (9, (10,), (12, 13)),
    ]
    payload = json.loads(json.dumps(view.to_dict()))
    assert payload["start"] == 5 and payload["index_base"] == 1
    assert payload["basis"] == "explicit_expression" and not payload["complete"]
    assert len(payload["operations"]) == 4


@given(hs.lists(hs.sampled_from([s + loop for s in "XVAWM" for loop in ("", "-FLO", "-BLO")]),
                min_size=1, max_size=70), hs.integers(0, 100), hs.integers(1, MAX_CONNECTION_WINDOW))
def test_windows_match_an_independent_expanded_stitch_oracle(operations, offset, limit):
    symbols = [op.split("-")[0] for op in operations]
    part = _part(",".join(operations), "".join(symbols))
    expected = []
    source, target = 1, 1
    for index, (symbol, operation) in enumerate(zip(symbols, operations, strict=True), 1):
        consumed, produced = _IO[symbol]
        expected.append((index, symbol, operation.partition("-")[2] or "both",
                         tuple(range(source, source + consumed)), tuple(range(target, target + produced))))
        source += consumed
        target += produced
    start = offset % len(operations)
    view = round_connections(part, 1, start=start, limit=limit)
    actual = [(op.index, op.symbol, op.loop, op.sources, op.targets) for op in view.operations]
    assert actual == expected[start:start + limit]
    assert view.operation_count == len(expected)
    assert view.source_stitches == source - 1 and view.target_stitches == target - 1


def test_large_late_window_does_not_expand_the_entire_expression(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("windowing must skip repeated subtrees, not expand iter_stitches")

    monkeypatch.setattr(StitchExpression, "iter_stitches", forbidden)
    part = {"name": "长圈", "rounds": [{"row": 1, "stitches": 75_000},
                                      {"row": 2, "stitches": MAX_ROUND_STITCHES,
                                       "increase": 25_000, "notes": "(X,V,X)×25000"}]}
    view = round_connections(part, 1, start=74_976)
    assert view.operation_count == 75_000 and len(view.operations) == 24
    assert view.operations[0].sources == (74_977,)
    assert view.operations[0].targets == (99_969,)
    assert view.operations[-1].sources == (75_000,)
    assert view.operations[-1].targets == (100_000,)
    assert len(json.dumps(view.to_dict())) < 10_000


@pytest.mark.parametrize("note", [None, "均匀加减针", "X,V,A,2ch", "4X；4X", "FLO；BLO；X,V,A",
                                  "下一圈可用 BLO；X,V,A", "3X", "inv-sc2tog,2X"])
def test_missing_ambiguous_unsupported_or_inconsistent_formulas_do_not_infer_connections(note):
    with pytest.raises(ValueError):
        round_connections(_part(note), 1)


@pytest.mark.parametrize("field,value", [("stitches", True), ("stitches", 0), ("stitches", 4.5),
                                         ("increase", False), ("decrease", True), ("row", 7)])
def test_invalid_round_fields_are_rejected_without_mutation(field, value):
    part = _part()
    part["rounds"][1][field] = value
    before = deepcopy(part)
    with pytest.raises(ValueError):
        round_connections(part, 1)
    assert part == before


@pytest.mark.parametrize("kwargs", [{"row_index": 0}, {"row_index": -1}, {"row_index": True},
                                    {"row_index": 2}, {"start": -1}, {"start": True},
                                    {"start": 3}, {"limit": 0}, {"limit": 41}, {"limit": True}])
def test_first_round_and_invalid_windows_are_explicitly_rejected(kwargs):
    args = {"row_index": 1, **kwargs}
    with pytest.raises(ValueError):
        round_connections(_part(), **args)


def test_svg_encodes_true_parent_edges_and_escapes_part_names():
    part = _part()
    part["name"] = '<script>alert("x")</script>'
    root = ET.fromstring(connection_svg(round_connections(part, 1)))
    edges = [node.attrib for node in root.iter() if "data-parent" in node.attrib]
    assert {(e["data-parent"], e["data-child"], e["data-loop"]) for e in edges} == {
        ("1", "1", "FLO"), ("2", "2", "FLO"), ("2", "3", "FLO"),
        ("3", "4", "BLO"), ("4", "4", "BLO"),
    }
    assert not any(node.tag.endswith("script") for node in root.iter())
    assert "不是线股路径或实物形状" in " ".join(root.itertext())


def test_inspector_is_opt_in_and_does_not_compute_on_ordinary_reruns(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("closed inspector must not construct a connection window")

    monkeypatch.setattr("app.ui.stitch_connections.round_connections", forbidden)
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = _mock_result("connections-disabled")
    at.run()
    assert not at.exception
    assert len(at.selectbox) == 0


def test_inspector_downloads_match_page_and_preserve_result_and_progress(monkeypatch):
    import streamlit as st

    result = _mock_result("connections-ui")
    result["params"]["parts"] = [_part("(X,V,X)×12", "XVX" * 12)]
    original = deepcopy(result)
    downloads = {}
    real_download = st.download_button

    def capture(label, data, *args, **kwargs):
        downloads[label] = data
        return real_download(label, data, *args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture)
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = result
    at.session_state["chk_connections-ui_头部_0"] = True
    at.session_state["project_notes_connections-ui"] = "保留我的备注"
    at.run()
    prefix = "edit_connections-ui_connections_"
    at.checkbox(key=prefix + "enabled").check().run()
    assert not at.exception
    payload = json.loads(downloads["下载本页连接记录 JSON"])
    assert payload["start"] == 0 and len(payload["operations"]) == 24 and not payload["complete"]
    assert payload["pattern_revision"] == pattern_revision(result)
    at.number_input(key=prefix + "part0_row1_page").set_value(2).run()
    assert not at.exception
    payload = json.loads(downloads["下载本页连接记录 JSON"])
    assert payload["start"] == 24 and len(payload["operations"]) == 12
    assert payload["operations"][0]["sources"] == [25]
    assert downloads["下载本页连接图 SVG"] == connection_svg(round_connections(result["params"]["parts"][0],
                                                                              1, start=24))
    assert at.session_state["result"] == original
    assert at.session_state["chk_connections-ui_头部_0"]
    assert at.session_state["project_notes_connections-ui"] == "保留我的备注"

    at.selectbox(key=prefix + "part0_row").set_value(0).run()
    assert not at.exception
    assert any("首圈" in message.value for message in at.info)
    assert not at.get("download_button")


def test_unsupported_formula_shows_reason_instead_of_a_graph():
    result = _mock_result("connections-unsupported")
    result["params"]["parts"] = [_part(None)]
    at = AppTest.from_string(_UI, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    at.checkbox(key="edit_connections-unsupported_connections_enabled").check().run()
    assert not at.exception
    assert any("不按聚合针数推测针位" in message.value for message in at.info)
    assert not at.get("download_button")


@pytest.mark.parametrize("slot", ["result", "manual_result"])
def test_inspector_resets_cleanly_after_an_inline_edit_and_can_be_reopened(slot):
    at = AppTest.from_string('''
import streamlit as st
from app.ui.result_renderer import render_results
render_results(st.session_state[st.session_state.active_slot], st.session_state.active_slot)
''', default_timeout=30)
    at.session_state["active_slot"] = slot
    at.session_state[slot] = _mock_result("connections-edit")
    at.run()
    prefix = "edit_connections-edit_connections_"
    at.checkbox(key=prefix + "enabled").check().run()
    assert not at.exception and at.selectbox(key=prefix + "part") is not None
    next(button for button in at.button if button.label == "更新材料估算").click().run()
    assert not at.exception
    rid = at.session_state[slot]["result_id"]
    assert not any(widget.key and widget.key.startswith(prefix) for widget in at.selectbox)
    assert prefix + "part" not in at.session_state
    at.checkbox(key=f"edit_{rid}_connections_enabled").check().run()
    assert not at.exception
    assert at.selectbox(key=f"edit_{rid}_connections_part") is not None
