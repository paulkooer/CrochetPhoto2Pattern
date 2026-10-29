"""A skirt must use real, reserved stitches on the correct body component."""
from copy import deepcopy

import pytest

from app.models.crochet_params import CrochetParamsGenerator, refresh_derived
from app.models.gauge import Gauge, ShapingStyle
from app.models.instruction_checks import round_expression
from app.models.validator import require_valid_pattern, validate_pattern
from app.schemas import PatternResult
from app.ui.result_logic import import_backup, regenerate_with_size
from app.utils.exporters import export_markdown
from tests.test_crochet_params import _sd


def _result(*, one_piece=False, gauge=None, profile=None, sphere_mode="ladder", ruffle=False):
    a, structure = _sd(["头部", "身体", "手臂", "裙子"])
    style = ShapingStyle(one_piece=one_piece, skirt_style="attached", sphere_mode=sphere_mode,
                         ruffle_hem=ruffle)
    params = CrochetParamsGenerator.generate_params(a, structure, style=style,
                                                     gauge=gauge or Gauge(13, 16), body_profile=profile)
    return PatternResult(analysis=a.model_dump(), structure=structure, params=params,
                         style=style.__dict__, gauge=params["gauge"], result_id="joined").to_result_dict()


def _check(result):
    params = result["params"]
    require_valid_pattern(params)
    c = params["stitch_attachments"]["connections"][0]
    parts = {p["name"]: p for p in params["parts"]}
    body, skirt = parts[c["target_part"]], parts["裙子"]
    base = next(r for r in body["rounds"] if r["row"] == c["target_row"])
    following = next(r for r in body["rounds"] if r["row"] == c["reservation_row"])
    assert c["reservation_row"] == c["target_row"] + 1
    assert base["stitches"] == c["end_stitch"] == skirt["rounds"][0]["stitches"]
    expression = round_expression(following["notes"])
    assert expression is not None and expression.counts.consumed == base["stitches"]
    # Independent expansion proves every consumed position uses the front loop.
    assert all(stitch.endswith("-FLO") for stitch in expression.iter_stitches())
    assert skirt["rounds"][0]["notes"].startswith(f"BLO({c['end_stitch']}X)")
    assembly = params["assembly_instructions"]
    assert f"第 {c['target_row']} 圈" in assembly
    assert f"第 {c['reservation_row']} 圈" in assembly
    assert f"1–{c['end_stitch']} 针" in assembly
    assert "最上 1–2 圈" not in str(params)
    assert "接合准备" in export_markdown(params, result=result)
    return c


@pytest.mark.parametrize("one_piece", [False, True])
@pytest.mark.parametrize("gauge", [Gauge(13, 16), Gauge(20, 24), Gauge(28, 32)])
@pytest.mark.parametrize("sphere_mode", ["ladder", "ideal", "egg"])
def test_generated_attachments_match_actual_body_and_merged_rounds(one_piece, gauge, sphere_mode):
    result = _result(one_piece=one_piece, gauge=gauge, sphere_mode=sphere_mode, ruffle=True)
    c = _check(result)
    if one_piece:
        body = next(p for p in result["params"]["parts"] if p["type"] == "onepiece")
        neck = next(r["row"] for r in body["rounds"] if "此处为颈部" in r["notes"])
        assert c["target_row"] >= neck


@pytest.mark.parametrize("one_piece", [False, True])
def test_profile_resize_and_backup_recompute_and_preserve_attachment(one_piece):
    result = _result(one_piece=one_piece, profile=[0.8, 0.7, 0.6, 0.5, 0.7, 0.9, 1.0])
    _check(result)
    restored = import_backup(PatternResult.from_result(result).to_backup(), "restored")
    assert restored["params"]["stitch_attachments"] == result["params"]["stitch_attachments"]
    _check(regenerate_with_size(restored, 12, 26))


@pytest.mark.parametrize("damage", ["missing_body", "target_row", "reservation_row", "range",
                                   "front_loop", "source_loop", "quantity", "reuse", "version",
                                   "bool_row", "source_magic_ring", "graph_method", "graph_target"])
