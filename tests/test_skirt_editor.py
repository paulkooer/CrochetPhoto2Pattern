"""Waist edits must preserve craft instructions and use actual reserved loops."""
import json
from copy import deepcopy
from xml.etree import ElementTree

import pytest
from streamlit.testing.v1 import AppTest

from app.models.attachment_diagram import attachment_svg, diagram_rows
from app.models.instruction_checks import round_expression
from app.models.skirt_edit import move_skirt_join, skirt_connection, waist_rows
from app.ui.progress_state import progress_entries, retained_progress
from app.ui.result_logic import import_backup
from app.utils.exporters import export_markdown
from app.utils.project import project_backup, read_project_state
from tests.test_project_backup import RENDER
from tests.test_stitch_attachments import _check, _result


def _shaped(one_piece=False):
    return _result(one_piece=one_piece, profile=[.8, .7, .6, .5, .7, .9, 1.0], ruffle=True)


def _destination(result, *, different=True):
    old = skirt_connection(result["params"])
    return next(r["row"] for r in waist_rows(result["params"])
                if r["row"] != old["target_row"]
                and (r["stitches"] != old["end_stitch"]) == different)


@pytest.mark.parametrize("one_piece", [False, True])
@pytest.mark.parametrize("different", [False, True])
def test_waist_move_rebuilds_real_references_and_keeps_hem_and_original(one_piece, different):
    result = _shaped(one_piece)
    snapshot = deepcopy(result)
    old = skirt_connection(result["params"])
    updated = move_skirt_join(result, _destination(result, different=different))
    new = _check(updated)
    assert result == snapshot
    assert new["target_row"] != old["target_row"]
    assert (new["end_stitch"] != old["end_stitch"]) == different
    body = next(p for p in updated["params"]["parts"] if p["name"] == new["target_part"])
    original_reserve = next(r for r in body["rounds"] if r["row"] == old["reservation_row"])
    assert not round_expression(original_reserve["notes"]).has_loop_technique
    before_skirt = next(p for p in result["params"]["parts"] if p["name"] == "裙子")
    after_skirt = next(p for p in updated["params"]["parts"] if p["name"] == "裙子")
    assert after_skirt["rounds"][-1]["stitches"] == before_skirt["rounds"][-1]["stitches"]
    assert after_skirt["rounds"][-1]["color"] == before_skirt["rounds"][-1]["color"]
    assert updated["params"]["total_stitches"] == sum(
        r["stitches"] * p["quantity"] for p in updated["params"]["parts"] for r in p["rounds"])
    if not different:
        assert after_skirt == before_skirt
    # Repeated moves leave one current reservation, not accumulated FLO markers.
    back = move_skirt_join(updated, old["target_row"])
    _check(back)
    body = next(p for p in back["params"]["parts"] if p["name"] == old["target_part"])
    assert sum("为裙子保留接合位" in (r.get("notes") or "") for r in body["rounds"]) == 1


def test_same_waist_preserves_custom_skirt_but_different_waist_refuses_to_replace_it():
    result = _shaped()
    skirt = next(p for p in result["params"]["parts"] if p["name"] == "裙子")
    skirt["rounds"][2]["notes"] += "；为装饰保留长线"
    changed = move_skirt_join(result, _destination(result, different=False))
    assert next(p for p in changed["params"]["parts"] if p["name"] == "裙子") == skirt
    with pytest.raises(ValueError, match="手工针法"):
        move_skirt_join(result, _destination(result))


@pytest.mark.parametrize("damage", ["missing_marker", "special_target", "head_region", "no_neck"])
def test_unrecoverable_or_special_instructions_are_not_silently_rewritten(damage):
    result = _shaped(one_piece=True)
    old = skirt_connection(result["params"])
    target = _destination(result)
    body = next(p for p in result["params"]["parts"] if p["name"] == old["target_part"])
    if damage == "missing_marker":
        r = next(r for r in body["rounds"] if r["row"] == old["reservation_row"])
        r["notes"] = r["notes"].split("；")[0]
    elif damage == "special_target":
        r = body["rounds"][next(i for i, r in enumerate(body["rounds"]) if r["row"] == target) + 1]
        r["notes"] = "BLO(" + r["notes"].split("；")[0] + ")"
    elif damage == "head_region":
        target = 1
    else:
        for r in body["rounds"]:
            r["notes"] = r["notes"].replace("此处为颈部", "自定义位置")
    snapshot = deepcopy(result)
    with pytest.raises(ValueError):
        move_skirt_join(result, target)
    assert result == snapshot


