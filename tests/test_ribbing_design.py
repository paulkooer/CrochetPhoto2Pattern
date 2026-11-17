"""The dimensional design pipeline must not emit a pattern when sizing is unknown."""
import json

import pytest

from app.models.attached_ribbing import RibbingMethod, RibbingTarget
from app.models.working_path import ExistingEdge, Hold, Route, Span, Work, WorkingPath
from app.ribbing_design import main, write_design
from app.working_paths import read_path


def _inputs():
    base = WorkingPath(title="合成基底", steps=[
        Route(id="row", label="已有行", expected_sites=7,
              operations=[Work(source=Span(edge="seed", first=1, last=7))]),
        Hold(id="base", label="相邻六位", spans=[Span(edge="row", first=1, last=6, direction="reverse")]),
        Hold(id="corner", label="工作环根部", spans=[Span(edge="row", first=7, last=7)]),
    ], existing_edges=[ExistingEdge(id="seed", count=7)], final_edges=["base", "corner"])
    method = RibbingMethod(prefix="rib", title="参数生成的小样", base_edge="base",
                           current_loop=Span(edge="corner", first=1, last=1), stitch="sc",
                           foundation_face="underside", foundation_turn="counterclockwise",
                           hook_mm=3.0, start_side="RS", outer_edge_both=True,
                           design_basis="独立合成构造，尺寸输入是假设，不是实测。")
    target = RibbingTarget(base_sites=6, edge_length_cm=2.0, width_cm=1.0,
                           rib_rows_per_10cm=40.0, rib_stitches_per_10cm=30.0,
                           gauge_basis="hypothetical")
    return base, method, target


def test_unknown_gauge_exports_the_specific_gap_and_no_crochet_steps(tmp_path):
    base, method, _ = _inputs()
    target = RibbingTarget(base_sites=6, edge_length_cm=2.0, width_cm=1.0)
    out = tmp_path / "missing"
    paths = write_design(target, out, base=base, method=method, pdf=True)
    assert [p.name for p in paths] == ["design-proposal.json"]
    assert json.loads(paths[0].read_text())["status"] == "needs_gauge"
    assert not list(out.glob("path-*"))


def test_cli_generates_an_actual_reloadable_path_from_dimensions(tmp_path):
    base, method, target = _inputs()
    for name, model in [("base", base), ("method", method), ("target", target)]:
        (tmp_path / f"{name}.json").write_text(model.model_dump_json())
    out = tmp_path / "out"
    assert main(["--base-plan", str(tmp_path / "base.json"), "--method", str(tmp_path / "method.json"),
                 "--target", str(tmp_path / "target.json"), "--out-dir", str(out)]) == 0
    generated = read_path((out / "path-plan.json").read_bytes())
    rows = [step for step in generated.steps if isinstance(step, Route) and step.section == "rib"]
    assert len(rows) == 8 and all(row.expected_sites == 3 for row in rows)
    proposal = json.loads((out / "design-proposal.json").read_text())
    assert proposal["layout"]["rows"] == 8 and proposal["physical_execution_verified"] is False


def test_a_pdf_failure_leaves_no_partial_design_package(tmp_path, monkeypatch):
    base, method, target = _inputs()

    def fail(_):
        raise ValueError("PDF排版失败")

    monkeypatch.setattr("app.ribbing_design.export_working_recipe_pdf", fail)
    with pytest.raises(ValueError, match="排版"):
        write_design(target, tmp_path / "failed", base=base, method=method, pdf=True)
    assert not (tmp_path / "failed").exists()


def test_existing_output_cannot_be_overwritten(tmp_path):
    base, method, target = _inputs()
    out = tmp_path / "existing"
    out.mkdir()
    original = b"existing design"
    (out / "path-plan.json").write_bytes(original)
    with pytest.raises(ValueError, match="已存在"):
        write_design(target, out, base=base, method=method)
    assert (out / "path-plan.json").read_bytes() == original
    assert not (out / "design-proposal.json").exists()
