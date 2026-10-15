"""Probe accounting must not confuse boundary cases with successful recognition."""
import json
import sys
from copy import deepcopy

import pytest
from PIL import Image

from scripts import probe_public_pairs as probe


@pytest.mark.parametrize("group,expected", [("single_animal", ["头部", "耳朵"]),
                                            ("boundary_non_animal", [])])
def test_probe_distinguishes_valid_stitches_from_semantic_match(tmp_path, monkeypatch, group, expected):
    path = tmp_path / "input.png"
    Image.new("RGB", (32, 32), "white").save(path)
    result = {"analysis": {"parts": ["头部", "身体"]}, "vision_meta": {"source": "default"},
              "params": {"parts": [{"name": "头部", "rounds": [
                  {"row": 1, "stitches": 6, "increase": 0, "decrease": 0}]}]}}
    monkeypatch.setattr(probe.PipelineOrchestrator, "run_full_pipeline", lambda *a, **kw: result)
    ref = {"visible_parts": expected, "evaluation_group": group, "target_height_cm": 18}
    report = probe.probe("case", path, ref)
    assert report["pattern_validation"]["ok"]
    if expected:
        assert report["missing_visible_parts"] == ["耳朵"]
        assert report["unexpected_parts"] == ["身体"]
        assert report["canonical_parts_exact"] is False
    else:
        assert report["canonical_parts_exact"] is None
        assert report["visible_part_recall"] is None
        assert not report["part_metrics_applicable"]


def test_catalog_failure_remains_in_report(tmp_path, monkeypatch):
    catalog, output = tmp_path / "catalog.json", tmp_path / "report.json"
    catalog.write_text(json.dumps({"cases": {
        "missing": {"image_file": "missing.png"}, "valid": {"image_file": "valid.png"}}}))
    good = {"status": "completed", "part_metrics_applicable": True, "sha256": "abc",
            "canonical_parts_exact": False, "pattern_validation": {"ok": True},
            "missing_visible_parts": ["耳朵"], "unexpected_parts": [], "vision_meta": {}}

    def run(name, path, ref):
        if name == "missing":
            raise FileNotFoundError(path)
        return {"id": name, **deepcopy(good)}

    monkeypatch.setattr(probe, "probe", run)
    monkeypatch.setattr(sys, "argv", ["probe", "--catalog", str(catalog),
                                     "--image-dir", str(tmp_path), "--out", str(output)])
    probe.main()
    report = json.loads(output.read_text())
    assert report["summary"]["requested"] == 2
    assert report["summary"]["errors"] == 1
    assert report["summary"]["canonical_part_scored_cases"] == 1
    assert report["summary"]["canonical_parts_exact_cases"] == 0
    assert report["cases"][0]["status"] == "error"