@pytest.mark.parametrize("row", [True, 999, -1, "12"])
def test_invalid_waist_selection_is_rejected(row):
    with pytest.raises(ValueError):
        move_skirt_join(_shaped(), row)


def test_moved_join_retains_body_prefix_clears_skirt_and_roundtrips_progress():
    result = _shaped()
    updated = move_skirt_join(result, _destination(result, different=False))
    old, new = (skirt_connection(r["params"]) for r in (result, updated))
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}
    kept = retained_progress(result, updated, "result", progress)
    cut = min(old["reservation_row"], new["reservation_row"])
    assert {json.loads(k)[2] for k in kept if json.loads(k)[0] == "身体"} == set(range(1, cut))
    assert not any(json.loads(k)[0] == "裙子" for k in kept)
    assert any(json.loads(k)[0] == "手臂" for k in kept)
    project = project_backup(updated, kept, "新腰位")
    restored = import_backup(project, "restored")
    assert read_project_state(project, restored) == (kept, "新腰位")
    assert "接裙圈序示意" in export_markdown(updated["params"])
    assert f"第 {new['target_row']} 圈" in export_markdown(updated["params"])


def test_diagram_escapes_names_and_shares_exact_rows_with_printable_export():
    connection = skirt_connection(_shaped()["params"])
    connection["target_part"] = '<script>alert("x")</script>'
    svg = attachment_svg(connection)
    ElementTree.fromstring(svg)
    assert "<script>" not in svg and "&lt;script&gt;" in svg
    for row in diagram_rows(skirt_connection(_shaped()["params"])):
        for value in row:
            assert value in export_markdown(_shaped()["params"])


def test_waist_selector_previews_applies_and_undo_restores_connection():
    result = _shaped()
    at = AppTest.from_string(RENDER, default_timeout=30)
    at.session_state["result"] = result
    at.run()
    target = _destination(result, different=False)
    at.checkbox(key="chk_joined_身体_0").check().run()
    at.checkbox(key="chk_joined_裙子_0").check().run()
    at.selectbox(key="edit_joined_waist").select(target).run()
    assert not at.exception and at.session_state["result"] == result
    at.button(key="edit_joined_waist_preview").click().run()
    assert not at.exception and at.session_state["result"] == result
    at.button(key="edit_joined_preview_apply").click().run()
    assert not at.exception
    updated = at.session_state["result"]
    rid = updated["result_id"]
    assert skirt_connection(updated["params"])["target_row"] == target
    assert at.checkbox(key=f"chk_{rid}_身体_0").value
    assert not at.checkbox(key=f"chk_{rid}_裙子_0").value
    at.button(key=f"edit_{rid}_undo").click().run()
    assert not at.exception
    assert skirt_connection(at.session_state["result"]["params"]) == skirt_connection(result["params"])


def test_pdf_diagram_uses_the_moved_connection(monkeypatch):
    import html

    pytest.importorskip("reportlab")
    import reportlab.platypus as platypus

    from app.utils.pdf_export import export_pdf

    result = _shaped()
    changed = move_skirt_join(result, _destination(result, different=False))
    texts = []
    paragraph = platypus.Paragraph

    def capture(text, *args, **kwargs):
        texts.append(html.unescape(text))
        return paragraph(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    assert export_pdf(changed["params"], result=changed).startswith(b"%PDF-")
    assert "接裙圈序示意" in texts
    assert all(value in texts for row in diagram_rows(skirt_connection(changed["params"])) for value in row)


def test_reordering_joined_physical_pairs_requires_review_of_the_attached_source():
    result = _shaped()
    for name in ("身体", "裙子"):
        part = next(p for p in result["structure"]["parts"] if p["name"] == name)
        part["count"] = 2
        second = deepcopy(part["instances"][0])
        second["instance_id"] += "_second"
        part["instances"].append(second)
        next(p for p in result["params"]["parts"] if p["name"] == name)["quantity"] = 2
    progress = {identity: True for identity, _, _ in progress_entries(result, "result")}
    changed = deepcopy(result)
    next(p for p in changed["structure"]["parts"] if p["name"] == "身体")["instances"].reverse()
    kept = retained_progress(result, changed, "result", progress)
    assert not any(json.loads(k)[0] == "裙子" for k in kept)
    assert sum(json.loads(k)[0] == "身体" for k in kept) == sum(json.loads(k)[0] == "身体" for k in progress)