def test_invalid_attachments_block_edit_import_and_print(damage):
    result = _result()
    params = result["params"]
    c = params["stitch_attachments"]["connections"][0]
    body = next(p for p in params["parts"] if p["name"] == "身体")
    skirt = next(p for p in params["parts"] if p["name"] == "裙子")
    if damage == "missing_body":
        params["parts"].remove(body)
    elif damage == "target_row":
        c["target_row"] = 999
    elif damage == "reservation_row":
        c["reservation_row"] = c["target_row"]
    elif damage == "range":
        c["end_stitch"] += 1
    elif damage == "front_loop":
        r = body["rounds"][c["reservation_row"] - 1]
        r["notes"] = r["notes"].replace("FLO", "BLO")
    elif damage == "source_loop":
        skirt["rounds"][0]["notes"] = skirt["rounds"][0]["notes"].replace("BLO", "FLO")
    elif damage == "quantity":
        skirt["quantity"] = 2
    elif damage == "reuse":
        params["stitch_attachments"]["connections"].append(deepcopy(c))
    elif damage == "version":
        params["stitch_attachments"]["schema_version"] = "999"
    elif damage == "bool_row":
        c["source_row"] = True
    elif damage == "source_magic_ring":
        skirt["magic_ring"] = True
    else:
        link = next(c for c in params["assembly_plan"]["connections"] if c["source_part_name"] == "裙子")
        field = "method" if damage == "graph_method" else "target_part_name"
        link[field] = "worn" if damage == "graph_method" else "头部"
    assert not validate_pattern(params)["ok"]
    with pytest.raises(ValueError):
        export_markdown(params)
    with pytest.raises(ValueError):
        import_backup(PatternResult.from_result(result).to_backup(), "invalid")


def test_legacy_attached_backup_stays_readable_but_needs_review():
    result = _result()
    del result["params"]["stitch_attachments"]
    restored = import_backup(PatternResult.from_result(result).to_backup(), "old")
    validation = validate_pattern(restored["params"])
    assert validation["ok"] and any("旧接裙" in n for n in validation["notes"])
    refresh_derived(restored["params"])
    assert "接裙位置待核对" in restored["params"]["assembly_instructions"]


def test_missing_or_rewired_body_never_invents_a_skirt_connection():
    a, structure = _sd(["裙子"])
    with pytest.raises(ValueError, match="需要身体"):
        CrochetParamsGenerator.generate_params(a, structure, style=ShapingStyle(skirt_style="attached"))
    a, structure = _sd(["头部", "身体", "裙子"])
    skirt = next(p for p in structure["parts"] if p["name"] == "裙子")
    skirt["instances"][0]["attachments"] = []
    with pytest.raises(ValueError, match="结构连接"):
        CrochetParamsGenerator.generate_params(a, structure, style=ShapingStyle(skirt_style="attached"))


def test_printed_connection_comes_from_current_references_and_pdf_matches(monkeypatch):
    import html

    pytest.importorskip("reportlab")
    import reportlab.platypus as platypus

    from app.utils.pdf_export import export_pdf

    result = _result(one_piece=True)
    c = result["params"]["stitch_attachments"]["connections"][0]
    result["params"]["assembly_instructions"] = "旧的错误接合圈号 999"
    texts = []
    paragraph = platypus.Paragraph

    def capture(text, *args, **kwargs):
        texts.append(html.unescape(text))
        return paragraph(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", capture)
    assert export_pdf(result["params"], result=result).startswith(b"%PDF-")
    md = export_markdown(result["params"], result=result)
    assert "旧的错误接合圈号 999" not in md and "旧的错误接合圈号 999" not in "\n".join(texts)
    for output in (md, "\n".join(texts)):
        assert f"第 {c['target_row']} 圈" in output
        assert f"第 {c['reservation_row']} 圈" in output
        assert "接合准备" in output


def test_dsl_does_not_replace_attached_skirt_with_a_separate_magic_ring():
    from app.utils.parade_export import export_parade_report

    report = export_parade_report(_result())
    assert not report.complete
    assert any("跨部件预留半针" in w for w in report.warnings)
    assert report.exported_parts < report.requested_parts


def test_cyclic_reserved_loop_dependencies_are_rejected():
    params = {"parts": [
        {"name": name, "magic_ring": False, "rounds": [
            {"row": 1, "stitches": 6, "notes": "BLO(6X)"},
            {"row": 2, "stitches": 6, "notes": "FLO(6X)"}]} for name in ("a", "b")],
        "stitch_attachments": {"schema_version": "1", "connections": [
            {"source_part": source, "target_part": target, "target_row": 1,
             "reservation_row": 2, "end_stitch": 6} for source, target in (("a", "b"), ("b", "a"))]}}
    check = validate_pattern(params)
    assert not check["ok"] and any("循环依赖" in issue for issue in check["issues"])
